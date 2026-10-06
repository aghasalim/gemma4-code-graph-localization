# Reproduces "Does the Code Graph Find the Bug?" from the competition data.
# Clones the code, rebuilds the edit locations and the four search rankings for all
# 129 training tasks, then checks every number in the paper against the rerun.
import os, subprocess, sys

def sh(cmd, cwd=None):
    print("$", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)

import glob
W = "/tmp/repo"  # kept out of /kaggle/working so the output stays small
hits = glob.glob("/kaggle/input/**/tasks.jsonl", recursive=True)
print("competition files found at", hits, flush=True)
COMP = os.path.dirname(hits[0])
print(sorted(os.listdir(COMP))[:20], flush=True)
sh(f"git clone -q https://github.com/aghasalim/gemma4-code-graph-localization.git {W}")
sh(f"rm -f {W}/data && mkdir -p {W}/data/repos")
for name in ("graphs", "embeddings", "tasks.jsonl"):
    os.symlink(f"{COMP}/{name}", f"{W}/data/{name}")
for r in ("fastapi/fastapi", "Textualize/rich", "psf/requests", "encode/httpx"):
    sh(f"git clone -q https://github.com/{r}.git data/repos/{r.split('/')[1]}", cwd=W)

sh("cp results.jsonl results.committed.jsonl && cp gold.json gold.committed.json", cwd=W)
sh(f"{sys.executable} gold.py", cwd=W)
sh(f"{sys.executable} retrieve.py", cwd=W)
sh("cmp gold.json gold.committed.json && echo gold.json identical to the committed file", cwd=W)
sh(f"{sys.executable} -c \"import json;a=[json.loads(l) for l in open('results.jsonl')];b=[json.loads(l) for l in open('results.committed.jsonl')];"
   f"print('results.jsonl rows identical to the committed file:', a==b)\"", cwd=W)
sh(f"{sys.executable} stats.py", cwd=W)
sh(f"{sys.executable} check_paper.py", cwd=W)
