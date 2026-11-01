"""README figures from results.jsonl, audit.json, audit_extra.json and embed_audit.txt -> figures/."""
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from stats import boot

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"
COLORS = {"grep": "#8c8c8c", "bm25": "#1f4e79", "embed": "#b2182b", "graph": "#e08214", "bm25_src": "#6baed6"}


def hit_at_k(rows, title, ax, ks=(1, 5, 10)):
    for m, c in COLORS.items():
        pts = [boot([r[f"{m}_file@{k}"] for r in rows if r.get(f"{m}_file@{k}") is not None]) for k in ks]
        ax.plot(ks, [p[0] for p in pts], "o-", color=c, label=m)
        ax.fill_between(ks, [p[1] for p in pts], [p[2] for p in pts], color=c, alpha=0.12)
    ax.set_title(title, fontsize=10)
    ax.set_xticks(ks)
    ax.set_xlabel("k (files returned)")
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)


def fig_hits():
    rows = [json.loads(l) for l in open(HERE / "results.jsonl")]
    seeded = [r for r in rows if r["n_seeds"] > 0]
    n = lambda rs: sum(r["grep_file@5"] is not None for r in rs)
    fig, axes = plt.subplots(1, 2, figsize=(8, 4), sharey=True)
    hit_at_k(rows, f"all tasks (n = {n(rows)})", axes[0])
    hit_at_k(seeded, f"a name from the issue matches a node (n = {n(seeded)})", axes[1])
    axes[0].set_ylabel("share of tasks with an edited file in top k")
    axes[1].legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "hit_at_k.png", dpi=150)


def fig_audit():
    t = json.loads((HERE / "audit.json").read_text())["total"]
    x = json.loads((HERE / "audit_extra.json").read_text())["total"]
    txt = (HERE / "embed_audit.txt").read_text()
    nodes, dup = map(int, re.search(r"vectors (\d+), sharing an identical vector with another node (\d+)", txt).groups())
    stub = int(re.search(r"bare None body (\d+)", txt).group(1))
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.5, 3.6))
    cov = [("sync functions", t["sync_in_graph"], t["sync_total"]),
           ("classes", t["class_in_graph"], t["class_total"]),
           ("async functions", t["async_in_graph"], t["async_total"])]
    for i, (name, got, tot) in enumerate(cov):
        f = got / tot
        a.barh(i, f, color="#b2182b" if name.startswith("async") else "#1f4e79")
        inside = f > 0.75
        a.text(f - 0.02 if inside else f + 0.02, i, f"{got:,} of {tot:,}", va="center", fontsize=8,
               ha="right" if inside else "left", color="white" if inside else "black")
    a.set_yticks(range(3), [c[0] for c in cov])
    a.set_title("definitions in the source that are graph nodes", fontsize=10)
    share = [("test code", x["test_nodes"]), ("vector identical\nto another node", dup), ("text ends in a\nbare None body", stub)]
    for i, (name, k) in enumerate(share):
        b.barh(i, k / nodes, color="#8c8c8c")
        b.text(k / nodes + 0.02, i, f"{k:,} ({100 * k / nodes:.1f}%)", va="center", fontsize=8)
    b.set_yticks(range(3), [s[0] for s in share])
    b.set_title(f"share of all {nodes:,} graph nodes", fontsize=10)
    for ax in (a, b):
        ax.set_xlim(0, 1)
        ax.invert_yaxis()
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "audit.png", dpi=150)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    fig_hits()
    fig_audit()
