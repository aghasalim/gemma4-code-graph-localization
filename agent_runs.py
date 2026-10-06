"""How far apart are repeated end-to-end runs? Figures for section 5.

Each file in agent_runs/ is one full agent run (Gemma 4 31B QAT on vLLM, the
competition harness) on the same task list. v2_run1 and v2_run2 are the same
agent with the same settings; p13 and p13_b1..b3 are four prompt and budget
variants of one public two-stage agent; v4_bm25_12 adds a BM25 file ranking
skill to v1 on 12 tasks.

Leaderboard scores are copied from the competition's submissions page.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEADERBOARD = {"v1": 0.10, "v2": 0.06}


def run(name):
    return {(d := json.loads(l))["instance_id"]: bool(d["resolved"]) for l in open(HERE / "agent_runs" / f"{name}.jsonl")}


def figures():
    a, b = run("v2_run1"), run("v2_run2")
    variants = [run(n) for n in ("p13", "p13_b1", "p13_b2", "p13_b3")]
    ids = sorted(a)
    assert all(set(r) == set(ids) for r in [b, run("v1")] + variants)
    split = sum(0 < sum(v[i] for v in variants) < len(variants) for i in ids)
    return {
        "tasks": len(ids),
        "repeat": [sum(a.values()), sum(b.values()), sum(a[i] != b[i] for i in ids)],
        "variants": [sum(v.values()) for v in variants],
        "variants_split": split,
        "v1_local": sum(run("v1").values()),
        "bm25_12": [sum(run("v4_bm25_12").values()), sum(run("v1_12").values()), len(run("v1_12"))],
        "leaderboard": LEADERBOARD,
    }


if __name__ == "__main__":
    print(json.dumps(figures()))
