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
| 4 | New golden set (~50 Qs) for 10-K corpus + baseline eval | 1.5 | 🟡 |2026-10-05 | |
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

### Step 4 — Postgres + pgvector

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
    - `chunks`: `chunk_id` (PK), `section_id`, `ticker`, `cik`, `fiscal_year`, `item`, `title`, `chunk_index`, `text`, `embedding vector(384)`
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
- [ ] 🟡 **4c** Chunk 10-K sections (skip near-empty Items 4 and 6)
  - [ ] Read `data/processed/sections.jsonl` (one row per 10-K Item)
  - [ ] Drop Items 4 and 6
  - [ ] Write a pure function `chunk_section(section, size, overlap) -> list[chunk]`; keep section metadata on every chunk
  - [ ] Pick size/overlap (bge-small max = 512 tokens)
  - [ ] Write `data/processed/chunks.jsonl`
  - [ ] Test: no empty chunks, every chunk has `ticker`/`fiscal_year`/`item`, chunk IDs are stable (e.g. `MSFT-2026-item1-0003`)
- [ ] **4d** Embed chunks (`BAAI/bge-small-en-v1.5`, sentence-transformers) and load into pgvector
  - [ ] Add dep
    - `uv add sentence-transformers`
  - [ ] Load model, check output size
    - `model.get_sentence_embedding_dimension()` → `384`
  - [ ] Embed in batches with `normalize_embeddings=True`
  - [ ] Insert into `chunks` (`register_vector(conn)`, `executemany` / `COPY`); upsert on `chunk_id` so re-runs are safe
  - [ ] Add HNSW index
    - `CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);`
  - [ ] Check
    - `SELECT count(*) FROM chunks;` = number of lines in `chunks.jsonl`
    - test query: embed a question, `ORDER BY embedding <=> %s LIMIT 5`, results look relevant
- [ ] **4e** Load `data/processed/facts.parquet` into the `facts` table
  - [ ] Read with Polars
    - `pl.read_parquet("data/processed/facts.parquet")` (81,810 rows)
  - [ ] Insert with `COPY` (psycopg `cursor.copy`)
  - [ ] Check
    - `SELECT count(*) FROM facts;` = 81,810
    - spot check: `SELECT ticker, fiscal_year, val FROM facts WHERE concept = 'Revenues' LIMIT 5;`
