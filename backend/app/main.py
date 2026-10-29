"""应用装配：中间件、生命周期、路由挂载。业务逻辑在 routers/ 与 services.py。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, IMAGES_DIR
from .db import Base, SessionLocal, engine, ensure_schema
from .routers import accounts, characters, chat, media, memory, misc, variables
from .seed import seed_characters


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_schema()
    with SessionLocal() as db:
        seed_characters(db)
    yield


app = FastAPI(title="西窗 Web", lifespan=lifespan)

app.mount("/media", StaticFiles(directory=str(IMAGES_DIR)), name="media")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://xichuang.pangyifan.cn",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/media/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


app.include_router(accounts.router)
app.include_router(misc.router)
app.include_router(characters.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(media.router)
app.include_router(variables.router)

FRONTEND_DIST = Path(BASE_DIR).parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
