import json
import time
import os
import shlex
import hashlib
import re
import subprocess
from pathlib import Path
from pydantic import BaseModel
from rich.console import Console
from typing import Optional
from prefect import task
from log import logger
# from main import download_password, download_username, zpod_files_path
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
powers = {"KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}

download_username = os.getenv('USERNAME')
download_password = os.getenv('PASSWORD')
zpod_files_path = os.getenv("BASE_DIR")


# Download request model
class ComponentDownload(BaseModel):
    component_name: str
    component_version: str
    component_type: Optional[str]
    component_description: Optional[str]
    component_url: Optional[str]
    component_download_engine: str
    component_download_product: str
    component_download_subproduct: Optional[str]
    component_download_version: str
    component_download_file: str
    component_download_file_checksum: str  # "sha265:checksum"
    component_download_file_size: str
    component_isnested: Optional[bool]


class DownloadStatus(BaseModel):
    status: str


def convert_to_byte(download: ComponentDownload):
    size = float(download.component_download_file_size.split(" ")[0])
    unit = download.component_download_file_size.split(" ")[1].upper()
    return size * (byte_size ** powers[unit])


def replace_special_char_password(password: str):
    special_chars = r'([$!#&"()|<>`\;' + "'])"
    return re.sub(special_chars, r'@\1', password).replace('@', '\\')


def verify_checksum(download: ComponentDownload):
    logger.info(f"Verifying checksum for {download.component_download_file}")
    checksum_engine = download.component_download_file_checksum.split(":")[0]
    expected_checksum = download.component_download_file_checksum.split(":")[1]
    file_path = Path(f"{zpod_files_path}/{download.component_download_file}")
    with open(file_path, "rb") as f:
        bytes_read = f.read()
        match checksum_engine:
            case "md5":
                checksum = hashlib.md5(bytes_read).hexdigest()
            case "sha256":
                checksum = hashlib.sha256(bytes_read).hexdigest()
            case "sha1":
                checksum = hashlib.sha1(bytes_read).hexdigest()
        checksum_result = checksum
        if not checksum_result == expected_checksum:
            return False
        console.print(f"Checksum {checksum_result} verified \n", style="green")
        logger.info(f"Checksum {checksum_result} verified")
        return True


def wait_for_file(filename: str):
    while not Path(f"{filename}.tmp").exists():
        time.sleep(.2)


def check_if_file_exists(filename: str):
    if not Path(filename).exists():
        return False
    else:
        return True


def get_download_status(download: ComponentDownload):
    status = DownloadStatus(status="SCHEDULED")
    final_dst_file = Path(
        f"{zpod_files_path}/{download.component_name}/{download.component_version}/{download.component_download_file}")
    if final_dst_file.is_file():
        status.status = "DOWNLOAD_COMPLETE"
        return status

    expected_size = round(convert_to_byte(download))
    file_path = Path(f"{zpod_files_path}/{download.component_download_file}")
    tmp_file_path = Path(f"{zpod_files_path}/{download.component_download_file}.tmp")

    if file_path.is_file():
        current_size = file_path.stat().st_size
        status.status = str(check_percentage(current_size, expected_size))
    elif tmp_file_path.is_file():
        current_size = tmp_file_path.stat().st_size
        status.status = str(check_percentage(current_size, expected_size))

    return status


def check_percentage(current_size, expected_size):
    return round((100 * current_size / expected_size))


def rename_file(download: ComponentDownload):
    src_file = Path(f"{zpod_files_path}/{download.component_download_file}", )
    dst_file = Path(
        f"{zpod_files_path}/{download.component_name}/{download.component_version}/{download.component_download_file}")
    parent_dir = Path(f"{zpod_files_path}/{download.component_name}/{download.component_version}")
    parent_dir.mkdir(parents=True, mode=0o775, exist_ok=True)
    console.print(f"[blue]Renaming {download.component_download_file}")
    src_file.rename(dst_file)
    if dst_file.exists():
        console.print(f"File {download.component_download_file} renamed successfully", style="green")


def read_json_files():
    base_dir = os.path.join(zpod_files_path, "../zPodLibrary/official")
    all_json_files = []
    for subdir, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.json'):
                all_json_files.append(os.path.join(subdir, file))
    json_contents = []
    for json_file in all_json_files:
        with open(json_file) as f:
            json_contents.append(json.load(f))
    return json_contents


def show_progress(download: ComponentDownload, task_id: TaskID, status: dict):
    file_path = os.path.join(zpod_files_path, download.component_download_file)
    file = os.path.join(zpod_files_path, download.component_name, download.component_version,
                        download.component_download_file)
    if os.path.isfile(file):
        console.print(f"\t[magenta]{download.component_download_file} [green]is done downloading\n")
        return
    if not os.path.exists(f"{file_path}.tmp"):
        return
    expected_size = round(convert_to_byte(download))
    pct = 0
    while pct != 100:
        if os.path.exists(file_path):
            current_size = os.stat(file_path).st_size
        else:
            current_size = os.stat(f"{file_path}.tmp").st_size
        pct = round((100 * current_size / expected_size))
        status[task_id] = {"status": pct, "total": 100}
        time.sleep(0.1)
    return


def execute_vcc_cmd(download: ComponentDownload):
    logs = Path(f"{zpod_files_path}/logs")
    logs.mkdir(parents=True, mode=0o775, exist_ok=True)
    cmd = f"vcc download -a\
         --user {shlex.quote(download_username)} --pass {shlex.quote(download_password)}\
         -p {shlex.quote(download.component_download_product)}\
         -s {shlex.quote(download.component_download_subproduct)}\
         -v {shlex.quote(download.component_version)}\
         -f {shlex.quote(download.component_download_file)}\
         -o {shlex.quote(zpod_files_path)}"
    try:
        vcc = subprocess.Popen(
            args=cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
    except Exception as e:
        logger.error(e)
        return None
    return vcc


def check_status(download: ComponentDownload, process: subprocess.Popen):
    if not process:
        logger.info("Received None process object: Possible reasons file already exists or failed to execute the cmd")
        return
    stdout, stderr = process.communicate()
    logger.error(f"{stderr.decode()}")
    logger.info(f"{stdout.decode()}")
    tmp_file = Path(f"{zpod_files_path}/{download.component_download_file}")
    if process.returncode != 0:
        logger.error(f"{stderr.decode()}")
        console.print(f"Unable to download {download.component_download_file}\n", style="white on red")
        raise Exception("Unable to download the file")
    if check_if_file_exists(str(tmp_file)):
        logger.info(f"f{download.component_download_file} downloaded")
        verify_checksum(download)
        rename_file(download)


@task(retries=4, retry_delay_seconds=10)
def download_file(download: ComponentDownload):
    dst_file = Path(
        f"{zpod_files_path}/{download.component_name}/{download.component_version}/{download.component_download_file}")
    if check_if_file_exists(str(dst_file)):
        console.print(f"[magenta]{download.component_download_file} [blue]already exists \n")
        return
    proc = execute_vcc_cmd(download=download)
    check_status(download,proc)
    # if proc:
    #     return {"status": "SCHEDULED", "pid": proc.pid}
    # else:
    #     return {"status": "INITIAL_SCHEDULE_FAILED", "pid": proc.pid}
    # tmp_file = Path(f"{zpod_files_path}/{download.component_download_file}")
    # if check_if_file_exists(str(tmp_file)):
    #     # verify_checksum(download)
    #     rename_downloaded_file(download)
    # return True
