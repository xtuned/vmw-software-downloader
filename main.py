import asyncio
from vmw import utils
from constants import DOWNLOAD_REQUEST
import json

async def main():
    downloads = utils.read_json_files()
    download_requests = [utils.ComponentDownload(**payload) for payload in downloads]
   
    tasks = [asyncio.create_task(utils.download_file(download)) for download in download_requests]
    for task in asyncio.as_completed(tasks):
        await task
        utils.console.print("Done", style="green")

if __name__ == "__main__":
    asyncio.run(main())
