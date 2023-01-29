import asyncio
import os
import utils
from dotenv import load_dotenv


# from downloads import DOWNLOAD_REQUEST
# import json

load_dotenv()

# load env
download_username = os.getenv('USERNAME')
download_password = os.getenv('PASSWORD')
zpod_files_path = os.getenv("BASE_DIR")


async def main():
    num_proc = asyncio.Semaphore(value=8)

    downloads = utils.read_json_files()
    download_requests = [utils.ComponentDownload(**payload) for payload in downloads]
    tasks = [asyncio.create_task(utils.download_file(download, num_proc)) for download in download_requests]
    for future in asyncio.as_completed(tasks):
        if await future:
            logger.info("Done")


if __name__ == "__main__":
    asyncio.run(main())
