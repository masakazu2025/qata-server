"""server を組み立てて立ち上げる。設定は環境変数で渡す。

- `QATA_DATA_DIR`：保存先のフォルダ（既定は `./data`）
- `QATA_RUNNER_URL`：runner の場所（既定は `http://127.0.0.1:8001`）
- `QATA_HOST`・`QATA_PORT`：server が待ち受ける場所（既定は `127.0.0.1:8000`）
"""

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from qata_server.application import Service, Store, load_apps
from qata_server.rest import create_app
from qata_server.runner_http import HttpRunner


def build() -> FastAPI:
    data_dir = Path(os.environ.get("QATA_DATA_DIR", "data"))
    runner_url = os.environ.get("QATA_RUNNER_URL", "http://127.0.0.1:8001")
    service = Service(load_apps(), Store(data_dir), HttpRunner(runner_url))
    return create_app(service)


def serve() -> None:
    uvicorn.run(
        build(),
        host=os.environ.get("QATA_HOST", "127.0.0.1"),
        port=int(os.environ.get("QATA_PORT", "8000")),
    )
