import utils
from downloads import DOWNLOAD_REQUEST
import json


def main():
    download_requests = [utils.ComponentDownload(**payload) for payload in DOWNLOAD_REQUEST]
    request = download_requests[4]
    status = utils.get_download_status(request)
    print(json.dumps(status.dict()))


if __name__ == "__main__":
    main()
