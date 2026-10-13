# Build Log — rag-for-beginners

A running record of what we built, why, and what's next.
Newest entries at the bottom of each section. Checkboxes = still to do.

**Goal:** a working RAG + MCP project to show on my resume.
**Pace:** ~10 h/day. **Target:** MVP (steps 1–7) in ~2 weeks → resume + start applying; v2 (steps 8–9) in ~3–4 weeks total.
**Corpus plan:** SEC 10-K filings for 2–3 companies (Tesla, Microsoft, Nvidia) + related company files.

## Progress tracker

| # | Milestone | Est. days | Status | Started | Done |
|---|---|---|---|---|---|
| 1 | Finish Phase 1: review golden set, full baseline run, commit | 1 | ✅  | 2026-10-01 | 2026-10-01 |
| 2 | New corpus: download 10-Ks + JSON facts + annual-report PDF | 1 | ✅  |2026-10-01  | 2026-10-02|
| 3 | Loaders: .html, .txt, .pdf, .docx, .json, JSON→.parquet; split by 10-K Item with metadata (company, year, section) | 3 | ✅ | 2026-10-02 |2026-10-04 |
| 4 | Postgres + pgvector: Docker DB, tables, chunk 10-K sections, embed, load into pgvector | — | ✅ (facts load deferred) |2026-10-05 | 2026-10-10 |
| 4.5 | Search quality test: 50 questions with known answers, scored before improvements | 1.5 | ✅ | 2026-10-10 | 2026-10-12 |
| 5 | Better retrieval: metadata filters, hybrid (BM25 + vectors), reranker; before/after scores | 2.5 | ✅ |2026-10-12 | 2026-10-13 |
| 6 | MCP server: `search_filings(company, year, query)`, `answer`; test in Claude Desktop | 2 | ⬜ | | |
| 7 | Presentable: Streamlit UI, tests, Dockerfile, README (diagram + scorecard), demo video, GitHub | 2.5 | ⬜ | | |
| | **MVP total** | **≈ 13–14** | | | |
| 8 | (v2) Images: .jpg charts via vision model / OCR | 2 | ⬜ | | |
| 9 | (v2) Video: .mp4 earnings call → Whisper transcript (timestamps) → indexed | 2 | ⬜ | | |
| 10 | Buffer for surprises | 3 | ⬜ | | |
| | **Full total** | **≈ 20–21** | | | |

Status key: ⬜ not started · 🟡 in progress · ✅ done

**Target resume line (fill in X/Y):** "Built a RAG system over SEC 10-K filings (HTML/PDF/JSON/Parquet) with hybrid retrieval and an MCP server; built an eval harness (50-question golden set, LLM judge) and improved recall@5 from X to Y."

## Document formats plan

- **Long term:** text/desktop (.txt .md .pdf .docx .pptx), tabular (.csv .xlsx .parquet .lance), web/structured (.html .json .xml), messaging/e-books (.eml/.msg .epub), multimodal (.png .jpg .mp3 .mp4).
- **First 8 formats → source:**

| Format | Source |
|---|---|
| .html | 10-K main document (Inline XBRL) on SEC EDGAR |
| .txt | 10-K full-submission text file / older 10-Ks |
| .json | data.sec.gov `companyfacts` (all reported financial numbers) |
| .parquet | convert `companyfacts` JSON to Parquet myself |
| .pdf | annual report PDF from company investor-relations site |
| .docx | not on EDGAR — keep current NASA / IAC .docx files |
| .jpg | charts inside the 10-K filing (e.g. stock performance graph) |
| .mp4 | earnings call webcast from investor-relations site |

- SEC downloads need a `User-Agent` header with name + email; max 10 requests/second.

---

## Data flow

- Folder numbers under `src/sec_10k_rag/` follow this data flow, not the step numbers in the progress tracker.
- Each step reads what the step before it writes. `step_03_flattening` is a side branch: nothing reads `facts.parquet` yet.

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
   │                                                       ▼
   │                             step_07_search_quality ► data/processed/search_quality/scores.parquet
   │
   └── step_03_flattening ─────► data/processed/facts.parquet  (side branch)
```

| Step | Run | Reads | Writes |
|---|---|---|---|
| 01 | `uv run python -m sec_10k_rag.step_01_download.download` | SEC EDGAR | `data/raw/<ticker>/` |
| 02 | `uv run python -m sec_10k_rag.step_02_parsing.parse` | `data/raw/` | `sections.jsonl` |
| 03 | `uv run python -m sec_10k_rag.step_03_flattening.flattening_pl` | `data/raw/*/companyfacts.json` | `facts.parquet` |
| 04 | `uv run python -m sec_10k_rag.step_04_split_text.run` | `sections.jsonl` | `chunks.parquet` |
| 05 | `uv run python -m sec_10k_rag.step_05_embedding.run` | `chunks.parquet` | `embedding/chunks_embedded.parquet` |
| 06 | `uv run python -m sec_10k_rag.step_06_db_load.run` | `chunks_embedded.parquet` | Postgres `chunks` |
| 07 | `uv run python -m sec_10k_rag.step_07_search_quality.run` | Postgres `chunks` | `search_quality/questions.parquet`, `scores.parquet` |

---

## Concepts (quick reference)

- **Golden set** — fixed list of questions with known correct answers. Re-run it after every change to see if things got better or worse.
- **Unanswerable questions** — questions the documents can't answer. A good RAG says "I don't know" instead of inventing an answer.
- **recall@k** — share of questions where the chunk containing the answer appears in the top *k* retrieved chunks. 0.80 = 80% of questions.
- **MRR (Mean Reciprocal Rank)** — average of 1 / (rank of first correct chunk). Rank 1 → 1.0, rank 2 → 0.5, not found → 0. Rewards putting the right chunk *first*.
- **LLM judge** — a second LLM grades the RAG answer (1–5, shown as 0–1):
  - *faithfulness*: only uses facts from the retrieved chunks (no hallucination)
  - *answer relevance*: actually answers the question
  - *correctness*: matches the reference answer
- **Evidence matching** — each golden question stores a short exact quote from the document. A retrieved chunk is "correct" if it contains that quote. Chroma's chunk IDs are random and change every re-ingest; quotes don't, so scores stay comparable after re-chunking.
- **Config file** — all settings that change results (chunk size, k, models, prompt) live in `config.toml`. Every eval run saves a copy of it, so each score is reproducible.

---

## Phase 1 — Measure

### Done (2026-10-01)

1. **Git baseline** — `git init`, committed the project as-is, tagged `v0-baseline` (commit `8f73186`). No remote.
   *Why:* a fixed starting point to compare every change against.
2. **`config.toml`** (repo root) — chunk size 1000, overlap 0, `all-MiniLM-L6-v2`, k = 10, `openai/gpt-oss-120b`, the prompt from `answer_generate.py`, eval settings.
3. **Golden set** — `eval/golden_set.jsonl`, 50 questions: 40 answerable (~5 per document) + 10 unanswerable. Fields: `question`, `answerable`, `reference_answer`, `evidence`, `source`, `chunk_ids`, `reviewed`.
   Drafted by Claude → **must be reviewed by me**.
4. **Eval harness** — `src/rag_for_beginners/eval/`:
   | File | Role |
   |---|---|
   | `config.py` | loads `config.toml` |
   | `metrics.py` | recall@k, MRR, refusal detection (pure functions) |
   | `pipeline.py` | retrieval + generation, driven by config |
   | `judge.py` | judge prompt + score parsing |
   | `golden.py` | links each question to its chunk IDs via evidence |
   | `__main__.py` | runs everything, prints scorecard, saves JSON to `eval/results/` |

   Commands:
   - `uv run python -m rag_for_beginners.eval --retrieval-only` — retrieval scores only, ~30 s, no LLM cost
   - `uv run python -m rag_for_beginners.eval --label baseline` — full run (answers + judge)
   - `--limit N` — only first N questions (quick test)
   - `uv run python -m rag_for_beginners.eval.golden` — re-link chunk IDs after re-ingesting or editing evidence
5. **Retrieval baseline** — `eval/results/20261001-105859_retrieval-baseline.json`

   | Metric | k=3 | k=5 | k=10 |
   |---|---|---|---|
   | recall@k | 0.70 | 0.80 | 0.85 |
   | MRR@k | 0.58 | 0.60 | 0.61 |

   6 questions never retrieve their chunk in the top 10: tesla-01, google-01, microsoft-03, microsoft-05, nvidia-01, iac-02. Their answers sit in Wikipedia infoboxes / two-column PDF text that was scrambled when converted to text. → Phase 2 target.
6. **Lesson learned — API limits.** The first full run crashed at question 35: Groq free tier allows 200k tokens/day per model, a full run needs ~290k (about 5.8k per question). Results were only saved at the end, so they were lost. Fix: the harness now saves each question to a checkpoint file and resumes on re-run.

### To do

- [ ] **Choose: keep Claude's eval code as reference (A) or delete it and rewrite it myself (B)**
- [ ] Review all 50 golden questions; fix wrong ones; set `"reviewed": true`
- [ ] If any `evidence` changed: `uv run python -m rag_for_beginners.eval.golden`
- [ ] In `config.toml` `[eval]`: `judge_model = "qwen/qwen3-32b"` (separate free quota; a different model is also a fairer judge)
- [ ] Run full baseline: `uv run python -m rag_for_beginners.eval --label baseline` (if the rate limit hits, re-run later; it resumes)
- [ ] Record the full scorecard in this file
- [ ] `git checkout db/chroma_db/chroma.sqlite3` (Chroma touches this file when it's opened)
- [ ] `.gitignore`: add `eval/results/checkpoint_*` and `db/`, then `git rm -r --cached db`
- [ ] Commit: `git add -A && git commit -m "Phase 1: eval harness, golden set, config"`
- [ ] (Later) make `ingestion_pipeline.py` and `answer_generate.py` read `config.toml` too

---

## Steps 2–10

Detailed notes get added here as each milestone starts (see the Progress tracker above).

### Step 4 — Postgres + pgvector ✅ (2026-10-10)

**Note:** facts load deferred (4e). The `facts` table exists but is empty.

- [x] **4a** Postgres + pgvector in Docker: install Docker via snap, `compose.yaml` with `pgvector/pgvector:pg17`, `db/init/001_extension.sql`, `.env` vars
  - [x] Is Docker already installed?
    - `docker --version`
  - [x] Install Docker from snap
    - `sudo snap install docker`
  - [x] Run Docker without `sudo`
    - `sudo addgroup --system docker`
    - `sudo adduser $USER docker`
    - `newgrp docker`
    - `sudo snap disable docker && sudo snap enable docker`
  - [x] Check Docker and Compose work
    - `docker run hello-world`
    - `docker compose version`
  - [x] Add DB vars to `.env` (already git-ignored)
    - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT=5432`
  - [x] Create `db/init/001_extension.sql`
    - `CREATE EXTENSION IF NOT EXISTS vector;`
  - [x] Create `compose.yaml`
    - service `db`, image `pgvector/pgvector:pg17`, `env_file: .env`, port `5432:5432`
    - volumes: named volume `pgdata` → `/var/lib/postgresql/data`, `./db/init` → `/docker-entrypoint-initdb.d`
  - [x] Start the container
    - `docker compose up -d`
    - `docker compose ps` (status = running)
  - [x] Check pgvector is enabled
    - `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dx"'` (lists `vector`)
  - Note: `db/init/*.sql` only runs on an empty volume. To re-run: `docker compose down -v && docker compose up -d`
- [x] **4b** Create tables: `chunks` (with `vector(384)`), `facts`
  - [x] Add Python deps
    - `uv add "psycopg[binary]" pgvector`
  - [x] Create `db/init/002_tables.sql`
    - `chunks`: `PRIMARY KEY (section_id, chunk_index)`, `ticker`, `cik`, `fiscal_year`, `item`, `title`, `text`, `embedding vector(384)`, `report_date`, `source_url` (key and last two columns changed in 4c)
    - `facts`: same columns as `facts.parquet`, renamed `entityName`→`entity_name`, `start`→`start_date`, `end`→`end_date` (`end` is a reserved SQL word)
  - [x] Generate a draft `CREATE TABLE facts` from the Parquet schema (DuckDB in DBeaver, `:memory:` connection)
    ```sql
    SELECT 
        'CREATE TABLE facts (' || 
        string_agg(
            name || ' ' || 
            CASE LOWER(type)
                WHEN 'boolean' THEN 'boolean'
                WHEN 'int32' THEN 'integer'
                WHEN 'int64' THEN 'bigint'
                WHEN 'float' THEN 'real'
                WHEN 'double' THEN 'double precision'
                WHEN 'string' THEN 'text'
                WHEN 'binary' THEN 'bytea'
                WHEN 'timestamp_ms' THEN 'timestamp'
                WHEN 'timestamp_us' THEN 'timestamp'
                WHEN 'date' THEN 'date'
                ELSE 'text' -- Default fallback for complex/nested types
            END,
            ', '
        ) || ');' AS create_table_statement
    FROM parquet_schema('/home/nasim/Desktop/work/rag/sec-10k-rag/data/processed/facts.parquet');
    ```
    - Gotchas: `type` is the Parquet *physical* type, so the output needs hand fixes
      - an extra `root` row (the schema root, not a column) → remove it
      - dates are stored as `INT32` (logical type `DATE`) → come out as `integer`; change to `date`
      - strings are `BYTE_ARRAY` → hit the `ELSE 'text'` fallback (correct by luck)
      - `end` is a reserved SQL word → rename to `end_date`
  - [x] Dry-run the script (runs inside a transaction, then rolls back, so the DB is unchanged)
    - `{ echo 'BEGIN;'; cat db/init/002_tables.sql; echo; echo 'ROLLBACK;'; } | docker compose exec -T db psql -U rag -d sec10k`
    - Expect `CREATE TABLE` twice and no `ERROR`
  - [x] Re-create the DB so the script runs
    - `docker compose down -v && docker compose up -d`
  - [x] Check tables exist
    - `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'`
- [x] ✅ **4c** *Main purpose: turning 207 big sections into 2,977 small, searchable pieces that each fit the embedding model and carry their metadata, which will make retrieval precise.* Chunk 10-K sections (code in `src/sec_10k_rag/step_04_split_text/`)
  - [x] Read `data/processed/sections.jsonl` (one row per 10-K Item, 207 rows)
    - `load_ndjson(path)` → `pl.read_ndjson`
  - [x] Drop near-empty sections with a generic length rule, not by Item number
    - `drop_short_sections(df, min_chars=150)`: keeps `n_chars >= 150` → 168 kept, 39 dropped
    - Dropped = heading + "None." / "Not applicable." / "[Reserved]" (Items 1B, 4, 6, 9, 9C); works for any company
    - (Replaces the earlier "drop Items 4 and 6" and fixed 1,500/200-char slicing ideas)
  - [x] Pack whole lines (paragraphs) into chunks, no overlap: `chunk_sections(df, target_chars=1000, meta_columns)` (pure Polars, no loops)
    - Why lines: fixed slicing cut sentences and words in half; each line in `text` is one paragraph, heading or table row (`\n`-separated, no `\n\n`)
    - Why 1,000: bge-small reads max 512 tokens (~2,000 chars); bigger chunks get cut off and mix topics
    1. `str.split("\n")` → `.explode("para")` → one row per line; drop blank / whitespace-only lines
    2. `para_len = str.len_chars().cast(pl.Int64)` (`u32` would wrap below 0)
    3. `para_start_pos = (para_len + 1).cum_sum().over("section_id") - para_len - 1` (where each line starts; `+ 1` = the `\n`)
    4. `bucket = para_start_pos // target_chars` (which ~1,000-char window the line starts in)
    5. `group_by("section_id", "bucket", maintain_order=True).agg(str.join("\n"), first() of metadata)` → one row per chunk, lines in order
    6. `chunk_index = pl.int_range(pl.len()).over("section_id")` → 0..n-1 per section
    7. `report_date` → `str.to_date()`
  - [x] Key = `(section_id, chunk_index)`; no separate `chunk_id` column (deterministic, so re-runs give the same keys)
  - [x] Keep metadata on every chunk: `section_id`, `ticker`, `cik`, `fiscal_year`, `item`, `title`, `report_date`, `source_url`
  - [x] `run.py` writes `data/processed/chunks.parquet`
    - `uv run python -m sec_10k_rag.step_04_split_text.run`
    - 2,977 chunks (MSFT 938, NVDA 939, TSLA 1,100); 0 nulls; keys unique
    - length: min 6, median 1,008, max 4,021 chars; 98 chunks > 2,000 chars (single very long lines)
  - [x] `chunks` table: `PRIMARY KEY (section_id, chunk_index)`, added `report_date DATE`, `source_url TEXT`; DB re-created, checked with `\d chunks`
  - [x] Tests `tests/test_split_text.py` (7): drop short sections, packing by start position, lines never cut, blank lines dropped, rejoined chunks = original text, `chunk_index` 0..n-1 per section + unique keys, metadata kept + `report_date` is `Date`
  - [ ] Later (only if eval shows a need): cut lines > 1,000 chars before packing (fixes the 98 long chunks), merge tiny last chunks, overlap of ~200 chars of whole lines
- [x] ✅ **4d** (2026-10-10) *Main purpose: turning each chunk's text into a 384-number vector and storing it in Postgres, so chunks can be searched by meaning.* Embed chunks (`BAAI/bge-small-en-v1.5`, sentence-transformers) and load into pgvector
  - [x] Add dep
    - `uv add sentence-transformers`
  - [x] Stage 1: embed (code in `src/sec_10k_rag/step_05_embedding/`) → `data/processed/embedding/chunks_embedded.parquet`
    - `uv run python -m sec_10k_rag.step_05_embedding.run`
    - `config.py`: `Config[EmbeddingInstructions]` (`model_name`, `batch_size=64`); `load.py` reads `data/processed/chunks.parquet` (2,977 rows)
    - Model output size: `model.get_sentence_embedding_dimension()` → `384`; `model.max_seq_length` → `512`
    - `tokenize.py` + `report.py`: token length per chunk → 27 of 2,977 chunks are over 512 tokens and get cut off (min 4, median 209, max 740)
    - `vectorize.py`: `model.encode(texts, batch_size=64, normalize_embeddings=True)` → `embedding` column, `Array(Float32, 384)`, 0 nulls
    - No separate normalize step: the model already ends with a `Normalize` layer (vector length = 1 either way)
  - [x] Stage 2: load into Postgres (code in `src/sec_10k_rag/step_06_db_load/`)
    - `uv run python -m sec_10k_rag.step_06_db_load.run` → `loaded 2977 rows into chunks`
    - `convert_embedding_column_to_text(df)`: vector → pgvector text `"[0.01,-0.02,...]"` (cast to `List(String)` → `list.join(",")` → `pl.format("[{}]", ...)`)
    - `replace_rows(conn, df, "chunks")`: `TRUNCATE chunks`, then `COPY chunks (...) FROM STDIN WITH (FORMAT csv, HEADER true)` fed by `df.write_csv()` (a string, no file)
    - HNSW index: `CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)`
    - Verify in code: `count(*)` and `count(embedding)` must equal `df.height`, else `raise ValueError`
    - All of the above run in one transaction: any error or failed verify rolls everything back (old rows stay)
    - Re-run safe: ran twice, 2,977 rows both times
  - [x] Decisions
    - `TRUNCATE` + `COPY` instead of upsert: the Parquet file is the full source of truth, so a full replace is simpler and leaves no stale chunks
    - CSV in memory, sent by psycopg: Postgres runs in Docker and cannot read files on the host
    - Two stages with Parquet between them: can re-load the DB without re-embedding
    - Shelved for a day-2 project: scheduled server-side CSV loader
  - [x] Check (2026-10-10)
    - Rows, nulls, vector size: `SELECT count(*), count(embedding), min(vector_dims(embedding)), max(vector_dims(embedding)) FROM chunks;` → `2977 | 2977 | 384 | 384`
    - Rows per company: `SELECT ticker, count(*) FROM chunks GROUP BY ticker ORDER BY ticker;` → MSFT 938, NVDA 939, TSLA 1,100 (same as `chunks.parquet`)
    - Vectors are unit length: `SELECT min(vector_norm(embedding)), max(vector_norm(embedding)) FROM chunks;` → `1 | 1`
    - Indexes: `SELECT indexdef FROM pg_indexes WHERE tablename = 'chunks';` → `chunks_pkey` (btree) + `chunks_embedding_hnsw` (hnsw, `vector_cosine_ops`)
    - Nearest-neighbour test in SQL (DBeaver): chunks closest to one known chunk
      ```sql
      SELECT section_id, chunk_index,
             embedding <=> (SELECT embedding FROM chunks
                            WHERE section_id = 'TSLA-2025-item1A' AND chunk_index = 0) AS dist,
             left(text, 80)
      FROM chunks
      ORDER BY dist
      LIMIT 5;
      ```
      | # | section_id | chunk_index | dist | text |
      |---|---|---|---|---|
      | 1 | TSLA-2025-item1A | 0 | 0 | ITEM 1A. RISK FACTORS… (the chunk itself) |
      | 2 | TSLA-2023-item1A | 0 | 0.027 | ITEM 1A. RISK FACTORS… |
      | 3 | TSLA-2024-item1A | 0 | 0.027 | ITEM 1A. RISK FACTORS… |
      | 4 | NVDA-2025-item1A | 0 | 0.097 | Item 1A. Risk Factors… |
      | 5 | NVDA-2026-item1A | 0 | 0.098 | Item 1A. Risk Factors… |
      - `<=>` = cosine distance (0 = same, bigger = less similar)
      - `EXPLAIN` on the same query → `Index Scan using chunks_embedding_hnsw` (the index is used)
    - Question test in Python: embed `"Represent this sentence for searching relevant passages: What are Tesla's main risk factors?"` (`normalize_embeddings=True`), then `ORDER BY embedding <=> %s::vector LIMIT 5`
      - Top 5: TSLA-2023-item1A #12 (0.275), TSLA-2024-item1A #11 (0.275), TSLA-2025-item1A #11 (0.287), TSLA-2025-item1A #50 (0.288), NVDA-2026-item1A #0 (0.307) → 4 of 5 are Tesla risk factors
      - `%s` is a psycopg placeholder: it works only from Python, not in a SQL client (DBeaver gives `syntax error at or near "%"`)
    - Code checks: `uv run ruff check src tests` → passed; `uv run pyright src tests` → 0 errors; `uv run pytest -q` → 11 passed
  - [ ] Later (build step 5)
    - Add a `ticker` filter: in the question test, result 5 is the right topic but the wrong company
    - Add a `fiscal_year` filter or remove duplicates: in the question test, results 1 and 2 are the same paragraph from two years
    - Pick one rule for the bge query prefix and use it everywhere
- [ ] **4e** (deferred) Load `data/processed/facts.parquet` into the `facts` table
  - Note: facts load deferred. Plan: rename `entityName`→`entity_name`, `start`→`start_date`, `end`→`end_date`, then reuse `replace_rows(conn, df, "facts")` from `db_load/libs.py`
  - [ ] Read with Polars
    - `pl.read_parquet("data/processed/facts.parquet")` (81,810 rows)
  - [ ] Insert with `COPY` (psycopg `cursor.copy`)
  - [ ] Check
    - `SELECT count(*) FROM facts;` = 81,810
    - spot check: `SELECT ticker, fiscal_year, val FROM facts WHERE concept = 'Revenues' LIMIT 5;`

### Step 4.5 — Search quality test: 50 questions with known answers, scored before improvements ✅ (2026-10-12)

#### Scoring plan
- [x] **Load** `data/processed/search_quality/questions.parquet` (49 questions, each with its answer and its source chunk `section_id` + `chunk_index`).
- [x] **Search**: turn each question into a vector with bge-small (with the query prefix), then ask Postgres for the 10 nearest chunks, ranked 1–10.
- [x] **Check**: is the saved source chunk among those 10, and at what rank? (e.g. "found at rank 2" or "not found")
- [x] **Score**: turn the 49 ranks into recall@1/3/5/10 (how often the source chunk is in the top k) and MRR (mean of 1/rank, 0 when not found). Save per-question ranks to `scores.parquet` and print the summary.

Code (`src/sec_10k_rag/step_07_search_quality/lib.py`): Load + Search = `get_question_vectors` (bge-small + query prefix, reuses `embedding.vectorize`) and `find_nearest_neighbors` (pgvector `<=>`, top 10); Check = `rank_of_source` (left join on `question_id` + `section_id` + `chunk_index`); Score = `score` (recall@k + MRR). Run: `uv run python -m sec_10k_rag.step_07_search_quality.run` (default `generate_questions`: writes new questions with Groq, then scores them and saves `scores.parquet`).

#### How the check works (example)

Each question was written from one chunk, and questions.parquet stores that chunk's id (`section_id` + `chunk_index`). Search returns the top k chunks for each question. A question passes when its source id is among its own top k rows. The id is the table's primary key, so the same id means the same chunk text.

The neighbor rows below are from a real run; the source ids in Table 1 are made up for the example.

**Table 1: questions.parquet** (where each question came from)

| question_id | section_id | chunk_index |
|---|---|---|
| 0 | MSFT-2025-item1A | 28 |
| 1 | NVDA-2024-item1A | 6 |
| 2 | TSLA-2025-item7 | 1 |

**Table 2: nearest neighbors** (top 5 per question from Postgres `chunks`)

| question_id | rank | section_id | chunk_index |
|---|---|---|---|
| 0 | 1 | **MSFT-2025-item1A** | **28** |
| 0 | 2 | MSFT-2024-item1A | 29 |
| 1 | 1 | NVDA-2025-item1A | 6 |
| 1 | 2 | **NVDA-2024-item1A** | **6** |
| 2 | 1 | TSLA-2023-item7 | 1 |
| 2 | 2 | TSLA-2024-item7 | 1 |
| 2 | 3–5 | (no TSLA-2025-item7 #1) | |

**Check:** for each `question_id`, look in its top 5 rows for the same `section_id` + `chunk_index` (`rank_of_source`, one left join).

| question_id | found at rank | in top 5? |
|---|---|---|
| 0 | 1 | ✅ |
| 1 | 2 | ✅ |
| 2 | not found | ❌ |

**Score:**
- recall@k = share of questions whose source chunk is in the top k. Here recall@1 = 1/3 = 0.33 (only Q0 at rank 1), recall@5 = 2/3 = 0.67.
- MRR = average of 1/rank, 0 if not found. Here (1/1 + 1/2 + 0) / 3 = 0.50.

**Known limit:** Q2 shows it. Search found the same paragraph in the 2023 and 2024 filings but not the 2025 one the question came from, so it counts as a miss. The score is slightly strict.

#### Baseline result (2026-10-12)

Measured: 49 questions from `questions.parquet`, top 10 from Postgres `chunks`, bge-small-en-v1.5 with the query prefix, no filters, no reranking.

| recall@1 | recall@3 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|
| 0.24 | 0.43 | 0.51 | 0.63 | 0.37 |

Not found in top 10: 18 of 49.

Ranks: 1 ×12, 2 ×8, 3 ×1, 4 ×2, 5 ×2, 6 ×1, 8 ×2, 10 ×3, not found ×18.

Found per company: MSFT 13 of 16, NVDA 7 of 17, TSLA 11 of 16.

Known limit: only the exact source chunk counts; the same paragraph in another year's filing counts as a miss, so the score is slightly strict.

Next: improve search in build step 5 (company/year filters, hybrid search, reranking) and re-score the same questions.

### Step 5 — Better retrieval: metadata filters, hybrid (BM25 + vectors), reranker; before/after scores ✅ (2026-10-12 to 2026-10-13)

Measure every change on the same 49 questions in `questions.parquet` (don't regenerate; file locked with `chmod 444`). Step 5 baseline (2026-10-12): recall@1 0.22, @3 0.39, @5 0.45, @10 0.59, MRR 0.34; not found 20 of 49; found MSFT 12/16, NVDA 6/17, TSLA 11/16.

Why it differs from the Step 4.5 baseline (0.24 / 0.43 / 0.51 / 0.63 / 0.37): a `generate_questions` run at 06:02 UTC overwrote `questions.parquet` with 43 questions, so the exact 4.5 question file is lost. `questions.parquet` is now a copy of `2026_10_11_12_27_questions.parquet`: the same 49 source chunks, but the questions are worded differently. The 43-question file is kept as `questions_43_2026-10-12.parquet`. Open item: make question generation repeatable.

- [x] **5a** Fix score_search so it can run alone
  - [x] `step_07_search_quality/run.py:35`: read `ins.input_file_name` (questions.parquet), not `ins.output_file_name` (scores.parquet)
  - [x] Re-run `uv run python -m sec_10k_rag.step_07_search_quality.run score_search` → 49 rows scored (Step 5 baseline above)
  - [x] `start_db()` (`docker compose up --detach --wait db`) runs first in `main()`, so Postgres starts automatically
- [x] **5b** Filters: search only the question's company and fiscal year
  - [x] `step_07_search_quality/config.py`: add `filter_columns: tuple[str, ...] = ("ticker", "fiscal_year")` to `ScoreSearchInstructions` (`()` = baseline, so every scorecard row can be re-run)
  - [x] `lib/search.py` (lib.py split into a `lib/` package: db, questions, search, scoring) `find_nearest_neighbors`: build the `WHERE` from `filter_columns`, passing each question's own `ticker` and `fiscal_year` (already kept by `get_question_vectors`)
    - Example: `SELECT section_id, chunk_index FROM chunks WHERE ticker = %s AND fiscal_year = %s ORDER BY embedding <=> %s::vector LIMIT %s`
  - [x] Same connection: `SET hnsw.iterative_scan = strict_order` (without it, HNSW filters only ~40 candidates, so a filter can return fewer than 10 rows; `strict_order`, not `relaxed_order`, keeps results in exact distance order so rank and MRR stay right)
  - [x] `run.py`: pass `ins.filter_columns`; use `ins.top_k` instead of hard-coded `top_k=10`
  - [x] Check: every question gets 10 rows back: `nearest_neighbors.height == questions × top_k` (49 × 10 = 490; a `group_by` would miss a question with 0 rows)
  - [x] Re-score and record (2026-10-12): recall@1 0.43, @3 0.57, @5 0.65, @10 0.80, MRR 0.53; not found 10 of 49 (was 20); found MSFT 16/16, NVDA 11/17, TSLA 12/16; 28 questions ranked higher, none lower. Baseline scores kept in `search_quality/backup/2026_10_12_12_11_58_scores.parquet`
- [x] **5c** Hybrid: keyword search + vector search
  - [x] Add a `tsvector` column on `chunks.text` with a GIN index (Postgres full-text search, no new package)
    - `text_search tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED` + `CREATE INDEX chunks_text_search_gin ON chunks USING gin (text_search)`; run once on the live DB (2,977 rows filled); column and index added to `db/init/002_tables.sql`. Postgres fills it itself, and db_load's COPY skips generated columns
  - [x] Keyword search: top k by `ts_rank`, with the same filters as 5b
    - `lib/search.py` `keyword_query` + `find_keyword_matches` (params: question, ticker, fiscal_year, k)
    - `plainto_tsquery` ANDs every word, so a full question matches almost nothing; `replace(plainto_tsquery('english', %s)::text, '&', '|')::tsquery` turns it into OR
      - Example: `'revenu' & 'tesla' & '2024'` → `'revenu' | 'tesla' | '2024'`
    - `nearest_for_one` now builds its frame with explicit types (`section_id` String, `chunk_index` Int64): an empty result otherwise gets `Null` columns and `pl.concat` fails
    - Check: all 49 questions got 30 keyword rows
  - [x] Merge the vector and keyword ranks with Reciprocal Rank Fusion in Polars: `score = Σ 1 / (60 + rank)`
    - `lib/search.py` `fuse_ranks`: top 30 from each search, sum per chunk, sort (ties by `section_id`, `chunk_index`), keep top 10 → 490 rows
    - Example: vector rank 2 + keyword rank 5 → 1/62 + 1/65 = 0.032; vector rank 1 only → 1/61 = 0.016
  - [x] Wire into `run.py` + `config.py` (`candidate_k = 30`, `rrf_k = 60`, `hybrid = True`; `False` = 5b)
    - `lib/search.py` `search_chunks(vectors, ins)`: `hybrid=False` → one `find_nearest_neighbors` call (5b); `True` → vector top 30 + keyword top 30 → `fuse_ranks` → top 10. `run.py` calls `search_chunks`; the 490-row check stays
    - Re-run any scorecard row by config only (`search_mode` replaced the `hybrid` flag in 5d): baseline `search_mode=SearchMode.VECTOR, filter_columns=()`; 5b `search_mode=SearchMode.VECTOR`; 5c `search_mode=SearchMode.HYBRID`; 5d defaults
  - [x] Re-score with `run.py` and record (2026-10-13; same as the notebook): recall@1 0.45, @3 0.63, @5 0.65, @10 0.78, MRR 0.55 (vs 5b: +0.02 / +0.06 / 0 / −0.02 / +0.02; one question dropped out of the top 10). 5b scores kept in `search_quality/backup/2026_10_12_15_29_02_scores.parquet`
- [x] **5d** Reranker
  - [x] Take the top 30 from 5c and re-order them with the cross-encoder `BAAI/bge-reranker-base` (`sentence_transformers.CrossEncoder`); keep the top 10
    - Why vector + keyword (5c): each finds what the other misses

      | Question contains | Vector search (bge-small) | Keyword search |
      |---|---|---|
      | Same meaning, other words ("sales" vs "revenue") | ✅ | ❌ |
      | Exact names, codes, rare terms ("Cybertruck", "Blackwell", "Item 1C") | often ❌, the term gets blurred into the general topic | ✅ exact match |

      Neither one judges whether a chunk actually answers the question; only the cross-encoder does.
    - Models compared:

      | | bge-small (embedding) | bge-reranker-base (CrossEncoder) | gpt-oss-120b (LLM) |
      |---|---|---|---|
      | Size | ~33M parameters | ~278M parameters | ~120B parameters |
      | Output | a vector | one score | generated text |
      | Runs | on your laptop GPU | on your laptop GPU | OpenRouter API, paid |

    - Search funnel: each stage is slower but smarter, so it runs only on what is left
      ```
      2,977 chunks
        -> filters (5b):       one company + one year (~300)
        -> vector + keyword:   30 + 30 candidates
        -> RRF (5c):           one merged list
        -> CrossEncoder (5d):  best 10, in order
        -> LLM (/ask):         reads the top few, writes the answer
      ```
  - [x] Re-score and record (2026-10-13): recall@1 0.47, @3 0.69, @5 0.76, @10 0.80, MRR 0.59 (vs 5c: +0.02 / +0.06 / +0.10 / +0.02 / +0.04); not found 10 of 49 (was 11). 5c scores kept in `search_quality/backup/2026_10_13_00_07_43_scores.parquet`
- [x] **5e** Before/after scorecard (49 questions; files in `data/processed/search_quality/`)

  | Change | recall@1 | recall@3 | recall@5 | recall@10 | MRR | Scores file |
  |---|---|---|---|---|---|---|
  | Baseline (vectors only) | 0.22 | 0.39 | 0.45 | 0.59 | 0.34 | `backup/2026_10_12_12_11_58_scores.parquet` |
  | + filters (5b) | 0.43 | 0.57 | 0.65 | 0.80 | 0.53 | `backup/2026_10_12_15_29_02_scores.parquet` |
  | + hybrid (5c) | 0.45 | 0.63 | 0.65 | 0.78 | 0.55 | `backup/2026_10_13_00_07_43_scores.parquet` |
  | + reranker (5d) | 0.47 | 0.69 | 0.76 | 0.80 | 0.59 | `scores.parquet` |

  Result: recall@5 0.45 → 0.76, MRR 0.34 → 0.59. Filters gave the biggest jump; the reranker helped most at @3 and @5.
- [x] Checks: `uv run ruff check src tests` → passed; `uv run pyright src tests` → 0 errors; `uv run pytest -q` → 11 passed

### Step 6 — MCP server: `search_filings(company, year, query)`, `answer`; test in Claude Desktop

Code goes in a new package `src/sec_10k_rag/step_08_mcp_server/` (next folder in data-flow order).

- [x] **6a** `search_filings` function, no MCP yet: one question + company + year → top chunks with citation info (2026-10-13)
  - [x] `step_07_search_quality/lib/search.py`: split `vectorize_questions(questions)` out of `get_question_vectors` (adds `question_id`, query prefix, embeds); `get_question_vectors` now just loads the file and calls it. Exported in `lib/__init__.py`
  - [x] `step_07_search_quality/config.py`: `source_url` added to `CHUNK_COLUMNS` (step 7 unaffected: `rerank` and `generate_questions` pick their own columns)
  - [x] `step_08_mcp_server/lib/search_filings.py`: `search_filings(ticker, fiscal_year, query, top_k)`
    - `ticker` ("TSLA", "MSFT", "NVDA"), not a company name, because the `chunks` table filters on `ticker`
    - Builds a 1-row frame (`question`, `ticker`, `fiscal_year`) → `vectorize_questions` → `search_chunks` with the step 7 `SCORE_SEARCH` settings (filters 5b, hybrid 5c, reranker 5d) and `replace(instructions, top_k=top_k)`
    - Joins `load_chunks_text_from_db` on `section_id` + `chunk_index`, sorts by `rank` (a Polars join doesn't keep row order)
    - Returns `rank | section_id | chunk_index | item | title | source_url | rerank_score | text`
  - [x] Tried in `notebooks/search_quality.ipynb` → shape (5, 8), all rows `TSLA-2024-`

    Example:
    ```
    search_filings("TSLA", 2024, "How many vehicles did Tesla deliver?", top_k=5)

    rank | section_id       | chunk_index | rerank_score
    1    | TSLA-2024-item8  | 12          | 0.517
    2    | TSLA-2024-item1A | 7           | 0.247
    3    | TSLA-2024-item7  | 1           | 0.168
    4    | TSLA-2024-item8  | 11          | 0.031
    5    | TSLA-2024-item1A | 13          | 0.026
    ```
  - Notes: in a notebook, restart the kernel after moving a function between files (`%autoreload` missed it); Postgres must be up (`start_db()` from `common/common.py`)
- [ ] Before the `answer` tool: new OpenRouter key in `.env` `OPEN_ROUTER_API_KEY` (old key returned 401 "User not found" on 2026-10-13)
