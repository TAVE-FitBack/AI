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


@dataclass(frozen=True)
class AiSettings:
    provider: str
    api_key: str | None
    model: str
    base_url: str
    timeout_seconds: float


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        duplicate_prefix = f"{name}="
        if value.startswith(duplicate_prefix):
            value = value.removeprefix(duplicate_prefix).strip().strip('"').strip("'")
        os.environ.setdefault(name, value)


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        neo4j_uri=_neo4j_uri(),
        neo4j_username=_required("NEO4J_USERNAME"),
        neo4j_password=_required("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        neo4j_trust_self_signed=_bool("NEO4J_TRUST_SELF_SIGNED"),
    )


def load_ai_settings() -> AiSettings:
    load_dotenv()
    api_key = _env("OPENAI_API_KEY") or _env("AI_API_KEY") or None
    provider = _env("AI_PROVIDER", "auto").lower()
    if provider == "auto":
        provider = "openai" if api_key else "heuristic"
    model = _env("OPENAI_MODEL", _env("AI_MODEL", "gpt-4.1-mini"))
    base_url = os.getenv(
        "OPENAI_BASE_URL",
        os.getenv("AI_BASE_URL", "https://api.openai.com/v1"),
    ).strip()
    return AiSettings(
        provider=provider,
        api_key=api_key,
        model=model or "gpt-4.1-mini",
        base_url=base_url or "https://api.openai.com/v1",
        timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "25")),
    )


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    duplicate_prefix = f"{name}="
    if value.startswith(duplicate_prefix):
        return value.removeprefix(duplicate_prefix).strip().strip('"').strip("'")
    return value


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
