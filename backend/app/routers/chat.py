"""会话、消息、Swipe、对话与重新生成。"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from ..auth import current_user, owned_conversation, owned_message
from ..cleanup import purge_conversation
from ..db import SessionLocal
from ..deps import check_rate
from ..models import (
    Character,
    Conversation,
    ConversationVariable,
    Memory,
    Message,
    User,
)
from ..schemas import (
    ChatIn,
    ConversationCreate,
    MessageUpdate,
    RegenerateIn,
    SwipeIn,
)
from ..serializers import (
    conversation_payload,
    message_payload,
    parse_variants,
)
from ..services import build_context, fill_placeholders, get_profile, stream_reply

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/conversations")
def list_conversations(character_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        rows = db.scalars(
            select(Conversation)
            .where(
                Conversation.character_id == character_id,
                Conversation.user_id == user.id,
            )
            .order_by(Conversation.updated_at.desc())
        ).all()
        return [conversation_payload(db, row) for row in rows]


@router.post("/conversations")
def create_conversation(payload: ConversationCreate, user: User = Depends(current_user)):
    with SessionLocal() as db:
        character = db.get(Character, payload.character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        model = payload.model or character.default_model
        try:
            alternates = json.loads(character.alternates or "[]")
        except json.JSONDecodeError:
            alternates = []
        greetings = [character.greeting] + [
            item for item in alternates if isinstance(item, str) and item.strip()
        ]
        index = payload.greeting_index or 0
        greeting = (
            greetings[index] if 0 <= index < len(greetings) else character.greeting
        )
        profile = get_profile(db, user.id)
        greeting = fill_placeholders(
            greeting, character.name, (profile.name or "").strip() or "你"
        )

        conversation = Conversation(
            character_id=character.id,
            user_id=user.id,
            model=model,
            title="新对话",
        )
        db.add(conversation)
        db.flush()
        if greeting.strip():
            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=greeting,
                    model=model,
                    variants=json.dumps([greeting], ensure_ascii=False),
                    active_variant=0,
                )
            )
        db.commit()
        db.refresh(conversation)
        return conversation_payload(db, conversation)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        conversation = owned_conversation(db, conversation_id, user)
        purge_conversation(db, conversation.id)
        db.commit()
        return {"ok": True}


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        conversation = owned_conversation(db, conversation_id, user)
        return [message_payload(m) for m in conversation.messages]


@router.patch("/messages/{message_id}")
def update_message(
    message_id: int, payload: MessageUpdate, user: User = Depends(current_user)
):
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    with SessionLocal() as db:
        message = owned_message(db, message_id, user)
        message.content = content
        variants = parse_variants(message)
        index = min(max(message.active_variant or 0, 0), len(variants) - 1)
        variants[index] = content
        message.variants = json.dumps(variants, ensure_ascii=False)
        message.active_variant = index
        conversation = db.get(Conversation, message.conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(message)
        return message_payload(message)


@router.post("/messages/{message_id}/swipe")
def swipe_message(
    message_id: int, payload: SwipeIn, user: User = Depends(current_user)
):
    with SessionLocal() as db:
        message = owned_message(db, message_id, user)
        variants = parse_variants(message)
        if len(variants) < 2:
            raise HTTPException(status_code=400, detail="这条消息只有一个版本")
        index = payload.index
        if not 0 <= index < len(variants):
            raise HTTPException(status_code=400, detail="版本序号超出范围")
        message.active_variant = index
        message.content = variants[index]
        conversation = db.get(Conversation, message.conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(message)
        return message_payload(message)


@router.delete("/messages/{message_id}")
def delete_message(message_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        message = owned_message(db, message_id, user)
        conversation_id = message.conversation_id
        db.delete(message)
        conversation = db.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()
        db.commit()
        return {"ok": True}


def _export_rows(db, conversation: Conversation):
    facts = [
        row.content
        for row in db.scalars(
            select(Memory).where(Memory.conversation_id == conversation.id)
        ).all()
    ]
    variables = [
        (row.key, row.value)
        for row in db.scalars(
            select(ConversationVariable)
            .where(ConversationVariable.conversation_id == conversation.id)
            .order_by(ConversationVariable.id)
        ).all()
    ]
    return facts, variables


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: int,
    format: str = "json",
    user: User = Depends(current_user),
):
    with SessionLocal() as db:
        conversation = owned_conversation(db, conversation_id, user)
        character = db.get(Character, conversation.character_id)
        facts, variables = _export_rows(db, conversation)
        messages = []
        for item in conversation.messages:
            variants = parse_variants(item)
            index = min(max(item.active_variant or 0, 0), len(variants) - 1)
            messages.append(
                {
                    "id": item.id,
                    "role": item.role,
                    "content": variants[index],
                    "variants": variants,
                    "created_at": item.created_at.isoformat(),
                }
            )
        data = {
            "version": 1,
            "exported_at": datetime.utcnow().isoformat(),
            "character": {
                "id": character.id if character else None,
                "name": character.name if character else "",
                "tagline": character.tagline if character else "",
            },
            "conversation": {
                "id": conversation.id,
                "title": conversation.title,
                "model": conversation.model,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
            },
            "messages": messages,
            "memory": {"summary": conversation.summary or "", "facts": facts},
            "variables": [{"key": k, "value": v} for k, v in variables],
        }

    if format == "json":
        return data

    name = character.name if character else "角色"
    lines = [
        f"# {conversation.title}",
        "",
        f"- 角色：{name}",
        f"- 模型：{conversation.model}",
        f"- 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 消息数：{len(messages)}",
        "",
        "---",
        "",
    ]
    for item in messages:
        speaker = name if item["role"] == "assistant" else "我"
        if format == "md":
            lines.append(f"**{speaker}**：{item['content']}")
        else:
            lines.append(f"{speaker}：{item['content']}")
        lines.append("")

    if variables or facts or conversation.summary:
        lines.extend(["---", ""])
        if variables:
            lines.append("## 状态变量")
            lines.extend(f"- {k}：{v}" for k, v in variables)
            lines.append("")
        if conversation.summary:
            lines.append("## 剧情摘要")
            lines.append(conversation.summary)
            lines.append("")
        if facts:
            lines.append("## 长期事实")
            lines.extend(f"- {f}" for f in facts)
            lines.append("")

    body = "\n".join(lines)
    if format == "md":
        return Response(content=body, media_type="text/markdown; charset=utf-8")
    return Response(content=body, media_type="text/plain; charset=utf-8")


@router.post("/chat")
async def chat(
    payload: ChatIn, request: Request, user: User = Depends(current_user)
):
    check_rate(request, "chat", 30, 120)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息不能为空")
    if len(content) > 4000:
        raise HTTPException(status_code=400, detail="消息过长")

    with SessionLocal() as db:
        conversation = owned_conversation(db, payload.conversation_id, user)
        character = db.get(Character, conversation.character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        model = payload.model or conversation.model
        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=content,
                model=model,
            )
        )
        if conversation.title == "新对话":
            conversation.title = content[:24]
        conversation.model = model
        conversation.updated_at = datetime.utcnow()
        db.commit()

        system_prompt, history = build_context(db, conversation, character)

    return stream_reply(payload.conversation_id, model, system_prompt, history)


@router.post("/chat/regenerate")
async def regenerate(
    payload: RegenerateIn, request: Request, user: User = Depends(current_user)
):
    check_rate(request, "chat", 30, 120)
    with SessionLocal() as db:
        conversation = owned_conversation(db, payload.conversation_id, user)
        character = db.get(Character, conversation.character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        model = payload.model or conversation.model
        last = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id.desc())
            .limit(1)
        ).first()
        if not last or last.role != "assistant":
            raise HTTPException(status_code=400, detail="只能重新生成最后一条回复")

        system_prompt, history = build_context(
            db, conversation, character, before_id=last.id
        )

    return stream_reply(payload.conversation_id, model, system_prompt, history, last.id)
