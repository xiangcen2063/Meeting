import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8013"))
SERVER_RELOAD = os.getenv("SERVER_RELOAD", "false").lower() in ("1", "true", "yes", "on")

STORAGE_DIR = BASE_DIR / os.getenv("STORAGE_DIR", "Storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

AMAP_API_KEY = os.getenv("AMAP_API_KEY", "")
AMAP_MCP_URL = os.getenv("AMAP_MCP_URL", "")
