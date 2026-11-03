"""Conservative, durable reservations for model API spending.

Amounts are integer microdollars. A reservation remains charged if a call's
outcome is unknown; an operator must reconcile it before reclaiming funds.
"""
from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, func, insert, select, text, update

CAP = 120_000_000
metadata = MetaData()
ledger = Table(
    "model_spend_ledger", metadata,
    Column("id", Integer, primary_key=True),
    Column("model", String(80), nullable=False),
    Column("reserved_microdollars", BigInteger, nullable=False),
    Column("cost_microdollars", BigInteger),
    Column("input_tokens", BigInteger),
    Column("cached_tokens", BigInteger),
    Column("output_tokens", BigInteger),
    Column("status", String(16), nullable=False),
)


class SpendLimitExceeded(Exception):
    pass


def reserve(engine, model: str, maximum_microdollars: int) -> int:
    """Atomically reserve a caller-supplied upper bound before a paid call."""
    if type(maximum_microdollars) is not int or maximum_microdollars <= 0:
        raise ValueError("a positive integer upper bound is required")
    with engine.connect() as conn:
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        elif conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(831526027)"))
        else:
            raise ValueError("unsupported database")
        total = conn.scalar(select(func.coalesce(func.sum(ledger.c.reserved_microdollars), 0)))
        if total + maximum_microdollars > CAP:
            raise SpendLimitExceeded()
        result = conn.execute(insert(ledger).values(model=model, reserved_microdollars=maximum_microdollars, status="reserved"))
        reservation_id = result.inserted_primary_key[0]
        conn.commit()
        return reservation_id


def settle(engine, reservation_id: int, cost_microdollars: int, *, input_tokens: int, cached_tokens: int, output_tokens: int) -> None:
    values = (cost_microdollars, input_tokens, cached_tokens, output_tokens)
    if any(type(value) is not int or value < 0 for value in values) or cached_tokens > input_tokens:
        raise ValueError("invalid usage")
    with engine.begin() as conn:
        result = conn.execute(update(ledger).where(
            ledger.c.id == reservation_id, ledger.c.status == "reserved",
            ledger.c.reserved_microdollars >= cost_microdollars,
        ).values(reserved_microdollars=cost_microdollars, cost_microdollars=cost_microdollars,
                 input_tokens=input_tokens, cached_tokens=cached_tokens, output_tokens=output_tokens, status="settled"))
        if result.rowcount != 1:
            raise ValueError("reservation missing, already settled, or insufficient")
