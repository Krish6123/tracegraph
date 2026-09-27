from fastapi import FastAPI
from app.api.router import router

app = FastAPI(
    title="Nexus API",
    description="API for Nexus deterministic static-analysis engine.",
    version="3.0.0"
)

app.include_router(router)
