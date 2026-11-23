"""Run an actual ns-3 closed-loop episode and emit machine-readable evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .environment import Ns3GymEnv


def main() -> None:
    actions = (0, 1, 4, 2, 5)
    results = []
    with Ns3GymEnv(horizon=len(actions), timeout_seconds=15.0) as env:
        observation, initial = env.reset(seed=2026)
        for action in actions:
            observation, reward, terminated, truncated, info = env.step(action)
            results.append({
                "action": action,
                "observation": observation.tolist(),
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
                "kpis": info,
            })
            if terminated or truncated:
                break
    assert len(results) == len(actions), "Native ns-3 episode ended too early"
    assert results[-1]["terminated"] and not results[-1]["truncated"]
    assert results[-1]["kpis"]["rx_packets"] > 0
    assert results[-1]["kpis"]["rx_packets"] == results[-1]["kpis"]["tx_packets"]
    assert sum(r["reward"] for r in results) == results[-1]["kpis"]["rx_packets"]
    report = {
        "engine": "real-ns3",
        "ns3_release": "3.49",
        "python": os.sys.version.split()[0],
        "initial": {"observation": [0.0, 0.0, 0.0], "info": initial},
        "steps": results,
        "total_delivered_packets": results[-1]["kpis"]["rx_packets"],
    }
    destination = Path(os.getenv("VTNS3GYM_EVIDENCE", "/tmp/ns3gym-real-closed-loop.json"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
