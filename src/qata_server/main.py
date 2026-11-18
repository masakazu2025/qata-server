"""server を組み立てて立ち上げる。設定は環境変数で渡す（読み方は settings.py）。

REST（web 用）と MCP（AI 用、Streamable HTTP の `/mcp`）は、同じプロセス・同じ
Service で答える。runner への命令は、このプロセスからだけ出る（S12）。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from qata_server.application import Service, Store, contract_check, load_apps
from qata_server.mcp_server import create_server
from qata_server.rest import create_app
from qata_server.runner_http import HttpRunner
from qata_server.settings import Settings

MCP_PATH = "/mcp"


def build_service(settings: Settings) -> Service:
    return Service(
        load_apps(), Store(settings.data_dir), HttpRunner(settings.runner_url)
    )


def build(settings: Settings) -> FastAPI:
    # 読む版の契約がそろっていなければ、ここで落ちる（最初の呼び出しを待たない）
    contract_check.ensure_ready()
    service = build_service(settings)
    app = create_app(service)
    mcp = create_server(service)
    # 待ち受ける場所が手元（127.0.0.1 など）なら、SDK が DNS rebinding の守りを入れる
    mcp_app = mcp.streamable_http_app(streamable_http_path=MCP_PATH, host=settings.host)
    # MCP の道は OpenAPI に出ない（FastAPI の道ではないため）
    app.router.routes.extend(mcp_app.routes)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    app.router.lifespan_context = lifespan
    return app


def serve() -> None:
    settings = Settings()
    uvicorn.run(build(settings), host=settings.host, port=settings.port)
