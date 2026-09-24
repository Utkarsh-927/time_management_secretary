# AI Secretary Database V3 — PostgreSQL + pgvector

This backend now uses one canonical SQLAlchemy database layer and is designed for PostgreSQL + pgvector. SQLite remains only as a fallback for tests/offline development.

## 1. Install Python dependencies

From the backend folder:

```powershell
pip install -r requirements.txt
```

## 2. Start local PostgreSQL + pgvector

Docker Desktop must be running.

```powershell
docker compose -f docker-compose.postgres.yml up -d
```

## 3. Configure `.env`

Add/update:

```env
DATABASE_URL=postgresql+psycopg://management_user:management_password@localhost:5432/management_model
FRONTEND_URL=http://localhost:5173
EMBEDDING_DIMENSIONS=384
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

Do not commit real production database passwords.

## 4. Initialize PostgreSQL

```powershell
python -m app.database.init_db
```

This enables the `vector` extension, creates the relational/memory tables, and creates an HNSW cosine index for embeddings.

## 5. Verify it

```powershell
python -m app.database.check_postgres
```

Expected: PostgreSQL connection OK, a pgvector version, and the tables listed.

## 6. Optional: copy existing SQLite operational data

Back up the old database first, then:

```powershell
python -m app.database.migrate_sqlite_to_postgres --sqlite ./data/management_model.db
```

This copies tasks, meetings, reminders and availability. It does not delete the SQLite file.

## 7. Run API

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## New memory tables

- raw_notes — immutable source text
- entities — people/projects/clients/etc.
- facts — typed, versionable facts
- entity_relationships — graph-like links
- events — assignments/reviews/deadlines/etc.
- memories — retrieval-ready memory text
- embeddings — native pgvector vectors
- conversation_sessions / conversation_messages — short-term conversational context

## Current milestone

Database foundation + raw-note/conversation persistence is implemented. The next milestone is Gemma extraction into entities/facts/relationships/events, then embedding generation and hybrid retrieval.
