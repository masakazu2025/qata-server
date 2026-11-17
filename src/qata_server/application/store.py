"""登録したテストケースと実行の結果を SQLite に、スクショを PNG のファイルに保存する。

記録は契約の形（testcase_record・run）の JSON のまま持つ。中を探す要がないため（S4）。
ただし、タグは絞り込みに使うので、テストケースとタグの組の表にも持つ（S13）。
表は SQLAlchemy の Core で定義し、表の形の変更は Alembic で記録する（S11）。
Store を作るときに、マイグレーションを最新まで当てる。
"""

import re
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Column,
    Connection,
    Engine,
    MetaData,
    Table,
    Text,
    create_engine,
    delete,
    event,
    func,
    literal_column,
    select,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import URL

from qata_server.contracts.server_schema import Run, TestcaseRecord

_ID = re.compile(r"^[a-z]+_[0-9a-f]{32}$")

# src/qata_server/application/store.py から見て、src/qata_server/migrations
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

# 表の形の正。変えたら、マイグレーションを一つ足す（README の「表の形を変える」）
METADATA = MetaData()

testcases = Table(
    "testcases",
    METADATA,
    Column("id", Text, primary_key=True),
    Column("app_id", Text, nullable=False),
    Column("record", Text, nullable=False),
)

# 絞り込み用のテストケースとタグの組。正は記録の中のタグで、保存のたびに写す（S13）
testcase_tags = Table(
    "testcase_tags",
    METADATA,
    Column("testcase_id", Text, primary_key=True),
    Column("tag", Text, primary_key=True),
)

runs = Table(
    "runs",
    METADATA,
    Column("id", Text, primary_key=True),
    Column("testcase_id", Text, nullable=False),
    Column("record", Text, nullable=False),
)

# 新しい順は、入れた順（SQLite の rowid）の逆（S4）
_NEWEST_FIRST = literal_column("rowid").desc()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def database_url(data_dir: Path) -> URL:
    return URL.create("sqlite", database=str(data_dir / "qata.sqlite3"))


def upgrade(connection: Connection) -> None:
    """マイグレーションを最新まで当てる。"""
    # 出力は stderr に寄せる。MCP は stdout を通り道に使うため
    config = Config(stdout=sys.stderr)
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


def upgrade_exclusively(data_dir: Path) -> None:
    """ほかのプロセスと一つずつ、マイグレーションを最新まで当てる。

    REST と MCP が同時に立ち上がっても、同じマイグレーションを二度当てないように、
    当てる間は SQLite のファイルを排他で握る。あとから来たほうは待ってから版を読むので、
    当て終わったものは当てない。
    """
    # 待つのは 30 秒まで。表を作り直すマイグレーションは時間がかかるため
    engine = create_engine(database_url(data_dir), connect_args={"timeout": 30})

    # pysqlite は自分で BEGIN を出し、DDL の前で区切ってしまう。それを止め、
    # 始めに BEGIN EXCLUSIVE を出す（SQLAlchemy の SQLite の説明の書き方）
    @event.listens_for(engine, "connect")
    def _no_driver_begin(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin_exclusive(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN EXCLUSIVE")

    try:
        with engine.begin() as connection:
            upgrade(connection)
    finally:
        engine.dispose()


class Store:
    def __init__(self, data_dir: Path) -> None:
        self._screenshots = data_dir / "screenshots"
        self._screenshots.mkdir(parents=True, exist_ok=True)
        upgrade_exclusively(data_dir)
        self._engine: Engine = create_engine(database_url(data_dir))

    # テストケース

    def save_testcase(self, record: TestcaseRecord) -> None:
        testcase_id = record.id.root
        tags = record.testcase.tags.root if record.testcase.tags else []
        statement = insert(testcases).values(
            id=testcase_id,
            app_id=record.testcase.app_id.root,
            record=record.model_dump_json(exclude_none=True),
        )
        # 承認で上書きするときも、行は残すので並びは変わらない
        statement = statement.on_conflict_do_update(
            index_elements=[testcases.c.id],
            set_={"record": statement.excluded.record},
        )
        with self._engine.begin() as db:
            db.execute(statement)
            # 上書きのときも、タグの組は記録に合わせて入れ直す
            db.execute(
                delete(testcase_tags).where(testcase_tags.c.testcase_id == testcase_id)
            )
            if tags:
                db.execute(
                    testcase_tags.insert(),
                    [{"testcase_id": testcase_id, "tag": t.root} for t in tags],
                )

    def get_testcase(self, testcase_id: str) -> TestcaseRecord | None:
        with self._engine.connect() as db:
            record = db.scalar(
                select(testcases.c.record).where(testcases.c.id == testcase_id)
            )
        return TestcaseRecord.model_validate_json(record) if record else None

    def list_testcases(
        self, app_id: str | None = None, tags: Iterable[str] = ()
    ) -> list[TestcaseRecord]:
        """新しい順。tags を渡すと、それを全部持つもの（文字の完全な一致）だけ。"""
        query = select(testcases.c.record).order_by(_NEWEST_FIRST)
        if app_id is not None:
            query = query.where(testcases.c.app_id == app_id)
        # 重なりは一つと見なす（契約の tag_filter）。空なら絞り込まない。
        # タグがいくつでも一つの問い合わせにする（重ねると SQLite の深さの上限に届く）
        wanted = set(tags)
        if wanted:
            having_all = (
                select(testcase_tags.c.testcase_id)
                .where(testcase_tags.c.tag.in_(wanted))
                .group_by(testcase_tags.c.testcase_id)
                .having(func.count() == len(wanted))
            )
            query = query.where(testcases.c.id.in_(having_all))
        with self._engine.connect() as db:
            records = db.scalars(query).all()
        return [TestcaseRecord.model_validate_json(r) for r in records]

    def delete_testcase(self, testcase_id: str) -> bool:
        """消したら True。実行の結果は残す。"""
        with self._engine.begin() as db:
            result = db.execute(delete(testcases).where(testcases.c.id == testcase_id))
            db.execute(
                delete(testcase_tags).where(testcase_tags.c.testcase_id == testcase_id)
            )
        return result.rowcount > 0

    # 実行の結果

    def save_run(self, run: Run) -> None:
        with self._engine.begin() as db:
            db.execute(
                runs.insert().values(
                    id=run.id.root,
                    testcase_id=run.testcase_id.root,
                    record=run.model_dump_json(exclude_none=True),
                )
            )

    def get_run(self, run_id: str) -> Run | None:
        with self._engine.connect() as db:
            record = db.scalar(select(runs.c.record).where(runs.c.id == run_id))
        return Run.model_validate_json(record) if record else None

    def list_runs(self, testcase_id: str | None = None) -> list[Run]:
        """新しい順。"""
        query = select(runs.c.record).order_by(_NEWEST_FIRST)
        if testcase_id is not None:
            query = query.where(runs.c.testcase_id == testcase_id)
        with self._engine.connect() as db:
            records = db.scalars(query).all()
        return [Run.model_validate_json(r) for r in records]

    # スクショ

    def save_screenshot(self, png: bytes) -> str:
        screenshot_id = new_id("ss")
        (self._screenshots / f"{screenshot_id}.png").write_bytes(png)
        return screenshot_id

    def get_screenshot(self, screenshot_id: str) -> bytes | None:
        # ID はファイルの名前に使うので、振った形のものだけを受ける
        if not _ID.match(screenshot_id):
            return None
        path = self._screenshots / f"{screenshot_id}.png"
        return path.read_bytes() if path.is_file() else None
