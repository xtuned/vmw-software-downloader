import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Create a logger object
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_file = Path(f"{os.getenv('BASE_DIR')}/logs/download.log")
log_file.mkdir(parents=True, mode=0o775, exist_ok=True)
file_handler = logging.FileHandler(filename=str(log_file))

file_handler.setLevel(logging.DEBUG)

file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

file_handler.setFormatter(file_fmt)

logger.addHandler(file_handler)
