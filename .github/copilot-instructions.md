## Context
- Core service lives in `app.py`; FastAPI exposes `POST /convert_text_to_edi` that forwards requests to a singleton `EDIConverter`.
- Load `.env` before anything else; Populate `POSTGRES_*`, `OPENAI_API_KEY`, and any remote embedding keys or runs will fail at startup.

## Architecture
- `engine/edi_converter.py` orchestrates the workflow: fetch metadata (`query_edi_info_data`), load raw NL text (`query_raw_data`), iterate segments, and emit `(edi_expressions, entities)` tuples.
- Segment lists come from `utils.utils.get_segments_usage`; it prefers `mercury.custom_*` tables and falls back to base tables, so keep DB migrations aligned with that schema.
- `deduplicate_segments` sorts by `position` before removing duplicates; new segment feeds must include `position` or ordering breaks.
- `get_segment_description` and `get_entities_for_segment` return lists of dicts shaped for downstream prompts; preserve their return format when augmenting metadata.
- Missing DB rows raise `ValueError` early; caller expects exceptions to propagate into FastAPI’s 500 handler, so avoid swallowing them silently.

## Data & Retrieval
- `raw_processed_data` rows use doc_id suffixed with `_NL`/`_EDI`; respect that convention if you seed or query new data.
- `ChromaDBService` in `chroma/chromadb_service.py` talks to `http://3.217.236.185:8050` and uses `MercuryEmbeddings` at `http://ai.kontratar.com:5000`; metadata filters follow the Chroma REST `$and` syntax.
- `get_relevant_chunks` returns a list of strings; `convert_text_to_edi` reassembles them with `'\n'.join(...)` before prompting the LLM.
- `TOKENS_LIMIT` in `utils/constants.py` lets `EDIConverter` short-circuit retrieval; adjust the constant there rather than in-line if limits change.
- Database access uses async SQLAlchemy engines per call in `EDIConverter`; remember to `await engine.dispose()` when introducing new helper queries.

## LLM Chains
- All LangChain chains live in `engine/chains.py` and share a `ChatOpenAI(model="gpt-4.1", temperature=0.1)` instance; reuse it instead of creating new clients.
- `chain_relevant_text` gates each segment; if `.relevant` is `False`, skip extraction to avoid bogus EDI expressions.
- `chain_entities_extraction` expects `json.dumps` of entity dicts; required flags stay in `'M'/'O'` form because downstream validation compares against `'M'`.
- After extraction, `convert_text_to_edi` drops segments where any mandatory entity has `found == False`; keep that guard when adding post-processing.
- `chain_edi_expression` returns an object with `.edi_expression`; append that string to the result list to preserve FastAPI’s response contract.

## Token Management
- Token counting uses `tiktoken` with `"cl100k_base"`; call `tokens_count` before hitting the LLM if you introduce new text sources.
- When text exceeds `TOKENS_LIMIT`, rely on Chroma slices instead of truncation; the service already constrains results with `n_results` and metadata filters.
- If Chroma returns zero documents, fall back to the original text rather than generating empty prompts; current code handles this by retaining `raw_text`.

## Workflows
- Local run: `uvicorn app:app --host 0.0.0.0 --port 8000 --reload`; Dockerfile mirrors this and copies `.env` into the image.
- Logs stream to `logs/app.log` via `logging.basicConfig`; inspect that file for production issues instead of stdout.
- Ad-hoc scripts (`test.py`, `testing.py`) show how to call async converters with `asyncio.run`; replicate that pattern in tooling or notebooks.
- Dependencies are pinned in `requirements.txt`; install with `pip install -r requirements.txt` before attempting LangChain calls.
