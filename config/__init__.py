# Config module# config/__init__.py
import os

# Load environment variables from .env file before importing config classes
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv is optional - environment variables can be set directly
    pass

# Optional modules; import only if present
try:
    from .production import ProductionConfig
except Exception:
    ProductionConfig = None

try:
    from .staging import StagingConfig
except Exception:
    StagingConfig = None

try:
    from .development import DevelopmentConfig
except Exception:
    DevelopmentConfig = None


def load_config():
    env = os.getenv("ENV", "production").lower()
    if env in ("staging",) and StagingConfig:
        return StagingConfig()
    if env in ("dev", "development") and DevelopmentConfig:
        return DevelopmentConfig()
    if ProductionConfig:
        return ProductionConfig()
    raise RuntimeError(
        "No suitable config class found. Ensure config/production.py (or staging/development) exists."
    )


# Legacy export expected by older code: `from config import config`
config = load_config()

# Legacy shim for tests expecting `from config import Config`
Config = type(config)

__all__ = ["config", "load_config", "Config"]
