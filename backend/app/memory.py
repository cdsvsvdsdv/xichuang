import json
import re
from datetime import datetime

from sqlalchemy import delete, select

from .config import MEMORY_KEEP, MEMORY_TRIGGER
from .db import SessionLocal
from .models import Conversation, Memory, Message
from .providers import complete_chat

MEMORY_PROMPT = """你是对话记忆整理助手。请阅读角色对话，输出严格的 JSON（不要 markdown 代码块）：
{"summary": "...", "facts": ["...", "..."]}

要求：
- summary：不超过 300 字，用第三人称概括剧情进展、关系变化、重要事件与情绪基调。
- facts：不超过 8 条，每条一句话，只保留长期有用的事实（用户设定、角色关系、承诺、偏好、关键物件/地点）。
- 若已有摘要和事实，请在其基础上更新，不要丢失旧信息。
- 不要编造对话中没有的内容。
"""


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {}


async def maybe_update_memory(conversation_id: int, force: bool = False) -> None:
    try:
        with SessionLocal() as db:
            conversation = db.get(Conversation, conversation_id)
            if not conversation:
                return

            rows = db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.id > (conversation.summary_upto_id or 0),
                )
                .order_by(Message.id)
            ).all()
            if not force and len(rows) <= MEMORY_TRIGGER:
                return

            if force:
                chunk = rows[:-2] if len(rows) > 3 else rows
            else:
                chunk = rows[: len(rows) - MEMORY_KEEP]
            if not chunk:
                return

            old_summary = conversation.summary or ""
            old_facts = [
                m.content
                for m in db.scalars(
                    select(Memory).where(Memory.conversation_id == conversation_id)
                ).all()
            ]
            transcript = "\n".join(
                f"{'用户' if m.role == 'user' else '角色'}：{m.content}" for m in chunk
            )
            cutoff = chunk[-1].id

        facts_text = "\n".join(f"- {f}" for f in old_facts) if old_facts else "无"
        user_prompt = (
            f"已有摘要：{old_summary or '无'}\n\n"
            f"已有事实：\n{facts_text}\n\n"
            f"新增对话：\n{transcript[:12000]}"
        )

        raw = await complete_chat(
            "deepseek-chat",
            [
                {"role": "system", "content": MEMORY_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        data = _parse_json(raw)
        summary = str(data.get("summary") or "").strip()
        facts = [str(f).strip() for f in (data.get("facts") or []) if str(f).strip()]
        if not summary and not facts:
            return

        seen: set[str] = set()
        unique_facts: list[str] = []
        for fact in facts:
            if fact not in seen:
                seen.add(fact)
                unique_facts.append(fact)

        with SessionLocal() as db:
            conversation = db.get(Conversation, conversation_id)
            if not conversation:
                return
            if summary:
                conversation.summary = summary[:1200]
            conversation.summary_upto_id = max(conversation.summary_upto_id or 0, cutoff)
            conversation.memory_updated_at = datetime.utcnow()
            if unique_facts:
                db.execute(
                    delete(Memory).where(Memory.conversation_id == conversation_id)
                )
                for fact in unique_facts[:10]:
                    db.add(
                        Memory(
                            conversation_id=conversation_id,
                            kind="fact",
                            content=fact[:300],
                        )
                    )
            db.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"[memory] update failed: {exc}")
