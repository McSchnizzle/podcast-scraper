#!/usr/bin/env python3
"""
Prose Validation and Rewriting System - GPT-5 Implementation
Ensures digest content is proper prose suitable for TTS, not bullet lists or markdown
"""

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import openai

from utils.datetime_utils import now_utc
from utils.openai_helpers import (
    call_openai_with_backoff,
    generate_idempotency_key,
    get_json_schema,
)

logger = logging.getLogger(__name__)


class ProseValidator:
    def __init__(self):
        """Initialize with GPT-5 client for rewriting capabilities"""
        self.client = None
        self.api_available = False

        # Load configuration
        from config import config

        self.model = config.GPT5_MODELS["validator"]
        self.max_output_tokens = config.OPENAI_TOKENS["validator"]
        self.reasoning_effort = config.REASONING_EFFORT["validator"]
        self.feature_enabled = config.FEATURE_FLAGS["use_gpt5_validator"]

        # Check for mock mode
        self.mock_mode = os.getenv("MOCK_OPENAI") == "1" or os.getenv("CI_SMOKE") == "1"

        if self.mock_mode:
            logger.info("🧪 MOCK MODE: Using mock prose validation")
            self.client = None
            self.api_available = True
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key and len(api_key.strip()) >= 10:
                try:
                    from openai import OpenAI

                    self.client = OpenAI(api_key=api_key.strip())
                    self.api_available = True
                    logger.info(f"✅ Prose validator initialized with {self.model}")
                except Exception as e:
                    logger.error(
                        f"Failed to initialize OpenAI client for prose validation: {e}"
                    )
            else:
                logger.warning("OpenAI API not available for prose rewriting")

        # Log configuration
        logger.info(
            f"component=validator model={self.model} max_output_tokens={self.max_output_tokens} "
            f"reasoning={self.reasoning_effort} feature_enabled={self.feature_enabled}"
        )

    def validate_prose(self, text: str) -> Tuple[bool, List[str]]:
        """
        Validate that text is proper prose suitable for TTS narration
        Returns (is_valid, list_of_issues)
        """
        issues = []

        # Remove empty lines and normalize whitespace
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

        if not lines:
            issues.append("Text is empty")
            return False, issues

        # Check for bullet points and lists
        bullet_patterns = [
            r"^\s*[-*•]\s+",  # Bullet points
            r"^\s*\d+\.\s+",  # Numbered lists
            r"^\s*[a-zA-Z]\.\s+",  # Letter lists
            r"^\s*[ivx]+\.\s+",  # Roman numeral lists
        ]

        bullet_lines = 0
        for line in lines:
            for pattern in bullet_patterns:
                if re.match(pattern, line):
                    bullet_lines += 1
                    break

        # If more than 20% of lines are bullets, it's not prose
        if bullet_lines / len(lines) > 0.2:
            issues.append(
                f"Contains too many bullet points ({bullet_lines}/{len(lines)} lines)"
            )

        # Check for markdown headers
        header_lines = 0
        for line in lines:
            if re.match(r"^#+\s+", line) or line.isupper() and len(line) > 3:
                header_lines += 1

        if header_lines / len(lines) > 0.1:
            issues.append(
                f"Contains too many headers ({header_lines}/{len(lines)} lines)"
            )

        # Check for too many short lines (likely lists)
        short_lines = sum(1 for line in lines if len(line) < 30)
        if short_lines / len(lines) > 0.4:
            issues.append(
                f"Too many short lines ({short_lines}/{len(lines)}), likely fragmented text"
            )

        # Check for colon-heavy formatting (like definitions)
        colon_lines = sum(1 for line in lines if ":" in line and len(line) < 100)
        if colon_lines / len(lines) > 0.3:
            issues.append(
                f"Too many colon-separated items ({colon_lines}/{len(lines)}), likely definitions or lists"
            )

        # Check for excessive capitalization
        caps_lines = sum(
            1
            for line in lines
            if sum(c.isupper() for c in line) / max(len(line), 1) > 0.3
        )
        if caps_lines / len(lines) > 0.2:
            issues.append(
                f"Excessive capitalization in {caps_lines}/{len(lines)} lines"
            )

        # Check average sentence length (prose should have varied sentence lengths)
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(
                sentences
            )
            if avg_sentence_length < 8:
                issues.append(
                    f"Average sentence too short ({avg_sentence_length:.1f} words), likely fragmented"
                )

        # Check for markdown formatting remnants
        markdown_patterns = [
            r"\*\*.*?\*\*",  # Bold
            r"\*.*?\*",  # Italic
            r"`.*?`",  # Code
            r"\[.*?\]\(.*?\)",  # Links
        ]

        markdown_count = 0
        for pattern in markdown_patterns:
            markdown_count += len(re.findall(pattern, text))

        if markdown_count > 5:
            issues.append(f"Contains markdown formatting ({markdown_count} instances)")

        is_valid = len(issues) == 0
        return is_valid, issues

    def rewrite_to_prose(self, text: str, max_attempts: int = 2) -> Optional[str]:
        """
        Use GPT-5 to rewrite non-prose text into smooth narrative suitable for TTS
        """
        if not self.feature_enabled:
            logger.warning("GPT-5 prose validation disabled by feature flag")
            return text  # Return original text if disabled

        if not self.api_available:
            logger.error("OpenAI API not available for prose rewriting")
            return None

        # Mock mode - return lightly processed text
        if self.mock_mode:
            logger.info("🧪 MOCK: Performing mock prose validation")
            return self._mock_prose_rewrite(text)

        for attempt in range(max_attempts):
            try:
                system_prompt = """You are an expert prose writer specializing in creating TTS-friendly content. Your task is to transform any text into smooth, flowing prose suitable for text-to-speech narration."""

                user_prompt = f"""
Rewrite the following content as smooth, flowing prose suitable for text-to-speech narration.

Requirements:
- Convert bullet points and lists into natural sentences
- Remove all markdown formatting (headers, bold, italics, etc.)
- Create coherent paragraphs with varied sentence structure
- Maintain all factual information and key points
- Use natural transitions between topics
- Write in a conversational but professional tone
- Ensure it flows naturally when read aloud
- Identify any content that cannot be converted to TTS-friendly prose

Original content:
{text}

Provide your response in the specified JSON format."""

                # Generate run ID for idempotency
                run_id = generate_idempotency_key(text[:100], str(attempt), self.model)

                # Call GPT-5 with structured output
                logger.info(
                    f"🤖 Rewriting to prose (attempt {attempt + 1}): {len(text)} chars"
                )

                result = call_openai_with_backoff(
                    client=self.client,
                    component="validator",
                    run_id=run_id,
                    idempotency_key=run_id,
                    model=self.model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    reasoning={"effort": self.reasoning_effort},
                    max_output_tokens=self.max_output_tokens,
                    text={"format": get_json_schema("validator")},
                )

                # Parse structured response
                validation_data = result.to_json()

                is_valid = validation_data.get("is_valid", False)
                error_codes = validation_data.get("error_codes", [])
                corrected_text = validation_data.get("corrected_text", text)
                reasoning = validation_data.get("reasoning", "No reasoning provided")

                if is_valid and corrected_text:
                    # Double-check with our own validation
                    local_valid, local_issues = self.validate_prose(corrected_text)
                    if local_valid:
                        logger.info(
                            f"✅ Successfully rewrote text to prose (attempt {attempt + 1})"
                        )
                        return corrected_text
                    else:
                        logger.warning(
                            f"GPT-5 marked as valid but local validation failed: {', '.join(local_issues)}"
                        )

                # Log issues for debugging
                if error_codes:
                    logger.warning(
                        f"Rewrite attempt {attempt + 1} has issues: {', '.join(error_codes)} - {reasoning}"
                    )
                else:
                    logger.warning(
                        f"Rewrite attempt {attempt + 1} failed validation - {reasoning}"
                    )

                if attempt == max_attempts - 1:
                    logger.error("Failed to create valid prose after maximum attempts")
                    return (
                        corrected_text if corrected_text else text
                    )  # Return best attempt

            except Exception as e:
                logger.error(f"Error rewriting to prose (attempt {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    return text  # Return original text if all attempts failed

        return text  # Fallback to original text

    def _mock_prose_rewrite(self, text: str) -> str:
        """
        Mock prose rewriting for testing environments
        Performs basic text cleaning to simulate rewriting
        """
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

        # Convert bullet points to sentences
        processed_lines = []
        for line in lines:
            # Remove bullet point markers
            line = re.sub(r"^[-*•]\s+", "", line)
            line = re.sub(r"^\d+\.\s+", "", line)
            line = re.sub(r"^[a-zA-Z]\.\s+", "", line)

            # Remove markdown headers
            line = re.sub(r"^#+\s+", "", line)

            # Remove markdown formatting
            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)  # Bold
            line = re.sub(r"\*(.*?)\*", r"\1", line)  # Italic
            line = re.sub(r"`(.*?)`", r"\1", line)  # Code
            line = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", line)  # Links

            if line:
                processed_lines.append(line)

        # Join into paragraphs
        result = ". ".join(processed_lines)
        if result and not result.endswith("."):
            result += "."

        return result

    def ensure_prose_quality(self, text: str) -> Tuple[bool, str, List[str]]:
        """
        Main method: validate text and rewrite if necessary
        Returns (success, final_text, issues_found)
        """
        # First validation
        is_valid, issues = self.validate_prose(text)

        if is_valid:
            logger.info("✅ Text already valid prose")
            return True, text, []

        logger.info(f"❌ Text validation failed: {', '.join(issues)}")

        # Attempt rewrite
        if not self.api_available:
            logger.error("Cannot rewrite - OpenAI API not available")
            return False, text, issues

        rewritten = self.rewrite_to_prose(text)
        if rewritten:
            # Final validation
            is_valid_final, final_issues = self.validate_prose(rewritten)
            if is_valid_final:
                return True, rewritten, []
            else:
                logger.error(f"Rewrite still invalid: {', '.join(final_issues)}")
                return False, rewritten, final_issues
        else:
            logger.error("Failed to rewrite text")
            return False, text, issues


def main():
    """Test the prose validator"""
    validator = ProseValidator()

    # Test with bullet points
    bullet_text = """
    • First item here
    • Second important point
    • Third consideration

    ## Next Section

    1. Numbered item
    2. Another point
    3. Final thought
    """

    success, result, issues = validator.ensure_prose_quality(bullet_text)
    print(f"Success: {success}")
    print(f"Issues: {issues}")
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
