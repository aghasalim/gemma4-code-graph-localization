"""Where does each reference fix edit the code?

For every task, parse the gold patch, read each touched file at base_commit from
the upstream repo, and name the innermost function or class that encloses each
changed line. Names follow the graph's convention (module path, then classes,
then the function), so they can be looked up in the released graph.
"""
import ast
import json
import re
import subprocess
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)


def module_name(path):
    """File path to the dotted module name the graph uses."""
    parts = path[:-3].split("/")
    if parts[0] in ("docs_src", "src"):
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def split_patch(patch):
    """Yield (path, is_new_file, patch text for that file)."""
    for chunk in re.split(r"(?m)^(?=--- )", patch):
        m = re.match(r"--- (\S+)\n\+\+\+ b/(\S+)", chunk)
        if m:
            yield m.group(2), m.group(1) == "/dev/null" or "@@ -0,0 " in chunk, chunk


def changed_old_lines(chunk):
    """Old-side line numbers that a hunk removes, or the line it inserts after."""
    lines = set()
    for m in HUNK.finditer(chunk):
        start = int(m.group(1))
        body = chunk[m.end():].split("\n@@", 1)[0].splitlines()[1:]
        line = start
        for b in body:
            if b.startswith("-"):
                lines.add(line)
                line += 1
            elif b.startswith("+"):
                lines.add(max(line - 1, 1))
            elif b.startswith(" ") or b == "":
                line += 1
    return lines


def symbols(source, module):
    """(start, end, name, is_async, is_class) for every def and class."""
    out = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                name = f"{prefix}.{child.name}"
                out.append((child.lineno, child.end_lineno, name, False, True))
                walk(child, name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}.{child.name}"
                out.append((child.lineno, child.end_lineno, name,
                            isinstance(child, ast.AsyncFunctionDef), False))
                # The graph lifts a function nested in a function to the
                # enclosing class or module, so nested names drop the parent.
                walk(child, prefix)
            else:
                walk(child, prefix)

    walk(ast.parse(source), module)
    return out


def enclosing(syms, line):
    inside = [s for s in syms if s[0] <= line <= s[1]]
    return min(inside, key=lambda s: s[1] - s[0]) if inside else None


def gold_for(task, repos):
    repo = repos / task["repo"].split("/")[1]
    files, loci = [], []
    for path, is_new, chunk in split_patch(task["patch"]):
        if not path.endswith(".py"):
            continue
        files.append({"path": path, "module": module_name(path), "new": is_new})
        if is_new:
            continue
        source = subprocess.run(["git", "-C", repo, "show", f"{task['base_commit']}:{path}"],
                                capture_output=True, text=True, check=True).stdout
        syms = symbols(source, module_name(path))
        for line in sorted(changed_old_lines(chunk)):
            s = enclosing(syms, line)
            if s:
                loci.append({"path": path, "name": s[2], "async": s[3], "class": s[4]})
    unique = {l["name"]: l for l in loci}
    return {"instance_id": task["instance_id"], "files": files, "loci": list(unique.values())}


def main():
    tasks = [json.loads(l) for l in open(DATA / "tasks.jsonl")]
    gold = [gold_for(t, DATA / "repos") for t in tasks]
    (Path(__file__).parent / "gold.json").write_text(json.dumps(gold, indent=1))
    n_loci = sum(len(g["loci"]) for g in gold)
    print(f"{len(gold)} tasks, {n_loci} edited symbols, "
          f"{sum(l['async'] for g in gold for l in g['loci'])} of them async")


if __name__ == "__main__":
    main()
