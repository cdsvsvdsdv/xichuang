"""角色级正则改写：对用户输入或 AI 回复做查找替换。"""

import re

from sqlalchemy import select

from .models import CharacterRegex

MAX_PATTERN = 500
MAX_TEXT = 20000


def apply_rules(rules: list[CharacterRegex], text: str) -> str:
    if not rules or not text:
        return text
    result = text[:MAX_TEXT]
    for rule in rules:
        if not rule.enabled or not rule.pattern:
            continue
        try:
            result = re.sub(rule.pattern, rule.replacement or "", result)
        except re.error:
            continue
    return result


def load_rules(db, character_id: int, scope: str) -> list[CharacterRegex]:
    """scope: user / assistant。both 规则两种都会命中。"""
    return list(
        db.scalars(
            select(CharacterRegex)
            .where(
                CharacterRegex.character_id == character_id,
                CharacterRegex.enabled.is_(True),
                CharacterRegex.scope.in_((scope, "both")),
            )
            .order_by(CharacterRegex.id)
        ).all()
    )
