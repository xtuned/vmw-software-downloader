import re
import json
import sys
import time
import subprocess
import docker
import asyncio
import os
import shutil
import hashlib
from pydantic import BaseModel
from rich.console import Console
from typing import Optional
from dotenv import load_dotenv
from vmw.log import logger
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

# load env
load_dotenv()

download_username = os.getenv('USERNAME')
download_password = os.getenv('PASSWORD')
download_container_image = os.getenv("CONTAINER_IMAGE")
zpod_files_path = os.getenv("BASE_DIR")

client = docker.from_env()
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
    file_path = os.path.join(zpod_files_path, download.component_download_file)
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
    while not os.path.exists(f"{filename}.tmp"):
        await asyncio.sleep(.2)


async def get_download_status(download: ComponentDownload):
    file_path = os.path.join(zpod_files_path, download.component_download_file)
    console.print("Waiting for download to begin ...\n", style="green")
    await wait_for_file(file_path)
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
    await rename_downloaded_file(download)
    if await check_if_file_exists(download):
        await verify_checksum(download)
        return True
    else:
        console.print(f"Something went wrong retry downloading the {download.component_download_file}",
                      style="red on white")
        return False


async def check_if_file_exists(download: ComponentDownload):
    file = os.path.join(zpod_files_path, download.component_download_file)
    if not os.path.isfile(file):
        return False
    return True


async def rename_downloaded_file(download: ComponentDownload):
    src_file = os.path.join(zpod_files_path, download.component_download_file)
    dst_file = os.path.join(zpod_files_path, download.component_name, download.component_version,
                            download.component_download_file)
    os.makedirs(os.path.join(zpod_files_path, download.component_name, download.component_version), mode=0o775,
                exist_ok=True)
    console.print(f"[blue]Renaming {download.component_download_file}")
    os.rename(src_file, dst_file)
    # check file
    if os.path.exists(dst_file):
        console.print(f"File {download.component_download_file} renamed successfully", style="green")


async def check_for_cache_error(download: ComponentDownload):
    log_file = os.path.join(zpod_files_path, "logs", f"{download.component_download_file}.log")
    error_file = os.path.join(zpod_files_path, "failed_downloads.txt")
    await wait_for_file(log_file)
    # ensure there is a content to read
    while not os.stat(log_file).st_size >= 100:
        await asyncio.sleep(.2)
    with open(log_file, 'r') as f:
        for line in f:
            if '[ERROR]' in line:
                # record the failed attempt
                if not os.path.exists(error_file):
                    with open(error_file, "w") as f:
                        pass
                with open(error_file, "a") as f:
                    f.writelines([f"{download.component_download_file}\n"])
                return True


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


async def remove_log_file():
    error_file = os.path.join(zpod_files_path, "failed_downloads.txt")
    log_dir = os.path.join(zpod_files_path, "logs")
    if os.path.exists(error_file):
        os.remove(error_file)
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir, ignore_errors=True)


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
    os.makedirs(zpod_files_path, mode=0o775, exist_ok=True)
    os.makedirs(os.path.join(zpod_files_path, "logs"), mode=0o775, exist_ok=True)
    download_cmd = f'''vcc download -a -p {download.component_download_product} -s {download.component_download_subproduct} -v {download.component_version} -f {download.component_download_file} -o {zpod_files_path} & '''
    console.print(f"Initiating {download.component_download_file} ...\n", style="green")
    cmd = await asyncio.create_subprocess_shell(
        cmd=download_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=runtime_env
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
        if await check_if_file_exists(download):
            console.print(f"[magenta]{download.component_download_file} [blue]already exists \n")
            return
        if semaphore.locked():
            console.print("Process limit is exceeded,waiting...\n", style="green")
            await asyncio.sleep(0.1)
        await execute_download_cmd(download=download)
        if await check_if_file_exists(download):
            await verify_checksum(download)
            await rename_downloaded_file(download)
    return True
