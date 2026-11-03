"""Reset only records belonging to the fictional demo persona."""
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionLog, CircleActivity, Consent, DemoSeed, EscalationRequest, Grant, Incident, Preference, Profile, Reminder, Task, TrustedContact

router = APIRouter()


@router.post("/demo/reset")
def reset_demo(request: Request, db: Session = Depends(get_db)):
    if os.getenv("DEMO_RESET_ENABLED") != "1":
        raise HTTPException(403, detail={"en": "Demo reset is disabled.", "es": "El reinicio de demostración está desactivado."})
    token = os.getenv("DEMO_API_TOKEN")
    if token:
        scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
        if not separator or scheme.lower() != "bearer" or not hmac.compare_digest(credential.encode(), token.encode()):
            raise HTTPException(401, detail={"en": "Authentication required.", "es": "Se requiere autenticación."}, headers={"WWW-Authenticate": "Bearer"})
    from seed_demo import PROFILE_ID
    marker = db.get(DemoSeed, PROFILE_ID)
    if marker:
        task_id = marker.task_id
        contacts = select(TrustedContact.id).where(TrustedContact.profile_id == PROFILE_ID)
        reminders = select(Reminder.id).where(Reminder.task_id == task_id)
        db.execute(delete(ActionLog).where(ActionLog.reminder_id.in_(reminders)))
        db.execute(delete(Reminder).where(Reminder.task_id == task_id))
        db.execute(delete(CircleActivity).where(CircleActivity.profile_id == PROFILE_ID))
        db.execute(delete(EscalationRequest).where(EscalationRequest.profile_id == PROFILE_ID))
        db.execute(delete(Grant).where(Grant.contact_id.in_(contacts)))
        db.execute(delete(TrustedContact).where(TrustedContact.profile_id == PROFILE_ID))
        db.execute(delete(Incident).where(Incident.profile_id == PROFILE_ID))
        db.delete(marker)
        db.flush()
        db.execute(delete(Task).where(Task.id == task_id))
        db.execute(delete(Preference).where(Preference.profile_id == PROFILE_ID))
        db.execute(delete(Consent).where(Consent.profile_id == PROFILE_ID))
        db.execute(delete(Profile).where(Profile.id == PROFILE_ID))
        db.commit()
        from app.main import drafts
        for key in [key for key, draft in drafts.items() if draft["profile_id"] == PROFILE_ID]:
            del drafts[key]
    return {"en": "Demo data cleared.", "es": "Datos de demostración borrados."}
