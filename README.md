# vt-ns3-gym: Modern ns-3.49 + Gymnasium (experimental)

**Phase 2 verification is a hard gate.** Do not integrate this source
into Agentic-RAN until the *native ns-3.49 Docker* workflow **compiles and
executes** the real network simulation, publishes a reproducible JSON
evidence artifact, and reports overall success.

This repository is a small, independently maintained GPL-2.0-only
alternative to the [historical ns3-gym](https://github.com/tkn-tub/ns3-gym)
implementation. It does not bundle or depend on old ns3-gym source
at runtime, and it deliberately introduces a **new versioned
ZeroMQ/Protocol Buffers protocol**. See [ATTRIBUTION.md](ATTRIBUTION.md).

## Versions and reproducibility

- **ns-3.49**, upstream commit `418210e8914e9f6bcb5cddbcc94a2cecb7853b68` (not a moving branch).
- **Python 3.13**, base image `python:3.13-bookworm`.
- **C++23 and CMake/Ninja** under ns-3.49 (mandatory upstream CMake requirement).
- Debian Bookworm's `libzmq3-dev`, `libprotobuf-dev`, `protobuf-compiler` supply the compiled wire dependencies.
- Python package: `vt-ns3-gym==0.1.0` (this source); `gymnasium==1.4.0`, `pyzmq==27.1.0`, `protobuf>=6.31,<7`, `numpy>=2.2,<3`.
- GitHub Actions uses the same Dockerfile and uploads a JSON trace **only after a real compiled native simulation**.

## Docker build, native tests, real simulation

```sh
docker build --progress=plain --build-arg BUILD_JOBS=4 -t vtns3gym:ci .
docker run --rm vtns3gym:ci
```

The Docker build **must pass** all of the following:
`protoc` for Python and C++, `git checkout` of the *exact* ns-3 commit,
ns-3 CMake configure, C++ module and scratch binary build,
`python3.13 -m pip install --no-cache-dir ".[test]"`,
`python3.13 -m pytest -q tests`, and `python3.13 -m vtns3gym.demo`.
It is not enough to build a Python wheel or import `gymnasium`.

To save the observed action/reward/packet KPI trace:
```sh
mkdir -p evidence
docker run --rm -v "$PWD/evidence:/evidence" \
  -e VTNS3GYM_EVIDENCE=/evidence/native-closed-loop.json vtns3gym:ci
```

## What the real experiment does

Two ns-3 nodes are connected by a **5 Mbps point-to-point link with 2 ms delay**.
Python's `Discrete(6)` action selects 0..5 **actual UDP packets**
(256 bytes each) to transmit in the next 100 ms of ns-3 simulated time.
The receiver's `Socket::RecvFrom` callback is the only source of
received packet and byte counts.

- Observation: `Box(shape=(3,), dtype=float64)`, cumulative
  `[rx_packets, tx_packets, simulation_steps]`.
- Reward: count of UDP packets **actually received** in that step.
- Info: actual total received/transmitted packets, received bytes,
  per-step delivered packets and measured Mbps.
- `terminated=True` when the configured simulation horizon is reached;
  `truncated=False` for this model.
- A fresh native ns-3 process and seeded RNG state is created on each
  `reset(seed=N)`. Failed requests abort with explicit errors/timeouts.
- The native C++ process and ZeroMQ sockets are terminated on `close()`
  and after errors. No mock fallback is provided.

Usage:
```python
from vtns3gym import Ns3GymEnv
with Ns3GymEnv(horizon=5) as env:
    obs, info = env.reset(seed=2026)
    for action in [0, 1, 4, 2, 5]:
        obs, reward, terminated, truncated, info = env.step(action)
        print(obs, action, reward, info)
        if terminated or truncated:
            break
```
The default constructor requires `VTNS3GYM_BINARY` to point to a
**compiled** ns-3 scenario; an unconfigured installation fails explicitly.

## Repository layout

- `protocol/gym.proto`: documented versioned wire contract.
- `cpp/contrib/vtns3gym/`: CMake module for ns-3.49; direct ZeroMQ and
  generated Protobuf C++ sources.
- `cpp/scratch/modern-gym-loop.cc`: actual ns-3 UDP two-node simulator.
- `src/vtns3gym/environment.py`: Gymnasium lifecycle and protocol errors.
- `src/vtns3gym/demo.py`: complete example and JSON observation/action/reward trace.
- `scripts/generate-proto.sh`: both languages generated from one schema.
- `tests/`: wire, timeout/cleanup and **real simulator** integration.
- `.github/workflows/native-ns3.yml`: compile and full simulation gate.

## Important limitations

This new protocol is **not** binary compatible with the upstream
OpenGymInterface interface, and this scenario is **not** a 5G NR,
O-RAN E2, RAN slice/PRB scheduler, or handover simulator.
A physical Agentic-RAN integration must use a separately implemented
and tested action-dependent RAN scenario and adapter; it may not
reinterpret UDP packet count as a PRB scheduling action.

**Acceptance status:** evidence is determined solely by the
GitHub Actions native run, not by source review or ordinary Python tests.
