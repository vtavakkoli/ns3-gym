#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v protoc >/dev/null
mkdir -p "$ROOT/cpp/contrib/vtns3gym/model/generated" "$ROOT/src/vtns3gym"
protoc -I "$ROOT/protocol"   --cpp_out="$ROOT/cpp/contrib/vtns3gym/model/generated" "$ROOT/protocol/gym.proto"
protoc -I "$ROOT/protocol"   --python_out="$ROOT/src/vtns3gym" "$ROOT/protocol/gym.proto"
mv "$ROOT/src/vtns3gym/gym_pb2.py" "$ROOT/src/vtns3gym/gym_pb2.py"
echo "Generated Protocol Buffers for C++ and Python"
