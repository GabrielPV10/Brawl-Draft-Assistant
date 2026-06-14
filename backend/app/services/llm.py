"""Capa de razonamiento con Claude Haiku (Fase 5).

Genera una explicación corta (1-2 líneas en español) para cada recomendación,
usando el breakdown numérico como contexto. Se cachea la explicación por
combinación de draft para no pagar el LLM dos veces por el mismo escenario.
"""

from __future__ import annotations

import hashlib
import json

from anthropic import Anthropic

from app.core.config import get_settings
from app.db.redis_client import get_redis
from app.schemas.draft import DraftRecommendation, DraftRequest


SYSTEM_PROMPT = (
    "Eres un coach experto de Brawl Stars competitivo. "
    "Dado el contexto de un draft y una recomendación con su breakdown numérico, "
    "explica en 1-2 frases CORTAS (español) por qué es buena elección. "
    "No repitas números, da intuición jugable. "
    "Usa terminología del juego (counter, sinergia, last pick, etc.)."
)


class LLMExplainer:
    def __init__(self) -> None:
        s = get_settings()
        self.client = Anthropic(api_key=s.anthropic_api_key) if s.anthropic_api_key else None
        self.model = s.anthropic_model

    def explain(
        self, rec: DraftRecommendation, req: DraftRequest, map_name: str | None = None
    ) -> str | None:
        if self.client is None:
            return None

        cache_key = self._cache_key(rec, req)
        cached = get_redis().get(cache_key)
        if cached:
            return cached

        user_msg = self._build_user_message(rec, req, map_name)
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=120,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text")).strip()
        get_redis().setex(cache_key, 24 * 3600, text)
        return text

    def _cache_key(self, rec: DraftRecommendation, req: DraftRequest) -> str:
        payload = {
            "brawler_id": rec.brawler_id,
            "map_id": req.map_id,
            "phase": req.phase,
            "allies": sorted(req.allies),
            "enemies": sorted(req.enemies),
        }
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        return f"llm:explanation:{h}"

    def _build_user_message(
        self, rec: DraftRecommendation, req: DraftRequest, map_name: str | None
    ) -> str:
        return (
            f"Mapa: {map_name or req.map_id}. Fase: {req.phase}. "
            f"Aliados: {req.allies}. Enemigos: {req.enemies}. "
            f"Recomendación: {rec.brawler_name} (score {rec.score:.1f}). "
            f"Breakdown: {rec.breakdown}."
        )
