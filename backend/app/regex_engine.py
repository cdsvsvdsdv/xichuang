"""角色级正则改写：对用户输入或 AI 回复做查找替换。"""

import re

from sqlalchemy import select

from .models import CharacterRegex

MAX_PATTERN = 500
MAX_TEXT = 20000


def _expand(template: str, match: re.Match) -> str:
    """展开 $1 / \\1 / $& 这类分组引用，其余反斜杠原样保留。"""
    out: list[str] = []
    index = 0
    length = len(template)
    groups = match.re.groups
    while index < length:
        char = template[index]
        nxt = template[index + 1 : index + 2]

        if char == "$" and nxt == "$":
            out.append("$")
            index += 2
            continue
        if char == "$" and nxt == "&":
            out.append(match.group(0))
            index += 2
            continue
        if char in ("$", "\\") and nxt.isdigit():
            end = index + 1
            while end < length and template[end].isdigit():
                end += 1
            number = int(template[index + 1 : end])
            if 1 <= number <= groups:
                out.append(match.group(number) or "")
            index = end
            continue

        out.append(char)
        index += 1
    return "".join(out)


def apply_rules(rules: list[CharacterRegex], text: str) -> str:
    if not rules or not text:
        return text
    result = text[:MAX_TEXT]
    for rule in rules:
        if not rule.enabled or not rule.pattern:
            continue
        try:
            updated = re.sub(
                rule.pattern,
                lambda match: _expand(rule.replacement or "", match),
                result,
            )
        except re.error:
            continue
        # 防止“隐藏楼层”之类的规则把整段内容清空
        if not updated.strip() and result.strip():
            continue
        result = updated
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
