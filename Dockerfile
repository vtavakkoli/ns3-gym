# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: GPL-2.0-only
# CI must compile native ns-3 and execute a real closed-loop, not just import.
FROM python:3.13-bookworm
ARG DEBIAN_FRONTEND=noninteractive
ARG NS3_VERSION=3.49
ARG NS3_SHA=418210e8914e9f6bcb5cddbcc94a2cecb7853b68
ARG BUILD_JOBS=4
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git cmake ninja-build build-essential pkg-config \
    libzmq3-dev libprotobuf-dev protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/ns3-gym
COPY . .
RUN bash scripts/generate-proto.sh \
    && python3.13 -m pip install --no-cache-dir ".[test]"
RUN git clone --depth 1 --branch "ns-${NS3_VERSION}" \
      https://github.com/nsnam/ns-3-dev-git.git /opt/ns3 \
    && test "$(git -C /opt/ns3 rev-parse HEAD)" = "${NS3_SHA}"
RUN cp -r cpp/contrib/vtns3gym /opt/ns3/contrib/vtns3gym \
    && cp cpp/scratch/modern-gym-loop.cc /opt/ns3/scratch/modern-gym-loop.cc
# Modern ns-3.49 CMake build. No Waf/legacy ns-O-RAN forks.
RUN cmake -S /opt/ns3 -B /opt/ns3/cmake-build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=17 \
      -DNS3_EXAMPLES=OFF -DNS3_TESTS=OFF -DNS3_GSL=OFF \
      "-DNS3_ENABLED_MODULES=core;network;internet;point-to-point;vtns3gym" \
    && cmake --build /opt/ns3/cmake-build \
         --target scratch_modern-gym-loop --parallel "${BUILD_JOBS}"
RUN set -eu; \
    executable="$(find /opt/ns3 -path '*/scratch/*' -type f -executable \
      -name '*modern-gym-loop*' -print -quit)"; \
    test -n "$executable"; \
    ln -s "$executable" /usr/local/bin/vtns3gym-sim; \
    test -x /usr/local/bin/vtns3gym-sim
ENV VTNS3GYM_BINARY=/usr/local/bin/vtns3gym-sim
ENV PYTHONDONTWRITEBYTECODE=1
RUN python3.13 -m pytest -q tests \
    && python3.13 -m vtns3gym.demo
CMD ["python3.13", "-m", "vtns3gym.demo"]
