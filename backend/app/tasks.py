from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionLog, Reminder, Task

router = APIRouter()


def missing(en, es):
    raise HTTPException(404, detail={"en": en, "es": es})


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Title is required / Se requiere un título")
        return value.strip()


class ReminderInput(BaseModel):
    task_id: int
    kind: Literal["reminder", "callback"] = "reminder"
    due_at: datetime

    @field_validator("due_at")
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError("Time zone is required / Se requiere zona horaria")
        return value.astimezone(timezone.utc).replace(tzinfo=None)


def task_dict(task):
    return {"id": task.id, "title": task.title, "completed": task.completed}


def get_task(db, task_id):
    task = db.get(Task, task_id)
    if task is None:
        missing("Task not found", "Tarea no encontrada")
    return task


def reminder_dict(reminder):
    return {"id": reminder.id, "task_id": reminder.task_id, "kind": reminder.kind,
            "due_at": reminder.due_at.replace(tzinfo=timezone.utc).isoformat(),
            "state": reminder.state, "status": "failed" if reminder.failure_reason_en else reminder.state,
            "evidence": reminder.evidence,
            "failure_reason": {"en": reminder.failure_reason_en, "es": reminder.failure_reason_es} if reminder.failure_reason_en else None}


@router.post("/tasks", status_code=201)
def create_task(body: TaskInput, db: Session = Depends(get_db)):
    task = Task(title=body.title, completed=False)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task_dict(task)


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    return [task_dict(task) for task in db.scalars(select(Task).order_by(Task.id))]


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, body: TaskInput, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    task.title = body.title
    db.commit()
    return task_dict(task)


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    task.completed = True  # The user's explicit request is evidence of task completion.
    db.commit()
    return task_dict(task)


@router.post("/reminders", status_code=201)
def create_reminder(body: ReminderInput, db: Session = Depends(get_db)):
    get_task(db, body.task_id)
    reminder = Reminder(task_id=body.task_id, kind=body.kind, due_at=body.due_at, state="proposed")
    db.add(reminder)
    db.flush()
    db.add(ActionLog(reminder_id=reminder.id, state="proposed"))
    reminder.state = "scheduled"
    db.add(ActionLog(reminder_id=reminder.id, state="scheduled"))
    db.commit()
    db.refresh(reminder)
    return reminder_dict(reminder)


@router.get("/reminders/{reminder_id}")
def get_reminder(reminder_id: int, db: Session = Depends(get_db)):
    reminder = db.get(Reminder, reminder_id)
    if reminder is None:
        missing("Reminder not found", "Recordatorio no encontrado")
    result = reminder_dict(reminder)
    logs = db.scalars(select(ActionLog).where(ActionLog.reminder_id == reminder_id).order_by(ActionLog.id))
    result["history"] = [{"state": log.state, "evidence": log.evidence,
                          "reason": {"en": log.reason_en, "es": log.reason_es} if log.reason_en else None} for log in logs]
    return result

@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    reminder_ids = list(db.scalars(select(Reminder.id).where(Reminder.task_id == task_id)))
    if reminder_ids:
        raise HTTPException(409, detail={"en": "This task has reminders and cannot be deleted.",
                                         "es": "Esta tarea tiene recordatorios y no se puede eliminar."})
    db.delete(task)
    db.commit()
    return {"deleted": True}
