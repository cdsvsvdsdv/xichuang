"""角色卡（Character Card V2/V3、V1 扁平格式、Character.AI 导出）的读写。"""

import base64
import json
import zlib

MAX_PERSONA = 4000

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_text_chunks(data: bytes) -> dict[str, str]:
    """读取 PNG 的 tEXt / zTXt / iTXt 文本块，返回 {关键字: 文本}。"""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("不是 PNG 文件")

    chunks: dict[str, str] = {}
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        pos += 12 + length

        if kind == b"tEXt":
            key, _, value = body.partition(b"\x00")
            chunks[key.decode("latin-1")] = value.decode("utf-8", "ignore")
        elif kind == b"zTXt":
            key, _, rest = body.partition(b"\x00")
            try:
                chunks[key.decode("latin-1")] = zlib.decompress(rest[1:]).decode(
                    "utf-8", "ignore"
                )
            except zlib.error:
                pass
        elif kind == b"iTXt":
            key, _, rest = body.partition(b"\x00")
            compressed = rest[:1] == b"\x01"
            rest = rest[2:]
            _, _, rest = rest.partition(b"\x00")  # language tag
            _, _, text = rest.partition(b"\x00")  # translated keyword
            if compressed:
                try:
                    text = zlib.decompress(text)
                except zlib.error:
                    continue
            chunks[key.decode("latin-1")] = text.decode("utf-8", "ignore")
        elif kind == b"IEND":
            break

    return chunks


def parse_png_card(data: bytes) -> dict:
    chunks = _png_text_chunks(data)
    raw = chunks.get("ccv3") or chunks.get("chara")
    if not raw:
        raise ValueError("这张 PNG 里没有角色数据（缺少 chara/ccv3 文本块）")

    payload = raw.strip()
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.b64decode(payload)
        card = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("PNG 里的角色数据无法解析") from exc

    return parse_card(card)


def _text(*values) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def parse_card(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("角色卡必须是 JSON 对象")

    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload

    name = _text(data.get("name"), data.get("char_name"))
    greeting = _text(data.get("first_mes"), data.get("char_greeting"), data.get("greeting"))

    parts = []
    description = _text(data.get("description"), data.get("char_persona"))
    if description:
        parts.append(description)
    personality = _text(data.get("personality"))
    if personality:
        parts.append("性格：" + personality)
    scenario = _text(data.get("scenario"), data.get("world_scenario"))
    if scenario:
        parts.append("场景：" + scenario)
    example = _text(data.get("mes_example"), data.get("example_dialogue"))
    if example:
        parts.append("示例对话：\n" + example)
    persona = "\n\n".join(parts)[:MAX_PERSONA]

    alternates = [
        item
        for item in _str_list(data.get("alternate_greetings"))
        if item and item != greeting
    ]

    avatar = _text(data.get("avatar"))
    if not avatar.startswith(("http://", "https://")) or len(avatar) > 500:
        avatar = ""

    notes = _text(data.get("creator_notes"), data.get("tagline"))
    tagline = notes.splitlines()[0][:120] if notes else ""

    return {
        "name": name[:50],
        "greeting": greeting,
        "persona": persona,
        "alternates": alternates[:10],
        "tags": _str_list(data.get("tags"))[:8],
        "avatar_url": avatar,
        "tagline": tagline,
        "system_prompt": _text(data.get("system_prompt"))[:3000],
    }


def to_v2(
    name: str,
    persona: str,
    greeting: str,
    alternates,
    tags,
    tagline,
    avatar,
    system_prompt: str = "",
) -> dict:
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": name,
            "description": persona,
            "personality": "",
            "scenario": "",
            "first_mes": greeting,
            "mes_example": "",
            "creator_notes": tagline,
            "system_prompt": system_prompt,
            "post_history_instructions": "",
            "alternate_greetings": list(alternates or []),
            "tags": list(tags or []),
            "creator": "",
            "character_version": "1.0",
            "extensions": {"avatar_url": avatar or ""},
        },
    }
