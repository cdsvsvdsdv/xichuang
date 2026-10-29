"""AI 生图。"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from ..auth import current_user, owned_conversation
from ..config import IMAGES_DIR, SILICONFLOW_API_KEY, ZHIPU_API_KEY
from ..db import SessionLocal
from ..deps import check_rate
from ..images import (
    active_provider,
    build_image_prompt,
    clean_prompt,
    generate_image_bytes,
    localize_prompt,
    save_image,
)
from ..models import Conversation, GeneratedImage, User
from ..schemas import ImageGenerateIn
from ..serializers import image_payload

router = APIRouter(prefix="/api", tags=["media"])


@router.get("/images/status")
def image_status():
    provider = active_provider()
    configured = {
        "zhipu": bool(ZHIPU_API_KEY),
        "siliconflow": bool(SILICONFLOW_API_KEY),
        "pollinations": True,
    }.get(provider, False)
    return {"provider": provider, "configured": configured}


@router.post("/images/generate")
async def generate_image(
    payload: ImageGenerateIn, request: Request, user: User = Depends(current_user)
):
    check_rate(request, "image", 5, 300)
    with SessionLocal() as db:
        owned_conversation(db, payload.conversation_id, user)

    prompt = (payload.prompt or "").strip()
    try:
        if not prompt:
            prompt = await build_image_prompt(payload.conversation_id)
        prompt = clean_prompt(prompt)
        prompt = await localize_prompt(prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        data, provider = await generate_image_bytes(prompt, payload.size)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"生图失败：{exc}") from exc

    image = save_image(payload.conversation_id, prompt, data, provider)
    return image_payload(image)


@router.get("/conversations/{conversation_id}/images")
def list_images(conversation_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        owned_conversation(db, conversation_id, user)
        rows = db.scalars(
            select(GeneratedImage)
            .where(GeneratedImage.conversation_id == conversation_id)
            .order_by(GeneratedImage.id.desc())
        ).all()
        return [image_payload(row) for row in rows]


@router.delete("/images/{image_id}")
def delete_image(image_id: int, user: User = Depends(current_user)):
    with SessionLocal() as db:
        image = db.get(GeneratedImage, image_id)
        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")
        owned_conversation(db, image.conversation_id, user)
        file_path = IMAGES_DIR / image.filename
        db.delete(image)
        db.commit()

    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass
    return {"ok": True}
