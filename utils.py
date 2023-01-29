import json
import time
import asyncio
import os
import shutil
import hashlib
from pathlib import Path
from pydantic import BaseModel
from rich.console import Console
from typing import Optional
from log import logger
from main import download_password, download_username, zpod_files_path
from rich.progress import (
    BarColumn,
    Progress,
    TimeElapsedColumn,
    TaskID
)

progress = Progress(
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    TimeElapsedColumn()
)

console = Console()

byte_size = 1024
powers = {"KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}


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


def convert_to_byte(download: ComponentDownload):
    size = float(download.component_download_file_size.split(" ")[0])
    unit = download.component_download_file_size.split(" ")[1].upper()
    return size * (byte_size ** powers[unit])


async def verify_checksum(download: ComponentDownload):
    console.print(f"Verifying the checksum...\n", style="green")
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
        return True


async def wait_for_file(filename: str):
    while not Path(f"{filename}.tmp").exists():
        await asyncio.sleep(.2)


async def check_if_file_exists(filename: str):
    if not Path(filename).exists():
        return False
    else:
        return True


async def get_download_status(download: ComponentDownload):
    file_path = Path(f"{zpod_files_path}/{download.component_download_file}")
    console.print("Waiting for download to begin ...\n", style="green")
    await wait_for_file(str(file_path))
    console.print(f"{download.component_download_file} download has started...\n", style="green")
    expected_size = round(convert_to_byte(download))
    pct = 0
    while pct != 100:
        if os.path.exists(file_path):
            current_size = os.stat(file_path).st_size
        else:
            current_size = os.stat(f"{file_path}.tmp").st_size
        pct = round((100 * current_size / expected_size))
        time.sleep(0.1)


async def rename_downloaded_file(download: ComponentDownload):
    src_file = Path(f"{zpod_files_path}/{download.component_download_file}", )
    dst_file = Path(
        f"{zpod_files_path}/{download.component_name}/{download.component_version}/{download.component_download_file}")
    parent_dir = Path(f"{zpod_files_path}/{download.component_name}/{download.component_version}")
    parent_dir.mkdir(parents=True, mode=0o775, exist_ok=True)
    console.print(f"[blue]Renaming {download.component_download_file}")
    src_file.rename(dst_file)
    if dst_file.exists():
        console.print(f"File {download.component_download_file} renamed successfully", style="green")


async def log_failed_download(download: ComponentDownload):
    error_file = Path(f"{zpod_files_path}/failed-downloads.txt")
    error_file.open("a").writelines(f"{download.component_download_file}\n")


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


async def execute_download_cmd(download: ComponentDownload):
    runtime_env = dict(os.environ)
    runtime_env["VCC_USER"] = download_username
    runtime_env["VCC_PASS"] = download_password
    # ensure the specified volume exists
    logs = Path(f"{zpod_files_path}/logs")
    logs.mkdir(parents=True, mode=0o775, exist_ok=True)
    download_cmd = f'''
    vcc download -a \
    -p {download.component_download_product} \
    -s {download.component_download_subproduct} -v {download.component_version} \
    -f {download.component_download_file} -o {zpod_files_path} &
    '''
    console.print(f"Initiating {download.component_download_file} ...\n", style="green")
    cmd = await asyncio.create_subprocess_shell(
        cmd=download_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await cmd.communicate()
    # log this to file
    logger.info(stdout.decode())
    logger.error(stderr.decode())
    if await cmd.wait():
        console.print(f"{download.component_download_file} download done \n", style="green")
    else:
        console.print(f"Unable to download {download.component_download_file}\n", style="white on red")
        return


async def download_file(download: ComponentDownload, semaphore: asyncio.Semaphore):
    async with semaphore:
        dst_file = Path(
            f"{zpod_files_path}/{download.component_name}/{download.component_version}/{download.component_download_file}")
        tmp_file = Path(f"{zpod_files_path}/{download.component_download_file}")
        if await check_if_file_exists(str(dst_file)):
            console.print(f"[magenta]{download.component_download_file} [blue]already exists \n")
            return
        if semaphore.locked():
            console.print("Process limit is exceeded,waiting...\n", style="green")
            await asyncio.sleep(0.1)
        await execute_download_cmd(download=download)
        if await check_if_file_exists(str(tmp_file)):
            await verify_checksum(download)
            await rename_downloaded_file(download)
    return True
