#!/usr/bin/env python3
"""
Rotating Logger Configuration for BlammoBot

Provides centralized logging configuration with automatic log rotation.
This module replaces the scattered FileHandler configurations throughout
the codebase with a consistent RotatingFileHandler approach.

Features:
- Size-based log rotation (default: 10MB per file)
- Keeps multiple backup files (default: 5 backups)
- Consistent formatting across all modules
- Thread-safe logging for concurrent operations
"""

import logging
import logging.handlers
import os
from typing import Optional

from log.loggers.custom_format import CustomFormatter


def get_rotating_logger(
    name: str,
    log_file: str = "logs.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    log_level: int = logging.DEBUG
) -> logging.Logger:
    """
    Create a logger with rotating file handler and console output.
    
    Args:
        name: Logger name (typically __name__)
        log_file: Path to log file (default: "logs.log")
        max_bytes: Maximum size per log file in bytes (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        log_level: Logging level (default: DEBUG)
    
    Returns:
        Configured logger with rotating file handler
    """
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Avoid adding duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    # Create rotating file handler
    rotating_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    
    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s : %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )
    
    # Set formatters
    rotating_handler.setFormatter(file_formatter)
    console_handler.setFormatter(CustomFormatter())
    
    # Add handlers to logger
    logger.addHandler(rotating_handler)
    logger.addHandler(console_handler)
    
    return logger


def setup_bot_logging(
    log_file: str = "logs.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Setup centralized logging configuration for the entire bot.
    
    This function configures the root logger and can be called once
    at application startup to establish consistent logging across
    all modules.
    
    Args:
        log_file: Path to log file (default: "logs.log")
        max_bytes: Maximum size per log file in bytes (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create rotating file handler
    rotating_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    
    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s : %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )
    
    # Set formatters
    rotating_handler.setFormatter(file_formatter)
    console_handler.setFormatter(CustomFormatter())
    
    # Add handlers to root logger
    root_logger.addHandler(rotating_handler)
    root_logger.addHandler(console_handler)


def get_log_file_info(log_file: str = "logs.log") -> dict:
    """
    Get information about current log file and its rotated backups.
    
    Args:
        log_file: Path to primary log file
        
    Returns:
        Dictionary with log file information including sizes and dates
    """
    info = {
        'primary_file': log_file,
        'exists': False,
        'size_bytes': 0,
        'size_mb': 0.0,
        'backup_files': []
    }
    
    if os.path.exists(log_file):
        info['exists'] = True
        info['size_bytes'] = os.path.getsize(log_file)
        info['size_mb'] = info['size_bytes'] / (1024 * 1024)
        
        # Find backup files
        base_name = log_file
        backup_num = 1
        while True:
            backup_file = f"{base_name}.{backup_num}"
            if os.path.exists(backup_file):
                backup_size = os.path.getsize(backup_file)
                info['backup_files'].append({
                    'file': backup_file,
                    'size_bytes': backup_size,
                    'size_mb': backup_size / (1024 * 1024)
                })
                backup_num += 1
            else:
                break
    
    return info


def force_log_rotation(log_file: str = "logs.log") -> bool:
    """
    Force rotation of the current log file.
    
    This can be useful for manual log rotation or testing purposes.
    
    Args:
        log_file: Path to log file to rotate
        
    Returns:
        True if rotation was successful, False otherwise
    """
    try:
        # Get all loggers that might be using this file
        loggers_to_close = []
        
        for logger_name in logging.Logger.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    if handler.baseFilename == os.path.abspath(log_file):
                        loggers_to_close.append(handler)
        
        # Force rotation on all matching handlers
        for handler in loggers_to_close:
            handler.doRollover()
            
        return True
        
    except Exception as e:
        print(f"Error forcing log rotation: {e}")
        return False


# Convenience function for backward compatibility
def custom_logger(
    loglevel: int = logging.DEBUG,
    logfile: str = 'logs.log'
) -> logging.Logger:
    """
    Backward compatibility function that creates a rotating logger.
    
    This function maintains the same signature as the original custom_logger
    but uses rotating file handlers instead of basic file handlers.
    """
    import inspect
    
    # Get the calling function name for logger naming
    caller_name = inspect.stack()[1][3]
    
    return get_rotating_logger(
        name=caller_name,
        log_file=logfile,
        log_level=loglevel
    )