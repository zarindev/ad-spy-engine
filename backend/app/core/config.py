"""Configuration: config/settings.yaml (+ data/settings.override.yaml), config/selectors.yaml, .env."""

from __future__ import annotations

import copy
import os
from functools import lru_cache
from typing import Any

import yaml
from dotenv import load_dotenv

from app.core.paths import CONFIG_DIR, ROOT_DIR, data_dir

load_dotenv(ROOT_DIR / ".env")


def _read_yaml(path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def override_path():
    return data_dir() / "settings.override.yaml"


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    """Merged settings. Call `reload_settings()` after changing the override file."""
    base = _read_yaml(CONFIG_DIR / "settings.yaml")
    return deep_merge(base, _read_yaml(override_path()))


@lru_cache(maxsize=1)
def get_selectors() -> dict[str, Any]:
    return _read_yaml(CONFIG_DIR / "selectors.yaml")


def reload_settings() -> None:
    get_settings.cache_clear()
    get_selectors.cache_clear()


def save_override(patch: dict[str, Any]) -> dict[str, Any]:
    current = _read_yaml(override_path())
    merged = deep_merge(current, patch)
    with override_path().open("w", encoding="utf-8") as fh:
        yaml.safe_dump(merged, fh, sort_keys=False, allow_unicode=True)
    reload_settings()
    return get_settings()


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, "")
    return value.strip() if value and value.strip() else default


def ai_model() -> str:
    return env("ANTHROPIC_MODEL") or get_settings().get("ai", {}).get("model", "claude-sonnet-5-5")
