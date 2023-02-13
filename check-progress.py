import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import vcc
import pickle
from downloads import DOWNLOAD_REQUEST


def main():
    download_requests = [vcc.ComponentDownload(**payload) for payload in DOWNLOAD_REQUEST]

    with vcc.progress as progress:
        with multiprocessing.Manager() as manager:
            status = manager.dict()
            overall_progress_status = progress.add_task("[green]Download Status:")
            with ProcessPoolExecutor() as executor:
                futures = []
                for request in download_requests:
                    download_helper = vcc.DownloadHelper(request)
                    task_id = progress.add_task(f"[yellow]{request.component_download_file}", visible=False)
                    future = executor.submit(download_helper.show_progress, task_id, status)
                    futures.append(future)

                task_finished = 0
                while task_finished < len(futures):
                    task_finished = sum([future.done() for future in futures])
                    progress.update(overall_progress_status, completed=task_finished, total=len(futures))
                    for task_id, current_status in status.items():
                        latest = current_status["status"]
                        total = current_status["total"]
                        progress.update(task_id, completed=latest, total=total, visible=latest < total)
                for future in as_completed(futures):
                    future.result()


if __name__ == "__main__":
    main()
