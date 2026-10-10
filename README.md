# Does the code graph find the bug?

The Gemma 4 Developer Agent competition on Kaggle gives every agent three search tools built on a released call graph and node embeddings. I wanted to know how often they point at the code a fix actually has to change, before spending an agent's small tool budget on them.

So I measured it on all 129 training tasks, without running any model. For each task I find the functions and classes the reference patch edits. Then I let four search methods rank the code using only the issue text. I also ran bm25, embed and graph a second time with test files left out; those runs end in `_src`. The table below shows the four methods and bm25_src, and `stats.txt` has all seven.

The paper draft for the competition's paper track is [PAPER.md](PAPER.md).

## Results

This is how often an edited file shows up in the first five files each method returns (95% bootstrap interval, 128 tasks).

| method | what it is | hit@5 |
|---|---|---|
| embed | the harness's `search_similar_code` | 0.29 [0.21, 0.37] |
| graph | the same seeds plus one-hop call neighbours | 0.30 [0.22, 0.38] |
| grep | the issue's identifiers counted in each source file | 0.41 [0.32, 0.49] |
| bm25 | BM25 over the same graph nodes | 0.48 [0.39, 0.56] |
| bm25_src | BM25 with test code filtered out | 0.64 [0.55, 0.72] |

The embedding tool only takes symbol names. For 57 of the 129 issues, no name in the text matches a graph node, so it returns nothing. When a name does match, it does about as well as BM25.

I also looked through the released data and found a few other problems. The graph has no async functions at all. There are 67 name matches among 49,126 async definitions, but every one of them is a sync definition that happens to have the same name. Also, 21.9% of node vectors are exact copies of another node's vector. And every edge is a `calls` edge, even though the harness docs mention other types.

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

Everything runs on a laptop CPU. `audit.py` is the slow part, because it parses every source file at 127 commits.

I don't include the competition data here. `fetch.sh` downloads it with your own Kaggle account.

## Checks

CI runs `check_paper.py` on every push. It recomputes each figure in the paper from `results.jsonl`, `gold.json` and `audit.json`. It also fails if the text has a two-decimal number that no script produced, so I can't sneak in a number by hand.

## Files

`gold.py` parses each reference patch and the upstream file at the base commit, and names the enclosing function or class the same way the graph does. `retrieve.py` has the four search methods. `audit.py` checks how much of each function type the graph covers. `stats.py` prints the tables. `agent_runs.py` reads the per-task results of the end-to-end runs in `agent_runs/` for section 5. `results.jsonl` has one row per task, so you can trace any number back to the tasks behind it.
