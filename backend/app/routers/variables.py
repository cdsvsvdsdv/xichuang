"""对话状态变量（好感度、金钱、地点等）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import current_user, owned_conversation
from ..db import SessionLocal
from ..models import Conversation, ConversationVariable, User
from ..schemas import VariableIn, VariableUpdate
from ..serializers import variable_payload
from ..variables import MAX_VARIABLES, load_variables

router = APIRouter(prefix="/api", tags=["variables"])


@router.get("/conversations/{conversation_id}/variables")
def list_variables(conversation_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        owned_conversation(db, conversation_id, user)
        return [variable_payload(row) for row in load_variables(db, conversation_id)]


@router.post("/conversations/{conversation_id}/variables")
def upsert_variable(
    conversation_id: int, payload: VariableIn, user: User = Depends(current_user)
):
    key = payload.key.strip()[:50]
    value = payload.value.strip()[:200]
    if not key:
        raise HTTPException(status_code=400, detail="状态名不能为空")

    with SessionLocal() as db:
        owned_conversation(db, conversation_id, user)

        existing = db.scalars(
            select(ConversationVariable).where(
                ConversationVariable.conversation_id == conversation_id,
                ConversationVariable.key == key,
            )
        ).first()
        if existing:
            existing.value = value
            db.commit()
            db.refresh(existing)
            return variable_payload(existing)

        rows = load_variables(db, conversation_id)
        if len(rows) >= MAX_VARIABLES:
            raise HTTPException(
                status_code=400, detail=f"最多 {MAX_VARIABLES} 个状态变量"
            )

        row = ConversationVariable(
            conversation_id=conversation_id, key=key, value=value
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return variable_payload(row)


def _owned_variable(db, variable_id: int, user: User) -> ConversationVariable:
    row = db.get(ConversationVariable, variable_id)
    if not row:
        raise HTTPException(status_code=404, detail="状态不存在")
    owned_conversation(db, row.conversation_id, user)
    return row


@router.patch("/variables/{variable_id}")
def update_variable(
    variable_id: int, payload: VariableUpdate, user: User = Depends(current_user)
):
    with SessionLocal() as db:
        row = _owned_variable(db, variable_id, user)
        if payload.key is not None:
            key = payload.key.strip()[:50]
            if not key:
                raise HTTPException(status_code=400, detail="状态名不能为空")
            row.key = key
        if payload.value is not None:
            row.value = payload.value.strip()[:200]
        db.commit()
        db.refresh(row)
        return variable_payload(row)


@router.delete("/variables/{variable_id}")
def delete_variable(variable_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        row = _owned_variable(db, variable_id, user)
        db.delete(row)
        db.commit()
        return {"ok": True}
