"""Gymnasium API backed by a *real* ns-3 process and versioned protobuf RPC."""
from __future__ import annotations

import os
import signal
import socket as network_socket
import subprocess
from pathlib import Path
from typing import Sequence

import gymnasium as gym
import numpy as np
import zmq
from gymnasium import spaces

from . import gym_pb2

PROTOCOL_VERSION = 1


class SimulationError(RuntimeError):
    """The actual simulator failed or returned invalid protocol data."""


class SimulationTimeout(SimulationError, TimeoutError):
    """The simulator did not respond within the configured deadline."""


class Ns3GymEnv(gym.Env):
    """2-node ns-3 UDP traffic experiment controlled by Python.

    Action is the real number of 256-byte UDP packets to send this step (0..5).
    Observation is cumulative [rx_packets, tx_packets, 100ms_time_step].
    Reward is the actual packets received this step, not a fabricated KPI.
    Each reset launches a fresh native ns-3 process for clean state/seed.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        command: Sequence[str] | None = None,
        *,
        working_directory: str | os.PathLike[str] | None = None,
        timeout_seconds: float = 10.0,
        horizon: int = 5,
    ) -> None:
        if horizon < 1:
            raise ValueError("horizon must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if command is None:
            binary = os.environ.get("VTNS3GYM_BINARY")
            if not binary:
                raise ValueError(
                    "Specify a real ns-3 executable with command=[..., '--port={port}', "
                    "'--horizon={horizon}'] or set VTNS3GYM_BINARY; "
                    "no synthetic backend is provided"
                )
            command = [binary, "--port={port}", "--horizon={horizon}"]
        self._command = tuple(command)
        self._cwd = str(working_directory) if working_directory else None
        self._timeout = float(timeout_seconds)
        self._horizon = int(horizon)
        self._process: subprocess.Popen[str] | None = None
        self._context: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._ended = False
        self._seed: int | None = None
        self.action_space = spaces.Discrete(6)
        self.observation_space = spaces.Box(
            low=0.0, high=np.inf, shape=(3,), dtype=np.float64
        )

    @property
    def simulator_pid(self) -> int | None:
        return self._process.pid if self._process else None

    def _start(self) -> None:
        with network_socket.socket(network_socket.AF_INET, network_socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.setsockopt(zmq.SNDTIMEO, int(self._timeout * 1000))
        self._socket.setsockopt(zmq.RCVTIMEO, int(self._timeout * 1000))
        self._socket.connect(f"tcp://127.0.0.1:{port}")
        cmd = [part.format(port=port, horizon=self._horizon) for part in self._command]
        self._process = subprocess.Popen(
            cmd, cwd=self._cwd, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True, start_new_session=(os.name == "posix")
        )

    def _rpc(self, request: gym_pb2.Request) -> gym_pb2.Response:
        if self._socket is None:
            raise SimulationError("No running ns-3 simulator; call reset()")
        try:
            self._socket.send(request.SerializeToString())
            payload = self._socket.recv()
        except zmq.Again as exc:
            status = self._process.poll() if self._process else None
            self.close()
            raise SimulationTimeout(
                f"ns-3 ZeroMQ response timeout after {self._timeout}s; exit={status}"
            ) from exc
        except zmq.ZMQError as exc:
            self.close()
            raise SimulationError(f"ns-3 ZeroMQ protocol failure: {exc}") from exc
        response = gym_pb2.Response()
        if not response.ParseFromString(payload):
            self.close()
            raise SimulationError("Malformed native ns-3 protobuf response")
        if response.protocol_version != PROTOCOL_VERSION:
            self.close()
            raise SimulationError(
                f"Protocol mismatch: received {response.protocol_version}, expected 1"
            )
        if not response.ok:
            raise SimulationError(response.error or "ns-3 rejected request")
        if len(response.observation) != 3:
            self.close()
            raise SimulationError("ns-3 returned unexpected observation shape")
        return response

    @staticmethod
    def _info(response: gym_pb2.Response, seed: int) -> dict:
        return {
            "backend": "real-ns3",
            "ns3_release": "3.49",
            "seed": seed,
            "step": int(response.episode_step),
            "rx_packets": int(response.received_packets),
            "tx_packets": int(response.transmitted_packets),
            "rx_bytes": int(response.received_bytes),
            "step_rx_packets": int(response.step_received_packets),
            "throughput_mbps": float(response.throughput_mbps),
        }

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self.close()
        if options:
            raise ValueError("Unsupported reset options; no silent semantics changes")
        self._seed = int(seed if seed is not None else self.np_random.integers(1, 2**31))
        self._ended = False
        try:
            self._start()
            request = gym_pb2.Request(
                protocol_version=PROTOCOL_VERSION,
                command=gym_pb2.Request.RESET,
                seed=self._seed,
            )
            response = self._rpc(request)
            return np.asarray(response.observation, dtype=np.float64), self._info(
                response, self._seed
            )
        except BaseException:
            self.close()
            raise

    def step(self, action: int):
        if self._process is None or self._socket is None:
            raise SimulationError("No ns-3 process; call reset() before step()")
        if self._ended:
            raise SimulationError("Episode ended; reset() before step()")
        if not self.action_space.contains(action):
            raise ValueError(f"Unsupported ns-3 action: {action!r}; require integer 0..5")
        response = self._rpc(
            gym_pb2.Request(
                protocol_version=PROTOCOL_VERSION,
                command=gym_pb2.Request.STEP,
                action=int(action),
            )
        )
        self._ended = bool(response.terminated or response.truncated)
        return (
            np.asarray(response.observation, dtype=np.float64),
            float(response.reward),
            bool(response.terminated),
            bool(response.truncated),
            self._info(response, self._seed if self._seed is not None else 0),
        )

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close(linger=0)
            self._socket = None
        if self._context is not None:
            self._context.term()
            self._context = None
        if self._process is not None:
            process = self._process
            self._process = None
            if process.poll() is None:
                try:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGTERM)
                    else:
                        process.terminate()
                    process.wait(timeout=2.0)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=2.0)
            if process.stderr is not None:
                process.stderr.close()
        self._ended = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False
