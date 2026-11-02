"""Persistent scheduler. Run one or more workers against the same database."""
import time
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import ActionLog, Reminder


class DeliveryFailure(Exception):
    def __init__(self, en: str, es: str):
        self.en, self.es = en, es
        super().__init__(en)


def unavailable(reminder: Reminder) -> str | None:
    raise DeliveryFailure("No delivery service is configured.", "No hay un servicio de entrega configurado.")


def run_due(engine, callback: Callable[[Reminder], str | None] = unavailable) -> int:
    with Session(engine) as db:
        ids = list(db.scalars(select(Reminder.id).where(Reminder.state == "scheduled", Reminder.due_at <= datetime.now(timezone.utc).replace(tzinfo=None))))
    count = 0
    for reminder_id in ids:
        with Session(engine) as db:
            claim = db.execute(update(Reminder).where(Reminder.id == reminder_id, Reminder.state == "scheduled").values(state="attempted"))
            if claim.rowcount != 1:
                db.rollback()
                continue
            db.add(ActionLog(reminder_id=reminder_id, state="attempted"))
            db.commit()
            count += 1
            reminder = db.get(Reminder, reminder_id)
            try:
                evidence = callback(reminder)
                if not isinstance(evidence, str) or not evidence.strip():
                    raise DeliveryFailure("Delivery could not be confirmed.", "No se pudo confirmar la entrega.")
                reminder.state = "completed"
                reminder.evidence = evidence.strip()
                db.add(ActionLog(reminder_id=reminder_id, state="completed", evidence=reminder.evidence))
            except Exception as exc:
                en = exc.en if isinstance(exc, DeliveryFailure) else "Delivery failed because of an unexpected error."
                es = exc.es if isinstance(exc, DeliveryFailure) else "La entrega falló debido a un error inesperado."
                reminder.failure_reason_en, reminder.failure_reason_es = en, es
                db.add(ActionLog(reminder_id=reminder_id, state="failed", reason_en=en, reason_es=es))
            db.commit()
    return count


def main():
    from app.phone import configured_delivery
    engine = get_engine()
    delivery = configured_delivery()
    while True:
        run_due(engine, delivery)
        time.sleep(1)


if __name__ == "__main__":
    main()
