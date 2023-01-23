import asyncio
from vmw import utils
from vmw.log import logger
# from constants import DOWNLOAD_REQUEST


async def main():
    num_proc = asyncio.Semaphore(value=2)
    downloads = utils.read_json_files()
    download_requests = [utils.ComponentDownload(**payload) for payload in downloads]
    # download_requests = [utils.ComponentDownload(**payload) for payload in DOWNLOAD_REQUEST]
    tasks = [asyncio.create_task(utils.download_file(download,num_proc)) for download in download_requests]
    # results = await asyncio.gather(*tasks)
    #     utils.console.print("Done", style="green")
    # tasks = {asyncio.create_task(
    #     utils.download_file(download)): download for download in download_requests}
    # print(download_future_map)
    await asyncio.gather(*tasks)
    for future in asyncio.as_completed(tasks):
        if await future:
            print("Done")


if __name__ == "__main__":
    asyncio.run(main())
