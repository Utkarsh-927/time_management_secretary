from .connection import engine, Base
from . import models


def init_database():
    Base.metadata.create_all(bind=engine)

    print("Database initialized successfully.")
    print(f"Database: {engine.url}")


if __name__ == "__main__":
    init_database()