from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = BACKEND_ROOT / "data"
SQLITE_ROOT = DATA_ROOT / "sqlite"


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "yingguibao-backend"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = ""
    database_url: str = _sqlite_url(SQLITE_ROOT / "yingguibao.db")
    rules_database_url: str = _sqlite_url(SQLITE_ROOT / "rules.db")
    test_database_url: str = _sqlite_url(SQLITE_ROOT / "test.db")
    test_rules_database_url: str = _sqlite_url(SQLITE_ROOT / "test_rules.db")
    database_echo: bool = False


def _load_config_file() -> dict:
    config_path = BACKEND_ROOT / "config.yaml"
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


@lru_cache
def get_settings() -> AppConfig:
    return AppConfig(**_load_config_file())
