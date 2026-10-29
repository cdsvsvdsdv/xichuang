"""注册、登录、邀请码。"""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from ..auth import (
    claim_orphans,
    create_token,
    current_user,
    hash_password,
    verify_password,
)
from ..db import SessionLocal
from ..models import Invite, User
from ..schemas import LoginIn, RegisterIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_payload(user: User) -> dict:
    return {"id": user.id, "username": user.username, "is_admin": bool(user.is_admin)}


@router.get("/status")
def status():
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(User)) or 0
    return {"users": count, "first_run": count == 0}


@router.post("/register")
def register(payload: RegisterIn):
    username = payload.username.strip()
    password = payload.password
    if not 2 <= len(username) <= 20:
        raise HTTPException(status_code=400, detail="用户名需要 2-20 个字符")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username)):
            raise HTTPException(status_code=400, detail="用户名已被占用")

        is_first = (db.scalar(select(func.count()).select_from(User)) or 0) == 0

        invite = None
        if not is_first:
            code = payload.invite.strip()
            if not code:
                raise HTTPException(status_code=400, detail="请填写邀请码")
            invite = db.scalars(
                select(Invite).where(Invite.code == code)
            ).first()
            if not invite:
                raise HTTPException(status_code=400, detail="邀请码无效")
            if invite.used_by:
                raise HTTPException(status_code=400, detail="邀请码已被使用")

        user = User(
            username=username,
            password_hash=hash_password(password),
            is_admin=is_first,
        )
        db.add(user)
        db.flush()

        if invite:
            invite.used_by = user.id

        if is_first:
            claim_orphans(db, user.id)

        db.commit()
        db.refresh(user)
        return {"token": create_token(user.id), "user": _user_payload(user)}


@router.post("/login")
def login(payload: LoginIn):
    with SessionLocal() as db:
        user = db.scalars(
            select(User).where(User.username == payload.username.strip())
        ).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        db.expunge(user)
        return {"token": create_token(user.id), "user": _user_payload(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _user_payload(user)


@router.get("/invites")
def list_invites(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员能查看邀请码")
    with SessionLocal() as db:
        rows = db.scalars(select(Invite).order_by(Invite.id.desc())).all()
        return [
            {
                "id": row.id,
                "code": row.code,
                "used": bool(row.used_by),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


@router.post("/invites")
def create_invite(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员能生成邀请码")
    with SessionLocal() as db:
        row = Invite(code=secrets.token_urlsafe(8), created_by=user.id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "code": row.code,
            "used": False,
            "created_at": row.created_at.isoformat(),
        }
