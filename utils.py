import json
import time
import os
import shlex
import hashlib
import subprocess
from pathlib import Path
from pydantic import BaseModel
from rich.console import Console
from typing import Optional, Tuple, Union
from prefect import task
from log import logger
from dotenv import load_dotenv
from rich.progress import (
    BarColumn,
    Progress,
    TimeElapsedColumn,
    TaskID
)

load_dotenv()
progress = Progress(
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    TimeElapsedColumn()
)

console = Console()
byte_size = 1024
powers = {
    "KB": 1,
    "MB": 2,
    "GB": 3,
    "TB": 4,
    "PB": 5
}

download_username = os.getenv('USERNAME')
download_password = os.getenv('PASSWORD')
zpod_files_path = os.getenv("BASE_DIR")


# Download request model
# class ComponentDownload(BaseModel):
#     component_name: str
#     component_version: str
#     component_type: Optional[str]
#     component_description: Optional[str]
#     component_url: Optional[str]
#     component_download_engine: str
#     component_download_product: str
#     component_download_subproduct: Optional[str]
#     component_download_version: str
#     component_download_file: str
#     component_download_file_checksum: str  # "sha265:checksum"
#     component_download_file_size: str
#     component_isnested: Optional[bool]
#
#
# class DownloadStatus(BaseModel):
#     status: str
#
#
# def convert_to_byte(download: ComponentDownload) -> int:
#     size, unit = get_size_unit(download)
#     return int(size * (byte_size ** powers[unit]))


# def get_size_unit(download: ComponentDownload) -> Tuple[float, str]:
#     size_str, unit_str = download.component_download_file_size.split(" ")
#     size = float(size_str)
#     unit = unit_str.upper()
#     return size, unit


# def verify_checksum(download: ComponentDownload) -> bool:
#     logger.info(f"Verifying checksum for {download.component_download_file}")
#     checksum_engine, expected_checksum = get_checksum_details(download)
#     file_path = Path(f"{zpod_files_path}/{download.component_download_file}")
#     checksum = compute_checksum(file_path, checksum_engine)
#     if checksum == expected_checksum:
#         logger.info(f"Checksum {checksum} verified")
#         return True
#     return False


# def get_checksum_details(download: ComponentDownload) -> Tuple[str, str]:
#     checksum_str = download.component_download_file_checksum
#     checksum_engine, expected_checksum = checksum_str.split(":")
#     return checksum_engine, expected_checksum


# def compute_checksum(file_path: Path, checksum_engine: str) -> str:
#     with open(file_path, "rb") as f:
#         bytes_read = f.read()
#         if checksum_engine == "md5":
#             return hashlib.md5(bytes_read).hexdigest()
#         if checksum_engine == "sha256":
#             return hashlib.sha256(bytes_read).hexdigest()
#         if checksum_engine == "sha1":
#             return hashlib.sha1(bytes_read).hexdigest()


# def wait_for_file(filename: str, timeout: int = 30):
#     start_time = time.time()
#     while not Path(f"{filename}.tmp").exists():
#         if time.time() - start_time > timeout:
#             raise Exception(f"Timed out waiting for file {filename}.tmp")
#         time.sleep(.2)


# def check_if_file_exists(filename: str):
#     return Path(filename).exists()


# def get_download_status(download: ComponentDownload) -> DownloadStatus:
#     final_dst_file = Path(
#         f"{zpod_files_path}/{download.component_name}/{download.component_version}/{download.component_download_file}")
#
#     expected_size = round(convert_to_byte(download))
#     file_path = Path(f"{zpod_files_path}/{download.component_download_file}")
#     tmp_file_path = Path(f"{zpod_files_path}/{download.component_download_file}.tmp")
#
#     current_size = get_file_size(file_path, tmp_file_path)
#     status = get_status(final_dst_file, current_size, expected_size)
#
#     return DownloadStatus(status=status)
#
#
# def get_file_size(file_path: Path, tmp_file_path: Path) -> Union[int, None]:
#     if file_path.is_file():
#         return file_path.stat().st_size
#     elif tmp_file_path.is_file():
#         return tmp_file_path.stat().st_size
#     return None
#
#
# def get_status(final_dst_file: Path, current_size: Union[int, None], expected_size: int) -> str:
#     if final_dst_file.is_file():
#         return "DOWNLOAD_COMPLETE"
#     elif current_size is not None:
#         return str(check_percentage(current_size, expected_size))
#     return "SCHEDULED"
#
#
# def check_percentage(current_size, expected_size):
#     return round((100 * current_size / expected_size))
#
#
# def rename_file(download: ComponentDownload):
#     src_file_path = f"{zpod_files_path}/{download.component_download_file}"
#     dst_file_dir = f"{zpod_files_path}/{download.component_name}/{download.component_version}"
#     dst_file_path = f"{dst_file_dir}/{download.component_download_file}"
#
#     Path(dst_file_dir).mkdir(parents=True, mode=0o775, exist_ok=True)
#
#     Path(src_file_path).rename(dst_file_path)
#
#     if Path(dst_file_path).exists():
#         logger.info(f"File {download.component_download_file} renamed successfully")
#
#
# def read_json_files():
#     base_dir = os.path.join(zpod_files_path, "../zPodLibrary/official")
#     all_json_files = []
#     for subdir, dirs, files in os.walk(base_dir):
#         for file in files:
#             if file.endswith('.json'):
#                 all_json_files.append(os.path.join(subdir, file))
#     json_contents = []
#     for json_file in all_json_files:
#         with open(json_file) as f:
#             json_contents.append(json.load(f))
#     return json_contents
#
#
# def show_progress(download: ComponentDownload, task_id: TaskID, status: dict):
#     file_path = os.path.join(zpod_files_path, download.component_download_file)
#     full_file_path = os.path.join(zpod_files_path, download.component_name, download.component_version,
#                                   download.component_download_file)
#     if os.path.isfile(full_file_path):
#         console.print(f"\t[magenta]{download.component_download_file} [green]is done downloading\n")
#         return
#
#     tmp_file_path = f"{file_path}.tmp"
#     if not os.path.exists(tmp_file_path):
#         return
#
#     expected_size = round(convert_to_byte(download))
#     while True:
#         current_size = os.stat(file_path if os.path.exists(file_path) else tmp_file_path).st_size
#         pct = round((100 * current_size / expected_size))
#         if pct == 100:
#             break
#         status[task_id] = {"status": pct, "total": 100}
#         time.sleep(0.1)
#
#
# def initiate_download(download: ComponentDownload):
#     logs = Path(f"{zpod_files_path}/logs")
#     logs.mkdir(parents=True, mode=0o775, exist_ok=True)
#
#     cmd = f"vcc download -a --user {shlex.quote(download_username)} --pass {shlex.quote(download_password)}"
#     cmd += f" -p {shlex.quote(download.component_download_product)}"
#     cmd += f" -s {shlex.quote(download.component_download_subproduct)}"
#     cmd += f" -v {shlex.quote(download.component_version)}"
#     cmd += f" -f {shlex.quote(download.component_download_file)}"
#     cmd += f" -o {shlex.quote(zpod_files_path)}"
#
#     try:
#         vcc = subprocess.run(args=cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True)
#         logger.info(f"{vcc.stdout.decode()}")
#         logger.error(f"{vcc.stderr.decode()}")
#
#         tmp_file = Path(f"{zpod_files_path}/{download.component_download_file}")
#
#         if check_if_file_exists(str(tmp_file)):
#             logger.info(f"{download.component_download_file} downloaded")
#             verify_checksum(download)
#             rename_file(download)
#
#     except subprocess.CalledProcessError as e:
#         logger.error(e)
#         logger.error(f"Unable to download {download.component_download_file}")
#
#
# @task(retries=4, retry_delay_seconds=10)
# def download_file(download: ComponentDownload):
#     file_path = Path(f"{zpod_files_path}/{download.component_name}/{download.component_version}/{download.component_download_file}")
#     if check_if_file_exists(str(file_path)):
#         logger.info(f"{download.component_download_file} already exists")
#         return
#     initiate_download(download)
#

