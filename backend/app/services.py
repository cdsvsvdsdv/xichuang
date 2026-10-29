"""对话主流程：拼系统提示词、裁剪上下文、流式落库。"""

import asyncio
import json
from datetime import datetime

from fastapi.responses import StreamingResponse
from sqlalchemy import select

from .config import CONTEXT_TOKEN_BUDGET, CONTEXT_TOKEN_RESERVE
from .db import SessionLocal
from .memory import maybe_update_memory
from .models import Character, Conversation, Memory, Message, Profile
from .providers import stream_chat
from .serializers import parse_variants
from .tokens import estimate_tokens, trim_history
from .variables import (
    StateExtractor,
    apply_updates,
    load_variables,
    parse_updates,
    variables_block,
)
from .world import (
    build_world_block,
    inject_at_depth,
    match_entries,
    split_by_depth,
)


def get_profile(db, user_id: int) -> Profile:
    profile = db.scalars(select(Profile).where(Profile.user_id == user_id)).first()
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def build_system_prompt(
    ch: Character,
    summary: str = "",
    facts: list[str] | None = None,
    profile: Profile | None = None,
    world: str = "",
    variables: str = "",
) -> str:
    custom = (ch.system_prompt or "").strip()
    if custom:
        parts = [custom, f"角色设定：{ch.persona}"]
    else:
        parts = [
            f"你正在扮演「{ch.name}」，与用户进行沉浸式角色对话。",
            f"角色设定：{ch.persona}",
            "对话要求：",
            "1. 始终以第一人称、保持角色身份和语气，不要提及 AI、模型或提示词。",
            "2. 回复自然口语化，长度以 2-4 段为宜，除非用户要求展开。",
            "3. 可以描写动作、神态和环境，用括号括起来。",
            "4. 不生成违法、色情、暴力或伤害未成年人的内容；遇到此类请求，以角色口吻婉拒。",
        ]
    if world:
        parts.append(world)
    if variables:
        parts.append(variables)
    if profile and (profile.name.strip() or profile.persona.strip()):
        user_block = f"【用户人设】\n用户称呼：{profile.name or '用户'}"
        if profile.persona.strip():
            user_block += f"\n{profile.persona.strip()}"
        parts.append(user_block)
    if summary:
        parts.append(f"【长期记忆 · 剧情摘要】\n{summary}")
    if facts:
        parts.append("【长期记忆 · 已知事实】\n" + "\n".join(f"- {f}" for f in facts))
    if summary or facts:
        parts.append("请在对话中自然运用这些记忆，不要生硬复述。")
    return "\n".join(parts)


def build_context(
    db, conversation: Conversation, character: Character, before_id: int | None = None
):
    stmt = select(Message).where(Message.conversation_id == conversation.id)
    if before_id:
        stmt = stmt.where(Message.id < before_id)
    rows = db.scalars(stmt.order_by(Message.id)).all()
    full_history = [
        {"role": row.role, "content": row.content}
        for row in rows
        if row.role in ("user", "assistant")
    ]
    facts = [
        m.content
        for m in db.scalars(
            select(Memory).where(Memory.conversation_id == conversation.id)
        ).all()
    ]
    profile = get_profile(db, conversation.user_id or 0)
    recent = "\n".join(item["content"] for item in full_history[-6:])
    hits = match_entries(db, character.id, conversation.id, recent)
    inline, deep = split_by_depth(hits)
    system_prompt = build_system_prompt(
        character,
        conversation.summary or "",
        facts,
        profile,
        build_world_block(inline),
        variables_block(load_variables(db, conversation.id)),
    )

    budget = CONTEXT_TOKEN_BUDGET - CONTEXT_TOKEN_RESERVE - estimate_tokens(
        system_prompt
    )
    history = trim_history(full_history, budget)
    return system_prompt, inject_at_depth(history, deep)


def stream_reply(
    conversation_id: int,
    model: str,
    system_prompt: str,
    history: list[dict],
    target_message_id: int | None = None,
):
    async def event_stream():
        parts: list[str] = []
        extractor = StateExtractor()
        try:
            async for piece in stream_chat(
                model, [{"role": "system", "content": system_prompt}, *history]
            ):
                clean = extractor.feed(piece)
                if clean:
                    parts.append(clean)
                    yield "data: " + json.dumps(
                        {"type": "delta", "content": clean}, ensure_ascii=False
                    ) + "\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            yield "data: " + json.dumps(
                {"type": "error", "message": str(exc)}, ensure_ascii=False
            ) + "\n\n"
        finally:
            tail = extractor.flush()
            if tail:
                parts.append(tail)
                yield "data: " + json.dumps(
                    {"type": "delta", "content": tail}, ensure_ascii=False
                ) + "\n\n"

            text = "".join(parts).strip()
            updates = parse_updates(extractor.state_raw)
            if text or updates:
                with SessionLocal() as db:
                    if text:
                        target = (
                            db.get(Message, target_message_id)
                            if target_message_id
                            else None
                        )
                        if target is not None:
                            variants = parse_variants(target)
                            variants.append(text)
                            target.variants = json.dumps(variants, ensure_ascii=False)
                            target.active_variant = len(variants) - 1
                            target.content = text
                            target.model = model
                        else:
                            db.add(
                                Message(
                                    conversation_id=conversation_id,
                                    role="assistant",
                                    content=text,
                                    model=model,
                                    variants=json.dumps([text], ensure_ascii=False),
                                    active_variant=0,
                                )
                            )
                        conv = db.get(Conversation, conversation_id)
                        if conv:
                            conv.model = model
                            conv.updated_at = datetime.utcnow()
                        db.commit()
                    if updates:
                        apply_updates(db, conversation_id, updates)
            asyncio.create_task(maybe_update_memory(conversation_id))
            yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
