"""健康检查、模型列表、用户人设。"""

from fastapi import APIRouter, Depends

from ..auth import current_user
from ..config import DEEPSEEK_API_KEY
from ..db import SessionLocal
from ..models import User
from ..providers import MODELS
from ..schemas import ProfileUpdate
from ..serializers import profile_payload
from ..services import get_profile

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health")
def health():
    return {"ok": True, "deepseek_configured": bool(DEEPSEEK_API_KEY)}


@router.get("/models")
def list_models():
    return MODELS


@router.get("/profile")
def read_profile(user: User = Depends(current_user)):
    with SessionLocal() as db:
        return profile_payload(get_profile(db, user.id))


@router.put("/profile")
def update_profile(payload: ProfileUpdate, user: User = Depends(current_user)):
    with SessionLocal() as db:
        profile = get_profile(db, user.id)
        if payload.name is not None:
            profile.name = payload.name.strip()[:80]
        if payload.persona is not None:
            profile.persona = payload.persona.strip()[:2000]
        if payload.theme is not None:
            profile.theme = payload.theme.strip()[:30] or "default"
        if payload.background_url is not None:
            profile.background_url = payload.background_url.strip()[:500]
        db.commit()
        db.refresh(profile)
        return profile_payload(profile)
