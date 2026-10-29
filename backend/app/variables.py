"""对话状态变量：模型在回复里用 <state> 块更新，流式输出时对用户隐藏。"""

import re

from sqlalchemy import select

from .models import ConversationVariable

STATE_OPEN = "<state>"
STATE_CLOSE = "</state>"
MAX_VARIABLES = 20


class StateExtractor:
    """边流式输出边剥离 <state> 块，连不完整的半个标签也先扣住。"""

    def __init__(self) -> None:
        self.buffer = ""
        self.in_state = False
        self.state_raw = ""

    @staticmethod
    def _held_tail(text: str, tag: str) -> int:
        """返回结尾处可能是半个标签的长度，需要扣住等下一块。"""
        for size in range(min(len(tag) - 1, len(text)), 0, -1):
            if text.endswith(tag[:size]):
                return size
        return 0

    def feed(self, piece: str) -> str:
        self.buffer += piece
        out: list[str] = []

        while True:
            if not self.in_state:
                index = self.buffer.find(STATE_OPEN)
                if index == -1:
                    hold = self._held_tail(self.buffer, STATE_OPEN)
                    if hold:
                        out.append(self.buffer[:-hold])
                        self.buffer = self.buffer[-hold:]
                    else:
                        out.append(self.buffer)
                        self.buffer = ""
                    break
                out.append(self.buffer[:index])
                self.buffer = self.buffer[index + len(STATE_OPEN) :]
                self.in_state = True
            else:
                index = self.buffer.find(STATE_CLOSE)
                if index == -1:
                    hold = self._held_tail(self.buffer, STATE_CLOSE)
                    if hold:
                        self.state_raw += self.buffer[:-hold]
                        self.buffer = self.buffer[-hold:]
                    else:
                        self.state_raw += self.buffer
                        self.buffer = ""
                    break
                self.state_raw += self.buffer[:index]
                self.buffer = self.buffer[index + len(STATE_CLOSE) :]
                self.in_state = False

        return "".join(out)

    def flush(self) -> str:
        tail = ""
        if not self.in_state:
            tail = self.buffer
        self.buffer = ""
        return tail


def parse_updates(raw: str) -> dict[str, str]:
    updates: dict[str, str] = {}
    if not raw.strip():
        return updates

    for part in re.split(r"[;\n]+", raw):
        part = part.strip()
        if not part:
            continue
        for sep in ("=", "：", ":"):
            if sep in part:
                key, value = part.split(sep, 1)
                key, value = key.strip().strip("-·* "), value.strip()
                if key and value:
                    updates[key[:50]] = value[:200]
                break
    return updates


def load_variables(db, conversation_id: int) -> list[ConversationVariable]:
    return list(
        db.scalars(
            select(ConversationVariable)
            .where(ConversationVariable.conversation_id == conversation_id)
            .order_by(ConversationVariable.id)
        ).all()
    )


def variables_block(rows: list[ConversationVariable]) -> str:
    if not rows:
        return ""
    lines = [f"- {row.key}：{row.value}" for row in rows]
    return (
        "【当前状态】\n"
        + "\n".join(lines)
        + "\n（每次回复的最后都要单独输出一行，列出全部状态的最新值，格式："
        f"{STATE_OPEN}键=值;键=值{STATE_CLOSE}。没有变化就照抄当前值。"
        "这一行不对用户展示，也不要提及它）"
    )


def apply_updates(db, conversation_id: int, updates: dict[str, str]) -> None:
    if not updates:
        return

    rows = {
        row.key: row for row in load_variables(db, conversation_id)
    }
    for key, value in updates.items():
        existing = rows.get(key)
        if existing:
            existing.value = value
        elif len(rows) < MAX_VARIABLES:
            row = ConversationVariable(
                conversation_id=conversation_id, key=key, value=value
            )
            db.add(row)
            rows[key] = row
    db.commit()
