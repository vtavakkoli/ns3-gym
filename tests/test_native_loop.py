"""Tests require an actual compiled ns-3.49 executable. No mocked ns-3 traffic."""
import os
import time

import numpy as np
import pytest

from vtns3gym import Ns3GymEnv, SimulationError, SimulationTimeout

pytestmark = pytest.mark.skipif(
    not os.getenv("VTNS3GYM_BINARY"),
    reason="VTNS3GYM_BINARY required: no dummy simulator substitute"
)


def episode(seed, actions=(0, 1, 4, 2, 5)):
    with Ns3GymEnv(horizon=len(actions), timeout_seconds=15) as env:
        initial, info = env.reset(seed=seed)
        assert np.allclose(initial, [0, 0, 0])
        assert info["backend"] == "real-ns3"
        traces = []
        for index, action in enumerate(actions, start=1):
            assert env.action_space.contains(action)
            obs, reward, terminated, truncated, info = env.step(action)
            assert env.observation_space.contains(obs)
            assert obs[2] == index
            assert not truncated
            assert terminated == (index == len(actions))
            assert reward == info["step_rx_packets"]
            assert int(obs[0]) == info["rx_packets"]
            assert int(obs[1]) == info["tx_packets"]
            assert info["rx_packets"] <= info["tx_packets"]
            assert info["throughput_mbps"] >= 0
            traces.append((tuple(obs), reward, terminated, info["rx_bytes"]))
        assert info["rx_packets"] > 0, "No real UDP packets traversed ns-3"
        assert info["rx_packets"] == sum(actions)
        assert info["rx_packets"] == info["tx_packets"]
        with pytest.raises(SimulationError):
            env.step(1)
        return traces


def test_real_closed_loop_and_multiple_sequential_episodes():
    a = episode(42)
    b = episode(42)
    c = episode(2026)
    assert a == b == c, "Same deterministic topology/actions must yield identical deliveries"


def test_invalid_action_fails_explicitly_without_fallback():
    with Ns3GymEnv(horizon=2) as env:
        env.reset(seed=42)
        with pytest.raises(ValueError, match="Unsupported ns-3 action"):
            env.step(999)
        _, reward, _, _, info = env.step(2)
        assert reward == 2
        assert info["rx_packets"] == 2


def test_real_simulator_timeout_and_cleanup():
    # The *timeout transport* is tested by starting a nonresponsive child.
    # This test is NOT treated as network/simulation evidence.
    env = Ns3GymEnv(command=["/bin/sleep", "10"], timeout_seconds=0.3)
    with pytest.raises(SimulationTimeout):
        env.reset(seed=42)
    assert env.simulator_pid is None
    env.close()
