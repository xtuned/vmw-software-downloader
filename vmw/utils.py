import re
import json
import sys
import docker
import signal
import asyncio
from os import path, makedirs, rename, stat, getenv
import time
import hashlib
from pydantic import BaseModel
from rich.console import Console
from typing import Optional
from dotenv import load_dotenv
from concurrent.futures import Future
from threading import Event
from asyncio import Queue

from rich.progress import (
    BarColumn,
    Progress,
    TimeRemainingColumn,
    TimeElapsedColumn,
    TaskID
)

progress = Progress(
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    TimeRemainingColumn(),
    TimeElapsedColumn()
)

# load env
load_dotenv()
download_username = getenv('USERNAME')
download_password = getenv('PASSWORD')
download_container_image = getenv("CONTAINER_IMAGE")
zpod_files_path = getenv("BASE_DIR")
client = docker.from_env()
console = Console()

byte_size = 1024
powers = {"KB": 1, "MB": 2, "GB": 3, "TB": 4, "PB": 5}


# Download request model
class ComponentDownload(BaseModel):
    component_download_name: str
    component_download_release: Optional[str]
    component_download_filename: str
    component_download_filesize: str
    component_download_group: Optional[str]
    component_download_checksum: str  # "sha265:checksum"
    component_name: str
    component_version: str


done_event = Event()


def handle_sigint(signum, frame):
    done_event.set()


signal.signal(signal.SIGINT, handle_sigint)


def convert_to_byte(download: ComponentDownload):
    size = float(download.component_download_filesize.split(" ")[0])
    unit = download.component_download_filesize.split(" ")[1].upper()
    return size * (byte_size ** powers[unit])


# def convert_from_byte(filesize: int, unit: str):
#     return filesize / (byte_size ** powers[unit])

def get_checksum(download: ComponentDownload):
    checksum_engine = download.component_download_checksum.split(":")[0]
    base_dir = getenv("BASE_DIR")
    file_path = path.join(base_dir, "logs", f"{download.component_download_filename}.log")
    with open(file_path, "r") as f:
        content = f.read()
        try:
            message = re.findall(r'(\{.*?\})', content, flags=re.DOTALL)[0]
            return json.loads(message)[f"{checksum_engine}checksum"]
        except IndexError:
            return ""


def verify_checksum(download: ComponentDownload):
    console.print(f"Verifying the checksum...", style="green")
    checksum_engine = download.component_download_checksum.split(":")[0]
    expected_checksum = download.component_download_checksum.split(":")[1]
    base_dir = getenv("BASE_DIR")
    file_path = path.join(base_dir, download.component_download_filename)
    with open(file_path, "rb") as f:
        bytes_read = f.read()
        match checksum_engine:
            case "md5":
                checksum = hashlib.md5(bytes_read).hexdigest()
            case "sha256":
                checksum = hashlib.sha256(bytes_read).hexdigest()
            case "sha1":
                checksum = hashlib.sha256(bytes_read).hexdigest()
        checksum_result = checksum
        if checksum_result == expected_checksum:
            return True
        return False


async def check_download_progress(download: ComponentDownload):
    base_dir = getenv("BASE_DIR")
    file_path = path.join(base_dir, download.component_download_filename)
    file_exist = False
    console.print("Waiting for download to begin ...\n", style="green")
    while file_exist is not True:
        await asyncio.sleep(.5)
        # time.sleep(1)
        file_exist = path.exists(file_path)
    expected_size = round(convert_to_byte(download))

    with progress:
        task_id = progress.add_task(f"[green]{download.component_download_filename}",total=100)
        while not progress.finished:
            current_size = stat(file_path).st_size
            pct = round((100 * current_size / expected_size))

            progress.update(task_id, completed=pct)
            await asyncio.sleep(.2)

    progress.console.log(f"Downloaded {download.component_download_filename}\n", style="green")
    if verify_checksum(download):
        rename_downloaded_file(download)
    return True


async def run_docker(download: ComponentDownload):
    # ensure the specified volume exists
    makedirs(zpod_files_path, mode=0o775, exist_ok=True)
    makedirs(path.join(zpod_files_path, "logs"), mode=0o775, exist_ok=True)

    log_file = f"/files/logs/{download.component_download_filename}.log 2>&1"

    try:
        if download.component_download_group and download.component_download_release:
            cmd_options = f"{download.component_download_name}/{download.component_download_release} {download.component_download_group}"
        elif not download.component_download_group and download.component_download_release:
            cmd_options = f"{download.component_download_name}/{download.component_download_release}"
        else:
            cmd_options = f"{download.component_download_name}"

        entrypoint = f"/bin/sh -c 'vmw-cli ls {cmd_options} && vmw-cli cp {download.component_download_filename} > {log_file} '"

        console.print("launching container ...", style="green")
        container = client.containers.run(image=download_container_image,
                                          detach=True,
                                          tty=True,
                                          entrypoint=entrypoint,
                                          volumes=[f"{zpod_files_path}:/files"],
                                          environment=[f"VMWUSER={download_username}", f"VMWPASS={download_password}"],
                                          auto_remove=True,
                                          )
        console.print(f"container {container.id[:10]} launched successfully", style="green")
    except docker.errors.ContainerError:
        console.print("Error launching the container", style="danger")
        sys.exit()
    except docker.errors.ImageNotFound:
        console.print("The specified image cannot be found", style="danger")
        sys.exit()
    except docker.errors.APIError:
        console.print("Error, cannot connect to docker engine. Make sure docker is running", style="danger")
        sys.exit()


def rename_downloaded_file(download: ComponentDownload):
    src_file = path.join(getenv("BASE_DIR"), download.component_download_filename)
    dst_file = path.join(getenv("BASE_DIR"), download.component_name, download.component_version,
                         download.component_download_filename)
    makedirs(path.join(getenv("BASE_DIR"), download.component_name, download.component_version), mode=0o775,
             exist_ok=True)
    console.print(f"Renaming {download.component_download_filename}")
    rename(src_file, dst_file)
    # check file
    if path.exists(dst_file):
        console.print(f"File {download.component_download_filename} renamed successfully", style="green")


async def download_file(download: ComponentDownload):
    await run_docker(download=download)
    await check_download_progress(download=download)