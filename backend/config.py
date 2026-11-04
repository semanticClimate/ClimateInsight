"""
config.py — loads config.toml from the project root
"""
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.9 / 3.10
    import tomli as tomllib
from pathlib import Path

_ROOT = Path(__file__).parent.parent  # project root
_TOML = _ROOT / "config.toml"

with open(_TOML, "rb") as f:
    _cfg = tomllib.load(f)

# Convenience accessors
# Optional sections default to {} so a missing table never crashes import.
APP      = _cfg.get("app", {})
BACKEND  = _cfg.get("backend", {})
LLM      = _cfg.get("llm", {})
RETRIEVAL= _cfg.get("retrieval", {})
CORS_CFG = _cfg.get("cors", {})

VERSION  = APP.get("version", "0.0.0")