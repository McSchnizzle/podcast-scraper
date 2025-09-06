#!/usr/bin/env python3
"""
Secret Redaction Utilities
Sanitize logs and responses to prevent leakage of sensitive information
"""

import json
import re
from typing import Any, Union

# Patterns for sensitive information
SENSITIVE_PATTERNS = [
    # API Keys
    (
        r'(?i)(api[_-]?key|apikey|key)[\'"\s]*[:=]\s*[\'"]([a-zA-Z0-9\-_]{20,})[\'"]',
        r'\1: "[REDACTED_API_KEY]"',
    ),
    (r"(?i)(bearer\s+)([a-zA-Z0-9\-._~+/]+=*)", r"\1[REDACTED_BEARER_TOKEN]"),
    # OpenAI API Keys (sk-... format)
    (r"sk-[a-zA-Z0-9]{48,}", "[REDACTED_OPENAI_KEY]"),
    # URLs with secrets
    (
        r"(https?://[^/\s]*?)([?&](api_key|token|key|secret|password)=)([^&\s]+)",
        r"\1\2[REDACTED_PARAM]",
    ),
    # Generic tokens
    (
        r'(?i)(token|secret|password)[\'"\s]*[:=]\s*[\'"]([a-zA-Z0-9\-_]{16,})[\'"]',
        r'\1: "[REDACTED_SECRET]"',
    ),
    # Base64 encoded secrets (common pattern)
    (
        r'(?i)(authorization|auth)[\'"\s]*[:=]\s*[\'"]([a-zA-Z0-9+/=]{32,})[\'"]',
        r'\1: "[REDACTED_AUTH]"',
    ),
    # GitHub tokens (ghp_, gho_, ghs_, ghr_)
    (r"gh[psor]_[a-zA-Z0-9]{36,}", "[REDACTED_GITHUB_TOKEN]"),
    # Generic long alphanumeric strings that might be secrets
    (
        r'(?i)(key|token|secret|password)["\']\s*:\s*["\']([a-zA-Z0-9\-_]{32,})["\']',
        r'\1": "[REDACTED_CREDENTIAL]"',
    ),
]


def redact_secrets(text: str) -> str:
    """
    Redact sensitive information from text

    Args:
        text: Text to redact

    Returns:
        Text with sensitive information replaced
    """
    if not isinstance(text, str):
        text = str(text)

    redacted_text = text

    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted_text = re.sub(pattern, replacement, redacted_text)

    return redacted_text


def redact_dict(data: dict) -> dict:
    """
    Recursively redact sensitive information from dictionary

    Args:
        data: Dictionary to redact

    Returns:
        Dictionary with sensitive values redacted
    """
    if not isinstance(data, dict):
        return data

    redacted = {}

    for key, value in data.items():
        key_lower = key.lower()

        # Redact known sensitive keys
        if any(
            sensitive in key_lower
            for sensitive in ["key", "token", "secret", "password", "auth", "bearer"]
        ):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_dict(value)
        elif isinstance(value, list):
            redacted[key] = [
                (
                    redact_dict(item)
                    if isinstance(item, dict)
                    else redact_secrets(str(item))
                )
                for item in value
            ]
        elif isinstance(value, str):
            redacted[key] = redact_secrets(value)
        else:
            redacted[key] = value

    return redacted


def redact_json_string(json_str: str) -> str:
    """
    Redact secrets from JSON string

    Args:
        json_str: JSON string to redact

    Returns:
        Redacted JSON string
    """
    try:
        data = json.loads(json_str)
        redacted_data = redact_dict(data)
        return json.dumps(redacted_data, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        # If not valid JSON, treat as plain text
        return redact_secrets(json_str)


def safe_log(message: str) -> str:
    """
    Make a log message safe by redacting sensitive information

    Args:
        message: Log message

    Returns:
        Redacted log message
    """
    return redact_secrets(message)


class RedactingFormatter:
    """
    Logging formatter that automatically redacts sensitive information
    """

    def __init__(self, base_formatter):
        self.base_formatter = base_formatter

    def format(self, record):
        # Format the message normally first
        formatted = self.base_formatter.format(record)

        # Redact sensitive information
        return redact_secrets(formatted)


# Test patterns for development
def test_redaction():
    """Test redaction patterns (for development use)"""
    test_cases = [
        'api_key="sk-1234567890abcdef1234567890abcdef12345678"',
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        'token: "ghp_1234567890123456789012345678901234567890"',
        "https://api.example.com/data?api_key=secret123456",
        'password="supersecret123456789"',
        '{"openai_key": "sk-abcdef123456", "normal": "value"}',
    ]

    print("Testing redaction patterns:")
    for test in test_cases:
        redacted = redact_secrets(test)
        print(f"Original: {test}")
        print(f"Redacted: {redacted}")
        print()


if __name__ == "__main__":
    test_redaction()
