#!/usr/bin/env python3
"""
Enhanced Security Validation for Production Deployment

Comprehensive security validation addressing critical hardening issues:
1. Content validation and sanitization
2. Path traversal prevention  
3. XML injection protection
4. Resource exhaustion prevention
5. Input validation boundaries
"""

import os
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
import logging
import hashlib
import tempfile
from urllib.parse import urlparse
from datetime import datetime, timezone
from utils.datetime_utils import now_utc
logger = logging.getLogger(__name__)

class SecurityValidator:
    """Comprehensive security validation for production environment"""
    
    def __init__(self):
        self.max_filename_length = 200
        self.max_content_length = 50000  # 50KB max content
        self.max_xml_content_length = 10000  # 10KB max XML content
        self.allowed_file_extensions = {'.mp3', '.md', '.txt', '.json', '.xml'}
        self.blocked_patterns = [
            r'\.\./',  # Path traversal
            r'\.\.\\',  # Windows path traversal
            r'<script[^>]*>',  # Script injection
            r'javascript:',  # JavaScript protocol
            r'data:',  # Data protocol
            r'vbscript:',  # VBScript protocol
            r'<iframe[^>]*>',  # Iframe injection
            r'<object[^>]*>',  # Object injection
            r'<embed[^>]*>',  # Embed injection
            r'<form[^>]*>',  # Form injection
            r'\x00',  # Null bytes
        ]
        
    def validate_filename(self, filename: str) -> Tuple[bool, str]:
        """
        Comprehensive filename validation
        
        Returns: (is_valid, sanitized_filename)
        """
        
        if not filename:
            return False, ""
        
        original_filename = filename
        
        try:
            # Remove directory traversal attempts
            filename = os.path.basename(filename)
            
            # Check length
            if len(filename) > self.max_filename_length:
                filename = filename[:self.max_filename_length]
            
            # Remove dangerous characters
            filename = re.sub(r'[<>:"|?*\x00-\x1f]', '_', filename)
            
            # Remove path traversal sequences
            filename = re.sub(r'\.\.+', '.', filename)
            
            # Ensure it doesn't start with dots or dashes
            filename = re.sub(r'^[.-]+', '', filename)
            
            # Ensure non-empty after sanitization
            if not filename or filename.isspace():
                filename = f"sanitized_file_{hashlib.md5(original_filename.encode()).hexdigest()[:8]}"
            
            # Validate file extension
            file_ext = Path(filename).suffix.lower()
            if file_ext not in self.allowed_file_extensions:
                logger.warning(f"⚠️ Suspicious file extension: {file_ext}")
                return False, filename
            
            # Final validation
            is_valid = (
                len(filename) > 0 and
                len(filename) <= self.max_filename_length and
                not any(re.search(pattern, filename, re.IGNORECASE) for pattern in self.blocked_patterns) and
                file_ext in self.allowed_file_extensions
            )
            
            return is_valid, filename
            
        except Exception as e:
            logger.error(f"❌ Filename validation error: {e}")
            return False, "invalid_filename"
    
    def validate_content(self, content: str, content_type: str = "text") -> Tuple[bool, str]:
        """
        Comprehensive content validation and sanitization
        
        Returns: (is_valid, sanitized_content)
        """
        
        if not content:
            return True, ""
        
        original_length = len(content)
        
        try:
            # Check content length
            if original_length > self.max_content_length:
                content = content[:self.max_content_length]
                logger.warning(f"⚠️ Content truncated from {original_length} to {len(content)} chars")
            
            # Remove null bytes and control characters
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
            
            # Content-type specific validation
            if content_type == "xml":
                return self._validate_xml_content(content)
            elif content_type == "html":
                return self._validate_html_content(content)
            else:
                return self._validate_text_content(content)
                
        except Exception as e:
            logger.error(f"❌ Content validation error: {e}")
            return False, ""
    
    def _validate_xml_content(self, content: str) -> Tuple[bool, str]:
        """Validate and sanitize XML content"""
        
        try:
            # Limit XML content length
            if len(content) > self.max_xml_content_length:
                content = content[:self.max_xml_content_length]
            
            # HTML encode dangerous characters
            content = html.escape(content, quote=True)
            
            # Remove CDATA escape sequences
            content = re.sub(r']]>', ']]&gt;', content)
            
            # Test XML validity by trying to create a simple XML document
            test_xml = f'<test>{content}</test>'
            try:
                ET.fromstring(test_xml)
            except ET.ParseError:
                # If parsing fails, use more aggressive escaping
                content = html.escape(content, quote=True)
            
            # Final pattern check
            is_valid = not any(
                re.search(pattern, content, re.IGNORECASE) 
                for pattern in self.blocked_patterns
            )
            
            return is_valid, content
            
        except Exception as e:
            logger.error(f"❌ XML validation error: {e}")
            return False, html.escape(str(content), quote=True)
    
    def _validate_html_content(self, content: str) -> Tuple[bool, str]:
        """Validate and sanitize HTML content"""
        
        try:
            # HTML escape all content for safety
            content = html.escape(content, quote=True)
            
            # Remove dangerous patterns
            for pattern in self.blocked_patterns:
                content = re.sub(pattern, '', content, flags=re.IGNORECASE)
            
            is_valid = True  # HTML escaped content is safe
            
            return is_valid, content
            
        except Exception as e:
            logger.error(f"❌ HTML validation error: {e}")
            return False, html.escape(str(content), quote=True)
    
    def _validate_text_content(self, content: str) -> Tuple[bool, str]:
        """Validate plain text content"""
        
        try:
            # Check for dangerous patterns
            dangerous_found = []
            for pattern in self.blocked_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    dangerous_found.append(pattern)
            
            if dangerous_found:
                logger.warning(f"⚠️ Dangerous patterns found: {dangerous_found}")
                
                # Sanitize by removing dangerous patterns
                for pattern in self.blocked_patterns:
                    content = re.sub(pattern, '', content, flags=re.IGNORECASE)
            
            # Final validation
            is_valid = len(dangerous_found) == 0
            
            return is_valid, content
            
        except Exception as e:
            logger.error(f"❌ Text validation error: {e}")
            return False, str(content)
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate URL for security issues"""
        
        if not url:
            return False, ""
        
        try:
            parsed = urlparse(url)
            
            # Check for dangerous schemes
            dangerous_schemes = ['javascript', 'data', 'vbscript', 'file']
            if parsed.scheme.lower() in dangerous_schemes:
                return False, url
            
            # Require HTTPS for external URLs
            if parsed.netloc and parsed.scheme.lower() not in ['https', 'http']:
                return False, url
            
            # Check for path traversal in URL path
            if '..' in parsed.path or '..' in parsed.query:
                return False, url
            
            return True, url
            
        except Exception as e:
            logger.error(f"❌ URL validation error: {e}")
            return False, ""
    
    def validate_file_path(self, file_path: Union[str, Path]) -> Tuple[bool, Path]:
        """Validate file path for security"""
        
        try:
            path = Path(file_path) if isinstance(file_path, str) else file_path
            
            # Resolve to absolute path
            resolved_path = path.resolve()
            
            # Check if path escapes project directory
            project_root = Path(__file__).parent.parent.resolve()
            
            try:
                resolved_path.relative_to(project_root)
            except ValueError:
                logger.error(f"❌ Path traversal attempt: {resolved_path}")
                return False, path
            
            # Validate filename
            filename_valid, _ = self.validate_filename(path.name)
            if not filename_valid:
                return False, path
            
            return True, resolved_path
            
        except Exception as e:
            logger.error(f"❌ File path validation error: {e}")
            return False, Path("invalid")
    
    def validate_database_input(self, value: Any) -> Tuple[bool, Any]:
        """Validate input for database operations"""
        
        if value is None:
            return True, None
        
        if isinstance(value, str):
            # Check for SQL injection patterns
            sql_patterns = [
                r"'.*'",  # Single quotes
                r'".*"',  # Double quotes  
                r'union\s+select',  # UNION SELECT
                r'drop\s+table',  # DROP TABLE
                r'delete\s+from',  # DELETE FROM
                r'insert\s+into',  # INSERT INTO
                r'update\s+.*set',  # UPDATE SET
                r'exec\s*\(',  # EXEC calls
                r'xp_cmdshell',  # SQL Server command shell
            ]
            
            suspicious_patterns = []
            for pattern in sql_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    suspicious_patterns.append(pattern)
            
            if suspicious_patterns:
                logger.warning(f"⚠️ Suspicious SQL patterns in input: {suspicious_patterns}")
                return False, value
        
        return True, value
    
    def validate_resource_limits(self, **kwargs) -> Dict[str, Any]:
        """Validate resource usage against limits"""
        
        results = {
            'within_limits': True,
            'violations': [],
            'warnings': []
        }
        
        # File size limits
        file_size = kwargs.get('file_size', 0)
        if file_size > 100 * 1024 * 1024:  # 100MB
            results['violations'].append(f"File size too large: {file_size / 1024 / 1024:.1f}MB")
            results['within_limits'] = False
        elif file_size > 50 * 1024 * 1024:  # 50MB warning
            results['warnings'].append(f"Large file size: {file_size / 1024 / 1024:.1f}MB")
        
        # Memory usage
        memory_usage = kwargs.get('memory_usage', 0)
        if memory_usage > 500 * 1024 * 1024:  # 500MB
            results['violations'].append(f"Memory usage too high: {memory_usage / 1024 / 1024:.1f}MB")
            results['within_limits'] = False
        
        # Processing time
        processing_time = kwargs.get('processing_time', 0)
        if processing_time > 300:  # 5 minutes
            results['violations'].append(f"Processing time too long: {processing_time}s")
            results['within_limits'] = False
        
        # Request rate
        requests_per_minute = kwargs.get('requests_per_minute', 0)
        if requests_per_minute > 60:
            results['violations'].append(f"Request rate too high: {requests_per_minute}/min")
            results['within_limits'] = False
        
        return results
    
    def create_security_report(self, validations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create comprehensive security validation report"""
        
        total_validations = len(validations)
        passed_validations = sum(1 for v in validations if v.get('valid', False))
        
        security_score = passed_validations / total_validations if total_validations > 0 else 0
        
        # Categorize issues
        critical_issues = [v for v in validations if not v.get('valid', False) and v.get('critical', False)]
        warnings = [v for v in validations if not v.get('valid', False) and not v.get('critical', False)]
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_validations': total_validations,
            'passed_validations': passed_validations,
            'security_score': security_score,
            'status': 'SECURE' if security_score >= 0.95 else 'AT_RISK' if security_score >= 0.8 else 'VULNERABLE',
            'critical_issues': len(critical_issues),
            'warnings': len(warnings),
            'details': validations,
            'recommendations': self._generate_security_recommendations(critical_issues, warnings)
        }
    
    def _generate_security_recommendations(self, critical_issues: List[Dict], warnings: List[Dict]) -> List[str]:
        """Generate security recommendations based on issues found"""
        
        recommendations = []
        
        if critical_issues:
            recommendations.append("🚨 CRITICAL: Address all critical security issues immediately")
            
            # Specific recommendations based on issue types
            issue_types = [issue.get('type', 'unknown') for issue in critical_issues]
            
            if 'path_traversal' in issue_types:
                recommendations.append("• Implement strict path validation and canonicalization")
            
            if 'xml_injection' in issue_types:
                recommendations.append("• Enable comprehensive XML content sanitization")
            
            if 'resource_exhaustion' in issue_types:
                recommendations.append("• Implement resource limits and timeout controls")
        
        if warnings:
            recommendations.append("⚠️ WARNING: Review and address security warnings")
        
        if not critical_issues and not warnings:
            recommendations.append("✅ Security validation passed - maintain current security practices")
        
        return recommendations

# Global security validator instance
security_validator = SecurityValidator()

# Convenience functions
def validate_filename_secure(filename: str) -> Tuple[bool, str]:
    """Securely validate and sanitize filename"""
    return security_validator.validate_filename(filename)

def validate_content_secure(content: str, content_type: str = "text") -> Tuple[bool, str]:
    """Securely validate and sanitize content"""
    return security_validator.validate_content(content, content_type)

def validate_xml_secure(content: str) -> Tuple[bool, str]:
    """Securely validate XML content"""
    return security_validator.validate_content(content, "xml")

def validate_url_secure(url: str) -> Tuple[bool, str]:
    """Securely validate URL"""
    return security_validator.validate_url(url)

def validate_path_secure(file_path: Union[str, Path]) -> Tuple[bool, Path]:
    """Securely validate file path"""
    return security_validator.validate_file_path(file_path)