from app.database.database import SessionLocal
from app.models import Memory, Embedding
from app.services.embedding_service import create_memory_embedding


def main():
    db = SessionLocal()

    try:
        memories = (
            db.query(Memory)
            .filter(Memory.is_active.is_(True))
            .all()
        )

        created = 0
        skipped = 0

        for memory in memories:
            existing = (
                db.query(Embedding)
                .filter(
                    Embedding.memory_id == memory.id,
                )
                .first()
            )

            if existing:
                skipped += 1
                continue

            create_memory_embedding(
                db=db,
                memory=memory,
            )

            created += 1

            if created % 10 == 0:
                db.commit()
                print(f"Processed {created} memories...")

        db.commit()

        print()
        print("Backfill complete")
        print("Memories checked:", len(memories))
        print("Embeddings created:", created)
        print("Already existed:", skipped)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()