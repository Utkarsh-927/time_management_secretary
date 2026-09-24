"""pgvector SQLAlchemy type with a lightweight fallback for test environments."""

import os
from sqlalchemy.types import UserDefinedType

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))

try:
    from pgvector.sqlalchemy import Vector as VectorType  # type: ignore
except ImportError:
    class VectorType(UserDefinedType):
        cache_ok = True

        def __init__(self, dimensions: int):
            self.dimensions = dimensions

        def get_col_spec(self, **kw):
            return f"VECTOR({self.dimensions})"

        def bind_processor(self, dialect):
            def process(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    return value
                return "[" + ",".join(str(float(x)) for x in value) + "]"
            return process

        def result_processor(self, dialect, coltype):
            def process(value):
                if value is None or isinstance(value, (list, tuple)):
                    return value
                text = str(value).strip().strip("[]")
                if not text:
                    return []
                return [float(x) for x in text.split(",")]
            return process
