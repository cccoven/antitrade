"""Automation task, run, and finding endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_response import success
from auth_dependency import get_current_user
from db import get_db
from services.automation import AutomationModule

router = APIRouter(prefix="/api/automations", tags=["automations"])


class CreateTaskRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    task_type: str
    schedule_kind: str
    schedule_config: dict[str, Any]
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    scope: dict[str, Any] = Field(default_factory=dict)
    notification_config: dict[str, Any] = Field(default_factory=dict)


class UpdateTaskRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    status: str | None = None
    schedule_kind: str | None = None
    schedule_config: dict[str, Any] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    scope: dict[str, Any] | None = None
    notification_config: dict[str, Any] | None = None


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/tasks")
def list_tasks(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(AutomationModule(session).list_tasks(user_id))


@router.post("/tasks")
def create_task(
    req: CreateTaskRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        row = AutomationModule(session).define_task(
            user_id,
            name=req.name,
            task_type=req.task_type,
            schedule_kind=req.schedule_kind,
            schedule_config=req.schedule_config,
            timezone_name=req.timezone,
            scope=req.scope,
            notification_config=req.notification_config or None,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return success(row)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: str,
    req: UpdateTaskRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        row = AutomationModule(session).update_task(
            user_id,
            task_id,
            req.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="automation_task_not_found")
    return success(row)


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        deleted = AutomationModule(session).delete_task(user_id, task_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="automation_task_not_found")
    return success(None)


@router.post("/tasks/{task_id}/run")
def run_task(
    task_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        row = AutomationModule(session).run_task(user_id, task_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="automation_task_not_found")
    return success(row)


@router.get("/tasks/{task_id}/runs")
def list_runs(
    task_id: str,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    rows = AutomationModule(session).list_runs(user_id, task_id, limit=limit)
    if rows is None:
        raise HTTPException(status_code=404, detail="automation_task_not_found")
    return success(rows)


@router.get("/findings")
def list_findings(
    status: str | None = None,
    severity: str | None = None,
    finding_type: str | None = None,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(AutomationModule(session).list_findings(
        user_id,
        status=status,
        severity=severity,
        finding_type=finding_type,
        limit=limit,
    ))


@router.get("/reports")
def list_reports(
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(AutomationModule(session).list_reports(user_id, limit=limit))
