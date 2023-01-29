import logging
import os
from rich.logging import RichHandler
from dotenv import load_dotenv
load_dotenv()

# Create a logger object
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(filename=os.path.join(os.getenv('BASE_DIR'), "download.log"))
rich_handler = RichHandler()

rich_handler.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)

rich_fmt = '%(message)s'
file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

rich_handler.setFormatter(rich_fmt)
file_handler.setFormatter(file_fmt)

logger.addHandler(file_handler)
logger.addHandler(rich_handler)

