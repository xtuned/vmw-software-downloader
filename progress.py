import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from vmw import utils
from constants import DOWNLOAD_REQUEST


def main():
    # download_requests = [utils.ComponentDownload(**payload) for payload in DOWNLOAD_REQUEST]
    downloads = utils.read_json_files()
    download_requests = [utils.ComponentDownload(**payload) for payload in downloads]

    with utils.progress as progress:
        with multiprocessing.Manager() as manager:
            status = manager.dict()
            overall_progress_status = progress.add_task("[green]Download Status:")
            with ProcessPoolExecutor() as executor:
                futures = []
                for download in download_requests:
                    task_id = progress.add_task(f"[yellow]{download.component_download_file}", visible=False)
                    future = executor.submit(utils.show_progress, download, task_id, status)
                    futures.append(future)
                while (task_finished := sum([future.done() for future in futures])) < len(futures):
                    progress.update(overall_progress_status, completed=task_finished, total=len(futures))
                    for task_id, current_status in status.items():
                        latest = current_status["status"]
                        total = current_status["total"]
                        progress.update(task_id, completed=latest, total=total, visible=latest < total)
                progress.update(overall_progress_status, completed=task_finished, total=len(futures))
                for future in as_completed(futures):
                    future.result()


if __name__ == "__main__":
    main()
