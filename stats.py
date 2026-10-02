"""Hit rates with 95% bootstrap intervals over tasks, and paired differences."""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
METHODS = ("grep", "bm25", "embed", "graph", "bm25_src", "embed_src", "graph_src")
B = 10_000


def boot(values, seed=0):
    """Percentile bootstrap of the mean. Returns (mean, lo, hi) for a 95% interval."""
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(B))
    return sum(values) / n, means[int(0.025 * B)], means[int(0.975 * B)]


def table(rows, level, ks=(1, 5, 10)):
    lines = ["| method | " + " | ".join(f"@{k}" for k in ks) + " | n |", "|" + "---|" * (len(ks) + 2)]
    for m in METHODS:
        cells, n = [], 0
        for k in ks:
            v = [r[f"{m}_{level}@{k}"] for r in rows if r.get(f"{m}_{level}@{k}") is not None]
            if not v:
                break
            mean, lo, hi = boot(v)
            cells.append(f"{mean:.2f} [{lo:.2f}, {hi:.2f}]")
            n = len(v)
        if cells:
            lines.append(f"| {m} | " + " | ".join(cells) + f" | {n} |")
    return "\n".join(lines)


def paired(rows, a, b, key):
    d = [r[f"{a}_{key}"] - r[f"{b}_{key}"] for r in rows
         if r.get(f"{a}_{key}") is not None and r.get(f"{b}_{key}") is not None]
    mean, lo, hi = boot(d)
    return f"{a} minus {b}, {key}: {mean:+.2f} [{lo:+.2f}, {hi:+.2f}], n = {len(d)}"


if __name__ == "__main__":
    rows = [json.loads(l) for l in open(HERE / "results.jsonl")]
    print("File level\n" + table(rows, "file"))
    print("\nSymbol level\n" + table(rows, "sym"))
    print()
    for a, b in (("grep", "embed"), ("grep", "bm25"), ("bm25", "embed"), ("graph", "embed")):
        print(paired(rows, a, b, "file@5"))
    seeded = [r for r in rows if r["n_seeds"] > 0]
    print("\nFile level, only tasks where a name from the issue resolves to a node\n" + table(seeded, "file"))
    print(paired(seeded, "bm25", "embed", "file@5"))
    print(paired(rows, "bm25_src", "bm25", "file@5"))
    print(paired(rows, "embed_src", "embed", "file@5"))
    print(f"\ntasks with no name from the issue resolving to a node: "
          f"{sum(r['n_seeds'] == 0 for r in rows)} of {len(rows)}")
