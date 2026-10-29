"""不引分词器的粗略 token 估算。

DeepSeek 官方口径：1 个中文字符 ≈ 0.6 token，1 个英文字符 ≈ 0.3 token。
这里各上调一点作为安全余量，宁可少带几条历史，也不要超上下文。
"""

CJK_RANGES = (
    (0x4E00, 0x9FFF),  # 基本汉字
    (0x3400, 0x4DBF),  # 扩展 A
    (0x3040, 0x30FF),  # 日文假名
    (0xAC00, 0xD7AF),  # 谚文
)


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return any(low <= code <= high for low, high in CJK_RANGES)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    return int(cjk * 0.7 + other * 0.35) + 1


def estimate_messages(messages: list[dict]) -> int:
    total = 0
    for item in messages:
        content = item.get("content")
        total += estimate_tokens(content if isinstance(content, str) else "")
        total += 4  # 每条消息的角色/分隔开销
    return total


def trim_history(messages: list[dict], budget: int) -> list[dict]:
    """从最新往回取，直到预算用尽；至少保留最后一条。"""
    if budget <= 0:
        return messages[-1:] if messages else []

    picked: list[dict] = []
    used = 0
    for item in reversed(messages):
        content = item.get("content")
        cost = estimate_tokens(content if isinstance(content, str) else "") + 4
        if picked and used + cost > budget:
            break
        picked.append(item)
        used += cost
    picked.reverse()
    return picked
