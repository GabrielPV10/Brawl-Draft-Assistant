import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import admin, brawlers, health, maps, profiles, recommend, team

settings = get_settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("brawl-draft-assistant")

app = FastAPI(
    title="Brawl Draft Assistant API",
    version="0.2.0",
    description="Motor de recomendación de draft para Brawl Stars competitivo.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(admin.router)
app.include_router(brawlers.router)
app.include_router(maps.router)
app.include_router(recommend.router)
app.include_router(team.router)
app.include_router(profiles.router)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Brawl Draft Assistant API arrancando en env=%s", settings.app_env)
