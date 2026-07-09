from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    neo4j_trust_self_signed: bool
    mock_store_id: str
    mock_batch_id: str
    mock_record_count: int


@dataclass(frozen=True)
class AiSettings:
    provider: str
    xai_api_key: str | None
    xai_model: str
    xai_base_url: str
    timeout_seconds: float


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        neo4j_uri=_neo4j_uri(),
        neo4j_username=_required("NEO4J_USERNAME"),
        neo4j_password=_required("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        neo4j_trust_self_signed=_bool("NEO4J_TRUST_SELF_SIGNED"),
        mock_store_id=os.getenv("MOCK_STORE_ID", "00000000-0000-4000-8000-000000000001"),
        mock_batch_id=os.getenv("MOCK_BATCH_ID", "mock-graph-rag-v1"),
        mock_record_count=int(os.getenv("MOCK_RECORD_COUNT", "100")),
    )


def load_ai_settings() -> AiSettings:
    load_dotenv()
    api_key = os.getenv("XAI_API_KEY", "").strip() or os.getenv("AI_API_KEY", "").strip() or None
    provider = os.getenv("AI_PROVIDER", "auto").strip().lower()
    if provider == "auto":
        provider = "xai" if api_key else "heuristic"
    return AiSettings(
        provider=provider,
        xai_api_key=api_key,
        xai_model=os.getenv("XAI_MODEL", "grok-4.5").strip() or "grok-4.5",
        xai_base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip() or "https://api.x.ai/v1",
        timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "25")),
    )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required. Add it to .env or export it in the shell.")
    return value


def _bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _neo4j_uri() -> str:
    uri = _required("NEO4J_URI")
    if not _bool("NEO4J_TRUST_SELF_SIGNED"):
        return uri
    return uri.replace("neo4j+s://", "neo4j+ssc://").replace("bolt+s://", "bolt+ssc://")
