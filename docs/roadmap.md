# Roadmap

Las fases siguen el plan original (PDF). Marcar `[x]` cuando se cierre la fase.

## Fase 0 — Cimientos (ESTE COMMIT)

- [x] Estructura del monorepo (`android/`, `backend/`, `shared/`, `docs/`).
- [x] Android existente movido a `android/` y renombrado a `com.brawldraft.assistant`.
- [x] Backend FastAPI base con config tipada (`pydantic-settings`).
- [x] Modelos SQLAlchemy: `brawlers`, `maps`, `map_stats`, `synergies`, `team_profiles`, `player_proficiency`.
- [x] Routers stub: `/health`, `/recommend`, `/recommend/dummy`, `/team/proficiency`, `/profiles`.
- [x] Services stub: `ScoringEngine`, `SupercellClient`, `LLMExplainer`.
- [x] Scraper Brawlify (esqueleto + rate limit).
- [x] Alembic configurado para autogenerate.
- [x] Tests con pytest: `test_health`, `test_recommend_dummy`, `test_scoring_formula`.
- [x] Docker Compose con Postgres + Redis + backend.
- [x] Contratos compartidos en `shared/api-schema.md`.

## Fase 1 — MVP funcional

- [x] Sembrar `brawlers` y `maps` desde BrawlAPI (`scripts/seed_catalog.py`).
- [x] Implementar parsing del scraper Brawlify (Next.js JSON + fallback HTML).
- [x] Persistencia en `run_daily.py` (upserts a `map_stats` y `synergies`).
- [x] Implementar `_enumerate_candidates`, `_winrate_mapa`, `_pickrate_relativo`, `_counter_score`, `_sinergia`, `_ban_risk`, `_counterable`, `_personal_proficiency`.
- [x] Implementar `_adjust_weights` con tabla de fase (PHASE_WEIGHT_MULTIPLIERS).
- [x] Tests del scoring con SQLite en memoria (`test_scoring_engine.py`).
- [x] Migración inicial Alembic con todo el esquema.
- [x] Android: dependencias Retrofit + kotlinx.serialization en `libs.versions.toml`.
- [x] Android: capa data (DTOs + ApiService + ApiClient).
- [x] Android: DraftRepository + DraftViewModel con StateFlow.
- [x] Android: pantalla Compose `ManualDraftScreen` con selector de fase, IDs y top 3.
- [ ] Primera corrida real de `run_daily.py` contra Brawlify (calibrar selectores).
- [ ] Smoke test end-to-end: emulador Android → backend → respuesta visible en UI.

## Fase 2 — Estadísticas del equipo

- [ ] Registro en developer.brawlstars.com + API key.
- [ ] Implementar `SupercellClient.fetch_player_proficiency` real.
- [ ] UI Android para crear/editar perfiles (hasta 5).
- [ ] Conectar `slot` + `profile_id` en `/recommend`.
- [ ] UI que muestra el pick recomendado para cada integrante.

## Fase 3 — Overlay flotante

- [ ] `OverlayService` (Foreground Service + notificación persistente).
- [ ] Permission flow `SYSTEM_ALERT_WINDOW`.
- [ ] Burbuja arrastrable tipo chat-head.
- [ ] Tap expande la UI de selección.

## Fase 4 — Captura automática

- [ ] Permission flow `MediaProjection`.
- [ ] Captura + crop de la región del draft (calibrar por resolución).
- [ ] OCR del nombre del mapa con ML Kit.
- [ ] Template matching de íconos con OpenCV.
- [ ] Fallback a input manual si el matching falla.

## Fase 5 — Capa de razonamiento (LLM)

- [ ] API key de Anthropic configurada.
- [ ] Activar `LLMExplainer` en `/recommend`.
- [ ] Prompt template afinado para respuestas en español.
- [ ] UI muestra la explicación debajo de cada brawler.
