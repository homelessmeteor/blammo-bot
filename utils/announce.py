import logging

from log.loggers.rotating_logger import get_rotating_logger

# Set up rotating logger with 10MB max size and 5 backup files
logger = get_rotating_logger(__name__)

# The purpose of this module is to provide a basic function to allow
# the bot to announce a message to the channel periodically.
# We do not need or want this functionality right now, but it may be useful
# in the future. Check with mods before enabling this feature.


MESSAGE_0 = "peepoHas 🪄 ✨ Submit trivia questions and scramble words using the \
    #submit command. Use the #help command to learn more."

MESSAGES = [
    'peepoHas 🪄✨ Submit trivia questions and scramble words using the \
        #submit command. Use the "#submit help" command to learn more.',
    'peepoHas 🪄✨ Type "#commands to get a list of all available commands.',
    "peepoHas 🪄✨ ",
]
