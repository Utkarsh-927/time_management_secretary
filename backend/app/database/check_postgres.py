from sqlalchemy import text
from .database import engine, IS_POSTGRES, DATABASE_URL

if not IS_POSTGRES:
    raise SystemExit("DATABASE_URL is not PostgreSQL. Set it in .env first.")

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")) .scalar_one()
    vector_version = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'")) .scalar_one_or_none()
    tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()

print("PostgreSQL connection: OK")
print("PostgreSQL:", version)
print("pgvector:", vector_version or "NOT ENABLED")
print("Tables:", ", ".join(tables))
