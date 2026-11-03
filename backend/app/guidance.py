"""Local, bilingual guidance that can also be called directly by an agent."""
from copy import deepcopy
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CommunityResource

Language = Literal["en", "es"]
router = APIRouter(prefix="/guidance", tags=["guidance"])

HEALTH = {
    "en": {
        "disclaimer": "This is navigation help, not medical advice. Consult a qualified healthcare professional about your health and treatment.",
        "checklist": ["Confirm the date, location, and any accessibility or interpreter needs.", "Write down your concerns and the purpose of the visit."],
        "what_to_bring": ["Bring identification and insurance information if available.", "Bring a list of medicines and supplements, and relevant records if available."],
        "questions": ["What should I understand about the next steps?", "Who should I contact if I have questions after the visit?"],
    },
    "es": {
        "disclaimer": "Esta es ayuda para orientarse, no consejo médico. Consulte a un profesional de salud calificado sobre su salud y tratamiento.",
        "checklist": ["Confirme la fecha, el lugar y si necesita accesibilidad o intérprete.", "Anote sus inquietudes y el motivo de la cita."],
        "what_to_bring": ["Lleve identificación y datos del seguro si los tiene.", "Lleve una lista de medicamentos y suplementos, y los registros pertinentes si los tiene."],
        "questions": ["¿Qué debo entender sobre los próximos pasos?", "¿Con quién puedo comunicarme si tengo preguntas después de la cita?"],
    },
}
GOVERNMENT = {
    "en": {"benefit_lookup": ["Use an official government benefits website or contact the agency to learn about programs and eligibility.", "Confirm the application steps and required documents with the agency."], "office_visit": ["Confirm the office address, hours, appointment and interpreter availability.", "Bring requested identification, documents and a list of questions; ask for a receipt for anything submitted."]},
    "es": {"benefit_lookup": ["Use un sitio oficial de beneficios del gobierno o contacte a la agencia para conocer programas y requisitos.", "Confirme con la agencia los pasos para solicitar y los documentos necesarios."], "office_visit": ["Confirme la dirección, el horario, la cita y la disponibilidad de intérprete.", "Lleve la identificación y los documentos solicitados y una lista de preguntas; pida un recibo por lo que entregue."]},
}
UTILITY = {
    "en": {"bill_reading": ["Find the billing period, amount due, due date, usage and any past-due balance or fees.", "Ask the utility to explain charges you do not recognize."], "payment_options": ["Ask the utility about payment plans, due-date changes and fees before choosing an option."], "hardship_programs": ["Ask the utility about hardship assistance and contact your local community action agency about energy assistance programs.", "Check eligibility, deadlines and required documents with the program."]},
    "es": {"bill_reading": ["Busque el período de facturación, el monto y la fecha de pago, el consumo y cualquier saldo vencido o cargo.", "Pida a la compañía que explique los cargos que no reconozca."], "payment_options": ["Pregunte a la compañía sobre planes de pago, cambios de fecha y cargos antes de elegir una opción."], "hardship_programs": ["Pregunte a la compañía por ayuda ante dificultades y contacte a su agencia local de acción comunitaria sobre programas de ayuda energética.", "Confirme los requisitos, plazos y documentos con el programa."]},
}

# Examples are categories, not claims that a real local provider exists.
EXAMPLES = (
    {"id": None, "category": "food", "name": {"en": "Food support (example)", "es": "Apoyo alimentario (ejemplo)"}},
    {"id": None, "category": "transportation", "name": {"en": "Transportation support (example)", "es": "Apoyo de transporte (ejemplo)"}},
    {"id": None, "category": "housing", "name": {"en": "Housing support (example)", "es": "Apoyo de vivienda (ejemplo)"}},
)


def healthcare_guidance(lang: Language = "en") -> dict:
    return deepcopy(HEALTH[lang])


def government_guidance(lang: Language = "en") -> dict:
    return deepcopy(GOVERNMENT[lang])


def utility_guidance(lang: Language = "en") -> dict:
    return deepcopy(UTILITY[lang])


def community_directory(db: Session, lang: Language = "en", category: str | None = None) -> list[dict]:
    query = select(CommunityResource).order_by(CommunityResource.id)
    if category:
        query = query.where(CommunityResource.category == category)
    rows = [{"id": row.id, "category": row.category, "name": getattr(row, f"name_{lang}"),
             "location": row.location, "contact": row.contact, "example": False} for row in db.scalars(query)]
    examples = [{"id": item["id"], "category": item["category"], "name": item["name"][lang],
                 "location": None, "contact": None, "example": True} for item in EXAMPLES
                if not category or item["category"] == category]
    return examples + rows


@router.get("/healthcare")
def healthcare_api(lang: Language = "en"):
    return healthcare_guidance(lang)


@router.get("/government")
def government_api(lang: Language = "en"):
    return government_guidance(lang)


@router.get("/utilities")
def utilities_api(lang: Language = "en"):
    return utility_guidance(lang)


@router.get("/community")
def community_api(lang: Language = "en", category: str | None = None, db: Session = Depends(get_db)):
    return community_directory(db, lang, category)
