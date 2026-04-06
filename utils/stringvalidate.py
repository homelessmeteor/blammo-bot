import logging
import re

from log.loggers.custom_format import CustomFormatter  # for level colors

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter1 = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s : %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)
file_handler = logging.FileHandler("logs.log")
file_handler.setFormatter(formatter1)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(CustomFormatter())

logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# TODO: Add logging

# The purpose of this file is to provide a fast function that can be used to
# make sure a string is safe to chat (i.e. won't get automodded or be cause for
# concern). This is done by checking the string against a list of banned words
# and phrases, and taking the appropriate action if a match is found.

# Example: 1488 --> 1,488

def check_string_safety(content: str) -> bool:
    """
    Check if a string is safe for submission.
    Returns True if safe, False if contains problematic content.
    Based on the proven implementation from submit.py
    """
    # Check that input is a string:
    if not isinstance(content, str):
        logger.warning(f"String safety check failed: content is not a string: {content}")
        return False
    
    # Empty string is not allowed
    if not content or content.strip() == "":
        return False
    
    # Check string length (reasonable limit for reports)
    if len(content) > 500:
        logger.warning(f"String safety check failed: string too long ({len(content)} chars)")
        return False
    
    # Special check for ".." but allow "..." and more dots (from submit.py)
    # Block patterns with exactly two dots but allow three or more
    if re.search(r'(^|[^.])\.\.[^.]', content) or content == ".." or content.startswith("../") or content.endswith("/.."):
        # This matches ".." that is not part of "..." or longer sequences
        logger.warning(f"String safety check failed: content contains suspicious '..' pattern: {content}")
        return False
    
    # Check for dangerous patterns (adapted from submit.py)
    dangerous_patterns = [
        "__init__",
        "__class__", 
        "__globals__",
        "__builtins__",
        "eval(",
        "exec(",
        "open(",
        "0x27",
        "0x3f", 
        "0x5c",
        "0x07",
        "0x08",
        "0x0c",
        "0x22",
        "0x0a",
        "0x0d", 
        "0x09",
        "0x0b",
        "\n",
        "\\n",
        "\r",
        "\\r",
        "\f",
        "\\f",
        "&#10;",
        "&#41;",
        "&#40;", 
        "&#32;",
        "&#9;",
        "&Tab;",
    ]
    
    if any(pattern in content for pattern in dangerous_patterns):
        logger.warning(f"String safety check failed: content contains suspicious string: {content}")
        return False
    
    return True
