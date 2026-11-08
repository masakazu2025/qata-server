"""server を組み立てて立ち上げる。設定は環境変数で渡す。

- `QATA_DATA_DIR`：保存先のフォルダ（既定は `./data`）
- `QATA_RUNNER_URL`：runner の場所（既定は `http://127.0.0.1:8001`）
- `QATA_HOST`・`QATA_PORT`：server が待ち受ける場所（既定は `127.0.0.1:8000`）

REST（`qata-server`）と MCP（`qata-server-mcp`、stdio）は別のプロセスで動く。
同じ `QATA_DATA_DIR` を指せば、同じテストケースと実行の結果を見る（S7）。
"""

import os
from pathlib import Path

import anyio
import uvicorn
from fastapi import FastAPI
from mcp.server.stdio import stdio_server

from qata_server.application import Service, Store, load_apps
from qata_server.mcp_server import create_server
from qata_server.rest import create_app
from qata_server.runner_http import HttpRunner


def build_service() -> Service:
    data_dir = Path(os.environ.get("QATA_DATA_DIR", "data"))
    runner_url = os.environ.get("QATA_RUNNER_URL", "http://127.0.0.1:8001")
    return Service(load_apps(), Store(data_dir), HttpRunner(runner_url))


def build() -> FastAPI:
    return create_app(build_service())


def serve() -> None:
    uvicorn.run(
        build(),
        host=os.environ.get("QATA_HOST", "127.0.0.1"),
        port=int(os.environ.get("QATA_PORT", "8000")),
    )


def serve_mcp() -> None:
    server = create_server(build_service())

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    anyio.run(run)
