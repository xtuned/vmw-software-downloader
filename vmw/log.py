import logging
import os
from rich.logging import RichHandler

# Create a logger object
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
rich_handler = RichHandler()

file_handler = logging.FileHandler(os.path.join(os.getenv("BASE_DIR"),"downloads.log"))


rich_handler.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)

# Create a formatter
rich_fmt = logging.Formatter('%(message)s')
file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Add formatter to handlers
file_handler.setFormatter(file_fmt)
rich_handler.setFormatter(rich_fmt)


# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(rich_handler)