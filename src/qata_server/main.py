"""server を組み立てて立ち上げる。設定は環境変数で渡す（読み方は settings.py）。

REST（`qata-server`）と MCP（`qata-server-mcp`、stdio）は別のプロセスで動く。
同じ `QATA_DATA_DIR` を指せば、同じテストケースと実行の結果を見る（S7）。
"""

import anyio
import uvicorn
from fastapi import FastAPI
from mcp.server.stdio import stdio_server

from qata_server.application import Service, Store, load_apps
from qata_server.mcp_server import create_server
from qata_server.rest import create_app
from qata_server.runner_http import HttpRunner
from qata_server.settings import Settings


def build_service(settings: Settings) -> Service:
    return Service(
        load_apps(), Store(settings.data_dir), HttpRunner(settings.runner_url)
    )


def build(settings: Settings) -> FastAPI:
    return create_app(build_service(settings))


def serve() -> None:
    settings = Settings()
    uvicorn.run(build(settings), host=settings.host, port=settings.port)


def serve_mcp() -> None:
    server = create_server(build_service(Settings()))

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    anyio.run(run)
