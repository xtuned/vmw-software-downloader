import logging
import os
from rich.logging import RichHandler
from main import zpod_files_path

# Create a logger object
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
rich_handler = RichHandler()
file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(filename=os.path.join(zpod_files_path, "download.log"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_fmt)
logger.addHandler(file_handler)

