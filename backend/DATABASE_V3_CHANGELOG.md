# Database V3 changes

This build moves the AI Secretary database target to PostgreSQL + pgvector while preserving the existing FastAPI APIs.

Implemented:
- one canonical SQLAlchemy database layer
- PostgreSQL URL normalization for psycopg 3
- automatic `CREATE EXTENSION IF NOT EXISTS vector`
- HNSW cosine index for memory embeddings
- secretary memory tables: raw_notes, entities, facts, entity_relationships, events, memories, embeddings, conversation_sessions, conversation_messages
- richer operational task/meeting/reminder/availability models
- exact raw user-message persistence before AI interpretation
- secretary notes and conversation-history endpoints
- compatibility wrappers for the old database.connection/database.models imports
- optional SQLite -> PostgreSQL operational-data copy script
- local Docker PostgreSQL + pgvector compose file
- PostgreSQL environment example and verification script

Not yet implemented:
- Gemma extraction into entities/facts/relationships/events
- embedding generation
- hybrid semantic + structured retrieval
- final secretary answer generation from retrieved memory
