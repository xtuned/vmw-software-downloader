import os
import vcc
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner
from dotenv import load_dotenv
from downloads import DOWNLOAD_REQUEST
from log import logger

download_requests = [vcc.ComponentDownload(**payload) for payload in DOWNLOAD_REQUEST]


@task(retries=5, retry_delay_seconds=10)
def download_task(request):
    download_helper = vcc.DownloadHelper(request)
    download_helper.download_file()


@flow(task_runner=ConcurrentTaskRunner())
def download_files(requests):
    download_task.map(requests)


if __name__ == "__main__":
    download_files(download_requests)
