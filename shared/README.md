# shared/

Contratos y constantes que viven entre la app Android y el backend.

- **`api-schema.md`** — Contrato REST único. Si el backend cambia un response, hay que actualizar aquí y la capa de DTOs en Android.
- **`brawler-ids.json`** — Lookup `id ↔ name ↔ slug` de brawlers. Sembrado desde BrawlAPI (`https://api.brawlapi.com/v1/brawlers`).
