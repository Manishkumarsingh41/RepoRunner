from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings

app = FastAPI(
    title="RepoRunner API",
    description="Mobile-first GitHub repository inspection and guarded runner",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {"app": "RepoRunner", "status": "running", "version": app.version}


@app.get("/health")
def health():
    return {"status": "ok", "execution": settings.execution_status}
