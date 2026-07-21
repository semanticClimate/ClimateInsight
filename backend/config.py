"""
config.py — loads config.toml from the project root
"""
import tomllib
from pathlib import Path

_ROOT = Path(__file__).parent.parent  # project root
_TOML = _ROOT / "config.toml"

with open(_TOML, "rb") as f:
    _cfg = tomllib.load(f)

# Convenience accessors
APP      = _cfg["app"]
BACKEND  = _cfg["backend"]
LLM      = _cfg["llm"]
RETRIEVAL= _cfg["retrieval"]
CORS_CFG = _cfg["cors"]

VERSION  = APP["version"]