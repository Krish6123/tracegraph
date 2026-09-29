from fastapi import FastAPI
from app.api.router import router
from app.db.database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Nexus API",
    description="API for Nexus deterministic static-analysis engine.",
    version="4.0.0"
)

app.include_router(router)
