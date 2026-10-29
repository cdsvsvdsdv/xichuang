"""ORM 对象转成前端用的普通字典。"""

import json

from sqlalchemy import func, select

from .models import Character, Conversation, GeneratedImage, Memory, Message, Profile
from .world import keywords_of, secondary_of


def _json_list(raw: str, keep_str_only: bool = False) -> list:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    if keep_str_only:
        return [item for item in data if isinstance(item, str)]
    return data


def profile_payload(profile: Profile) -> dict:
    return {
        "name": profile.name or "",
        "persona": profile.persona or "",
        "theme": profile.theme or "default",
        "background_url": profile.background_url or "",
    }


def character_payload(c: Character, favorite: bool | None = None) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "tagline": c.tagline,
        "greeting": c.greeting,
        "persona": c.persona,
        "default_model": c.default_model,
        "system_prompt": c.system_prompt or "",
        "avatar_url": c.avatar_url or "",
        "tags": _json_list(c.tags),
        "alternates": _json_list(c.alternates, keep_str_only=True),
        "favorite": bool(c.favorite) if favorite is None else bool(favorite),
        "created_by": c.created_by,
    }


def parse_variants(message: Message) -> list[str]:
    data = [str(item) for item in _json_list(message.variants) if str(item).strip()]
    return data or [message.content]


def message_payload(message: Message) -> dict:
    variants = parse_variants(message)
    index = min(max(message.active_variant or 0, 0), len(variants) - 1)
    return {
        "id": message.id,
        "role": message.role,
        "content": variants[index],
        "variants": variants,
        "active_variant": index,
        "created_at": message.created_at,
    }


def conversation_payload(db, conversation: Conversation) -> dict:
    last = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
        .limit(1)
    ).first()
    count = (
        db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation.id)
        )
        or 0
    )
    preview = (last.content or "").replace("\n", " ")[:80] if last else ""
    return {
        "id": conversation.id,
        "character_id": conversation.character_id,
        "title": conversation.title,
        "model": conversation.model,
        "updated_at": conversation.updated_at.isoformat(),
        "last_message": preview,
        "message_count": count,
    }


def world_payload(entry) -> dict:
    return {
        "id": entry.id,
        "character_id": entry.character_id,
        "keywords": keywords_of(entry),
        "keywords_secondary": secondary_of(entry),
        "logic": entry.logic or "and_any",
        "depth": entry.depth,
        "sticky": entry.sticky or 0,
        "content": entry.content,
        "constant": bool(entry.constant),
        "enabled": bool(entry.enabled),
    }


def variable_payload(row) -> dict:
    return {"id": row.id, "key": row.key, "value": row.value}


def memory_payload(db, conversation: Conversation) -> dict:
    facts = db.scalars(
        select(Memory)
        .where(Memory.conversation_id == conversation.id)
        .order_by(Memory.id)
    ).all()
    return {
        "summary": conversation.summary or "",
        "facts": [{"id": f.id, "content": f.content} for f in facts],
        "updated_at": conversation.memory_updated_at.isoformat()
        if conversation.memory_updated_at
        else None,
        "cursor": conversation.summary_upto_id or 0,
    }


def image_payload(image: GeneratedImage) -> dict:
    return {
        "id": image.id,
        "url": f"/media/{image.filename}",
        "prompt": image.prompt,
        "provider": image.provider,
        "created_at": image.created_at.isoformat(),
    }
