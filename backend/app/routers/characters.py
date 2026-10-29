"""角色、角色卡导入导出、世界书条目。"""

import json
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from ..auth import current_user
from ..cards import parse_card, parse_png_card, to_v2
from ..config import AVATARS_DIR
from ..db import SessionLocal
from ..models import Character, WorldEntry
from ..schemas import CharacterUpdate, FavoriteIn, WorldEntryIn, WorldEntryUpdate
from ..serializers import character_payload, world_payload
from ..world import LOGIC_ANY, LOGIC_CHOICES

router = APIRouter(
    prefix="/api", tags=["characters"], dependencies=[Depends(current_user)]
)


@router.get("/characters")
def list_characters():
    with SessionLocal() as db:
        rows = db.scalars(
            select(Character).order_by(
                Character.favorite.desc(), Character.sort_order, Character.id
            )
        ).all()
        return [character_payload(row) for row in rows]


@router.patch("/characters/{character_id}")
def update_character(character_id: int, payload: CharacterUpdate):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
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
        return character_payload(character)


@router.post("/characters/{character_id}/favorite")
def set_favorite(character_id: int, payload: FavoriteIn):
    with SessionLocal() as db:
        character = db.get(Character, character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")
        character.favorite = payload.favorite
        db.commit()
        db.refresh(character)
        return character_payload(character)


def _create_character(db, fields: dict, avatar_url: str = "") -> Character:
    if not fields["name"] or not fields["greeting"]:
        raise HTTPException(status_code=400, detail="角色卡缺少角色名或开场白")

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
        default_model="deepseek-chat",
        avatar_url=avatar_url or fields["avatar_url"],
        system_prompt=fields.get("system_prompt", ""),
        tags=json.dumps(fields["tags"], ensure_ascii=False),
        alternates=json.dumps(fields["alternates"], ensure_ascii=False),
    )
    db.add(character)
    return character


@router.post("/characters/import")
def import_character(payload: dict):
    try:
        fields = parse_card(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with SessionLocal() as db:
        character = _create_character(db, fields)
        db.commit()
        db.refresh(character)
        return character_payload(character)


@router.post("/characters/import-png")
async def import_character_png(request: Request):
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
        character = _create_character(db, fields, f"/media/avatars/{filename}")
        db.commit()
        db.refresh(character)
        return character_payload(character)


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
