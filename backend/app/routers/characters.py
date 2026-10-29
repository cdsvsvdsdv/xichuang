"""角色、角色卡导入导出、世界书条目。"""

import json
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from ..auth import current_user
from ..cards import parse_card, parse_png_card, to_v2
from ..cleanup import purge_character
from ..config import AVATARS_DIR
from ..db import SessionLocal
from ..providers import complete_chat
from ..models import (
    Character,
    CharacterFavorite,
    CharacterRegex,
    Conversation,
    User,
    WorldEntry,
)
from ..schemas import (
    CardGenerateIn,
    CharacterCreate,
    CharacterUpdate,
    FavoriteIn,
    RegexIn,
    RegexUpdate,
    WorldEntryIn,
    WorldEntryUpdate,
)
from ..serializers import character_payload, world_payload
from ..world import LOGIC_ANY, LOGIC_CHOICES

router = APIRouter(
    prefix="/api", tags=["characters"], dependencies=[Depends(current_user)]
)


def _favorite_ids(db, user: User) -> set[int]:
    return set(
        db.scalars(
            select(CharacterFavorite.character_id).where(
                CharacterFavorite.user_id == user.id
            )
        ).all()
    )


def _can_manage(character: Character, user: User) -> bool:
    return bool(user.is_admin) or (
        character.created_by is not None and character.created_by == user.id
    )


def _require_manage(character: Character, user: User) -> None:
    if not _can_manage(character, user):
        raise HTTPException(
            status_code=403, detail="只有创建者或管理员可以修改这个角色"
        )


@router.get("/characters")
def list_characters(user: User = Depends(current_user)):
    with SessionLocal() as db:
        rows = db.scalars(
            select(Character).order_by(Character.sort_order, Character.id)
        ).all()
        favorites = _favorite_ids(db, user)
        payloads = [character_payload(row, row.id in favorites) for row in rows]

    payloads.sort(key=lambda item: not item["favorite"])
    return payloads


@router.post("/characters")
def create_character(payload: CharacterCreate, user: User = Depends(current_user)):
    fields = {
        "name": payload.name.strip()[:50],
        "tagline": payload.tagline.strip()[:120],
        "persona": payload.persona.strip()[:6000],
        "greeting": payload.greeting.strip()[:6000],
        "tags": [item.strip() for item in payload.tags if item.strip()][:8],
        "alternates": [item.strip() for item in payload.alternates if item.strip()][
            :10
        ],
        "avatar_url": payload.avatar_url.strip()[:500],
        "system_prompt": payload.system_prompt.strip()[:3000],
        "default_model": payload.default_model.strip()[:50] or "deepseek-chat",
    }
    if not fields["name"] or not fields["greeting"]:
        raise HTTPException(status_code=400, detail="角色名和开场白不能为空")

    with SessionLocal() as db:
        character = _create_character(db, fields, created_by=user.id)
        db.commit()
        db.refresh(character)
        return character_payload(character, False)


@router.patch("/characters/{character_id}")
def update_character(
    character_id: int,
    payload: CharacterUpdate,
    user: User = Depends(current_user),
):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        _require_manage(character, user)

        if payload.name is not None:
            name = payload.name.strip()[:50]
            if not name:
                raise HTTPException(status_code=400, detail="角色名不能为空")
            if name != character.name and db.scalar(
                select(Character).where(
                    Character.name == name, Character.id != character.id
                )
            ):
                raise HTTPException(status_code=400, detail="角色名已被占用")
            character.name = name
        if payload.persona is not None:
            character.persona = payload.persona.strip()[:6000]
        if payload.greeting is not None:
            greeting = payload.greeting.strip()
            if not greeting:
                raise HTTPException(status_code=400, detail="开场白不能为空")
            character.greeting = greeting[:6000]
        if payload.alternates is not None:
            character.alternates = json.dumps(
                [item.strip() for item in payload.alternates if item.strip()][:10],
                ensure_ascii=False,
            )
        if payload.default_model is not None:
            character.default_model = (
                payload.default_model.strip()[:50] or character.default_model
            )
        if payload.avatar_url is not None:
            character.avatar_url = payload.avatar_url.strip()[:500]
        if payload.tagline is not None:
            character.tagline = payload.tagline.strip()[:120]
        if payload.tags is not None:
            tags = [t.strip() for t in payload.tags if t.strip()][:8]
            character.tags = json.dumps(tags, ensure_ascii=False)
        if payload.system_prompt is not None:
            character.system_prompt = payload.system_prompt.strip()[:3000]

        db.commit()
        db.refresh(character)
        return character_payload(
            character, character.id in _favorite_ids(db, user)
        )


@router.delete("/characters/{character_id}")
def delete_character(character_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        _require_manage(character, user)
        purge_character(db, character)
        db.commit()
        return {"ok": True}


@router.post("/characters/{character_id}/favorite")
def set_favorite(
    character_id: int, payload: FavoriteIn, user: User = Depends(current_user)
):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        existing = db.get(CharacterFavorite, (user.id, character_id))
        if payload.favorite and not existing:
            db.add(CharacterFavorite(user_id=user.id, character_id=character_id))
        elif not payload.favorite and existing:
            db.delete(existing)

        db.commit()
        return character_payload(character, payload.favorite)


def _create_character(
    db, fields: dict, avatar_url: str = "", created_by: int | None = None
) -> Character:
    if not fields["name"]:
        raise HTTPException(status_code=400, detail="角色卡缺少角色名")

    base = re.sub(r"（\d+）$", "", fields["name"]) or fields["name"]
    name = base
    suffix = 2
    while db.scalar(select(Character).where(Character.name == name)):
        tail = f"（{suffix}）"
        name = base[: 50 - len(tail)] + tail
        suffix += 1

    character = Character(
        name=name,
        tagline=fields["tagline"],
        persona=fields["persona"],
        greeting=fields["greeting"],
        default_model=fields.get("default_model") or "deepseek-chat",
        avatar_url=avatar_url or fields["avatar_url"],
        system_prompt=fields.get("system_prompt", ""),
        html_greeting=fields.get("html_greeting", ""),
        card_rules=fields.get("card_rules", ""),
        tags=json.dumps(fields["tags"], ensure_ascii=False),
        alternates=json.dumps(fields["alternates"], ensure_ascii=False),
        created_by=created_by,
    )
    db.add(character)
    return character


def _add_card_regex(db, character_id: int, scripts: list[dict]) -> None:
    for item in scripts:
        pattern = (item.get("pattern") or "").strip()
        if not pattern:
            continue
        try:
            re.compile(pattern)
        except re.error:
            continue
        db.add(
            CharacterRegex(
                character_id=character_id,
                name=item.get("name", "")[:80],
                pattern=pattern[:2000],
                replacement=(item.get("replacement") or "")[:20000],
                scope=item.get("scope") or "assistant",
                enabled=True,
            )
        )


def _add_world_entries(db, character_id: int, entries: list[dict]) -> None:
    for item in entries:
        db.add(
            WorldEntry(
                character_id=character_id,
                keywords=json.dumps(item["keywords"], ensure_ascii=False),
                keywords_secondary=json.dumps(
                    item["keywords_secondary"], ensure_ascii=False
                ),
                logic=item["logic"],
                depth=item["depth"],
                sticky=item["sticky"],
                content=item["content"],
                constant=item["constant"],
                enabled=item["enabled"],
            )
        )


@router.post("/characters/import")
def import_character(payload: dict, user: User = Depends(current_user)):
    try:
        fields = parse_card(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with SessionLocal() as db:
        character = _create_character(db, fields, created_by=user.id)
        db.flush()
        _add_world_entries(db, character.id, fields.get("world_entries", []))
        _add_card_regex(db, character.id, fields.get("regex_scripts", []))
        db.commit()
        db.refresh(character)
        result = character_payload(character, False)
        result["import_meta"] = fields.get("import_meta")
        return result


@router.post("/characters/import-png")
async def import_character_png(request: Request, user: User = Depends(current_user)):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="没有收到图片内容")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片太大，请控制在 8MB 以内")

    try:
        fields = parse_png_card(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"{uuid4().hex}.png"
    (AVATARS_DIR / filename).write_bytes(data)

    with SessionLocal() as db:
        character = _create_character(
            db, fields, f"/media/avatars/{filename}", created_by=user.id
        )
        db.flush()
        _add_world_entries(db, character.id, fields.get("world_entries", []))
        _add_card_regex(db, character.id, fields.get("regex_scripts", []))
        db.commit()
        db.refresh(character)
        result = character_payload(character, False)
        result["import_meta"] = fields.get("import_meta")
        return result


@router.get("/characters/{character_id}/export")
def export_character(character_id: int):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        payload = character_payload(character)

    return to_v2(
        payload["name"],
        payload["persona"],
        payload["greeting"],
        payload["alternates"],
        payload["tags"],
        payload["tagline"],
        payload["avatar_url"],
        payload["system_prompt"],
    )


def _adapt_source(character: Character, entries: list[WorldEntry]) -> str:
    parts = [f"角色名：{character.name}"]
    if character.tagline:
        parts.append(f"简介：{character.tagline}")
    if character.persona.strip():
        parts.append(f"原人设：\n{character.persona[:1500]}")
    if character.greeting.strip():
        parts.append(f"原开场白：\n{character.greeting[:1200]}")

    def score(entry: WorldEntry) -> int:
        comment = entry.comment if hasattr(entry, "comment") else ""
        text = (comment or "") + " " + (entry.keywords or "")
        value = 0
        for word in ("人设", "序章", "大纲", "铁则", "主角", "夏恋", "私奔"):
            if word in text:
                value += 2
        if entry.constant:
            value += 1
        return value

    candidates = sorted(entries, key=lambda item: (-score(item), item.id))
    budget = 6500
    picked = 0
    for entry in candidates:
        keys = json.loads(entry.keywords or "[]")
        if not keys:
            continue
        content = (entry.content or "").strip()
        if not content:
            continue
        snippet = content[:900]
        user_entry = bool(
            {"我", "<user>", "user", "主角"} & set(keys)
        ) or "用户人设" in content[:80] or "主角：" in content[:40]
        label = "用户人设（用户扮演，你不要扮演）" if user_entry else "设定"
        parts.append(f"【{label}：{'/'.join(keys[:3])}】\n{snippet}")
        budget -= len(snippet)
        picked += 1
        if budget <= 0 or picked >= 12:
            break

    return "\n\n".join(parts)


@router.post("/characters/{character_id}/adapt")
async def adapt_character(character_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        _require_manage(character, user)
        entries = list(
            db.scalars(
                select(WorldEntry).where(WorldEntry.character_id == character_id)
            ).all()
        )
        source = _adapt_source(character, entries)
        name = character.name

    system = (
        "你是角色卡适配器。用户会给你一张酒馆角色卡的信息，请把它改写成"
        "适合纯文本 AI 角色聊天使用的设定。要求：\n"
        "0. 你要扮演的是角色卡里的主要角色（{{char}}），用户扮演主角/用户自己。"
        "如果卡里写的是用户视角的故事，绝对不要把用户当成你要扮演的角色；"
        "标注为「用户人设」的内容只作为你的对话对象参考。"
        "如果卡里没有明确指定你扮演谁，就选择与用户关系最密切、戏份最多的女性角色来扮演。\n"
        "1. 全部使用简体中文；\n"
        "2. 不输出 HTML、Markdown、代码块、选项按钮、BGM、变量标签或任何界面控制符；\n"
        "3. 保留原作的核心世界观、人物关系、性格与说话风格，删掉只服务于界面和游戏机制的内容；\n"
        "4. persona 用第二人称「你是……」写，800-1500 字，包含身份、外貌、性格、说话方式、"
        "与用户的关系和当前处境；\n"
        "5. greeting 写 300-600 字的小说式开场场景，直接渲染画面和氛围，不要提问、不要解释设定；\n"
        "6. tagline 是不超过 20 字的简介；\n"
        "7. 只输出 JSON，格式为 "
        '{"tagline": "...", "persona": "...", "greeting": "..."}'
    )

    try:
        raw = await complete_chat(
            "deepseek-chat",
            [
                {"role": "system", "content": system},
                {"role": "user", "content": source},
            ],
            max_tokens=2600,
            temperature=0.65,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI 适配失败：{exc}") from exc

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise HTTPException(status_code=502, detail="AI 返回格式不正确，请重试")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="AI 返回内容无法解析，请重试") from exc

    persona = str(data.get("persona") or "").strip()[:6000]
    greeting = str(data.get("greeting") or "").strip()[:6000]
    tagline = str(data.get("tagline") or "").strip()[:120]
    if not persona or not greeting:
        raise HTTPException(status_code=502, detail="AI 没有生成完整的人设或开场白，请重试")

    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        character.persona = persona
        character.greeting = greeting
        if tagline:
            character.tagline = tagline
        db.commit()
        db.refresh(character)
        return character_payload(character, character.id in _favorite_ids(db, user))


def _regex_payload(rule: CharacterRegex) -> dict:
    return {
        "id": rule.id,
        "name": rule.name or "",
        "pattern": rule.pattern,
        "replacement": rule.replacement or "",
        "scope": rule.scope or "assistant",
        "enabled": bool(rule.enabled),
    }


def _check_pattern(pattern: str) -> str:
    pattern = (pattern or "").strip()
    if not pattern:
        raise HTTPException(status_code=400, detail="正则表达式不能为空")
    if len(pattern) > 500:
        raise HTTPException(status_code=400, detail="正则表达式太长（上限 500 字符）")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise HTTPException(status_code=400, detail=f"正则语法错误：{exc}") from exc
    return pattern


@router.get("/characters/{character_id}/regex")
def list_regex(character_id: int):
    with SessionLocal() as db:
        if not db.get(Character, character_id):
            raise HTTPException(status_code=404, detail="角色不存在")
        rows = db.scalars(
            select(CharacterRegex)
            .where(CharacterRegex.character_id == character_id)
            .order_by(CharacterRegex.id)
        ).all()
        return [_regex_payload(row) for row in rows]


@router.post("/characters/{character_id}/regex")
def create_regex(
    character_id: int, payload: RegexIn, user: User = Depends(current_user)
):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        _require_manage(character, user)
        scope = payload.scope if payload.scope in ("user", "assistant", "both") else "assistant"
        rule = CharacterRegex(
            character_id=character_id,
            name=payload.name.strip()[:80],
            pattern=_check_pattern(payload.pattern),
            replacement=payload.replacement[:2000],
            scope=scope,
            enabled=payload.enabled,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return _regex_payload(rule)


@router.patch("/regex/{rule_id}")
def update_regex(
    rule_id: int, payload: RegexUpdate, user: User = Depends(current_user)
):
    with SessionLocal() as db:
        rule = db.get(CharacterRegex, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        character = db.get(Character, rule.character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        _require_manage(character, user)

        if payload.name is not None:
            rule.name = payload.name.strip()[:80]
        if payload.pattern is not None:
            rule.pattern = _check_pattern(payload.pattern)
        if payload.replacement is not None:
            rule.replacement = payload.replacement[:2000]
        if payload.scope is not None:
            rule.scope = (
                payload.scope
                if payload.scope in ("user", "assistant", "both")
                else rule.scope
            )
        if payload.enabled is not None:
            rule.enabled = payload.enabled
        db.commit()
        db.refresh(rule)
        return _regex_payload(rule)


@router.delete("/regex/{rule_id}")
def delete_regex(rule_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        rule = db.get(CharacterRegex, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
        character = db.get(Character, rule.character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        _require_manage(character, user)
        db.delete(rule)
        db.commit()
        return {"ok": True}


@router.post("/cards/generate")
async def card_generate(
    payload: CardGenerateIn, request: Request, user: User = Depends(current_user)
):
    """前端卡脚本调用：按卡片提示生成一段文本，不写入聊天记录。"""
    prompt = (payload.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="生成提示不能为空")
    if len(prompt) > 20000:
        raise HTTPException(status_code=400, detail="生成提示过长")

    character = None
    with SessionLocal() as db:
        if payload.conversation_id:
            conversation = db.get(Conversation, payload.conversation_id)
            if not conversation or conversation.user_id != user.id:
                raise HTTPException(status_code=404, detail="会话不存在")
            character = db.get(Character, conversation.character_id)
        elif payload.character_id:
            character = db.get(Character, payload.character_id)
            if not character:
                raise HTTPException(status_code=404, detail="角色不存在")

    name = character.name if character else "角色"
    system = (
        f"你正在协助完成一次角色扮演生成任务（角色：{name}）。"
        "严格按用户给出的模板与要求输出，不要解释、不要加开场白或结束语，"
        "不要输出 Markdown 代码块以外的多余内容。"
    )

    try:
        text = await complete_chat(
            "deepseek-chat",
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8000,
            temperature=0.8,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"生成失败：{exc}") from exc

    text = re.sub(
        r"<thinking>.*?</thinking>", "", text, flags=re.I | re.S
    ).strip()
    return {"text": text}


@router.get("/characters/{character_id}/world")
def list_world(character_id: int):
    with SessionLocal() as db:
        rows = db.scalars(
            select(WorldEntry)
            .where(WorldEntry.character_id == character_id)
            .order_by(WorldEntry.id)
        ).all()
        return [world_payload(row) for row in rows]


def _create_world_entry(db, character_id: int | None, payload: WorldEntryIn):
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="设定内容不能为空")
    keywords = [item.strip() for item in payload.keywords if item.strip()][:10]
    if not keywords and not payload.constant:
        raise HTTPException(status_code=400, detail="普通条目至少需要一个关键词")

    entry = WorldEntry(
        character_id=character_id,
        keywords=json.dumps(keywords, ensure_ascii=False),
        keywords_secondary=json.dumps(
            [item.strip() for item in payload.keywords_secondary if item.strip()][:10],
            ensure_ascii=False,
        ),
        logic=payload.logic if payload.logic in LOGIC_CHOICES else LOGIC_ANY,
        depth=payload.depth if payload.depth is not None and payload.depth >= 0 else None,
        sticky=max(0, payload.sticky),
        content=content[:2000],
        constant=payload.constant,
        enabled=payload.enabled,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return world_payload(entry)


@router.post("/characters/{character_id}/world")
def create_world(character_id: int, payload: WorldEntryIn):
    with SessionLocal() as db:
        if not db.get(Character, character_id):
            raise HTTPException(status_code=404, detail="角色不存在")
        return _create_world_entry(db, character_id, payload)


@router.get("/world/global")
def list_global_world():
    with SessionLocal() as db:
        rows = db.scalars(
            select(WorldEntry)
            .where(WorldEntry.character_id.is_(None))
            .order_by(WorldEntry.id)
        ).all()
        return [world_payload(row) for row in rows]


@router.post("/world/global")
def create_global_world(payload: WorldEntryIn):
    with SessionLocal() as db:
        return _create_world_entry(db, None, payload)


@router.patch("/world/{entry_id}")
def update_world(entry_id: int, payload: WorldEntryUpdate):
    with SessionLocal() as db:
        entry = db.get(WorldEntry, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="条目不存在")
        if payload.keywords is not None:
            keywords = [item.strip() for item in payload.keywords if item.strip()][:10]
            entry.keywords = json.dumps(keywords, ensure_ascii=False)
        if payload.keywords_secondary is not None:
            secondary = [
                item.strip() for item in payload.keywords_secondary if item.strip()
            ][:10]
            entry.keywords_secondary = json.dumps(secondary, ensure_ascii=False)
        if payload.logic is not None:
            entry.logic = payload.logic if payload.logic in LOGIC_CHOICES else LOGIC_ANY
        if payload.depth is not None:
            # -1 表示清除深度，改回注入系统提示词
            entry.depth = payload.depth if payload.depth >= 0 else None
        if payload.sticky is not None:
            entry.sticky = max(0, payload.sticky)
        if payload.content is not None:
            content = payload.content.strip()
            if not content:
                raise HTTPException(status_code=400, detail="设定内容不能为空")
            entry.content = content[:2000]
        if payload.constant is not None:
            entry.constant = payload.constant
        if payload.enabled is not None:
            entry.enabled = payload.enabled
        db.commit()
        db.refresh(entry)
        return world_payload(entry)


@router.delete("/world/{entry_id}")
def delete_world(entry_id: int):
    with SessionLocal() as db:
        entry = db.get(WorldEntry, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="条目不存在")
        db.delete(entry)
        db.commit()
        return {"ok": True}
