import json
from typing import AsyncIterator

import httpx

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, OLLAMA_BASE_URL

MODELS = [
    {"id": "deepseek-chat", "label": "DeepSeek Chat", "provider": "deepseek"},
    {"id": "deepseek-reasoner", "label": "DeepSeek Reasoner", "provider": "deepseek"},
    {"id": "ollama:qwen2.5:7b", "label": "本地 Qwen2.5 7B", "provider": "ollama"},
]


def _resolve(model: str) -> dict:
    if model.startswith("ollama:"):
        return {
            "url": f"{OLLAMA_BASE_URL}/chat/completions",
            "model": model.split(":", 1)[1],
            "headers": {},
        }
    return {
        "url": f"{DEEPSEEK_BASE_URL}/chat/completions",
        "model": model,
        "headers": {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
    }


async def complete_chat(
    model: str,
    messages: list[dict],
    max_tokens: int = 900,
    temperature: float = 0.2,
) -> str:
    cfg = _resolve(model)
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            cfg["url"],
            json=payload,
            headers={**cfg["headers"], "Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"记忆整理请求失败 {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()


async def stream_chat(model: str, messages: list[dict]) -> AsyncIterator[str]:
    cfg = _resolve(model)
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "temperature": 1.0,
        "max_tokens": 1600,
    }
    timeout = httpx.Timeout(connect=15, read=None, write=30, pool=15)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            cfg["url"],
            json=payload,
            headers={**cfg["headers"], "Content-Type": "application/json"},
        ) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise RuntimeError(
                    f"模型请求失败 {resp.status_code}: {body.decode('utf-8', 'ignore')[:300]}"
                )

            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield piece
