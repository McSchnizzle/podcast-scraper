#!/usr/bin/env python3
"""
Security Utilities for Podcast Scraper System
Provides filename sanitization, URL encoding, and secret scrubbing functions
"""

import html
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

# Patterns for sensitive data detection
SENSITIVE_PATTERNS = [
    # API Keys and tokens
    r'["\']?(?:api[_-]?key|token|secret|password)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]+)["\']?',
    r'["\']?(sk-[a-zA-Z0-9]+)["\']?',  # OpenAI API keys
    r'["\']?(pk_[a-zA-Z0-9]+)["\']?',  # Stripe keys
    r'["\']?(ghp_[a-zA-Z0-9]+)["\']?',  # GitHub tokens
    r'["\']?([a-f0-9]{32,64})["\']?',  # Generic hex keys
    # Basic auth and passwords
    r'(?:password|pass|pwd)\s*[:=]\s*["\']?([^"\'\s]+)["\']?',
    r'(?:user|username)\s*[:=]\s*["\']?([^"\'\s@]+@[^"\'\s]+)["\']?',
    # URLs with credentials
    r"(?:https?|ftp)://[^/\s]*:([^@\s]+)@",
]


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename for safe use in filesystem and URLs

    Args:
        filename: Original filename
        max_length: Maximum allowed length (default 255 for most filesystems)

    Returns:
        Sanitized filename safe for filesystem and URL use
    """
    if not filename:
        return "unnamed_file"

    # Convert to string and strip whitespace
    clean_name = str(filename).strip()

    if not clean_name:
        return "unnamed_file"

    # Replace problematic characters with safe alternatives
    replacements = {
        # Path traversal prevention
        "../": "",
        "./": "",
        "..\\": "",
        ".\\": "",
        # Filesystem-unsafe characters
        "<": "_",
        ">": "_",
        ":": "_",
        '"': "_",
        "|": "_",
        "?": "_",
        "*": "_",
        # URL-unsafe characters
        " ": "_",
        "#": "_",
        "%": "_",
        "&": "_and_",
        "+": "_plus_",
        "=": "_eq_",
        "[": "_",
        "]": "_",
        "{": "_",
        "}": "_",
        "@": "_at_",
        "!": "_",
        "$": "_",
        "'": "_",
        "`": "_",
        "~": "_",
    }

    # Apply replacements
    for char, replacement in replacements.items():
        clean_name = clean_name.replace(char, replacement)

    # Remove any remaining control characters
    clean_name = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", clean_name)

    # Collapse multiple underscores
    clean_name = re.sub(r"_+", "_", clean_name)

    # Remove leading/trailing underscores and dots
    clean_name = clean_name.strip("._")

    # Ensure filename isn't empty after cleaning
    if not clean_name:
        clean_name = "sanitized_file"

    # Prevent reserved names (Windows)
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    name_without_ext = clean_name
    extension = ""

    if "." in clean_name:
        parts = clean_name.rsplit(".", 1)
        if len(parts) == 2:
            name_without_ext, extension = parts
            extension = "." + extension

    if name_without_ext.upper() in reserved_names:
        name_without_ext = f"safe_{name_without_ext}"

    clean_name = name_without_ext + extension

    # Truncate if too long, preserving extension
    if len(clean_name) > max_length:
        if extension:
            max_name_length = max_length - len(extension)
            clean_name = clean_name[:max_name_length] + extension
        else:
            clean_name = clean_name[:max_length]

    return clean_name


def sanitize_xml_content(content: str) -> str:
    """
    Sanitize content for safe inclusion in XML/RSS feeds

    Args:
        content: Raw content string

    Returns:
        XML-safe content with proper escaping
    """
    if not content:
        return ""

    # HTML/XML escape
    safe_content = html.escape(str(content))

    # Remove or replace potentially problematic characters
    # Control characters (except tab, newline, carriage return)
    safe_content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", safe_content)

    # Normalize whitespace
    safe_content = re.sub(r"\s+", " ", safe_content)

    return safe_content.strip()


def sanitize_url_component(component: str) -> str:
    """
    Sanitize a URL component for safe inclusion in URLs

    Args:
        component: URL component to sanitize

    Returns:
        URL-encoded safe component
    """
    if not component:
        return ""

    # URL encode the component
    safe_component = urllib.parse.quote(str(component), safe="")

    return safe_component


def create_safe_slug(text: str, max_length: int = 50) -> str:
    """
    Create a URL-safe slug from text

    Args:
        text: Input text
        max_length: Maximum length for slug

    Returns:
        Safe slug suitable for URLs and filenames
    """
    if not text:
        return "unnamed"

    # Convert to lowercase
    slug = str(text).lower()

    # Replace spaces and special characters with hyphens
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Truncate if needed
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug or "unnamed"


def scrub_secrets_from_text(text: str) -> str:
    """
    Remove or mask sensitive information from text for safe logging

    Args:
        text: Text that may contain sensitive information

    Returns:
        Text with sensitive information masked
    """
    if not text:
        return text

    scrubbed = str(text)

    # Apply each sensitive pattern
    for pattern in SENSITIVE_PATTERNS:
        scrubbed = re.sub(
            pattern,
            lambda m: m.group(0).replace(m.group(1), "*" * len(m.group(1))),
            scrubbed,
            flags=re.IGNORECASE,
        )

    return scrubbed


def scrub_secrets_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively scrub sensitive information from dictionary

    Args:
        data: Dictionary that may contain sensitive information

    Returns:
        Dictionary with sensitive values masked
    """
    if not isinstance(data, dict):
        return data

    scrubbed = {}
    sensitive_keys = {
        "password",
        "pass",
        "pwd",
        "secret",
        "token",
        "key",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "credential",
        "credentials",
    }

    for key, value in data.items():
        key_lower = str(key).lower()

        if any(sensitive in key_lower for sensitive in sensitive_keys):
            # Mask sensitive values
            if isinstance(value, str) and value:
                scrubbed[key] = "*" * min(len(value), 8)
            else:
                scrubbed[key] = "[REDACTED]"
        elif isinstance(value, dict):
            # Recursively process nested dictionaries
            scrubbed[key] = scrub_secrets_from_dict(value)
        elif isinstance(value, str):
            # Apply text scrubbing to string values
            scrubbed[key] = scrub_secrets_from_text(value)
        else:
            scrubbed[key] = value

    return scrubbed


def safe_path_join(*components) -> Path:
    """
    Safely join path components, preventing directory traversal

    Args:
        components: Path components to join

    Returns:
        Safe Path object

    Raises:
        ValueError: If path traversal attempt is detected
    """
    # Start with first component
    if not components:
        return Path(".")

    result_path = Path(components[0])

    # Process remaining components
    for component in components[1:]:
        if not component:
            continue

        component_str = str(component)

        # Check for path traversal attempts
        if (
            ".." in component_str
            or component_str.startswith("/")
            or ":" in component_str
        ):
            raise ValueError(
                f"Potential path traversal detected in component: {component_str}"
            )

        # Sanitize the component
        safe_component = sanitize_filename(component_str)
        result_path = result_path / safe_component

    return result_path


def validate_file_path(
    file_path: Union[str, Path], allowed_dirs: Optional[list] = None
) -> bool:
    """
    Validate that a file path is safe and within allowed directories

    Args:
        file_path: Path to validate
        allowed_dirs: List of allowed base directories (optional)

    Returns:
        True if path is safe, False otherwise
    """
    try:
        path = Path(file_path).resolve()

        # Check if path exists and is a file
        if not path.exists() or not path.is_file():
            return False

        # Check against allowed directories if specified
        if allowed_dirs:
            allowed_paths = [Path(d).resolve() for d in allowed_dirs]
            if not any(str(path).startswith(str(allowed)) for allowed in allowed_paths):
                return False

        # Additional security checks
        path_str = str(path)

        # Check for suspicious patterns
        suspicious_patterns = [
            "..",
            "/etc/",
            "/proc/",
            "/sys/",
            "/dev/",
            "passwd",
            "shadow",
            "hosts",
            ".ssh/",
            ".env",
        ]

        if any(pattern in path_str.lower() for pattern in suspicious_patterns):
            return False

        return True

    except Exception as e:
        logger.warning(f"Path validation failed for {file_path}: {e}")
        return False


# Convenience functions for common use cases
def safe_digest_filename(topic: str, timestamp: str) -> str:
    """Create safe filename for digest files"""
    safe_topic = create_safe_slug(topic)
    safe_timestamp = sanitize_filename(timestamp)
    return f"{safe_topic}_digest_{safe_timestamp}.md"


def safe_audio_filename(topic: str, timestamp: str, enhanced: bool = False) -> str:
    """Create safe filename for audio files"""
    safe_topic = create_safe_slug(topic)
    safe_timestamp = sanitize_filename(timestamp)
    suffix = "_enhanced" if enhanced else ""
    return f"{safe_topic}_digest_{safe_timestamp}{suffix}.mp3"


# Centralized filename format functions
def create_topic_digest_filename(topic: str, timestamp: str) -> str:
    """
    Create standardized topic digest filename

    Args:
        topic: Topic name (will be slugified)
        timestamp: Timestamp string in YYYYMMDD_HHMMSS format

    Returns:
        Standardized filename: {topic}_digest_{timestamp}.md
    """
    safe_topic = create_safe_slug(topic)
    return f"{safe_topic}_digest_{timestamp}.md"


def create_topic_mp3_filename(
    topic: str, timestamp: str, enhanced: bool = False
) -> str:
    """
    Create standardized topic MP3 filename

    Args:
        topic: Topic name (will be slugified)
        timestamp: Timestamp string in YYYYMMDD_HHMMSS format
        enhanced: Whether this is an enhanced version

    Returns:
        Standardized filename: {topic}_digest_{timestamp}[_enhanced].mp3
    """
    safe_topic = create_safe_slug(topic)
    suffix = "_enhanced" if enhanced else ""
    return f"{safe_topic}_digest_{timestamp}{suffix}.mp3"


def create_topic_pattern() -> re.Pattern:
    """
    Create compiled regex pattern for topic digest files

    Returns:
        Compiled regex pattern that matches: {topic}_digest_{timestamp}.md
        Supports both hyphens and underscores in topic names for backward compatibility
        Groups: (topic, timestamp)
    """
    return re.compile(r"^([A-Za-z0-9_-]+)_digest_(\d{8}_\d{6})\.md$")


def create_topic_mp3_patterns() -> tuple[re.Pattern, re.Pattern]:
    """
    Create compiled regex patterns for topic MP3 files

    Returns:
        Tuple of (topic_pattern, legacy_pattern) for matching MP3 files
        topic_pattern: matches {topic}_digest_{timestamp}[_enhanced].mp3
        legacy_pattern: matches complete_topic_digest_{timestamp}[_enhanced].mp3
        Both support groups: (topic/timestamp, enhanced_suffix)
    """
    topic_pattern = re.compile(
        r"^([A-Za-z0-9_-]+)_digest_(\d{8}_\d{6})(_enhanced)?\.mp3$"
    )
    legacy_pattern = re.compile(
        r"^complete_topic_digest_(\d{8}_\d{6})(_enhanced)?\.mp3$"
    )
    return topic_pattern, legacy_pattern


def create_topic_file_pattern() -> re.Pattern:
    """
    Create compiled regex pattern for topic digest files (any extension)

    Returns:
        Compiled regex pattern that matches: {topic}_digest_{timestamp}.{ext}
        Supports both hyphens and underscores in topic names for backward compatibility
        Groups: (topic, timestamp, extension)
    """
    return re.compile(r"^([A-Za-z0-9_-]+)_digest_(\d{8}_\d{6})\.(md|mp3|json)$")


def safe_log_message(message: str) -> str:
    """Prepare message for safe logging"""
    return scrub_secrets_from_text(str(message))


# Export commonly used functions
__all__ = [
    "sanitize_filename",
    "sanitize_xml_content",
    "sanitize_url_component",
    "create_safe_slug",
    "scrub_secrets_from_text",
    "scrub_secrets_from_dict",
    "safe_path_join",
    "validate_file_path",
    "safe_digest_filename",
    "safe_audio_filename",
    "safe_log_message",
    "create_topic_digest_filename",
    "create_topic_mp3_filename",
    "create_topic_pattern",
    "create_topic_mp3_patterns",
    "create_topic_file_pattern",
]
