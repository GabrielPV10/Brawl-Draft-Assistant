import os
import sys
from pathlib import Path

# permite importar `app.*` desde tests/ sin instalar el backend como paquete
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Forzamos valores seguros para los tests
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SUPERCELL_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
