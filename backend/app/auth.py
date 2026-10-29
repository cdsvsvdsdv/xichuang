"""账号与凭证：PBKDF2 存密码，HMAC 签名 token，不引第三方依赖。"""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, Request
from sqlalchemy import select

from .config import DATA_DIR
from .db import SessionLocal
from .models import Conversation, Message, Profile, User

TOKEN_TTL = 60 * 60 * 24 * 30  # 30 天
PBKDF2_ROUNDS = 200_000
SECRET_FILE = DATA_DIR / "auth_secret"


def _secret() -> bytes:
    if os.getenv("AUTH_SECRET"):
        return os.environ["AUTH_SECRET"].encode()

    if SECRET_FILE.exists():
        return SECRET_FILE.read_bytes()

    raw = os.urandom(32)
    SECRET_FILE.write_bytes(raw)
    return raw


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed.hex(), digest_hex)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(user_id: int) -> str:
    payload = json.dumps(
        {"uid": user_id, "exp": int(time.time()) + TOKEN_TTL}
    ).encode()
    body = _b64(payload)
    signature = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_token(token: str) -> int | None:
    body, _, signature = token.partition(".")
    if not body or not signature:
        return None
    expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        data = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(data.get("exp", 0)) < time.time():
        return None
    return int(data.get("uid", 0)) or None


def current_user(request: Request) -> User:
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")

    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="账号不存在")
        db.expunge(user)
        return user


def owned_conversation(db, conversation_id: int, user: User) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


def owned_message(db, message_id: int, user: User) -> Message:
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    conversation = db.get(Conversation, message.conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="消息不存在")
    return message


def claim_orphans(db, user_id: int) -> None:
    """首个用户接管所有没有归属的老数据。"""
    for row in db.scalars(
        select(Conversation).where(Conversation.user_id.is_(None))
    ).all():
        row.user_id = user_id
    for row in db.scalars(select(Profile)).all():
        if row.user_id is None:
            row.user_id = user_id
    db.commit()
