"""How many node vectors are exact copies of another node's vector, and how
many node texts are stubs with a bare None body?"""
import glob
import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent / "data"

total = dup = stub = 0
for f in sorted(glob.glob(str(DATA / "embeddings" / "*.npz"))):
    z = np.load(f)
    m = np.stack([z[k] for k in z.files])
    total += len(m)
    _, inv, cnt = np.unique(m.round(6), axis=0, return_inverse=True, return_counts=True)
    dup += int((cnt[inv.ravel()] > 1).sum())
for f in sorted(glob.glob(str(DATA / "graphs" / "*.json"))):
    for n in json.load(open(f))["nodes"]:
        t = n["text"].rstrip()
        stub += t.endswith(": None") or t.endswith(":\n    None")
print(f"vectors {total}, sharing an identical vector with another node {dup} ({dup / total:.1%})")
print(f"nodes {total}, text ending in a bare None body {stub} ({stub / total:.1%})")
