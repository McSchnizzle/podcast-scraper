#!/usr/bin/env python3
"""
Config validation system for podcast scraper.
Ensures all required keys are present and prevents runtime errors.
"""

# Required keys in OPENAI_SETTINGS
REQUIRED_OPENAI_KEYS = [
    "model",
    "temperature",
    "max_tokens",
    "timeout",
    "relevance_threshold",
    "scoring_model",
    "validator_model",
    # Production config uses digest_model instead of summary_model
    "digest_model",
]


def assert_openai_settings(cfg):
    """
    Validates that all required OPENAI_SETTINGS keys are present.
    Raises RuntimeError if any keys are missing.
    """
    if not hasattr(cfg, "OPENAI_SETTINGS") or not cfg.OPENAI_SETTINGS:
        raise RuntimeError("Missing OPENAI_SETTINGS in config")

    missing = [k for k in REQUIRED_OPENAI_KEYS if k not in cfg.OPENAI_SETTINGS]
    if missing:
        raise RuntimeError(f"Missing OPENAI_SETTINGS keys: {', '.join(missing)}")

    print(
        f"✅ Config validation passed - all {len(REQUIRED_OPENAI_KEYS)} required keys present"
    )


def validate_config_complete():
    """
    Complete config validation including environment variables and structure.
    """
    try:
        from config import config

        # Check OPENAI_SETTINGS structure
        assert_openai_settings(config)

        # Check API key is loaded
        if not config.OPENAI_API_KEY or len(config.OPENAI_API_KEY) < 20:
            print("⚠️  WARNING: OPENAI_API_KEY appears invalid or too short")
        else:
            print(f"✅ OpenAI API key loaded ({len(config.OPENAI_API_KEY)} chars)")

        # Check other critical settings
        critical_attrs = [
            "ENV",
            "PODCAST_BASE_URL",
            "AUDIO_BASE_URL",
            "TRANSCRIPTS_DIR",
        ]
        for attr in critical_attrs:
            if not hasattr(config, attr) or not getattr(config, attr):
                print(f"⚠️  WARNING: Missing or empty {attr}")
            else:
                print(f"✅ {attr}: {getattr(config, attr)}")

        print("\n🎯 Configuration validation completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Config validation failed: {e}")
        return False


if __name__ == "__main__":
    validate_config_complete()
