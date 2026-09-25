import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'local.db'}")
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-only")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

if DATABASE_URL.startswith("sqlite"):
    (PROJECT_ROOT / "data").mkdir(exist_ok=True)
