# Brawl Draft Assistant

Asistente inteligente de draft para Brawl Stars competitivo: overlay flotante en Android + backend Python con scoring estadístico personalizado por miembro del equipo.

> Plan completo en [`docs/`](docs/) (arquitectura, algoritmo, roadmap).

## Estructura del monorepo

```
brawl-draft-assistant/
├── android/         # Proyecto Android Studio (Kotlin + Jetpack Compose)
├── backend/         # FastAPI + SQLAlchemy + Alembic + scrapers
├── shared/          # api-schema.md + brawler-ids.json
├── docs/            # arquitectura / algoritmo / roadmap
└── docker-compose.yml
```

## Arranque rápido (backend)

```bash
# 1. Variables de entorno
cp backend/.env.example backend/.env

# 2. Levantar Postgres + Redis + backend
docker compose up -d

# 3. Aplicar migraciones (primera vez)
docker compose exec backend alembic revision --autogenerate -m "init schema"
docker compose exec backend alembic upgrade head

# 4. Ver la API
# http://localhost:8000/health
# http://localhost:8000/docs
```

### Desarrollo sin Docker

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Tests

```bash
cd backend
pytest
```

## Arranque rápido (Android)

1. Abrir `android/` en Android Studio.
2. Sync Gradle.
3. Editar la base URL del backend en código (`http://10.0.2.2:8000` para emulador).
4. Run.

## Estado actual

Fase 0 (cimientos) completa. Ver [`docs/roadmap.md`](docs/roadmap.md) para el plan por fases.

- `/health` y `/recommend/dummy` funcionan sin BD.
- `/recommend` real espera que el scraper de Brawlify pueble `map_stats`.
- Fase 2 (personal proficiency) requiere API key en `developer.brawlstars.com`.

## Stack

- **Android**: Kotlin, Jetpack Compose, MediaProjection, ML Kit, OpenCV.
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Postgres 16, Redis 7.
- **Datos**: API oficial Supercell + BrawlAPI + scraping Brawlify.
- **LLM**: Claude Haiku 4.5 (opcional, Fase 5).

## Configuración necesaria

| Variable               | Cuándo                                    |
|------------------------|--------------------------------------------|
| `SUPERCELL_API_KEY`    | Fase 2 (proficiency por jugador)           |
| `ANTHROPIC_API_KEY`    | Fase 5 (explicaciones LLM)                 |
| `DATABASE_URL`         | Siempre (Postgres)                         |
| `REDIS_URL`            | Siempre (cache)                            |

## Autor

Mauricio Jair · 2026
