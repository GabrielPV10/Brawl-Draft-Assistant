# Arquitectura — Brawl Draft Assistant

## Vista de alto nivel

```
┌────────────────────────────────────────────────────────────┐
│                    Android (Kotlin + Compose)              │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ Overlay      │  │ Manual draft   │  │ Team profile   │  │
│  │ Service      │  │ entry screen   │  │ config screen  │  │
│  └──────┬───────┘  └────────┬───────┘  └───────┬────────┘  │
│         │                   │                  │           │
│  ┌──────┴───────────────────┴──────────────────┴────────┐  │
│  │ ScreenCapture (MediaProjection) + OCR (ML Kit) +     │  │
│  │ icon template matching (OpenCV)                      │  │
│  └────────────────────────┬─────────────────────────────┘  │
└───────────────────────────┼────────────────────────────────┘
                            │ HTTPS / JSON
┌───────────────────────────┴────────────────────────────────┐
│                  Backend (FastAPI · Python 3.12)            │
│  routers/   recommend · team · profiles · health            │
│  services/  scoring   · supercell · llm                     │
│  scrapers/  brawlify  · run_daily (cron 6h)                 │
└───────────┬──────────────────────────┬─────────────────────┘
            │                          │
   ┌────────┴────────┐         ┌───────┴──────┐
   │  Postgres 16    │         │  Redis 7     │
   │  brawlers       │         │  stat cache  │
   │  maps           │         │  player cache│
   │  map_stats      │         │  llm cache   │
   │  synergies      │         └──────────────┘
   │  team_profiles  │
   │  proficiency    │
   └─────────────────┘
            │
   ┌────────┴───────────────┐    ┌───────────────────────────┐
   │  Supercell official    │    │  Brawlify (scraping HTML) │
   │  api.brawlstars.com    │    │  brawlify.com/maps/{slug} │
   └────────────────────────┘    └───────────────────────────┘
```

## Decisiones de diseño

- **Monorepo simple, sin Gradle compartido.** Android se abre con Android Studio sobre `android/`. Python se abre con VS Code/PyCharm sobre `backend/`. Lo único compartido vive en `shared/` (markdown + JSON, sin build).
- **Stub primero, scraping después.** El endpoint `/recommend` y la fórmula están listos para conectar; los sub-cálculos retornan `0.0` hasta que el scraper de Brawlify pueble `map_stats` y `synergies`. Esto permite que Android se integre desde el día 1 contra `/recommend/dummy`.
- **Multi-perfil (hasta 5 por `owner_id`).** El `owner_id` en v1 es el device_id (no hay auth). Las decisiones por slot del draft (`slot=0..2`) consultan el `player_tag` del miembro correspondiente del perfil seleccionado.
- **Cache agresivo.** Brawlify TTL 6h. Supercell TTL 1h por jugador. Explicaciones LLM TTL 24h por hash del escenario.
- **Pesos del scoring vienen del .env.** Recalibrar el meta no requiere redeploy; basta cambiar variables y reiniciar el proceso.

## Capas Python

| Capa       | Responsabilidad                                                   |
|------------|-------------------------------------------------------------------|
| `routers`  | Entrada HTTP, validación con Pydantic, sin lógica de negocio.     |
| `services` | Lógica: scoring, cliente Supercell, capa LLM.                     |
| `scrapers` | Job cron de Brawlify (ETL). No usa `routers`, sí usa `models`.    |
| `models`   | Tablas SQLAlchemy. Importadas por Alembic para autogenerate.      |
| `schemas`  | DTOs Pydantic. Lo que entra/sale por la API.                      |
| `db`       | Engine, `SessionLocal`, cliente Redis.                            |
| `core`     | `Settings` (env-driven), pesos del scoring.                       |

## Capas Android (planeado)

| Capa             | Responsabilidad                                          |
|------------------|----------------------------------------------------------|
| `ui/`            | Composables: pantallas, overlay UI, config equipo.        |
| `data/api/`      | Cliente Retrofit / Ktor para el backend.                 |
| `data/repo/`     | Repositorios, cache local.                                |
| `domain/`        | Modelos de dominio (`Brawler`, `Draft`, `Recommendation`).|
| `service/`       | `OverlayService`, `ScreenCaptureService`.                |
| `cv/`            | Template matching, OCR pipeline.                         |
