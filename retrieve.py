"""How often does each way of searching put the edited code in its top k?

The query is the issue text only, which is all the agent sees. Every method
ranks graph nodes; a node counts toward a file through its module name.

  bm25       lexical search over node names and code
  embed      the harness's search_similar_code: names from the issue are
             resolved to nodes, then all nodes are ranked by cosine similarity
  graph      the resolved nodes plus their one-hop call neighbours
  grep       no graph at all: files ranked by how often the issue's names
             occur in them at base_commit (file level only)
"""
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from gold import module_name

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
K = (1, 5, 10)
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
IDENT = re.compile(r"`([^`\s]+)`|\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\b"
                   r"|\b([a-z]+_[a-z0-9_]+|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*)\b")


def words(text):
    out = []
    for w in WORD.findall(text):
        out += [p.lower() for p in re.split(r"_|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", w) if len(p) > 1]
    return out


def identifiers(issue):
    """Names a reader would copy out of the issue to search for."""
    found = []
    for m in IDENT.finditer(issue):
        s = next(g for g in m.groups() if g).strip("().,:;'\"")
        s = re.sub(r"[(=].*$", "", s)
        if len(s) > 2 and s not in found:
            found.append(s)
    return found


def resolve(name, names, lower):
    """The harness's four tiers: exact, dotted suffix, case-insensitive, substring."""
    if name in names:
        return [name]
    hits = [n for n in names if n.endswith("." + name) or n.endswith("/" + name)]
    if hits:
        return hits
    hits = [n for n in names if lower[n] == name.lower()]
    if hits:
        return hits
    return [n for n in names if name in n]


class Index:
    def __init__(self, repo, commit):
        g = json.load(open(DATA / "graphs" / f"{repo}_{commit}.json"))
        self.names = [n["name"] for n in g["nodes"]]
        self.text = {n["name"]: n["text"] for n in g["nodes"]}
        self.lower = {n: n.lower() for n in self.names}
        self.adj = defaultdict(set)
        for e in g["edges"]:
            self.adj[e["source"]].add(e["target"])
            self.adj[e["target"]].add(e["source"])
        z = np.load(DATA / "embeddings" / f"{repo}_{commit}.npz")
        self.vec_names = [n for n in z.files]
        m = np.stack([z[n] for n in self.vec_names]).astype(np.float32)
        self.vecs = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
        self.row = {n: i for i, n in enumerate(self.vec_names)}
        self.docs = {n: Counter(words(n) * 3 + words(self.text[n])) for n in self.names}
        self.df = Counter(w for d in self.docs.values() for w in d)
        self.avg = sum(sum(d.values()) for d in self.docs.values()) / max(len(self.docs), 1)

    def bm25(self, issue, k1=1.2, b=0.75):
        q = set(words(issue))
        n = len(self.docs)
        scores = {}
        for name, d in self.docs.items():
            length = sum(d.values())
            s = 0.0
            for w in q & d.keys():
                idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                s += idf * d[w] * (k1 + 1) / (d[w] + k1 * (1 - b + b * length / self.avg))
            if s:
                scores[name] = s
        return sorted(scores, key=scores.get, reverse=True)

    def seeds(self, issue):
        out = []
        for ident in identifiers(issue):
            for n in resolve(ident, self.names, self.lower)[:5]:
                if n not in out:
                    out.append(n)
        return out

    def embed(self, issue):
        seeds = [s for s in self.seeds(issue) if s in self.row]
        if not seeds:
            return []
        sims = self.vecs @ self.vecs[[self.row[s] for s in seeds]].T
        order = np.argsort(-sims.max(axis=1))
        return seeds + [self.vec_names[i] for i in order if self.vec_names[i] not in seeds]

    def graph(self, issue):
        seeds = self.seeds(issue)
        out = list(seeds)
        for s in seeds:
            out += sorted(n for n in self.adj[s] if n not in out)
        return out


def file_of(node, modules):
    """Longest module prefix of a node name that is a real file."""
    parts = node.split(".")
    for i in range(len(parts), 0, -1):
        m = ".".join(parts[:i])
        if m in modules:
            return modules[m]
    return None


def grep_files(repo_dir, commit, idents, paths):
    counts = Counter()
    for ident in idents:
        leaf = ident.split(".")[-1]
        r = subprocess.run(["git", "-C", repo_dir, "grep", "-c", "-F", "-e", leaf, commit, "--"]
                           + paths, capture_output=True, text=True)
        for line in r.stdout.splitlines():
            path, n = line.split(":", 1)[1].rsplit(":", 1)
            counts[path] += int(n)
    return [p for p, _ in counts.most_common()]


def dedup(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def run():
    tasks = {t["instance_id"]: t for t in map(json.loads, open(DATA / "tasks.jsonl"))}
    gold = json.load(open(HERE / "gold.json"))
    rows, cache = [], {}
    for g in gold:
        t = tasks[g["instance_id"]]
        repo = t["repo"].split("/")[1]
        key = (repo, t["base_commit"])
        if key not in cache:
            cache.clear()
            cache[key] = Index(*key)
        idx = cache[key]
        repo_dir = DATA / "repos" / repo
        ls = subprocess.run(["git", "-C", repo_dir, "ls-tree", "-r", "--name-only", t["base_commit"]],
                            capture_output=True, text=True, check=True).stdout.split()
        py = [p for p in ls if p.endswith(".py")]
        modules = {module_name(p): p for p in py}
        gold_files = {f["path"] for f in g["files"] if not f["new"]}
        gold_syms = {l["name"] for l in g["loci"]}
        in_graph = {s for s in gold_syms if s in idx.text}
        issue = t["problem_statement"]
        ranked = {m: getattr(idx, m)(issue) for m in ("bm25", "embed", "graph")}
        row = {"instance_id": g["instance_id"], "repo": repo,
               "n_gold_files": len(gold_files), "n_gold_syms": len(gold_syms),
               "n_gold_syms_in_graph": len(in_graph),
               "n_gold_syms_async": sum(l["async"] for l in g["loci"]),
               "n_seeds": len(idx.seeds(issue))}
        # The same rankings with test code removed, which an agent can do for free.
        for m in list(ranked):
            ranked[m + "_src"] = [n for n in ranked[m]
                                  if not (file_of(n, modules) or "tests/").startswith(("tests/", "test/"))]
        for m, nodes in ranked.items():
            files = dedup(file_of(n, modules) for n in nodes)
            for k in K:
                row[f"{m}_file@{k}"] = int(bool(gold_files & set(files[:k]))) if gold_files else None
                row[f"{m}_sym@{k}"] = int(bool(gold_syms & set(nodes[:k]))) if gold_syms else None
        src = [p for p in py if not p.startswith(("tests/", "test/", "docs/"))]
        files = grep_files(repo_dir, t["base_commit"], identifiers(issue), src)
        for k in K:
            row[f"grep_file@{k}"] = int(bool(gold_files & set(files[:k]))) if gold_files else None
        rows.append(row)
        print(g["instance_id"], {k: v for k, v in row.items() if k.endswith("@5")}, flush=True)
    (HERE / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    run()
