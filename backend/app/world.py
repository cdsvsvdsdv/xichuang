"""世界书：关键词触发的设定条目，命中后注入系统提示词或对话深度。"""

import json

from sqlalchemy import or_, select

from .models import WorldEntry

MAX_INJECT_CHARS = 3000

LOGIC_ANY = "and_any"      # 主键命中 且 任一副键命中
LOGIC_ALL = "and_all"      # 主键命中 且 全部副键命中
LOGIC_NOT_ANY = "not_any"  # 主键命中 且 没有副键命中
LOGIC_NOT_ALL = "not_all"  # 主键命中 且 不是全部副键命中
LOGIC_CHOICES = (LOGIC_ANY, LOGIC_ALL, LOGIC_NOT_ANY, LOGIC_NOT_ALL)

# (conversation_id, entry_id) -> 剩余粘性轮数，进程内状态，重启即失
_sticky_turns: dict[tuple[int, int], int] = {}


def _keys(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if str(item).strip()]


def keywords_of(entry: WorldEntry) -> list[str]:
    return _keys(entry.keywords)


def secondary_of(entry: WorldEntry) -> list[str]:
    return _keys(entry.keywords_secondary)


def _logic_ok(logic: str, total: int, hits: int) -> bool:
    if total == 0:
        return True
    if logic == LOGIC_ALL:
        return hits == total
    if logic == LOGIC_NOT_ANY:
        return hits == 0
    if logic == LOGIC_NOT_ALL:
        return hits < total
    return hits >= 1


def match_entries(
    db, character_id: int, conversation_id: int, text: str
) -> list[WorldEntry]:
    rows = db.scalars(
        select(WorldEntry)
        .where(
            WorldEntry.enabled.is_(True),
            or_(
                WorldEntry.character_id == character_id,
                WorldEntry.character_id.is_(None),
            ),
        )
        .order_by(WorldEntry.constant.desc(), WorldEntry.id)
    ).all()

    haystack = text.lower()
    hits: list[WorldEntry] = []

    for entry in rows:
        state_key = (conversation_id, entry.id)
        remaining = _sticky_turns.get(state_key, 0)

        triggered = bool(entry.constant)
        if not triggered:
            primary = any(key.lower() in haystack for key in keywords_of(entry))
            if primary:
                secondary = secondary_of(entry)
                matched = sum(1 for key in secondary if key.lower() in haystack)
                triggered = _logic_ok(entry.logic or LOGIC_ANY, len(secondary), matched)

        if triggered:
            if entry.sticky and entry.sticky > 0:
                _sticky_turns[state_key] = entry.sticky
            hits.append(entry)
        elif remaining > 0:
            _sticky_turns[state_key] = remaining - 1
            if _sticky_turns[state_key] <= 0:
                del _sticky_turns[state_key]
            hits.append(entry)

    return hits


def split_by_depth(entries: list[WorldEntry]):
    inline: list[WorldEntry] = []
    deep: list[WorldEntry] = []
    for entry in entries:
        (deep if entry.depth is not None else inline).append(entry)
    return inline, deep


def build_world_block(entries: list[WorldEntry]) -> str:
    if not entries:
        return ""

    lines = []
    used = 0
    for entry in entries:
        content = entry.content.strip()
        if not content:
            continue
        if used + len(content) > MAX_INJECT_CHARS:
            break
        used += len(content)
        lines.append(f"- {content}")

    if not lines:
        return ""
    return "【世界设定】\n" + "\n".join(lines)


def inject_at_depth(history: list[dict], entries: list[WorldEntry]) -> list[dict]:
    """depth=0 表示插在最后一条之后，depth=N 表示插在倒数第 N 条之前。"""
    if not entries:
        return history

    result = list(history)
    for entry in sorted(entries, key=lambda item: -(item.depth or 0)):
        content = entry.content.strip()
        if not content:
            continue
        position = max(0, len(result) - (entry.depth or 0))
        result.insert(position, {"role": "system", "content": content})
    return result
