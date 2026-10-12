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
| 5 | Better retrieval: metadata filters, hybrid (BM25 + vectors), reranker; before/after scores | 2.5 | ⬜ | | |
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
- [x] ✅ **4c** *Main purpose: turning 207 big sections into 2,977 small, searchable pieces that each fit the embedding model and carry their metadata, which will make retrieval precise.* Chunk 10-K sections (code in `src/sec_10k_rag/split_text/`)
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
    - `uv run python -m sec_10k_rag.split_text.run`
    - 2,977 chunks (MSFT 938, NVDA 939, TSLA 1,100); 0 nulls; keys unique
    - length: min 6, median 1,008, max 4,021 chars; 98 chunks > 2,000 chars (single very long lines)
  - [x] `chunks` table: `PRIMARY KEY (section_id, chunk_index)`, added `report_date DATE`, `source_url TEXT`; DB re-created, checked with `\d chunks`
  - [x] Tests `tests/test_split_text.py` (7): drop short sections, packing by start position, lines never cut, blank lines dropped, rejoined chunks = original text, `chunk_index` 0..n-1 per section + unique keys, metadata kept + `report_date` is `Date`
  - [ ] Later (only if eval shows a need): cut lines > 1,000 chars before packing (fixes the 98 long chunks), merge tiny last chunks, overlap of ~200 chars of whole lines
- [x] ✅ **4d** (2026-10-10) *Main purpose: turning each chunk's text into a 384-number vector and storing it in Postgres, so chunks can be searched by meaning.* Embed chunks (`BAAI/bge-small-en-v1.5`, sentence-transformers) and load into pgvector
  - [x] Add dep
    - `uv add sentence-transformers`
  - [x] Stage 1: embed (code in `src/sec_10k_rag/embedding/`) → `data/processed/embedding/chunks_embedded.parquet`
    - `uv run python -m sec_10k_rag.embedding.run`
    - `config.py`: `Config[EmbeddingInstructions]` (`model_name`, `batch_size=64`); `load.py` reads `data/processed/chunks.parquet` (2,977 rows)
    - Model output size: `model.get_sentence_embedding_dimension()` → `384`; `model.max_seq_length` → `512`
    - `tokenize.py` + `report.py`: token length per chunk → 27 of 2,977 chunks are over 512 tokens and get cut off (min 4, median 209, max 740)
    - `vectorize.py`: `model.encode(texts, batch_size=64, normalize_embeddings=True)` → `embedding` column, `Array(Float32, 384)`, 0 nulls
    - No separate normalize step: the model already ends with a `Normalize` layer (vector length = 1 either way)
  - [x] Stage 2: load into Postgres (code in `src/sec_10k_rag/db_load/`)
    - `uv run python -m sec_10k_rag.db_load.run` → `loaded 2977 rows into chunks`
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

Code (`src/sec_10k_rag/search_quality/lib.py`): Load + Search = `get_question_vectors` (bge-small + query prefix, reuses `embedding.vectorize`) and `find_nearest_neighbors` (pgvector `<=>`, top 10); Check = `rank_of_source` (left join on `question_id` + `section_id` + `chunk_index`); Score = `score` (recall@k + MRR). Run: `uv run python -m sec_10k_rag.search_quality.run` (default `generate_questions`: writes new questions with Groq, then scores them and saves `scores.parquet`).

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
