"""application 層の feature の手順。runner は偽物を使う。"""

import base64
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from generate_contracts import CONTRACTS_DIR
from pytest_bdd import given, parsers, scenarios, then, when

from qata_server.application import (
    AppConfigError,
    NotFound,
    RunnerUnavailable,
    Service,
    ServiceError,
    Store,
    load_apps,
)
from qata_server.application.apps import APPS_DIR
from qata_server.application.contract_check import problems

scenarios("validation.feature", "testcases.feature", "runs.feature", "apps.feature")

EXAMPLES_DIR = CONTRACTS_DIR / "examples"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_example(file_name: str) -> Any:
    return json.loads((EXAMPLES_DIR / file_name).read_text(encoding="utf-8"))


def png_for(index: int) -> bytes:
    return PNG_SIGNATURE + f"step {index}".encode()


class FakeRunner:
    """決まった結果を返す runner。受けた命令を覚えておく。"""

    def __init__(self) -> None:
        self.text = "表示は 3 です"
        self.mode = "ok"
        self.abort_at: int | None = None
        self.commands: list[dict[str, Any]] = []

    def run(self, command: dict[str, Any]) -> Any:
        if self.mode == "unreachable":
            raise RunnerUnavailable("runner に届かない（偽物）")
        self.commands.append(copy.deepcopy(command))
        base = {
            "run_id": command["run_id"],
            "started_at": "2026-11-08T10:06:00+09:00",
            "finished_at": "2026-11-08T10:06:03+09:00",
        }
        if self.mode == "broken":
            return {**base, "status": "done", "steps": []}
        if self.mode == "launch_failed":
            error = {"code": "launch_failed", "message": "アプリを起動できない"}
            return {**base, "status": "aborted", "error": error, "steps": []}
        steps = []
        for i, step in enumerate(command["steps"]):
            if i == self.abort_at:
                error = {"code": "step_failed", "message": "ボタンが見つからない"}
                steps.append({"index": i, "status": "error", "error": error})
                return {**base, "status": "aborted", "error": error, "steps": steps}
            result = {
                "index": i,
                "status": "ok",
                "screenshot": {
                    "media_type": "image/png",
                    "data_base64": base64.b64encode(png_for(i)).decode(),
                },
            }
            if step["type"] == "read_text":
                result["text"] = self.text
            steps.append(result)
        return {**base, "status": "completed", "steps": steps}


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "data")


@pytest.fixture
def service(store: Store, runner: FakeRunner) -> Service:
    return Service(load_apps(), store, runner)


@pytest.fixture
def ctx() -> dict[str, Any]:
    """シナリオの中で手順の間に渡すもの。"""
    return {}


def walk_to_parent(document, pointer: str):
    *parents, last = pointer.split("/")[1:]
    node = document
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node, (int(last) if isinstance(node, list) else last)


def assert_contract(contract: str, data: Any) -> None:
    found = problems(contract, data)
    assert not found, found


def dump(model) -> Any:
    return model.model_dump(mode="json", exclude_none=True)


def refused(action, code: str) -> None:
    with pytest.raises(ServiceError) as caught:
        action()
    assert caught.value.code == code, caught.value.message


# テストケース


@given(
    parsers.parse('契約の例 "{file_name}" のテストケース'), target_fixture="testcase"
)
def given_testcase(file_name: str):
    return load_example(file_name)


@when(parsers.parse('"{pointer}" を {value} に変える'))
def change_value(testcase, pointer: str, value: str) -> None:
    parent, key = walk_to_parent(testcase, pointer)
    parent[key] = json.loads(value)


@when("検証する")
def validate(service: Service, testcase, ctx) -> None:
    ctx["validation"] = service.validate_testcase(testcase)


@when("登録する")
def register(service: Service, testcase, ctx) -> None:
    result = service.register_testcase(testcase)
    ctx["register"] = result
    if result.registered:
        ctx["record"] = result.testcase_record


def register_example(service: Service, ctx, needs_review: bool) -> None:
    testcase = load_example("testcase.add.json")
    testcase["needs_review"] = needs_review
    result = service.register_testcase(testcase)
    assert result.registered, result.errors
    ctx.setdefault("records", []).append(result.testcase_record)
    ctx["record"] = result.testcase_record


@given("人の確認が要るテストケースを登録した")
def given_needs_review(service: Service, ctx) -> None:
    register_example(service, ctx, needs_review=True)


@given("人の確認が要らないテストケースを登録した")
def given_no_review(service: Service, ctx) -> None:
    register_example(service, ctx, needs_review=False)


@when("承認する")
def approve(service: Service, ctx) -> None:
    ctx["record"] = service.approve_testcase(ctx["record"].id.root)


@when("テストケースを消す")
def delete(service: Service, ctx) -> None:
    service.delete_testcase(ctx["record"].id.root)


@then("検証を通る")
def validation_passes(ctx) -> None:
    result = ctx["validation"]
    assert result.valid and not result.errors, dump(result)


@then(parsers.parse('"{path}" が "{code}" ではじかれる'))
def validation_rejects(ctx, path: str, code: str) -> None:
    result = dump(ctx["validation"])
    assert_contract("server.schema.json#/$defs/validation_result", result)
    assert not result["valid"]
    assert {(e["path"], e["code"]) for e in result["errors"]} == {(path, code)}, result


@then(parsers.parse("問題が {count:d} つ返る"))
def error_count(ctx, count: int) -> None:
    assert len(ctx["validation"].errors) == count, dump(ctx["validation"])


@then("登録できる")
def registered(ctx) -> None:
    result = dump(ctx["register"])
    assert_contract("server.schema.json#/$defs/register_result", result)
    assert result["registered"], result


@then("登録できない")
def not_registered(ctx) -> None:
    result = dump(ctx["register"])
    assert_contract("server.schema.json#/$defs/register_result", result)
    assert not result["registered"] and result["errors"], result


@then(parsers.parse('確認の状態は "{status}"'))
def review_status(ctx, status: str) -> None:
    assert ctx["record"].review_status.value == status


@then(parsers.parse('登録したテストケースが契約 "{contract}" に通る'))
def record_matches_contract(ctx, contract: str) -> None:
    assert_contract(contract, dump(ctx["record"]))


@then(parsers.parse('登録したテストケースを取ると、確認の状態は "{status}"'))
def stored_review_status(service: Service, ctx, status: str) -> None:
    record = service.get_testcase(ctx["record"].id.root)
    assert record.review_status.value == status


@then(parsers.parse('承認すると "{code}" で断られる'))
def approve_refused(service: Service, ctx, code: str) -> None:
    refused(lambda: service.approve_testcase(ctx["record"].id.root), code)


@then(parsers.parse("テストケースの一覧は {count:d} 件"))
def count_of_testcases(service: Service, count: int) -> None:
    assert len(service.list_testcases()) == count


@then(parsers.parse("テストケースの一覧は {count:d} 件で、あとに登録したものが先"))
def newest_testcase_first(service: Service, ctx, count: int) -> None:
    ids = [r.id.root for r in service.list_testcases()]
    assert ids == [r.id.root for r in reversed(ctx["records"])]
    assert len(ids) == count


@then(parsers.parse('アプリ "{app_id}" で絞ったテストケースの一覧は {count:d} 件'))
def count_of_testcases_by_app(service: Service, app_id: str, count: int) -> None:
    assert len(service.list_testcases(app_id)) == count


@then("登録したテストケースは見つからない")
def registered_case_gone(service: Service, ctx) -> None:
    with pytest.raises(NotFound):
        service.get_testcase(ctx["record"].id.root)


# 部品の辞書


@then(parsers.parse('アプリの一覧に "{app_id}" の "{name}" がある'))
def app_listed(service: Service, app_id: str, name: str) -> None:
    assert {"app_id": app_id, "name": name} in [dump(a) for a in service.list_apps()]


@then(parsers.parse('"{app_id}" の部品の辞書が契約 "{contract}" に通る'))
def dictionary_matches_contract(service: Service, app_id: str, contract: str) -> None:
    assert_contract(contract, dump(service.get_part_dictionary(app_id)))


@then(parsers.parse('"{app_id}" の部品の辞書は見つからない'))
def dictionary_missing(service: Service, app_id: str) -> None:
    refused(lambda: service.get_part_dictionary(app_id), "not_found")


# 実行


@given(parsers.parse('runner は表示に "{text}" を返す'))
def runner_text(runner: FakeRunner, text: str) -> None:
    runner.text = text


@given(parsers.parse("runner は {number:d} 番目のステップで止まる"))
def runner_aborts(runner: FakeRunner, number: int) -> None:
    runner.abort_at = number - 1


@given("runner はアプリを起動できない")
def runner_launch_fails(runner: FakeRunner) -> None:
    runner.mode = "launch_failed"


@given("runner は契約に合わない結果を返す")
def runner_broken(runner: FakeRunner) -> None:
    runner.mode = "broken"


@given("runner に届かない")
def runner_unreachable(runner: FakeRunner) -> None:
    runner.mode = "unreachable"


@given("実行した")
@when("実行する")
def run(service: Service, ctx) -> None:
    run = service.run_testcase(ctx["record"].id.root)
    ctx.setdefault("runs", []).append(run)
    ctx["run"] = run


@then(parsers.parse('実行すると "{code}" で断られる'))
def run_refused(service: Service, ctx, code: str) -> None:
    refused(lambda: service.run_testcase(ctx["record"].id.root), code)


@then(parsers.parse('実行の結果は "{status}"'))
def run_status(ctx, status: str) -> None:
    assert ctx["run"].status.value == status, dump(ctx["run"])


@then(parsers.parse('ステップの結果は "{statuses}"'))
def step_statuses(ctx, statuses: str) -> None:
    actual = [s.status.value for s in ctx["run"].steps]
    assert actual == statuses.split(","), dump(ctx["run"])


@then(parsers.parse('確認事項で取り出した値は "{value}"'))
def extracted_value(ctx, value: str) -> None:
    assert ctx["run"].steps[-1].actual == value, dump(ctx["run"])


@then(parsers.parse('実行のエラーは "{code}"'))
def run_error(ctx, code: str) -> None:
    assert ctx["run"].error.code == code, dump(ctx["run"])


@then(parsers.parse('実行の結果が契約 "{contract}" に通る'))
def run_matches_contract(ctx, contract: str) -> None:
    assert_contract(contract, dump(ctx["run"]))


@then(parsers.parse('runner への命令が契約 "{contract}" に通る'))
def command_matches_contract(runner: FakeRunner, contract: str) -> None:
    assert_contract(contract, runner.commands[-1])


@then(parsers.parse('runner への命令は親の例 "{file_name}" と、run_id のほかは同じ'))
def command_matches_example(runner: FakeRunner, file_name: str) -> None:
    command = {**runner.commands[-1], "run_id": "-"}
    assert command == {**load_example(file_name), "run_id": "-"}


@then("どのステップにもスクショがあり、runner が撮った PNG が取れる")
def screenshots_saved(service: Service, ctx) -> None:
    for step in ctx["run"].steps:
        assert step.screenshot_id is not None
        assert service.get_screenshot(step.screenshot_id.root) == png_for(step.index)


@then(parsers.parse("実行の結果の一覧は {count:d} 件"))
def run_count(service: Service, count: int) -> None:
    assert len(service.list_runs()) == count


@then(parsers.parse("実行の結果の一覧は {count:d} 件で、あとに実行したものが先"))
def runs_newest_first(service: Service, ctx, count: int) -> None:
    testcase_id = ctx["record"].id.root
    ids = [r.id.root for r in service.list_runs(testcase_id)]
    assert ids == [r.id.root for r in reversed(ctx["runs"])]
    assert len(ids) == count
    assert service.list_runs("tc_none") == []


@then("実行の結果を ID で取れる")
def run_by_id(service: Service, ctx) -> None:
    assert service.get_run(ctx["run"].id.root) == ctx["run"]


@then("実行の結果は残っている")
def run_kept(service: Service, ctx) -> None:
    assert service.get_run(ctx["run"].id.root) == ctx["run"]


# アプリの設定


@then("置いてあるアプリの設定がすべて読める")
def all_apps_load() -> None:
    assert len(load_apps()) == len(list(APPS_DIR.glob("*.json")))


@given("電卓の設定", target_fixture="config")
def calculator_config():
    return json.loads((APPS_DIR / "calculator.json").read_text(encoding="utf-8"))


@when(parsers.parse('部品 "{part}" の "{action}" の規則を {rule} に変える'))
def change_rule(config, part: str, action: str, rule: str) -> None:
    config["parts"][part]["rules"] = {action: json.loads(rule)}


def load_config(tmp_path: Path, config) -> dict:
    directory = tmp_path / "apps"
    directory.mkdir()
    (directory / "app.json").write_text(json.dumps(config), encoding="utf-8")
    return load_apps(directory)


@then(parsers.parse('設定を読むと "{reason}" ではじかれる'))
def config_rejected(tmp_path: Path, config, reason: str) -> None:
    with pytest.raises(AppConfigError, match=reason):
        load_config(tmp_path, config)


@then(
    parsers.parse('設定を読むと、"{part}" が読んだ "{text}" から取り出す値は "{value}"')
)
def extract_without_rule(
    tmp_path: Path, config, part: str, text: str, value: str
) -> None:
    app = load_config(tmp_path, config)["calculator"]
    assert app.conversions[(part, "expect_text")].extract(text) == value
