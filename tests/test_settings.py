"""設定の feature の手順。"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pytest_bdd import given, parsers, scenarios, then, when

from qata_server import main
from qata_server.settings import Settings

scenarios("settings.feature")

ROOT = Path(__file__).resolve().parent.parent
# 環境変数に触れる書き方。子のプロセスに環境をそのまま渡す {**os.environ} だけは許す
ENVIRON = re.compile(r"\benviron\b|\bgetenv\b")
PASS_THROUGH = re.compile(r"\{\*\*os\.environ\b")


def reads_environ(code: str) -> bool:
    return bool(ENVIRON.search(PASS_THROUGH.sub("", code)))


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


@given("qata の環境変数を置いていない")
def no_qata_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.upper().startswith("QATA_"):
            monkeypatch.delenv(name)


@given(parsers.re(r'環境変数 "(?P<name>[^"]+)" を "(?P<value>[^"]*)" にする'))
def set_env(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)


@then(parsers.parse('設定の "{field}" は "{expected}"'))
def setting_is(field: str, expected: str) -> None:
    value = getattr(Settings(), field)
    if isinstance(value, Path):
        assert value == Path(expected)
    else:
        assert str(value) == expected


@then("契約の判定を読み込み直しても、誤りにならない")
def contract_check_imports() -> None:
    # 読み込みの状態をほかのテストに残さないよう、別のプロセスで読み込む
    result = subprocess.run(
        [sys.executable, "-c", "import qata_server.application.contract_check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8", **os.environ},
    )
    assert result.returncode == 0, result.stderr


@given('環境変数 "QATA_DATA_DIR" を一時フォルダにする')
def data_dir_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QATA_DATA_DIR", str(tmp_path / "data"))


@when("server を立ち上げる")
def serve(monkeypatch: pytest.MonkeyPatch, ctx: dict[str, Any]) -> None:
    calls: list[dict[str, Any]] = []

    def record(app: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(main.uvicorn, "run", record)
    main.serve()
    ctx["uvicorn_calls"] = calls


@then(parsers.parse('"{host}" の {port:d} 番で待ち受ける'))
def listens_on(ctx: dict[str, Any], host: str, port: int) -> None:
    assert ctx["uvicorn_calls"] == [{"host": host, "port": port}]


@then(parsers.parse('設定を読むと、"{field}" の誤りになる'))
def setting_rejected(field: str) -> None:
    with pytest.raises(ValidationError) as info:
        Settings()
    assert [error["loc"] for error in info.value.errors()] == [(field,)]


@given(
    parsers.parse('保存先を一時フォルダに、runner の場所を "{url}" にした設定'),
    target_fixture="settings",
)
def settings_for(tmp_path: Path, url: str) -> Settings:
    return Settings(data_dir=tmp_path / "data", runner_url=url)


@when("その設定で server を組み立てる")
def build_with(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, ctx: dict[str, Any]
) -> None:
    urls: list[str] = []

    class RecordingRunner:
        def __init__(self, base_url: str) -> None:
            urls.append(base_url)

    monkeypatch.setattr(main, "HttpRunner", RecordingRunner)
    main.build(settings)
    ctx["runner_urls"] = urls


@then("保存先の一時フォルダに、保存のファイルができる")
def store_in_data_dir(settings: Settings) -> None:
    assert (settings.data_dir / "qata.sqlite3").is_file()


@then(parsers.parse('runner への道具は "{url}" を指す'))
def runner_points_to(ctx: dict[str, Any], url: str) -> None:
    assert ctx["runner_urls"] == [url]


@then("src と scripts に、settings.py を通さずに環境変数を読むところがない")
def no_environ_reads() -> None:
    files = sorted((ROOT / "src").rglob("*.py")) + sorted(
        (ROOT / "scripts").rglob("*.py")
    )
    readers = [
        path.relative_to(ROOT).as_posix()
        for path in files
        if reads_environ(path.read_text(encoding="utf-8"))
    ]
    assert readers == []


@then(parsers.re(r"(?P<code>.+) は、環境変数を読むとみなす$"))
def detected(code: str) -> None:
    assert reads_environ(code)


@then(parsers.re(r"(?P<code>.+) は、環境変数を読むとみなさない$"))
def not_detected(code: str) -> None:
    assert not reads_environ(code)
