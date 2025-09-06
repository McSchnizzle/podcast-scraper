#!/usr/bin/env python3
"""
Compatibility shim for legacy OpenAIScorer imports.
This module provides backward compatibility while encouraging migration.

DEPRECATED: This module will be removed in v2.0.0
Please migrate to: from openai_scorer import OpenAITopicScorer
"""

import warnings

from openai_scorer import OpenAITopicScorer

# Issue deprecation warning
warnings.warn(
    "OpenAIScorer is deprecated and will be removed in v2.0.0. "
    "Please use 'from openai_scorer import OpenAITopicScorer' instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Export with old name for compatibility
OpenAIScorer = OpenAITopicScorer
OpenAIRelevanceScorer = OpenAITopicScorer  # Additional legacy alias

__all__ = ["OpenAIScorer", "OpenAIRelevanceScorer"]
