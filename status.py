import vcc
from downloads import DOWNLOAD_REQUEST
import json


def main():
    download_requests = [vcc.ComponentDownload(**payload) for payload in DOWNLOAD_REQUEST]
    request = download_requests[3]
    download_helper = vcc.DownloadHelper(request)
    status = download_helper.get_download_status()
    print(json.dumps(status.dict()))


if __name__ == "__main__":
    main()
