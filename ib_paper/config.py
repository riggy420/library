"""Configuration file management.

Stores connection settings and defaults in ~/.ib_paper/config.json.
"""

import json
import os
from pathlib import Path
from typing import Any

from .exceptions import ConfigError


class Config:
    """Read/write configuration stored at ~/.ib_paper/config.json."""

    _CONFIG_DIR = Path.home() / ".ib_paper"
    _CONFIG_PATH = _CONFIG_DIR / "config.json"

    _DEFAULT_CONFIG: dict[str, Any] = {
        "connection": {
            "host": "127.0.0.1",
            "port": 7497,
            "client_id": 1,
            "timeout": 5,
        },
        "defaults": {
            "order_quantity": 100,
            "order_type": "MKT",
            "currency": "USD",
            "exchange": "SMART",
        },
        "safety": {
            "confirm_live": True,
            "confirm_orders": True,
        },
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> dict[str, Any]:
        """Return the current configuration as a dictionary.

        If the config file does not exist, defaults are returned and
        the file is created.
        """
        if not cls._CONFIG_PATH.exists():
            cls.save(cls._DEFAULT_CONFIG)
            return dict(cls._DEFAULT_CONFIG)

        try:
            raw = cls._CONFIG_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            # Deep-merge defaults so new keys added in future versions
            # appear automatically.
            return cls._deep_merge(cls._DEFAULT_CONFIG, data)
        except (json.JSONDecodeError, OSError) as exc:
            raise ConfigError(
                f"Config file at {cls._CONFIG_PATH} is corrupt. "
                f"Delete it and run 'ibpaper setup' to recreate.\n"
                f"Details: {exc}"
            ) from exc

    @classmethod
    def save(cls, data: dict[str, Any]) -> None:
        """Write *data* as the full configuration."""
        cls._CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            cls._CONFIG_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise ConfigError(
                f"Could not write config to {cls._CONFIG_PATH}: {exc}"
            ) from exc

    @classmethod
    def update(cls, updates: dict[str, Any]) -> None:
        """Merge *updates* into the current config and persist."""
        current = cls.load()
        merged = cls._deep_merge(current, updates)
        cls.save(merged)

    @classmethod
    def get(cls, *keys: str, default: Any = None) -> Any:
        """Walk nested keys into the config dict.

        Example:
            Config.get("connection", "port")  -> 7497
            Config.get("safety", "confirm_live")  -> True
        """
        data = cls.load()
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data

    @classmethod
    def reset(cls) -> None:
        """Delete the config file (defaults will be used on next load)."""
        try:
            cls._CONFIG_PATH.unlink(missing_ok=True)
        except OSError as exc:
            raise ConfigError(
                f"Could not delete config at {cls._CONFIG_PATH}: {exc}"
            ) from exc

    @classmethod
    def path(cls) -> Path:
        """Return the path to the config file."""
        return cls._CONFIG_PATH

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge *overlay* into *base*, returning a new dict."""
        result = base.copy()
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
