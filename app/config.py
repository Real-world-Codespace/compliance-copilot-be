import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'local.db'}")
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-only")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
S3_REGION = os.getenv("S3_REGION", "ap-southeast-1")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PRESIGNED_EXPIRY_SECONDS = int(os.getenv("S3_PRESIGNED_EXPIRY_SECONDS", "600"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))

if DATABASE_URL.startswith("sqlite"):
    (PROJECT_ROOT / "data").mkdir(exist_ok=True)
