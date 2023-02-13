from loguru import logger
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

log_file_dir = Path(f"{os.getenv('BASE_DIR')}/logs")
log_file = Path(f"{os.getenv('BASE_DIR')}/logs/download.log")
log_file_dir.mkdir(parents=True, mode=0o775, exist_ok=True)
logger.remove(0)
logger.add(sys.stderr, format="<red>{time}</red> | <green>{level}</green> | {message}", colorize=True)
logger.add(log_file, rotation="30 MB")
