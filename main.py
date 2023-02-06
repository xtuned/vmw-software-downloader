import os
import utils
from prefect import flow
from prefect.task_runners import ConcurrentTaskRunner
from dotenv import load_dotenv
from downloads import DOWNLOAD_REQUEST
from log import logger

load_dotenv()

# load env
download_username = os.getenv("USERNAME")
download_password = os.getenv("PASSWORD")
zpod_files_path = os.getenv("BASE_DIR")

download_requests = [utils.ComponentDownload(**payload) for payload in DOWNLOAD_REQUEST]


@flow(task_runner=ConcurrentTaskRunner())
def download(requests):
    utils.download_file.map(requests)


if __name__ == "__main__":
    download(download_requests)
