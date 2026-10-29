"""长期记忆的查看与编辑。"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth import current_user, owned_conversation
from ..db import SessionLocal
from ..memory import maybe_update_memory
from ..models import Conversation, Memory, User
from ..schemas import MemoryUpdate
from ..serializers import memory_payload

router = APIRouter(prefix="/api", tags=["memory"])


def _owned_memory(db, memory_id: int, user: User) -> Memory:
    memory = db.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    conversation = db.get(Conversation, memory.conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory


@router.get("/conversations/{conversation_id}/memory")
def get_memory(conversation_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        conversation = owned_conversation(db, conversation_id, user)
        return memory_payload(db, conversation)


@router.post("/conversations/{conversation_id}/memory/refresh")
async def refresh_memory(conversation_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        owned_conversation(db, conversation_id, user)

    await maybe_update_memory(conversation_id, force=True)

    with SessionLocal() as db:
        conversation = owned_conversation(db, conversation_id, user)
        return memory_payload(db, conversation)


@router.patch("/memories/{memory_id}")
def update_memory(
    memory_id: int, payload: MemoryUpdate, user: User = Depends(current_user)
):
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    with SessionLocal() as db:
        memory = _owned_memory(db, memory_id, user)
        memory.content = content[:300]
        conversation = db.get(Conversation, memory.conversation_id)
        if conversation:
            conversation.memory_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(memory)
        return {"id": memory.id, "content": memory.content}


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        memory = _owned_memory(db, memory_id, user)
        conversation = db.get(Conversation, memory.conversation_id)
        db.delete(memory)
        if conversation:
            conversation.memory_updated_at = datetime.utcnow()
        db.commit()
        return {"ok": True}
