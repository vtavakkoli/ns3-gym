# Attribution and compatibility scope

- This project was independently designed using [tkn-tub/ns3-gym](https://github.com/tkn-tub/ns3-gym), by Piotr Gawłowicz and contributors, as an architectural and interface reference. The original implementation uses ZeroMQ, Protocol Buffers, C++ OpenGym environment callbacks and a Python Gym adapter.
- The upstream project is available under the GNU General Public License version 2. This repository is GPL-2.0-only to preserve compatible licensing expectations. Original source files are **not** copied into this implementation.
- ns-3 is developed by the ns-3 project. We use its tagged ns-3.49 release at commit 418210e8914e9f6bcb5cddbcc94a2cecb7853b68.
- The wire protocol in `protocol/gym.proto` is **new**, not binary compatible with original ns3-gym's `SimInitMsg`, `EnvActMsg` or `EnvStateMsg`. Unsupported old environments will not be silently loaded.
- The example demonstrates only actual UDP packet transmission in a two-node ns-3 topology. It does not implement 5G NR, PRB, scheduler or O-RAN E2 actuation.
