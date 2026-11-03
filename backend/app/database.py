"""Database setup for the API and development schema."""
import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base


@lru_cache
def get_engine():
    return create_engine(os.environ["DATABASE_URL"])


def get_db():
    with Session(get_engine()) as session:
        yield session


def create_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        Base.metadata.create_all(engine)
        from app.spend import metadata as spend_metadata
        spend_metadata.create_all(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    create_schema(os.environ["DATABASE_URL"])
