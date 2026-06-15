"""Endpoint de administración para poblar la base en la nube tras el primer deploy.

En el plan gratis de Render no hay shell cómoda para correr `seed_catalog` y
`run_daily` a mano. Este endpoint los ejecuta en segundo plano con un token, así
que basta una llamada HTTP para dejar la DB lista. Idempotente: los scripts usan
upsert, se puede llamar varias veces sin duplicar.
"""

from __future__ import annotations

import asyncio
import threading

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.brawler import Brawler
from app.models.map_stats import MapStats

router = APIRouter(prefix="/admin", tags=["admin"])

# Estado compartido del proceso de bootstrap (una corrida a la vez).
_status: dict[str, object] = {
    "running": False,
    "done": False,
    "message": "no iniciado",
    "error": None,
}


def _run_bootstrap() -> None:
    """Siembra catálogo + estadísticas. Corre en un hilo aparte (loop propio)."""
    from scrapers.run_daily import run as run_daily
    from scripts.seed_catalog import main as seed_catalog

    try:
        _status.update(running=True, done=False, error=None, message="Sembrando brawlers y mapas…")
        asyncio.run(seed_catalog())
        _status.update(message="Generando estadísticas de mapas (puede tardar 1-2 min)…")
        asyncio.run(run_daily())
        _status.update(running=False, done=True, message="Completado ✓")
    except Exception as exc:  # noqa: BLE001 - queremos reportar cualquier fallo al cliente
        _status.update(running=False, done=False, error=str(exc), message="Falló")


@router.post("/bootstrap")
def bootstrap(token: str = Query(..., description="ADMIN_TOKEN configurado en Render")) -> dict[str, object]:
    """Dispara el poblado de la DB en segundo plano. Requiere el token correcto."""
    settings = get_settings()
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Token inválido")
    if _status["running"]:
        return {"status": "ya en progreso", **_status}
    threading.Thread(target=_run_bootstrap, daemon=True).start()
    return {"status": "iniciado", "hint": "Consulta GET /admin/bootstrap/status para ver el avance"}


@router.get("/bootstrap/status")
def bootstrap_status() -> dict[str, object]:
    """Avance del bootstrap + conteos actuales en la DB (no requiere token)."""
    with SessionLocal() as db:
        brawlers = db.execute(select(func.count()).select_from(Brawler)).scalar() or 0
        map_stats = db.execute(select(func.count()).select_from(MapStats)).scalar() or 0
    return {**_status, "brawlers": brawlers, "map_stats": map_stats}
