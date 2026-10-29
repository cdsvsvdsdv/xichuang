"""角色卡（Character Card V2/V3、V1 扁平格式、Character.AI 导出）的读写。"""

import base64
import json
import re
import zlib

MAX_PERSONA = 4000
MAX_WORLD_ENTRIES = 120
MAX_CONSTANT_CONTENT = 800

FRONTEND_TAGS = (
    "私奔开局|开局|事件触发|BGM|MP4|options|gametxt|abstract|"
    "summer_lover|Ending_thank|StatusPlaceHolderImpl|button|div|span"
)

LOGIC_MAP = {0: "and_any", 1: "not_all", 2: "not_any", 3: "and_all"}


BLOCK_TAGS = "私奔开局|开局|事件触发|BGM|MP4|options"


def _clean_markup(text: str) -> str:
    """去掉酒馆前端卡的控制标记，保留正文与 <user>/<char> 占位符。"""
    if not text:
        return ""
    cleaned = re.sub(
        rf"<(?:{BLOCK_TAGS})(?:\s[^>]*)?>.*?</(?:{BLOCK_TAGS})>",
        "",
        text,
        flags=re.I | re.S,
    )
    cleaned = re.sub(rf"</?(?:{FRONTEND_TAGS})(?:\s[^>]*)?>", "", cleaned, flags=re.I)
    cleaned = re.sub(r"```[a-zA-Z]*\s*$", "", cleaned.strip(), flags=re.M)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


UI_RULE_PATTERN = re.compile(
    r"</?(?:options|BGM|MP4|gametxt|infoblock|StatusPlaceHolderImpl)\b"
    r"|```|<html|美化|状态栏|输出格式|前端卡|代码块|思维链|正则|"
    r"手机消息|朋友圈|排版|CSS|HTML",
    re.I,
)


def _is_ui_rule(content: str) -> bool:
    return bool(UI_RULE_PATTERN.search(content[:1500]))


def _parse_world_entries(data: dict) -> tuple[list[dict], int, int]:
    book = data.get("character_book") or {}
    raw_entries = book.get("entries") if isinstance(book, dict) else None
    if not isinstance(raw_entries, list):
        return [], 0, 0

    converted: list[dict] = []
    skipped = 0
    for entry in raw_entries:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        if entry.get("enabled") is False:
            skipped += 1
            continue

        content = str(entry.get("content") or "").strip()
        if not content:
            skipped += 1
            continue

        if _is_ui_rule(content):
            skipped += 1
            continue

        keys = [str(k).strip() for k in (entry.get("keys") or []) if str(k).strip()]
        secondary = [
            str(k).strip() for k in (entry.get("secondary_keys") or []) if str(k).strip()
        ]
        constant = bool(entry.get("constant"))

        if not keys:
            # 无关键词条目只保留短的常驻条目，避免大段规则把上下文吃光
            if not constant or len(content) > MAX_CONSTANT_CONTENT:
                skipped += 1
                continue

        extensions = entry.get("extensions") or {}
        depth = extensions.get("depth")
        if not isinstance(depth, int) or depth < 0:
            depth = None
        logic = LOGIC_MAP.get(extensions.get("selectiveLogic"), "and_any")

        converted.append(
            {
                "keywords": keys[:10],
                "keywords_secondary": secondary[:10],
                "logic": logic,
                "depth": depth,
                "sticky": 0,
                "content": content[:2000],
                "constant": constant,
                "enabled": True,
            }
        )

    converted = converted[:MAX_WORLD_ENTRIES]
    return converted, len(converted), skipped

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
    raw_greeting = _text(
        data.get("first_mes"), data.get("char_greeting"), data.get("greeting")
    )

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

    greeting = _clean_markup(raw_greeting)
    alternates = [
        cleaned
        for cleaned in (
            _clean_markup(item) for item in _str_list(data.get("alternate_greetings"))
        )
        if cleaned and cleaned != greeting
    ]

    avatar = _text(data.get("avatar"))
    if not avatar.startswith(("http://", "https://")) or len(avatar) > 500:
        avatar = ""

    notes = _text(data.get("creator_notes"), data.get("tagline"))
    tagline = notes.splitlines()[0][:120] if notes else ""

    world_entries, world_count, world_skipped = _parse_world_entries(data)
    regex_count = len(((data.get("extensions") or {}).get("regex_scripts")) or [])
    has_markup = raw_greeting != greeting
    frontend = bool(regex_count or has_markup or world_count > 12)

    return {
        "name": name[:50],
        "greeting": greeting,
        "persona": persona,
        "alternates": alternates[:10],
        "tags": _str_list(data.get("tags"))[:8],
        "avatar_url": avatar,
        "tagline": tagline,
        "system_prompt": _text(data.get("system_prompt"))[:3000],
        "world_entries": world_entries,
        "import_meta": {
            "world_entries": world_count,
            "world_skipped": world_skipped,
            "regex_scripts": regex_count,
            "frontend_card": frontend,
            "greeting_cleaned": bool(has_markup),
            "needs_adaptation": not persona.strip(),
        },
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
