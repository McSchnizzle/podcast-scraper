#!/usr/bin/env python3
"""
Prose Validation and Rewriting System
Ensures digest content is proper prose suitable for TTS, not bullet lists or markdown
"""

import re
import logging
import openai
import os
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

class ProseValidator:
    def __init__(self):
        """Initialize with OpenAI client for rewriting capabilities"""
        self.client = None
        self.api_available = False
        
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and len(api_key.strip()) >= 10:
            try:
                openai.api_key = api_key.strip()
                self.client = openai
                self.api_available = True
                logger.info("✅ Prose validator OpenAI client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client for prose validation: {e}")
        else:
            logger.warning("OpenAI API not available for prose rewriting")

    def validate_prose(self, text: str) -> Tuple[bool, List[str]]:
        """
        Validate that text is proper prose suitable for TTS narration
        Returns (is_valid, list_of_issues)
        """
        issues = []
        
        # Remove empty lines and normalize whitespace
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        if not lines:
            issues.append("Text is empty")
            return False, issues
        
        # Check for bullet points and lists
        bullet_patterns = [
            r'^\s*[-*•]\s+',  # Bullet points
            r'^\s*\d+\.\s+',  # Numbered lists
            r'^\s*[a-zA-Z]\.\s+',  # Letter lists
            r'^\s*[ivx]+\.\s+',  # Roman numeral lists
        ]
        
        bullet_lines = 0
        for line in lines:
            for pattern in bullet_patterns:
                if re.match(pattern, line):
                    bullet_lines += 1
                    break
        
        # If more than 20% of lines are bullets, it's not prose
        if bullet_lines / len(lines) > 0.2:
            issues.append(f"Contains too many bullet points ({bullet_lines}/{len(lines)} lines)")
        
        # Check for markdown headers
        header_lines = 0
        for line in lines:
            if re.match(r'^#+\s+', line) or line.isupper() and len(line) > 3:
                header_lines += 1
        
        if header_lines / len(lines) > 0.1:
            issues.append(f"Contains too many headers ({header_lines}/{len(lines)} lines)")
        
        # Check for too many short lines (likely lists)
        short_lines = sum(1 for line in lines if len(line) < 30)
        if short_lines / len(lines) > 0.4:
            issues.append(f"Too many short lines ({short_lines}/{len(lines)}), likely fragmented text")
        
        # Check for colon-heavy formatting (like definitions)
        colon_lines = sum(1 for line in lines if ':' in line and len(line) < 100)
        if colon_lines / len(lines) > 0.3:
            issues.append(f"Too many colon-separated items ({colon_lines}/{len(lines)}), likely definitions or lists")
        
        # Check for excessive capitalization
        caps_lines = sum(1 for line in lines if sum(c.isupper() for c in line) / max(len(line), 1) > 0.3)
        if caps_lines / len(lines) > 0.2:
            issues.append(f"Excessive capitalization in {caps_lines}/{len(lines)} lines")
        
        # Check average sentence length (prose should have varied sentence lengths)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_sentence_length < 8:
                issues.append(f"Average sentence too short ({avg_sentence_length:.1f} words), likely fragmented")
        
        # Check for markdown formatting remnants
        markdown_patterns = [
            r'\*\*.*?\*\*',  # Bold
            r'\*.*?\*',      # Italic
            r'`.*?`',        # Code
            r'\[.*?\]\(.*?\)',  # Links
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
        Use OpenAI to rewrite non-prose text into smooth narrative suitable for TTS
        """
        if not self.api_available:
            logger.error("OpenAI API not available for prose rewriting")
            return None
        
        for attempt in range(max_attempts):
            try:
                prompt = f"""
Rewrite the following content as smooth, flowing prose suitable for text-to-speech narration. 

Requirements:
- Convert bullet points and lists into natural sentences
- Remove markdown formatting
- Create coherent paragraphs with varied sentence structure
- Maintain all factual information
- Use transitions between topics
- Write in a conversational but professional tone
- Ensure it flows naturally when read aloud

Original content:
{text}

Rewritten prose:"""

                response = self.client.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000,
                    temperature=0.3
                )
                
                rewritten = response.choices[0].message.content.strip()
                
                # Validate the rewritten text
                is_valid, issues = self.validate_prose(rewritten)
                if is_valid:
                    logger.info(f"✅ Successfully rewrote text to prose (attempt {attempt + 1})")
                    return rewritten
                else:
                    logger.warning(f"Rewrite attempt {attempt + 1} still has issues: {', '.join(issues)}")
                    if attempt == max_attempts - 1:
                        logger.error("Failed to create valid prose after maximum attempts")
                        return None
                        
            except Exception as e:
                logger.error(f"Error rewriting to prose (attempt {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    return None
        
        return None

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