import vcc
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner
# from downloads import DOWNLOAD_REQUEST
all_requests = vcc.read_json_files()
download_requests = [vcc.ComponentDownload(**payload) for payload in all_requests]


@task(retries=5, retry_delay_seconds=10)
def download_task(request):
    download_helper = vcc.DownloadHelper(request)
    download_helper.download_file()


@flow(task_runner=ConcurrentTaskRunner())
def download_files(requests):
    download_task.map(requests)


if __name__ == "__main__":
    download_files(download_requests)
