#!/usr/bin/env bash
# Downloads what the scripts need into data/. You must have joined the Kaggle
# competition and have a Kaggle API token in ~/.kaggle/access_token.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/graphs data/embeddings data/repos
TOKEN=$(cat ~/.kaggle/access_token)
API=https://www.kaggle.com/api/v1/competitions/data
COMP=gemma-4-developer-agent

get() {
  local enc
  enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1")
  [ -s "data/$1" ] || curl -sfL --retry 3 -H "Authorization: Bearer $TOKEN" "$API/download/$COMP/$enc" -o "data/$1"
}

get tasks.jsonl
python3 - "$TOKEN" <<'PY' > data/files.txt
import json, sys, urllib.request
token, page, out = sys.argv[1], "", []
while True:
    req = urllib.request.Request(
        "https://www.kaggle.com/api/v1/competitions/data/list/gemma-4-developer-agent?pageSize=200&pageToken=" + page,
        headers={"Authorization": "Bearer " + token})
    d = json.load(urllib.request.urlopen(req))
    out += [f["name"] for f in d["files"]]
    page = d.get("nextPageTokenNullable") or ""
    if not page:
        break
print("\n".join(n for n in out if n.startswith(("graphs/", "embeddings/"))))
PY
while read -r f; do get "$f"; done < data/files.txt

for r in fastapi/fastapi Textualize/rich psf/requests encode/httpx; do
  [ -d "data/repos/${r#*/}" ] || git clone -q "https://github.com/$r.git" "data/repos/${r#*/}"
done
