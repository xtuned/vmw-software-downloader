import logging
import os
from rich.logging import RichHandler

# Create a logger object
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
rich_handler = RichHandler()
print(os.getenv("BASE_DIR"))
file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(filename=os.path.join(os.getenv("BASE_DIR"), "download.log"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_fmt)
logger.addHandler(file_handler)

