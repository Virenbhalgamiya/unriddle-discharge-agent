from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    load_dotenv()
    root = Path(__file__).resolve().parents[2]
    path = Path(config_path) if config_path else root / "config" / "config.yaml"
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    env_provider = os.getenv("LLM_PROVIDER")
    if env_provider:
        config["llm_provider"] = env_provider
    return config


def get_path(config: dict[str, Any], key: str, default: str) -> Path:
    paths = config.get("paths", {})
    root = Path(__file__).resolve().parents[2]
    rel = paths.get(key, default)
    return root / rel
