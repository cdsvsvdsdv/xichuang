import random
import re
import urllib.parse
import uuid

import httpx
from sqlalchemy import select

from .config import (
    IMAGE_MODEL,
    IMAGE_PROVIDER,
    IMAGE_SIZE,
    IMAGES_DIR,
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    ZHIPU_API_KEY,
    ZHIPU_BASE_URL,
    ZHIPU_IMAGE_MODEL,
)
from .db import SessionLocal
from .models import Character, Conversation, GeneratedImage, Message
from .providers import complete_chat

BLOCKED_TERMS = [
    "nsfw",
    "nude",
    "naked",
    "explicit",
    "loli",
    "child porn",
    "萝莉",
    "裸",
    "色情",
    "幼女",
    "血腥",
]


CJK_PATTERN = re.compile(r"[一-鿿]")


async def localize_prompt(prompt: str) -> str:
    if not CJK_PATTERN.search(prompt):
        return prompt
    try:
        translated = await complete_chat(
            "deepseek-chat",
            [
                {
                    "role": "user",
                    "content": (
                        "把下面的中文画面描述改写成适合文生图模型的英文提示词，"
                        "保留场景、人物、光线、氛围与画风，不要出现文字或字幕，"
                        "只输出英文提示词：\n" + prompt
                    ),
                }
            ],
            max_tokens=180,
            temperature=0.3,
        )
        translated = translated.strip().strip('"')
        if translated and not CJK_PATTERN.search(translated):
            return translated[:800]
    except Exception:  # noqa: BLE001
        pass
    return prompt


def clean_prompt(prompt: str) -> str:
    lowered = prompt.lower()
    for term in BLOCKED_TERMS:
        if term in lowered:
            raise ValueError("提示词包含不允许的内容")
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("提示词不能为空")
    return cleaned[:800]


async def build_image_prompt(conversation_id: int) -> str:
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError("会话不存在")
        character = db.get(Character, conversation.character_id)
        rows = list(
            reversed(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.id.desc())
                    .limit(12)
                ).all()
            )
        )

    transcript = "\n".join(
        f"{'用户' if m.role == 'user' else '角色'}：{m.content}" for m in rows
    )
    instruction = (
        "根据下面的角色对话，写一段用于文生图模型的英文提示词。"
        "描述画面场景、人物外观与动作、光线、氛围和画风；"
        "不要出现文字、字幕、对话框；只输出一段提示词，不超过 80 个英文单词。\n\n"
        f"角色：{character.name}（{character.tagline}）\n"
        f"{transcript[-3000:]}"
    )

    prompt = ""
    try:
        prompt = await complete_chat(
            "deepseek-chat",
            [{"role": "user", "content": instruction}],
            max_tokens=200,
            temperature=0.7,
        )
    except Exception:  # noqa: BLE001
        prompt = ""

    prompt = prompt.strip().strip('"').strip()
    if not prompt:
        last_user = next(
            (m.content for m in reversed(rows) if m.role == "user"), ""
        )
        prompt = (
            f"illustration of {character.name}, {character.tagline}, "
            f"{last_user[:120]}, cinematic lighting, detailed, anime style"
        )
    return prompt[:800]


def active_provider() -> str:
    if IMAGE_PROVIDER in ("zhipu", "siliconflow", "pollinations"):
        return IMAGE_PROVIDER
    if ZHIPU_API_KEY:
        return "zhipu"
    if SILICONFLOW_API_KEY:
        return "siliconflow"
    return "pollinations"


async def _fetch_pollinations(prompt: str, size: str) -> bytes:
    width, height = (size or IMAGE_SIZE).lower().split("x")
    params = {
        "width": width,
        "height": height,
        "model": "flux",
        "nologo": "true",
        "enhance": "false",
        "seed": str(random.randint(1, 999999)),
    }
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + "?"
        + urllib.parse.urlencode(params)
    )
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(url)
        if resp.status_code == 402:
            raise RuntimeError(
                "免密钥生图额度已用尽，请配置 ZHIPU_API_KEY（智谱，有免费额度）"
                "或 SILICONFLOW_API_KEY（硅基流动，约 0.05 元/张）"
            )
        resp.raise_for_status()
        return resp.content


async def _fetch_zhipu(prompt: str, size: str) -> bytes:
    if not ZHIPU_API_KEY:
        raise ValueError("未配置 ZHIPU_API_KEY")
    allowed = {
        "1024x1024": "1024x1024",
        "768x1024": "864x1152",
        "1024x576": "1344x768",
    }
    image_size = allowed.get((size or IMAGE_SIZE).lower(), "1024x1024")
    payload = {
        "model": ZHIPU_IMAGE_MODEL,
        "prompt": prompt,
        "size": image_size,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{ZHIPU_BASE_URL}/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {ZHIPU_API_KEY}"},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"生图失败 {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        image_url = data["data"][0]["url"]
        image_resp = await client.get(image_url)
        image_resp.raise_for_status()
        return image_resp.content


async def _fetch_siliconflow(prompt: str, size: str) -> bytes:
    if not SILICONFLOW_API_KEY:
        raise ValueError("未配置 SILICONFLOW_API_KEY")
    payload = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "image_size": size or IMAGE_SIZE,
        "batch_size": 1,
        "num_inference_steps": 20,
        "negative_prompt": "low quality, blurry, text, watermark, nsfw",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{SILICONFLOW_BASE_URL}/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {SILICONFLOW_API_KEY}"},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"生图失败 {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        image_url = data["images"][0]["url"]
        image_resp = await client.get(image_url)
        image_resp.raise_for_status()
        return image_resp.content


async def generate_image_bytes(
    prompt: str, size: str | None = None
) -> tuple[bytes, str]:
    provider = active_provider()
    if provider == "zhipu":
        return await _fetch_zhipu(prompt, size or IMAGE_SIZE), "zhipu"
    if provider == "siliconflow":
        return await _fetch_siliconflow(prompt, size or IMAGE_SIZE), "siliconflow"
    return await _fetch_pollinations(prompt, size or IMAGE_SIZE), "pollinations"


def save_image(
    conversation_id: int, prompt: str, data: bytes, provider: str
) -> GeneratedImage:
    extension = ".png" if data.startswith(b"\x89PNG") else ".jpg"
    filename = f"{uuid.uuid4().hex}{extension}"
    (IMAGES_DIR / filename).write_bytes(data)
    with SessionLocal() as db:
        image = GeneratedImage(
            conversation_id=conversation_id,
            prompt=prompt,
            filename=filename,
            provider=provider,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        return image
