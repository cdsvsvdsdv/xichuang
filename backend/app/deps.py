"""路由共用的轻量依赖：限流。"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_rate_limits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate(request: Request, scope: str, limit: int, window: int) -> None:
    key = f"{scope}:{client_ip(request)}"
    bucket = _rate_limits[key]
    now = time.time()
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")
    bucket.append(now)
