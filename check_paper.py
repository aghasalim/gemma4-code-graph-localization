"""Recompute every figure quoted in PAPER.md and fail if the text disagrees."""
import json
import re
import sys
from pathlib import Path

import agent_runs
from stats import boot, METHODS

HERE = Path(__file__).resolve().parent


def fmt(mean, lo, hi):
    return f"{mean:.2f} [{lo:.2f}, {hi:.2f}]"


def expected():
    rows = [json.loads(l) for l in open(HERE / "results.jsonl")]
    gold = json.load(open(HERE / "gold.json"))
    audit = json.load(open(HERE / "audit.json"))["total"]
    seeded = [r for r in rows if r["n_seeds"] > 0]
    want = []

    def cells(subset, level, m):
        for k in (1, 5, 10):
            v = [r[f"{m}_{level}@{k}"] for r in subset if r.get(f"{m}_{level}@{k}") is not None]
            if v:
                want.append(fmt(*boot(v)))

    for m in METHODS:
        cells(rows, "file", m)
        if m != "grep":
            cells(rows, "sym", m)
        if m in ("grep", "bm25", "embed", "graph", "bm25_src", "embed_src"):
            cells(seeded, "file", m)

    def diff(subset, a, b):
        d = [r[f"{a}_file@5"] - r[f"{b}_file@5"] for r in subset if r[f"{a}_file@5"] is not None]
        return boot(d)

    for (a, b, subset) in (("grep", "embed", rows), ("bm25", "embed", rows), ("graph", "embed", rows),
                           ("bm25_src", "bm25", rows), ("embed_src", "embed", rows),
                           ("bm25", "embed", seeded)):
        mean, lo, hi = diff(subset, a, b)
        want.append(f"{abs(mean):.2f}")
        want.append(f"{lo:.2f} to {hi:.2f}")

    want.append(f"{sum(r['n_seeds'] == 0 for r in rows)} of {len(rows)}")
    want.append(f"{sum(r['grep_file@5'] is not None for r in seeded)} file-level tasks")
    want.append(f"{sum(len(g['loci']) for g in gold)} edited symbols")
    want.append(f"{sum(l['async'] for g in gold for l in g['loci'])} of them `async`")
    want.append(f"{sum(not g['loci'] for g in gold)} tasks edit no existing symbol".capitalize().replace("8", "Eight"))
    for kind in ("sync", "async", "class"):
        want.append(f"{audit[kind + '_in_graph']:,} of {audit[kind + '_total']:,}")
    extra = json.load(open(HERE / "audit_extra.json"))
    tot, rep = extra["total"], extra["by_repo"]
    want.append(f"{tot['test_nodes']:,} of the {tot['nodes']:,} nodes")
    for r in ("httpx", "fastapi"):
        want.append(f"{rep[r]['test_nodes']:,} of {rep[r]['nodes']:,} in {'httpx' if r == 'httpx' else 'FastAPI'}")
    assert tot["async_hits"] == tot["async_hits_with_sync_twin"]
    want.append(f"All {tot['async_hits']} of those hits share")
    want.append(f"{tot['shared_names']:,} definitions share")
    gl = json.load(open(HERE / "external" / "graphloc129_e2e_analysis.json"))
    base, skill = (sum(gl["variance"]["resolved"][a].values()) for a in ("base", "skill"))
    want.append(f"from {base} to {skill} of {gl['taxonomy']['base']['n']}")
    ar = agent_runs.figures()
    n, (r1, r2, flips), v = ar["tasks"], ar["repeat"], ar["variants"]
    want.append(f"solved {r1} and then {r2} tasks, and {flips} of the {n} changed outcome")
    want.append(f"solved {', '.join(map(str, v[:-1]))} and {v[-1]}, and {ar['variants_split']} of the {n} tasks")
    want.append("solved {} of {} tasks against {} of {}".format(ar["bm25_12"][0], ar["bm25_12"][2], ar["bm25_12"][1], ar["bm25_12"][2]))
    want.append(f"{max(r1, ar['v1_local'])} against {ar['v1_local']}")
    lb = ar["leaderboard"]
    want.append(f"{lb['v2']:.2f} against {lb['v1']:.2f}")
    want.append(f"differed on {flips} of them")
    embed = (HERE / "embed_audit.txt").read_text()
    for n in re.findall(r"\d+(?:\.\d+)?%?", embed):
        if len(n) > 3:
            want.append(n if "%" in n else f"{int(n):,}")
    return want


if __name__ == "__main__":
    text = (HERE / "PAPER.md").read_text()
    readme = (HERE / "README.md").read_text()
    missing = [w for w in expected() if w not in text]
    allowed = {n for w in expected() for n in re.findall(r"-?\d\.\d\d", w)}
    allowed |= {n.lstrip("-") for n in allowed} | {"1.2", "0.75"}
    stray = sorted(set(re.findall(r"(?<![\d.])\d\.\d\d(?!\d)", text + readme)) - allowed)
    if stray:
        missing.append(f"numbers in the text that no script produced: {stray}")
    if "[AUDIT" in text:
        missing.append("unfilled [AUDIT] placeholder")
    if re.search("[–—]", text):
        missing.append("en or em dash in the text")
    if missing:
        sys.exit("not in PAPER.md:\n  " + "\n  ".join(missing))
    print(f"all {len(expected())} figures match")
