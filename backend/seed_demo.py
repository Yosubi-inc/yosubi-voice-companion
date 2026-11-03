"""Seed a fictional demo into a dedicated development database."""
from datetime import datetime, timedelta, timezone
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Consent, DemoSeed, Grant, Incident, Preference, Profile, Reminder, Task, TrustedContact, ActionLog

PROFILE_ID = "demo-maria"


def seed(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if db.get(DemoSeed, PROFILE_ID):
            return
        if db.get(Profile, PROFILE_ID):
            raise ValueError("Demo profile ID is already in use / El ID de demostración ya está en uso")
        db.add(Profile(id=PROFILE_ID, name="María Vega"))
        db.flush()
        db.add_all([Preference(profile_id=PROFILE_ID, preferred_language="es", communication_needs="Hablar despacio y con frases claras."), Consent(profile_id=PROFILE_ID, granted=True)])
        task = Task(title="Demo: revisar la cita médica", completed=False)
        contact = TrustedContact(profile_id=PROFILE_ID, name="Elena Vega", role="family")
        db.add_all([task, contact])
        db.flush()
        db.add_all([DemoSeed(profile_id=PROFILE_ID, task_id=task.id), Grant(contact_id=contact.id, permission="receive_escalation", revoked=False), Incident(profile_id=PROFILE_ID, summary="Consulta informativa resuelta sobre una llamada desconocida.", status="resolved")])
        reminder = Reminder(task_id=task.id, kind="reminder", due_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=2), state="scheduled")
        db.add(reminder)
        db.flush()
        db.add(ActionLog(reminder_id=reminder.id, state="scheduled"))
        db.commit()


if __name__ == "__main__":
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        seed(engine)
    finally:
        engine.dispose()
