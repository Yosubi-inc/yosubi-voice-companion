"""Create the development schema using DATABASE_URL."""
import os

from sqlalchemy import create_engine

from app.models import Base


def create_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    create_schema(os.environ["DATABASE_URL"])
