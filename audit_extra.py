"""Three smaller audit numbers the paper quotes.

1. How much of each graph is test code.
2. Whether the few async functions found in the graph are really sync
   functions or classes that happen to share the qualified name.
3. How many definitions share a qualified name with another definition in the
   same file, which the graph's naming can only store as one node.
"""
import json
import subprocess
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from gold import module_name, symbols

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def per_commit(repo, commit):
    names = {n["name"] for n in json.load(open(DATA / "graphs" / f"{repo}_{commit}.json"))["nodes"]}
    tests = sum(n.startswith(("tests.", "test.")) for n in names)
    repo_dir = DATA / "repos" / repo
    ls = subprocess.run(["git", "-C", repo_dir, "ls-tree", "-r", "--name-only", commit],
                        capture_output=True, text=True, check=True).stdout.split()
    c = Counter(nodes=len(names), test_nodes=tests)
    for path in ls:
        if not path.endswith(".py") or path.startswith(("tests/", "test/")):
            continue
        src = subprocess.run(["git", "-C", repo_dir, "show", f"{commit}:{path}"],
                             capture_output=True, text=True).stdout
        try:
            syms = symbols(src, module_name(path))
        except SyntaxError:
            continue
        counts = Counter(s[2] for s in syms)
        c["shared_names"] += sum(v - 1 for v in counts.values() if v > 1)
        not_async = {s[2] for s in syms if not s[3]}
        for _, _, name, is_async, _ in syms:
            if is_async and name in names:
                c["async_hits"] += 1
                c["async_hits_with_sync_twin"] += name in not_async
    return repo, c


def main():
    tasks = [json.loads(l) for l in open(DATA / "tasks.jsonl")]
    commits = sorted({(t["repo"].split("/")[1], t["base_commit"]) for t in tasks})
    with Pool() as pool:
        rows = pool.starmap(per_commit, commits)
    total, by_repo = Counter(), {}
    for repo, c in rows:
        total.update(c)
        by_repo.setdefault(repo, Counter()).update(c)
    out = {"total": total, "by_repo": by_repo}
    (HERE / "audit_extra.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
