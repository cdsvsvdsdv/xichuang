import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
DATABASE_URL = f"sqlite:///{DATA_DIR / 'rili.db'}"

MEMORY_TRIGGER = int(os.getenv("MEMORY_TRIGGER", "12"))
MEMORY_KEEP = int(os.getenv("MEMORY_KEEP", "6"))

# 上下文预算：总 token 上限，扣掉预留的回复长度后，剩余部分留给对话历史
CONTEXT_TOKEN_BUDGET = int(os.getenv("CONTEXT_TOKEN_BUDGET", "32000"))
CONTEXT_TOKEN_RESERVE = int(os.getenv("CONTEXT_TOKEN_RESERVE", "2000"))

IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "auto").strip().lower()
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "").strip()
SILICONFLOW_BASE_URL = os.getenv(
    "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
).rstrip("/")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "Kwai-Kolors/Kolors")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1024")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "").strip()
ZHIPU_BASE_URL = os.getenv(
    "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
).rstrip("/")
ZHIPU_IMAGE_MODEL = os.getenv("ZHIPU_IMAGE_MODEL", "cogview-3-flash")

IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

AVATARS_DIR = IMAGES_DIR / "avatars"
AVATARS_DIR.mkdir(exist_ok=True)
