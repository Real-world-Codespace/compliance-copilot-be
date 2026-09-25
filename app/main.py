from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
from .config import CORS_ORIGINS
from .seed import initialize_database

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database(); yield

app=FastAPI(title="Procurement Compliance Copilot",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=CORS_ORIGINS,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router)
