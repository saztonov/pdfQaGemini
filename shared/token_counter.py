"""Token counting utilities using tiktoken"""

import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Lazy load tiktoken to avoid import overhead
_encoding = None


def _get_encoding():
    """Get tiktoken encoding (lazy loaded)"""
    global _encoding
    if _encoding is None:
        try:
            import tiktoken

            # Use cl100k_base encoding (GPT-4, similar to Gemini)
            _encoding = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            logger.warning("tiktoken not installed, using fallback estimation")
            return None
    return _encoding


def count_tokens_text(text: str) -> int:
    """Count tokens in text string using tiktoken"""
    if not text:
        return 0

    encoding = _get_encoding()
    if encoding is None:
        # Fallback: ~4 chars per token
        return len(text) // 4

    try:
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Error counting tokens: {e}")
        return len(text) // 4


def count_tokens_file(file_path: Union[str, Path], encoding: str = "utf-8") -> Optional[int]:
    """Count tokens in a text file using tiktoken"""
    path = Path(file_path)
    if not path.exists():
        return None

    try:
        # Read file content
        text = path.read_text(encoding=encoding, errors="replace")
        return count_tokens_text(text)
    except Exception as e:
        logger.warning(f"Error reading file for token count: {e}")
        # Fallback: estimate from file size (~4 bytes per token)
        try:
            return path.stat().st_size // 4
        except Exception:
            return None


def count_tokens_bytes(data: bytes, encoding: str = "utf-8") -> int:
    """Count tokens in bytes data using tiktoken"""
    if not data:
        return 0

    try:
        text = data.decode(encoding, errors="replace")
        return count_tokens_text(text)
    except Exception as e:
        logger.warning(f"Error decoding bytes for token count: {e}")
        # Fallback: ~4 bytes per token
        return len(data) // 4
