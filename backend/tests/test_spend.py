import pytest
from sqlalchemy import create_engine, select

from app.spend import CAP, SpendLimitExceeded, ledger, metadata, reserve, settle


def test_reservations_refuse_over_cap_and_settle(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'spend.db'}")
    metadata.create_all(engine)
    first = reserve(engine, "muse-spark-1.3", CAP - 10)
    with pytest.raises(SpendLimitExceeded):
        reserve(engine, "muse-spark-1.3", 11)
    settle(engine, first, 5, input_tokens=10, cached_tokens=2, output_tokens=3)
    reserve(engine, "muse-spark-1.3", CAP - 5)
    with engine.connect() as conn:
        row = conn.execute(select(ledger).where(ledger.c.id == first)).mappings().one()
        assert (row["cost_microdollars"], row["input_tokens"], row["cached_tokens"], row["output_tokens"]) == (5, 10, 2, 3)
    with pytest.raises(ValueError):
        settle(engine, first, 1, input_tokens=0, cached_tokens=0, output_tokens=0)
    engine.dispose()
