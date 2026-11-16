"""Alembic がマイグレーションを当てるときに読む。

server は Store を作るときに、つないだ connection を渡して当てる（store.upgrade）。
CLI（`uv run alembic ...`）から呼ばれたときは、設定（QATA_DATA_DIR）の保存先につなぐ。
"""

from alembic import context
from sqlalchemy import Connection, create_engine

from qata_server.application.store import METADATA, database_url
from qata_server.settings import Settings


def run(connection: Connection) -> None:
    # SQLite は列の変更を ALTER でできないので、表を作り直す形（batch）で書く
    context.configure(
        connection=connection, target_metadata=METADATA, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    data_dir = Settings().data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    with create_engine(database_url(data_dir)).begin() as cli_connection:
        run(cli_connection)
