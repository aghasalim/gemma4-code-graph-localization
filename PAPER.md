# Does the Code Graph Find the Bug? Measuring Fault Localisation with the Released Gemma 4 Graphs and Embeddings

Subtitle: A reproducible audit of the competition's code intelligence data, and why plain lexical search beats it

Aghasalim Mustafazada, Howest University of Applied Sciences, Kortrijk

## Abstract

The Gemma 4 Developer Agent competition gives every agent three code intelligence tools built on a released call graph and node embeddings for each repository snapshot. Before spending tool calls on them, it is worth knowing how often they point at the code a fix actually has to change. I measure that directly on all 129 training tasks, with no model in the loop. For each task I recover the functions and classes the reference patch edits from the upstream repository at the task's base commit, then ask four search methods to rank graph nodes using only the issue text. My reimplementation of the harness's `search_similar_code` puts an edited file in its top five for 0.29 of tasks (95% bootstrap interval 0.21 to 0.37). Plain grep over the issue's identifiers reaches 0.41, and BM25 over the node names and code in the same graph reaches 0.48, rising to 0.64 once test code is filtered out. Most of the gap comes from the lookup step: for 57 of 129 issues, no name in the text resolves to a graph node, so the tool has nowhere to start. On the tasks where a name does resolve, the difference between BM25 and the embedding tool is not significant. An audit of the released data explains some of the rest: the graph contains no async function at all (the 67 matches among 49,126 async definitions are all sync definitions with the same name), 21.9% of node vectors are exact duplicates of another node's vector, and every edge is a `calls` edge. All code, the per-task results and the recovered edit locations are public, and every number from my own measurements is recomputed by a script. A concurrent resource, GraphLoc-129, studies the same tasks at function level and with end-to-end agent runs; section 7 sets out how the two differ.

## 1. Introduction

Fault localisation is the first thing a coding agent has to get right. If it edits the wrong file, nothing after that matters, and the Gemma 4 agent runs under a tight budget: every hidden task must finish within one 12 hour run on a quantised 31B model, which leaves a few minutes and a few dozen tool calls per task.

The competition ships a call graph and a 256 dimensional embedding for every function and class in each repository snapshot, exposed through three tools (`search_similar_code`, `get_code_neighbors`, `get_code_subgraph`). The harness documentation recommends them for "fast, targeted navigation". How often does it lead to the right place?

This paper answers that on the 129 released training tasks. It does not need Gemma or a GPU: the question is about the search tools, so I hold the agent fixed at "reads the issue and searches" and measure the searches.

The contributions are:

1. File and symbol level edit locations for every training task, named the way the graph names them.
2. Four search methods compared under one query, with bootstrap intervals and paired differences.
3. An audit of the released graphs and embeddings.

## 2. Setup

### 2.1 Data

The competition releases 129 training tasks from four repositories: 67 from FastAPI, 48 from Rich, 13 from Requests and 1 from httpx. The tasks cover 127 distinct base commits, and there is one graph file and one embedding file per commit.

A graph file is a NetworkX node-link dump. Nodes carry a dotted name (for example `fastapi.routing.get_request_handler`) and the source text; edges carry a type. The embedding file maps the same names to 256 dimensional float32 vectors.

The reference patches are small. 91 of the 129 change a single file, and the median patch changes 12 lines.

### 2.2 Ground truth

For every Python file a reference patch modifies, I read that file at the base commit from the public upstream repository and parse it with Python's `ast` module. Each removed line, and each insertion point, is assigned to the innermost enclosing function or class. The symbol is named the way the graph names it: the module path (with a leading `src/` or `docs_src/` dropped), then any enclosing classes, then the function. A function nested inside another function is lifted to its enclosing class or module, which is what the graph does.

This yields 519 edited symbols across the 129 tasks, 52 of them `async` functions. Eight tasks edit no existing symbol (they only add new files or change module-level code), and one task only adds files, so it has no existing file to find.

The naming convention was checked, not assumed: in the audit (section 4), 97,675 of 98,147 sync function definitions are found under the derived names, and every miss is in FastAPI.

### 2.3 Search methods

Every method sees only the issue text, which is also all the agent sees at the start.

grep. No graph at all. Identifiers are pulled from the issue (backticked spans, dotted names, snake_case and CamelCase tokens), and every non-test Python file at the base commit is ranked by how many times the identifiers occur in it. This is what an agent does with `run_command` and `grep -rn`.

bm25. Okapi BM25 (k1 = 1.2, b = 0.75) over each graph node, with the node's name split into words and weighted three times, plus the words of its source text. The query is every word in the issue.

embed. A reimplementation of the harness's `search_similar_code`. Because the scoring sandbox has no embedding model, the tool can only look a query up among node names, using four tiers in order: exact match, dotted suffix, case-insensitive match, substring. I resolve each identifier from the issue the same way, keep up to five nodes per identifier as seeds, then rank all nodes by their highest cosine similarity to any seed.

graph. The seeds followed by their one-hop neighbours in the call graph, in both directions.

For bm25, embed and graph I also report a `_src` variant that drops nodes whose file is under `tests/`. Test code is 223,327 of the 367,985 nodes across all graphs, from 144 of 740 in httpx to 179,288 of 265,825 in FastAPI, and no reference patch edits a file under `tests/`, so this is a filter an agent can apply for free.

### 2.4 Metrics

File hit@k is 1 if any file the reference patch modifies appears among the first k distinct files the method ranks, and 0 otherwise. Symbol hit@k is the same over edited symbols and the first k nodes. Tasks with no target at that level are left out, which gives n = 128 at file level and n = 121 at symbol level. Intervals are 95% percentile bootstrap intervals over tasks with 10,000 resamples. Differences between methods are paired per task, and the interval is computed on the paired differences.

## 3. Results

### 3.1 File level

| method | hit@1 | hit@5 | hit@10 |
|---|---|---|---|
| grep | 0.15 [0.09, 0.21] | 0.41 [0.32, 0.49] | 0.52 [0.43, 0.60] |
| bm25 | 0.20 [0.14, 0.27] | 0.48 [0.39, 0.56] | 0.66 [0.57, 0.73] |
| embed | 0.17 [0.11, 0.23] | 0.29 [0.21, 0.37] | 0.35 [0.27, 0.44] |
| graph | 0.17 [0.11, 0.23] | 0.30 [0.22, 0.38] | 0.32 [0.24, 0.40] |
| bm25_src | 0.23 [0.16, 0.31] | 0.64 [0.55, 0.72] | 0.77 [0.69, 0.84] |
| embed_src | 0.21 [0.14, 0.28] | 0.32 [0.24, 0.41] | 0.40 [0.31, 0.48] |
| graph_src | 0.21 [0.14, 0.28] | 0.30 [0.23, 0.38] | 0.34 [0.26, 0.42] |

n = 128 tasks for every row.

The harness's embedding tool finds an edited file in its top five less often than grep does. The paired difference is 0.12 in grep's favour, with an interval of 0.03 to 0.20. BM25 over the same graph beats the embedding tool by 0.19 (0.09 to 0.28). Expanding the seeds along call edges adds nothing measurable: graph minus embed is 0.01 (-0.02 to 0.04).

Removing test code is the largest single effect in the table. It lifts BM25 at five from 0.48 to 0.64, a paired gain of 0.16 (0.10 to 0.23), and the embedding tool by 0.03 (0.01 to 0.06).

### 3.2 Symbol level

| method | hit@1 | hit@5 | hit@10 |
|---|---|---|---|
| bm25 | 0.08 [0.03, 0.13] | 0.22 [0.15, 0.30] | 0.27 [0.20, 0.36] |
| embed | 0.09 [0.04, 0.15] | 0.14 [0.08, 0.21] | 0.23 [0.16, 0.31] |
| graph | 0.09 [0.04, 0.15] | 0.15 [0.09, 0.21] | 0.24 [0.17, 0.31] |
| bm25_src | 0.09 [0.04, 0.14] | 0.31 [0.23, 0.40] | 0.38 [0.30, 0.47] |
| embed_src | 0.12 [0.07, 0.17] | 0.19 [0.12, 0.26] | 0.24 [0.17, 0.31] |
| graph_src | 0.12 [0.07, 0.17] | 0.21 [0.14, 0.28] | 0.24 [0.17, 0.31] |

n = 121 tasks. grep does not rank symbols and is left out.

Finding the exact function is much harder than finding the file for every method. Even the best row puts an edited symbol in the top five for under a third of tasks, which suggests an agent should use search to pick a file and then read it, not trust a search hit as the place to edit.

### 3.3 Where the embedding tool loses

For 57 of the 129 issues, no identifier in the text resolves to any graph node, so the embedding and graph methods return nothing at all. In 8 of those 57 the extractor finds no identifier in the issue at all; in the other 49 the issue does name something, but no name matches a node, either because the issue names a concept and not a symbol, or because the symbol is one the graph does not contain (section 4).

Restricting to the 71 file-level tasks where at least one name resolves changes the picture:

| method | hit@1 | hit@5 | hit@10 |
|---|---|---|---|
| grep | 0.23 [0.13, 0.32] | 0.62 [0.51, 0.73] | 0.75 [0.65, 0.85] |
| bm25 | 0.28 [0.18, 0.39] | 0.59 [0.48, 0.70] | 0.76 [0.66, 0.86] |
| embed | 0.31 [0.21, 0.42] | 0.52 [0.41, 0.63] | 0.63 [0.52, 0.75] |
| graph | 0.31 [0.21, 0.42] | 0.54 [0.42, 0.65] | 0.58 [0.46, 0.69] |
| bm25_src | 0.30 [0.20, 0.41] | 0.69 [0.58, 0.79] | 0.80 [0.70, 0.89] |
| embed_src | 0.38 [0.27, 0.49] | 0.58 [0.46, 0.69] | 0.72 [0.61, 0.82] |

On this subset the embedding tool has the best hit@1, and the BM25 advantage at five shrinks to 0.07 with an interval of -0.06 to 0.20, which includes zero. So the weakness is mostly in getting started, not in the vectors themselves. A lookup that accepted free text, or that fell back to BM25 when no name matched, would remove most of the gap. This subset is selected by a property of the query, so it is a diagnosis, not a fair comparison, and the full-set numbers in 3.1 are the ones an agent actually faces.

## 4. Audit of the released graphs and embeddings

The audit parses every non-test Python file at each of the 127 base commits and checks which functions and classes appear as nodes. Counts are summed over snapshots, so a function in 60 FastAPI snapshots counts 60 times.

| repository | sync functions in graph | async functions in graph | classes in graph |
|---|---|---|---|
| fastapi | 48,293 of 48,765 | 67 of 49,026 | 36,950 of 38,448 |
| rich | 45,875 of 45,875 | none defined | 9,296 of 9,296 |
| requests | 2,986 of 2,986 | none defined | 576 of 576 |
| httpx | 521 of 521 | 0 of 100 | 75 of 75 |
| all | 97,675 of 98,147 | 67 of 49,126 | 46,897 of 48,395 |

Sync functions and classes are almost all present, which confirms that the derived names match the graph's convention. The remaining misses are all in FastAPI and I have not traced them; nested classes and repeated names in the tutorial files are the likely cause.

Async functions are missing. Across all snapshots, 67 of 49,126 async function definitions are graph nodes, against 97,675 of 98,147 sync ones. All 67 of those hits share their qualified name with a sync function or class in the same module, so in effect the graph contains no async function at all. This matters most for FastAPI, where request handling, dependency resolution and the lifespan machinery are `async`. 52 of the 519 symbols the reference patches edit are `async`, so no graph tool can ever return them.

Duplicate vectors. Across all 127 embedding files, 80,709 of 367,985 vectors (21.9%) are exactly equal to another node's vector. 49,193 node texts (13.4%) end in a bare `None` body, which suggests class bodies were stripped before embedding, so two classes with the same signature and base class become indistinguishable. In one FastAPI snapshot, 82 different classes named `Item`, spread across tutorials, test files and example apps, all share a single vector.

Only call edges. The harness documentation names `CALLS`, `DEFINED_IN` and `IMPORTS` as edge types for `get_code_neighbors`. Every edge in every released graph is a `calls` edge, so filtering by the other types returns nothing.

Nested functions collide. The graph lifts a nested function to module level, so the inner `wrapper` of `_wrap_gen_lifespan_context` becomes `fastapi.routing.wrapper`. Across the 127 snapshots, 2,228 definitions share their qualified name with another definition in the same file, and the graph can store each such name only once.

## 5. What this means for an agent

Three changes follow directly from the measurements, and all three fit inside the competition's rules.

First, search with lexical tools first. grep through `run_command` already beats the embedding tool, and BM25 over the same node text does better still. A skill script that runs BM25 over the source tree inside the sandbox is allowed by the submission format.

Second, exclude test code from every search. It is the largest and cheapest gain measured here.

Third, use the embedding tool only after a name has been found, for example to list functions similar to one the agent has already read. On the tasks where it has a starting point, it is competitive.

Localisation is necessary but not sufficient, because an agent that finds the right file can still write the wrong fix. In GraphLoc-129's end-to-end runs on the same tasks, adding a BM25 localisation skill to an agent changed resolved runs from 92 to 95 of 318, a gap smaller than the spread between repeated runs of the same agent. Better search on its own should not be expected to move the leaderboard much.

## 6. Limitations

The benchmark has 129 tasks from four repositories, and 67 of them come from one project, so the intervals are wide and the results may not carry over to repositories with different naming habits. The ground truth is the reference patch, but other correct fixes might edit different code; a method penalised here might still lead to a passing fix. The embed and graph methods are my reimplementation from the harness documentation, not the harness code, so the real tools may rank differently. The identifier extraction is a set of regular expressions, not a model, and a better extractor would change the embed and graph rows. BM25 is scored over the graph's node text, so it inherits the missing async functions; a BM25 over raw files could do better still.

## 7. Related work

SWE-bench (Jimenez et al., 2024) established repository-level issue resolution as a benchmark, and the competition scores patches the same way, by running the task's tests on the patched repository. Agentless (Xia et al., 2024) showed that a fixed localise, repair and validate pipeline is competitive with free-form agents, with localisation as its first stage. SWE-agent (Yang et al., 2024) argued that the design of the agent's tools matters as much as the model, which is the premise of this paper. Graph-based localisation has been studied in RepoGraph (Ouyang et al., 2025) and LocAgent (Chen et al., 2025), which build richer graphs than the call-only graphs released here. Concurrently, GraphLoc-129 (zzgtylors, 2026), the companion resource of another paper-track writeup, labels the same 129 tasks at function level, rebuilds the graph with containment and import edges, and runs agents end to end; it also notes that the released tools know no async function. This paper overlaps with it on that finding and on lexical search beating the graph. What it adds, as far as the released GraphLoc files show, is a measurement of the competition's own lookup step (57 of 129 issues resolve to no node), file-level paired intervals against grep, and the audits of duplicate vectors, call-only edges and shared names. BM25 (Robertson and Zaragoza, 2009) remains a strong baseline for code retrieval, as it was in the original SWE-bench retrieval setting. Bootstrap intervals follow Efron and Tibshirani (1993).

## 8. Reproducing this

Everything runs on a laptop CPU, with no GPU and no model. The competition files are downloaded with the Kaggle API; the upstream repositories are cloned from GitHub at each base commit.

Code: https://github.com/aghasalim/gemma4-code-graph-localization

## References

Chen, Z. et al. (2025). LocAgent: Graph-Guided LLM Agents for Code Localization. ACL 2025.

Efron, B. and Tibshirani, R. (1993). An Introduction to the Bootstrap. Chapman and Hall.

Jimenez, C. E. et al. (2024). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR 2024.

Ouyang, S. et al. (2025). RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph. ICLR 2025.

Robertson, S. and Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. Foundations and Trends in Information Retrieval.

Xia, C. S. et al. (2024). Agentless: Demystifying LLM-based Software Engineering Agents. arXiv:2407.01489.

Yang, J. et al. (2024). SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. NeurIPS 2024.

zzgtylors (2026). GraphLoc-129: localization labels and agent runs. Kaggle dataset, companion to the paper-track writeup "Where Does the Graph Help? A Localization Audit of Gemma 4 Agent Code Graphs". https://www.kaggle.com/datasets/zzgtylors/graphloc-129-localization-labels-and-agent-runs
