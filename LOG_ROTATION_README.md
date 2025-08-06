# BlammoBot Log Rotation System

This document describes the log rotation system implemented for BlammoBot to manage log file sizes and prevent disk space issues.

## Overview

The bot now uses `RotatingFileHandler` instead of basic `FileHandler` for all logging operations. This automatically rotates log files when they reach a specified size limit, keeping older logs as backup files.

## Configuration

### Default Settings
- **Maximum file size**: 10MB per log file
- **Backup count**: 5 files (logs.log.1, logs.log.2, etc.)
- **Primary log file**: `logs.log`
- **Encoding**: UTF-8

### Log File Structure
```
logs.log          # Current active log file
logs.log.1        # Most recent backup (rotated when logs.log hit 10MB)
logs.log.2        # Second most recent backup
logs.log.3        # Third most recent backup
logs.log.4        # Fourth most recent backup  
logs.log.5        # Oldest backup (deleted when new rotation occurs)
```

## Implementation Details

### For New Modules
```python
from log.loggers.rotating_logger import get_rotating_logger

# Create logger with default settings (10MB, 5 backups)
logger = get_rotating_logger(__name__)

# Or customize settings
logger = get_rotating_logger(
    name=__name__,
    log_file="custom.log",
    max_bytes=5*1024*1024,  # 5MB
    backup_count=3
)
```

### Migration from Old System
The old logging pattern:
```python
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter1 = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s : %(message)s", datefmt="%m/%d/%Y %I:%M:%S %p")
file_handler = logging.FileHandler("logs.log")
file_handler.setFormatter(formatter1)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(CustomFormatter())
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
```

Has been replaced with:
```python
from log.loggers.rotating_logger import get_rotating_logger
logger = get_rotating_logger(__name__)
```

## Updated Files

The following files have been migrated to use rotating loggers:

### Core Files
- `main.py` - Main bot application
- `scheduler.py` - Bot scheduler and process manager

### Utility Modules
- `utils/record.py` - Game data recording
- `utils/trivia.py` - Trivia game logic
- `utils/counter.py` - Counter utilities
- `utils/dbutils.py` - Database utilities
- `utils/db_health.py` - Database health checking
- `utils/announce.py` - Announcement system
- `utils/submit.py` - User submission handling
- `utils/secretcommand.py` - Secret command processing
- `utils/timestamps.py` - Timestamp management
- `utils/stringvalidate.py` - String validation
- `utils/scramble.py` - Word scramble game
- `utils/randommeal.py` - Random meal suggestions
- `utils/points.py` - Points and gambling system

### Supporting Files
- `check_online.py` - Stream status checker

## Utility Functions

### Get Log File Information
```python
from log.loggers.rotating_logger import get_log_file_info

info = get_log_file_info("logs.log")
print(f"Current size: {info['size_mb']:.2f} MB")
print(f"Backup files: {len(info['backup_files'])}")
```

### Force Log Rotation
```python
from log.loggers.rotating_logger import force_log_rotation

# Manually trigger rotation (useful for maintenance)
success = force_log_rotation("logs.log")
```

## Testing

Run the test suite to verify log rotation functionality:
```bash
python test_log_rotation.py
```

This tests:
- Basic size-based rotation
- Manual/forced rotation
- Multiple loggers sharing the same file
- Log file information retrieval

## Benefits

1. **Automatic Management**: No manual intervention needed for log cleanup
2. **Disk Space Protection**: Prevents logs from consuming unlimited disk space
3. **Historical Preservation**: Keeps recent log history available for debugging
4. **Thread Safety**: Handles concurrent logging from multiple modules
5. **Drop-in Replacement**: Minimal code changes required for migration

## Monitoring

To monitor log rotation status:
```bash
# Check current log size
ls -lh logs.log

# Check for backup files
ls -lh logs.log.*

# View log file information programmatically
python -c "from log.loggers.rotating_logger import get_log_file_info; print(get_log_file_info())"
```

## Troubleshooting

### Permissions Issues
If rotation fails due to permissions:
```bash
# Ensure bot user has write access
chmod 644 logs.log*
chown botuser:botgroup logs.log*
```

### Large Existing Log Files
If `logs.log` is already very large before implementing rotation, consider manually rotating it:
```bash
# Backup existing log
mv logs.log logs.log.backup

# Create new empty log file
touch logs.log
chmod 644 logs.log

# Restart bot to begin using rotation
```

### Disk Space Monitoring
Monitor total log space usage:
```bash
# Check total size of all log files
du -sh logs.log*
```

## Future Enhancements

Potential improvements to consider:
1. **Time-based rotation**: Rotate daily/weekly regardless of size
2. **Compression**: Compress older backup files to save space
3. **Remote log shipping**: Send logs to centralized logging system
4. **Log parsing utilities**: Tools to analyze rotated log files
5. **Configuration file**: External config for rotation settings