"""What is in the released graphs, and what is missing?

For each distinct base commit, parse every non-test .py file in the upstream
repo and check which functions and classes appear as graph nodes. Sync
functions check the naming convention (they should nearly all be found);
async functions test the reported gap.
"""
import json
import subprocess
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from gold import module_name, symbols

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def audit_commit(repo, commit):
    g = json.load(open(DATA / "graphs" / f"{repo}_{commit}.json"))
    names = {n["name"] for n in g["nodes"]}
    edges = Counter(e["type"] for e in g["edges"])
    repo_dir = DATA / "repos" / repo
    ls = subprocess.run(["git", "-C", repo_dir, "ls-tree", "-r", "--name-only", commit],
                        capture_output=True, text=True, check=True).stdout.split()
    c = Counter()
    for path in ls:
        if not path.endswith(".py") or path.startswith(("tests/", "test/")):
            continue
        src = subprocess.run(["git", "-C", repo_dir, "show", f"{commit}:{path}"],
                             capture_output=True, text=True).stdout
        try:
            syms = symbols(src, module_name(path))
        except SyntaxError:
            c["unparsable_files"] += 1
            continue
        for _, _, name, is_async, is_class in syms:
            kind = "class" if is_class else "async" if is_async else "sync"
            c[f"{kind}_total"] += 1
            c[f"{kind}_in_graph"] += name in names
    c["nodes"] = len(names)
    c["edges"] = sum(edges.values())
    for t, n in edges.items():
        c[f"edge_{t}"] += n
    print(repo, commit[:8], dict(c), flush=True)
    return {"repo": repo, "commit": commit, **c}


def main():
    tasks = [json.loads(l) for l in open(DATA / "tasks.jsonl")]
    commits = sorted({(t["repo"].split("/")[1], t["base_commit"]) for t in tasks})
    with Pool() as pool:
        per_commit = pool.starmap(audit_commit, commits)
    total = Counter()
    for c in per_commit:
        total.update({k: v for k, v in c.items() if isinstance(v, int)})
    (HERE / "audit.json").write_text(json.dumps({"total": total, "per_commit": per_commit}, indent=1))
    for kind in ("sync", "async", "class"):
        print(f"{kind}: {total[kind + '_in_graph']} of {total[kind + '_total']} in the graph")


if __name__ == "__main__":
    main()
