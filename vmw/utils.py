import re
import json
import sys
import docker
import asyncio
from os import path, makedirs, rename, stat, getenv,walk
import hashlib
from pydantic import BaseModel
from rich.console import Console
from typing import Optional
from dotenv import load_dotenv

from rich.progress import (
    BarColumn,
    Progress,
    TimeElapsedColumn
)

progress = Progress(
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
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
    component_name: str
    component_version: str
    component_type: Optional[str]
    component_description: Optional[str]
    component_url: Optional[str]
    component_download_category: str
    component_download_group: Optional[str]
    component_download_ova: str
    component_download_ova_checksum: str  # "sha265:checksum"
    component_download_ova_size: str


async def convert_to_byte(download: ComponentDownload):
    size = float(download.component_download_ova_size.split(" ")[0])
    unit = download.component_download_ova_size.split(" ")[1].upper()
    return size * (byte_size ** powers[unit])


async def get_checksum(download: ComponentDownload):
    checksum_engine = download.component_download_ova_checksum.split(":")[0]
    file_path = path.join(zpod_files_path, "logs", f"{download.component_download_ova}.log")
    with open(file_path, "r") as f:
        content = f.read()
        try:
            message = re.findall(r'(\{.*?\})', content, flags=re.DOTALL)[0]
            return json.loads(message)[f"{checksum_engine}checksum"]
        except IndexError:
            return ""


async def verify_checksum(download: ComponentDownload):
    # console.print(f"Verifying the checksum...", style="green")
    checksum_engine = download.component_download_ova_checksum.split(":")[0]
    expected_checksum = download.component_download_ova_checksum.split(":")[1]
    file_path = path.join(zpod_files_path, download.component_name, download.component_version,
                          download.component_download_ova)
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
        if not checksum_result == expected_checksum:
            return False
        return True


async def wait_for_file(filename: str):
    while not path.exists(filename):
        await asyncio.sleep(.5)


async def check_download_progress(download: ComponentDownload):
    file_path = path.join(zpod_files_path, download.component_download_ova)
    console.print("Waiting for download to begin ...\n", style="green")
    await wait_for_file(file_path)
    expected_size = round(await convert_to_byte(download))
    with progress:
        task_id = progress.add_task(f"[green]{download.component_download_ova}", total=100)
        while not progress.finished:
            current_size = stat(file_path).st_size
            pct = round((100 * current_size / expected_size))

            progress.update(task_id, completed=pct)
            await asyncio.sleep(.2)

    progress.console.log(f"{download.component_download_ova} downloaded \n", style="green")
    await rename_downloaded_file(download)
    if await check_if_file_exists(download):
        await verify_checksum(download)
        return True
    else:
        console.print(f"Something went wrong retry downloading the {download.component_download_ova}",
                      style="red on white")
        return False


async def run_docker(download: ComponentDownload):
    # ensure the specified volume exists
    makedirs(zpod_files_path, mode=0o775, exist_ok=True)
    makedirs(path.join(zpod_files_path, "logs"), mode=0o775, exist_ok=True)

    log_file = f"/files/logs/{download.component_download_ova}.log 2>&1"

    try:
        if download.component_download_group and download.component_download_category:
            cmd_options = f"{download.component_download_category} {download.component_download_group}"
        else:
            cmd_options = f"{download.component_download_category}"
        console.print(cmd_options,style="blue")
        entrypoint = f"/bin/sh -c 'vmw-cli ls {cmd_options} && vmw-cli cp {download.component_download_ova} > {log_file}'"
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


async def check_if_file_exists(download: ComponentDownload):
    file = path.join(zpod_files_path, download.component_name, download.component_version,
                     download.component_download_ova)
    if not path.isfile(file):
        return False
    # await verify_checksum(download)
    return True


async def rename_downloaded_file(download: ComponentDownload):
    src_file = path.join(zpod_files_path, download.component_download_ova)
    dst_file = path.join(zpod_files_path, download.component_name, download.component_version,
                         download.component_download_ova)
    makedirs(path.join(zpod_files_path, download.component_name, download.component_version), mode=0o775,
             exist_ok=True)
    console.print(f"Renaming {download.component_download_ova}")
    rename(src_file, dst_file)
    # check file
    if path.exists(dst_file):
        console.print(f"File {download.component_download_ova} renamed successfully", style="green")


async def check_for_cache_error(download: ComponentDownload):
    log_file = path.join(zpod_files_path, "logs", f"{download.component_download_ova}.log")
    error_file = path.join(zpod_files_path, "failed_downloads.txt")
    await wait_for_file(log_file)
    # ensure there is a content to read
    while not stat(log_file).st_size >= 100:
        await asyncio.sleep(.2)
    with open(log_file, 'r') as f:
        for line in f:
            if '[ERROR]' in line:
                # record the failed attempt
                if not path.exists(error_file):
                    with open(error_file, "w") as f:
                        pass
                with open(error_file, "a") as f:
                    f.writelines([f"{download.component_download_ova}\n"])
                return True


async def download_file(download: ComponentDownload):
    if await check_if_file_exists(download):
        console.print(f"[magenta]{download.component_download_ova} [blue]already exists")
        return
    await run_docker(download=download)
    if await check_for_cache_error(download):
        console.print(f"[magenta]{download.component_download_ova} [red]failed to download retry again")
        return
    await check_download_progress(download=download)
    return True


def read_json_files():
    base_dir = path.join(zpod_files_path, "../zPodLibrary/official")
    json_files = []
    for subdir, dirs, files in walk(base_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(path.join(subdir, file))
    json_contents = []
    for json_file in json_files:
        with open(json_file) as f:
            json_contents.append(json.load(f))
    return json_contents
