# Does the code graph find the bug?

The Gemma 4 Developer Agent competition on Kaggle gives every agent three search tools built on a released call graph and node embeddings. I wanted to know how often they point at the code a fix actually has to change, before spending an agent's small tool budget on them.

This repo measures that on all 129 training tasks without running any model. For each task it recovers the functions and classes the reference patch edits, then asks four search methods to rank the code using only the issue text.

The paper draft for the competition's paper track is [PAPER.md](PAPER.md).

## Results

How often an edited file is among the first five files each method returns (95% bootstrap interval, 128 tasks):

| method | what it is | hit@5 |
|---|---|---|
| embed | the harness's `search_similar_code` | 0.29 [0.21, 0.37] |
| graph | the same seeds plus one-hop call neighbours | 0.30 [0.22, 0.38] |
| grep | the issue's identifiers counted in each source file | 0.41 [0.32, 0.49] |
| bm25 | BM25 over the same graph nodes | 0.48 [0.39, 0.56] |
| bm25_src | BM25 with test code filtered out | 0.64 [0.55, 0.72] |

The embedding tool only accepts symbol names, and for 57 of the 129 issues no name in the text matches a graph node, so it returns nothing. On the tasks where a name does match, it is roughly level with BM25.

The audit of the released data found three more things. The graph contains no async function at all (the 67 name matches among 49,126 async definitions are all sync definitions with the same name), 21.9% of node vectors are exact copies of another node's vector, and every edge is a `calls` edge even though the harness documents other types.

## Running it

You need to have joined the competition and have a Kaggle API token in `~/.kaggle/access_token`.

```bash
pip install -r requirements.txt
./fetch.sh            # competition graphs, embeddings and tasks, plus the four upstream repos
python gold.py        # which symbols each reference patch edits -> gold.json
python retrieve.py    # the four methods on every task -> results.jsonl
python audit.py       # what the graphs contain -> audit.json
python embed_audit.py # duplicate vectors and stub node texts
python audit_extra.py # test-code share, async name matches, shared names
python stats.py       # the tables with bootstrap intervals
python check_paper.py # every number in PAPER.md, recomputed
```

The whole pipeline runs on a laptop CPU. `audit.py` is the slow step, because it parses every source file at 127 commits.

The competition data is not included here. `fetch.sh` downloads it with your own Kaggle account.

## Checks

CI runs `check_paper.py` on every push. It recomputes each figure in the paper from `results.jsonl`, `gold.json` and `audit.json`, and it also fails on any two-decimal number in the text that no script produced, so a hand-edited number cannot slip in.

## Files

`gold.py` parses each reference patch and the upstream file at the base commit and names the enclosing function or class the way the graph does. `retrieve.py` holds the four search methods. `audit.py` checks graph coverage by function type. `stats.py` prints the tables. `agent_runs.py` reads the per-task results of the end-to-end runs in `agent_runs/` for section 5. `results.jsonl` has one row per task, so any number can be traced back to the tasks behind it.
