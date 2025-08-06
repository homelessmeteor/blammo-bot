import logging

from log.loggers.rotating_logger import get_rotating_logger

# Set up rotating logger with 10MB max size and 5 backup files
logger = get_rotating_logger(__name__)

# TODO: Add logging

# The purpose of this file is to provide a fast function that can be used to
# make sure a string is safe to chat (i.e. won't get automodded or be cause for
# concern). This is done by checking the string against a list of banned words
# and phrases, and taking the appropriate action if a match is found.

# Example: 1488 --> 1,488
