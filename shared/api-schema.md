# API Schema — Brawl Draft Assistant

Contrato REST entre la app Android y el backend FastAPI. Las versiones se rompen por nueva ruta `/v2`, no por mutar las existentes.

## Base URL

- Dev local: `http://10.0.2.2:8000` (emulador Android → host)
- Dev LAN: `http://<ip-pc>:8000`
- Prod: TBD

Todas las respuestas son JSON con `Content-Type: application/json`.

---

## `GET /health`

```json
{ "status": "ok" }
```

## `GET /`

```json
{ "name": "Brawl Draft Assistant API", "version": "0.1.0" }
```

---

## `POST /recommend`

Calcula el top N de brawlers para la fase actual del draft.

### Request

```json
{
  "map_id": 15040002,
  "game_mode": "Knockout",
  "phase": "first_pick",        // first_pick | mid_picks | last_pick
  "allies": [16000037],         // IDs Supercell ya pickeados por mi equipo
  "enemies": [16000054],        // IDs Supercell ya pickeados por rivales
  "bans": [16000043],           // IDs baneados
  "profile_id": 3,              // opcional — para personalizar por equipo
  "slot": 0,                    // 0=tú, 1=cuate1, 2=cuate2 (requiere profile_id)
  "top_n": 3
}
```

### Response 200

```json
{
  "map_id": 15040002,
  "phase": "first_pick",
  "recommendations": [
    {
      "brawler_id": 16000000,
      "brawler_name": "Piper",
      "score": 87.5,
      "breakdown": {
        "winrate_mapa": 0.58,
        "counter_score": 0.12,
        "sinergia": 0.20,
        "pickrate_relativo": 0.32,
        "ban_risk": 0.18,
        "counterable": 0.10,
        "personal_proficiency": 0.85
      },
      "explanation": "Alto control de área y poca penalización de counter en first pick."
    }
  ],
  "computed_in_ms": 47
}
```

## `GET /recommend/dummy`

Mismo schema de respuesta, datos hardcodeados. Útil para validar la conexión Android↔backend antes de tener BD poblada.

---

## `POST /team/proficiency`

Calcula proficiency por brawler para cada player_tag. Cachea por jugador 1h en Redis.

### Request

```json
{ "player_tags": ["#ABC123XY", "#DEF456ZA"] }
```

### Response 200

```json
{
  "cached": false,
  "players": [
    {
      "player_tag": "ABC123XY",
      "nickname": "MauJair",
      "brawlers": [
        {
          "brawler_id": 16000000,
          "brawler_name": "Piper",
          "proficiency": 78.4,
          "trophies": 720,
          "power_level": 11,
          "gadgets_unlocked": 2,
          "star_powers_unlocked": 2,
          "recent_winrate": 0.7
        }
      ]
    }
  ]
}
```

---

## Perfiles (multi-perfil, hasta 5 por usuario)

### `GET /profiles?owner_id={device_id}`

```json
[
  {
    "id": 3,
    "owner_id": "android-uuid-...",
    "name": "Squad Ranked",
    "members": [
      { "slot": 0, "player_tag": "ABC123XY", "nickname": "Mauricio" },
      { "slot": 1, "player_tag": "DEF456ZA", "nickname": "Diego" },
      { "slot": 2, "player_tag": "GHI789BC", "nickname": "Alex" }
    ],
    "created_at": "...",
    "updated_at": "..."
  }
]
```

### `POST /profiles`

```json
{
  "owner_id": "android-uuid-...",
  "name": "Squad Ranked",
  "members": [
    { "slot": 0, "player_tag": "#ABC123XY", "nickname": "Mauricio" },
    { "slot": 1, "player_tag": "#DEF456ZA", "nickname": "Diego" },
    { "slot": 2, "player_tag": "#GHI789BC", "nickname": "Alex" }
  ]
}
```

Respuesta `201 Created` con el perfil. Si `owner_id` ya tiene 5 perfiles devuelve `409`.

### `PATCH /profiles/{id}`

Mismo payload de creación pero parcial. Reemplaza `members` por completo si se manda.

### `DELETE /profiles/{id}`

Devuelve `204 No Content`.

---

## Códigos de error

| Código | Cuándo                                          |
|--------|--------------------------------------------------|
| 400    | Payload inválido (Pydantic validation)           |
| 404    | Profile no existe                                |
| 409    | Límite de perfiles alcanzado                     |
| 422    | Player tag mal formado                           |
| 502    | Falló la API de Supercell o el scraper Brawlify  |
