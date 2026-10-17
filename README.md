# sec-10k-rag

A retrieval-augmented generation (RAG) system over SEC 10-K filings, served
to Claude Desktop through an MCP server.

Ask "How many vehicles did Tesla deliver in 2024?" and get an answer with
citations to the 10-K sections it came from.

## What it covers

- 9 annual reports (10-K) from SEC EDGAR:
  Tesla (FY2023–2025), Microsoft and Nvidia (FY2024–2026)
- Each 10-K is split into its Items (Item 1, 1A, 7, ...), chunked, embedded
  and stored in Postgres with pgvector
- Search: vector + keyword (hybrid, RRF) with ticker / fiscal-year filters,
  then a cross-encoder reranker
- Answers: an LLM answers only from the top 5 passages and cites them
- Follow-up questions ("and the next year?") are rewritten into standalone
  questions using the chat history

## Tech stack

| Part | Tool |
|---|---|
| Language / packaging | Python 3.12, uv |
| Data frames | Polars |
| Parsing | BeautifulSoup + lxml |
| Embeddings | `BAAI/bge-small-en-v1.5` (384 dims, sentence-transformers) |
| Reranker | `BAAI/bge-reranker-base` (CrossEncoder) |
| Vector DB | Postgres 17 + pgvector (Docker), HNSW cosine index, `tsvector` GIN index |
| LLM | `openai/gpt-oss-120b` via OpenRouter (OpenAI client) |
| MCP | `mcp` Python SDK, stdio transport |
| Checks | ruff, pyright (strict), pytest |

## Data flow

```
SEC EDGAR
   │  step_01_download
   ▼
data/raw/<ticker>/  (10k.html, full_submission.txt, companyfacts.json, manifest.json)
   │
   ├── step_02_parsing ────────► data/processed/sections.jsonl
   │                                │
   │                                ▼
   │                             step_04_split_text ──► data/processed/chunks.parquet
   │                                                       │
   │                                                       ▼
   │                             step_05_embedding ───► data/processed/embedding/chunks_embedded.parquet
   │                                                       │
   │                                                       ▼
   │                             step_06_db_load ─────► Postgres `chunks` (pgvector)
   │                                                       │
   │                                                       ├─► step_07_search_quality ► search_quality/scores.parquet
   │                                                       │
   │                                                       ▼
   │                             step_08_mcp_server ──► `search` tool ──► Claude Desktop
   │
   └── step_03_flattening ─────► data/processed/facts.parquet  (side branch, not used yet)
```

## How a question is answered

```
question + history
   │  get_rephrased_question_with_history   (only when history is not empty)
   ▼
standalone question                         "that year" -> "2024"
   │  extract_filing_attributes / validate_filing_attributes
   ▼
ticker + fiscal_year                        ("TSLA", 2024)
   │  retrieve_top_chunks                   vector + keyword -> RRF -> rerank
   ▼
top 5 chunks
   │  build_passages + ask_llm
   ▼
Answer {answer, citations[section_id, item, title, source_url]}
```

If the company or fiscal year is missing or not loaded, the tool returns a
message such as `Please name a Tesla fiscal year: 2023, 2024, 2025.` and no
citations.

## Project layout

```
src/sec_10k_rag/
  common/                  shared helpers: config (ROOT_DIR), db_config, llm_config, result, common
  step_01_download/        download.py
  step_02_parsing/         parse.py, html_text.py, sections.py, sgml.py, models.py
  step_03_flattening/      flattening_pl.py, flatten_pl.py, flattening_map.json
  step_04_split_text/      run.py, lib.py
  step_05_embedding/       run.py, tokenize.py, vectorize.py
  step_06_db_load/         run.py, libs.py
  step_07_search_quality/  run.py, config.py, lib/ (search, rerank, questions, scoring, db)
  step_08_mcp_server/      run.py, lib/ (answer, question, extract_attributes, search_filings, config)
db/init/                   SQL run on first DB start (pgvector extension, tables)
scripts/                   run_mcp_server.sh, run_notebook.sh
notebooks/                 exploration notebooks (search_quality.ipynb, mcp.ipynb, ...)
tests/                     pytest
BUILD_LOG.md               step-by-step build journal
```

Folder numbers follow the data flow, not the step numbers in `BUILD_LOG.md`.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), Docker with Compose.

```bash
uv sync
cp .env.example .env
```

Fill in `.env` (it is gitignored, never commit it):

| Variable | Used by |
|---|---|
| `SEC_USER_AGENT` | step 01, e.g. `"Your Name your-email@example.com"` (SEC requires it) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | `compose.yaml` and `common/db_config.py` |
| `POSTGRES_HOST` | optional, default `127.0.0.1` |
| `OPEN_ROUTER_API_KEY` | LLM calls (steps 07 and 08) |

Start the database (the first start runs `db/init/*.sql`):

```bash
docker compose up --detach --wait db
```

## Run the pipeline

Run from the repo root, in order:

| Step | Command | Reads | Writes |
|---|---|---|---|
| 01 | `uv run python -m sec_10k_rag.step_01_download.download` | SEC EDGAR | `data/raw/<ticker>/` |
| 02 | `uv run python -m sec_10k_rag.step_02_parsing.parse` | `data/raw/` | `sections.jsonl` |
| 03 | `uv run python -m sec_10k_rag.step_03_flattening.flattening_pl` | `data/raw/*/companyfacts.json` | `facts.parquet` |
| 04 | `uv run python -m sec_10k_rag.step_04_split_text.run` | `sections.jsonl` | `chunks.parquet` |
| 05 | `uv run python -m sec_10k_rag.step_05_embedding.run` | `chunks.parquet` | `embedding/chunks_embedded.parquet` |
| 06 | `uv run python -m sec_10k_rag.step_06_db_load.run` | `chunks_embedded.parquet` | Postgres `chunks` |
| 07 | `uv run python -m sec_10k_rag.step_07_search_quality.run score_search` | `search_quality/questions.parquet`, Postgres | `search_quality/scores.parquet` |

All outputs go under `data/processed/`. `data/raw` is never changed after
download.

Step 07 takes one word:

- `score_search`: scores the saved questions (use this to compare changes)
- `generate_questions` (the default): asks the LLM for a new question set,
  then scores it. The output is not exactly repeatable, so don't use it to
  compare scores.

## Search quality

49 questions, each generated from one known chunk. A question scores when
that chunk is in the top k results.

- recall@k: share of questions whose source chunk is in the top k
- MRR: mean of 1 / rank of the source chunk (0 when not found)

| Change | recall@1 | recall@3 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|
| Baseline (vectors only) | 0.22 | 0.39 | 0.45 | 0.59 | 0.34 |
| + ticker / fiscal-year filters | 0.43 | 0.57 | 0.65 | 0.80 | 0.53 |
| + hybrid (vector + keyword, RRF k=60) | 0.45 | 0.63 | 0.65 | 0.78 | 0.55 |
| + reranker (`bge-reranker-base`) | **0.47** | **0.69** | **0.76** | **0.80** | **0.59** |

recall@5 went from 0.45 to 0.76 and MRR from 0.34 to 0.59. The search mode is
set by `SearchMode` (`VECTOR`, `HYBRID`, `RERANK`; default `RERANK`) in
`step_07_search_quality/config.py`.

## MCP server

One tool, `search`:

```python
search(question: str, history: list[Turn] | None = None) -> Answer
# Turn   = {"question": str, "answer": str}
# Answer = {"answer": str, "citations": [{"section_id", "item", "title", "source_url"}]}
```

Run it on stdio (Postgres must be running):

```bash
uv run python -m sec_10k_rag.step_08_mcp_server.run
```

Or let the script start Postgres first:

```bash
bash scripts/run_mcp_server.sh
```

Each call is logged as one JSON line to `mcp_server.log` in the repo root:

```bash
tail -f mcp_server.log
```

### Claude Desktop

Add a top-level `mcpServers` key to `~/.config/Claude/claude_desktop_config.json`
(Linux), using the full path to the script:

```json
{
  "mcpServers": {
    "sec-10k-rag": {
      "command": "bash",
      "args": ["/full/path/to/sec-10k-rag/scripts/run_mcp_server.sh"]
    }
  }
}
```

Then fully restart Claude Desktop (`killall -9 claude-desktop` on Linux) and
turn the tool on under **+** → Connectors → `sec-10k-rag`.

Name the tool in the question, or Claude may answer from its own knowledge:

```
Use the sec-10k-rag search tool: How many vehicles did Tesla deliver in 2024?
-> about 1,789,000, cited from Item 7 of Tesla's FY2024 10-K

What about the next year?
-> rewritten to a question about Tesla's 2025 deliveries
```

## Checks

```bash
uv run ruff check src tests && uv run pyright src tests && uv run pytest -q
```

## Notebooks

```bash
uv run jupyter lab
```

Use the `.venv` kernel. Clear outputs before committing.

## Known limits

- Questions that span two years only search the first year named.
- Only 9 filings are loaded; `facts.parquet` (XBRL numbers) is not used by
  search yet.
