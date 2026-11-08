"""REST の入口と、runner への HTTP の道具の feature の手順。"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from generate_contracts import CONTRACTS_DIR
from pytest_bdd import given, parsers, scenarios, then, when
from support import FakeRunner, load_example

from qata_server.application import RunnerUnavailable, Service, Store, load_apps
from qata_server.application.contract_check import problems
from qata_server.contracts import server_schema, testcase_schema
from qata_server.contracts.part_dictionary_schema import PartDictionary
from qata_server.rest import create_app
from qata_server.runner_http import HttpRunner

scenarios("rest.feature", "runner_http.feature")

# openapi.yaml が指す契約と、そこから生成した型
SERVER = "schemas/server.schema.json#/$defs/"
MODELS = {
    SERVER + "app_summary": server_schema.AppSummary,
    "schemas/part-dictionary.schema.json": PartDictionary,
    "schemas/testcase.schema.json": testcase_schema.Testcase,
    SERVER + "validation_result": server_schema.ValidationResult,
    SERVER + "testcase_record": server_schema.TestcaseRecord,
    SERVER + "run": server_schema.Run,
    SERVER + "error_response": server_schema.ErrorResponse,
}
COMPONENTS = "#/components/schemas/"
METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def client(tmp_path: Path, runner: FakeRunner) -> TestClient:
    service = Service(load_apps(), Store(tmp_path / "data"), runner)
    return TestClient(create_app(service))


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def contract_openapi() -> dict[str, Any]:
    return yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8"))


def fastapi_openapi(client: TestClient) -> dict[str, Any]:
    return client.app.openapi()


def resolve(node: Any, document: dict[str, Any]) -> Any:
    """同じ文書の中の $ref を、中身に置き換える。"""
    if isinstance(node, dict):
        if "$ref" in node and node["$ref"].startswith("#/"):
            target = document
            for key in node["$ref"][2:].split("/"):
                target = target[key]
            return resolve(target, document)
        return {k: resolve(v, document) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve(v, document) for v in node]
    return node


def operations(document: dict[str, Any]):
    for path, item in document["paths"].items():
        shared = item.get("parameters", [])
        for method, operation in item.items():
            if method in METHODS:
                yield path, method, shared + operation.get("parameters", [])


def outline(document: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """道ごとに、operationId・引数・本文・応答のコードと media type。"""
    found = {}
    for path, method, parameters in operations(document):
        operation = document["paths"][path][method]
        parameters = [resolve(p, document) for p in parameters]
        body = operation.get("requestBody")
        found[(path, method)] = {
            "operationId": operation["operationId"],
            "parameters": sorted(
                (p["name"], p["in"], p.get("required", False)) for p in parameters
            ),
            "requestBody": body
            and (body.get("required", False), sorted(body["content"])),
            "responses": {
                code: sorted(resolve(r, document).get("content", {}))
                for code, r in operation["responses"].items()
            },
        }
    return found


def schemas(document: dict[str, Any]):
    """道ごとの本文と応答の schema。"""
    for path, method, _ in operations(document):
        operation = document["paths"][path][method]
        body = operation.get("requestBody")
        if body:
            for media, content in body["content"].items():
                yield (path, method, "requestBody", media), content["schema"]
        for code, response in operation["responses"].items():
            if "$ref" in response:  # components/responses だけをたどる
                response = resolve(response, document)
            for media, entry in response.get("content", {}).items():
                yield (path, method, code, media), entry["schema"]


def shape(schema: dict[str, Any], name_of) -> Any:
    """schema を、指す型の名前で表す。"""
    if "$ref" in schema:
        return {"model": name_of(schema["$ref"])}
    if schema.get("type") == "array":
        return {"array": shape(schema["items"], name_of)}
    return {k: v for k, v in schema.items() if k != "title"}


# OpenAPI


@then(
    "FastAPI が出す OpenAPI の道ごとの operationId・引数・本文・応答のコードと "
    "media type が、openapi.yaml と同じ"
)
def openapi_outline_matches(client: TestClient) -> None:
    expected = outline(contract_openapi())
    actual = outline(fastapi_openapi(client))
    assert sorted(actual) == sorted(expected)
    for key, value in expected.items():
        assert actual[key] == value, key


@then(
    "openapi.yaml が契約を指すところで、FastAPI が出す OpenAPI は、"
    "その契約から生成した型を指す"
)
def openapi_points_to_generated_types(client: TestClient) -> None:
    expected = dict(schemas(contract_openapi()))
    actual = dict(schemas(fastapi_openapi(client)))
    assert sorted(actual) == sorted(expected)
    for key, schema in expected.items():
        want = shape(schema, lambda ref: MODELS[ref].__name__)
        got = shape(actual[key], lambda ref: ref.removeprefix(COMPONENTS))
        assert got == want, key


@then("FastAPI が出す OpenAPI の型の中身は、生成した型の JSON Schema と同じ")
def openapi_components_match_generated_types(client: TestClient) -> None:
    document = fastapi_openapi(client)
    for model in MODELS.values():
        mode = "validation" if model is testcase_schema.Testcase else "serialization"
        own = model.model_json_schema(mode=mode)
        expected = normalized(resolve(own, {"$defs": own.pop("$defs", {})}))
        actual = normalized(
            resolve(document["components"]["schemas"][model.__name__], document)
        )
        assert actual == expected, (model.__name__, difference(actual, expected))


def normalized(node: Any) -> Any:
    """書き方だけの違いをそろえる。

    - 値が null の鍵を外す（FastAPI は OpenAPI を出すときに省く）。
    - discriminator の mapping に残る参照を、型の名前にする（置き場所が違う）。
    """
    if isinstance(node, dict):
        return {k: normalized(v) for k, v in node.items() if v is not None}
    if isinstance(node, list):
        return [normalized(v) for v in node]
    if isinstance(node, str):
        return node.removeprefix(COMPONENTS).removeprefix("#/$defs/")
    return node


def difference(actual: Any, expected: Any, path: str = "") -> str:
    """最初に食い違う場所（失敗したときに読むため）。"""
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in sorted(set(actual) | set(expected)):
            if actual.get(key) != expected.get(key):
                return difference(actual.get(key), expected.get(key), f"{path}/{key}")
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) == len(expected):
            for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
                if a != e:
                    return difference(a, e, f"{path}/{i}")
    return f"{path}: {actual!r} != {expected!r}"


# REST


def post_testcase(client: TestClient, ctx, path: str, testcase: Any) -> None:
    ctx["response"] = client.post(path, json=testcase)
    if ctx["response"].status_code == 201:
        ctx["testcase_id"] = ctx["response"].json()["id"]


@given("runner に届かない")
def runner_unreachable(runner: FakeRunner) -> None:
    runner.mode = "unreachable"


@when(parsers.parse('契約の例 "{file_name}" を "{path}" に POST する'))
def post_example(client: TestClient, ctx, file_name: str, path: str) -> None:
    post_testcase(client, ctx, path, load_example(file_name))


@when(parsers.parse('部品を "{part}" にした例を "{path}" に POST する'))
def post_unknown_part(client: TestClient, ctx, part: str, path: str) -> None:
    testcase = load_example("testcase.add.json")
    testcase["steps"][0]["part"] = part
    post_testcase(client, ctx, path, testcase)


@when(parsers.parse('人の確認が{need}例を "{path}" に POST する'))
def post_needs_review(client: TestClient, ctx, need: str, path: str) -> None:
    post_testcase(
        client,
        ctx,
        path,
        {**load_example("testcase.add.json"), "needs_review": need == "要る"},
    )


@when(parsers.parse('JSON でない本文を "{path}" に POST する'))
def post_not_json(client: TestClient, ctx, path: str) -> None:
    ctx["response"] = client.post(
        path, content=b"{not json", headers={"content-type": "application/json"}
    )


@when(parsers.parse('"{path}" を GET する'))
def get_path(client: TestClient, ctx, path: str) -> None:
    ctx["response"] = client.get(path)


@when("登録したテストケースを実行する")
def run_registered(client: TestClient, ctx) -> None:
    ctx["response"] = client.post(f"/testcases/{ctx['testcase_id']}/runs")
    if ctx["response"].status_code == 201:
        ctx["run"] = ctx["response"].json()


@when("登録したテストケースを承認する")
def approve_registered(client: TestClient, ctx) -> None:
    ctx["response"] = client.post(f"/testcases/{ctx['testcase_id']}/approve")


@when("登録したテストケースを消す")
def delete_registered(client: TestClient, ctx) -> None:
    ctx["response"] = client.delete(f"/testcases/{ctx['testcase_id']}")


@then(parsers.parse('応答は {status:d} で、本文が契約 "{contract}" に通る'))
def response_matches(ctx, status: int, contract: str) -> None:
    response = ctx["response"]
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/json"
    found = problems(contract, response.json())
    assert not found, found


@then(parsers.parse("応答は {status:d} で、本文はない"))
def response_empty(ctx, status: int) -> None:
    assert ctx["response"].status_code == status
    assert ctx["response"].content == b""


@then(parsers.parse('実行の結果は "{status}"'))
def run_status(ctx, status: str) -> None:
    assert ctx["run"]["status"] == status


@then("最初のステップのスクショが PNG で取れる")
def screenshot_png(client: TestClient, ctx) -> None:
    screenshot_id = ctx["run"]["steps"][0]["screenshot_id"]
    response = client.get(f"/screenshots/{screenshot_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


@then(parsers.parse('"{path}" の一覧は {count:d} 件で、どれも契約 "{contract}" に通る'))
def list_matches(client: TestClient, path: str, count: int, contract: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == count
    for item in items:
        found = problems(contract, item)
        assert not found, found


@then(parsers.parse('問題の code は "{code}"'))
def validation_code(ctx, code: str) -> None:
    assert [e["code"] for e in ctx["response"].json()["errors"]] == [code]


@then(parsers.parse('エラーの code は "{code}"'))
def error_code(ctx, code: str) -> None:
    assert ctx["response"].json()["error"]["code"] == code


# runner への HTTP


class RunnerServer:
    """httpx の MockTransport で、runner の代わりに応答する。"""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.respond = lambda request: httpx.Response(200, json={})

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)


@pytest.fixture
def runner_server() -> RunnerServer:
    return RunnerServer()


@pytest.fixture
def http_runner(runner_server: RunnerServer) -> HttpRunner:
    transport = httpx.MockTransport(runner_server.handle)
    return HttpRunner("http://runner.test", transport=transport)


@given(parsers.parse('runner は契約の例 "{file_name}" を返す'))
def runner_returns_example(runner_server: RunnerServer, file_name: str) -> None:
    body = load_example(file_name)
    runner_server.respond = lambda request: httpx.Response(200, json=body)


@given("runner は JSON でない本文を返す")
def runner_returns_html(runner_server: RunnerServer) -> None:
    runner_server.respond = lambda request: httpx.Response(200, text="<html>")


@given("runner は HTTP 500 を返す")
def runner_returns_500(runner_server: RunnerServer) -> None:
    runner_server.respond = lambda request: httpx.Response(500, text="boom")


@given("runner が立ち上がっていない", target_fixture="http_runner")
def runner_not_started() -> HttpRunner:
    # どこも待ち受けていない場所（ポート 9）に送る
    return HttpRunner("http://127.0.0.1:9", timeout=2.0)


@when(parsers.parse('契約の例 "{file_name}" の命令を送る'))
def send_command(http_runner: HttpRunner, ctx, file_name: str) -> None:
    ctx["command"] = load_example(file_name)
    ctx["returned"] = http_runner.run(ctx["command"])


@then(parsers.parse('runner は "{path}" に、その命令をそのまま受けた'))
def runner_received(runner_server: RunnerServer, ctx, path: str) -> None:
    (request,) = runner_server.requests
    assert request.method == "POST"
    assert request.url.path == path
    assert json.loads(request.content) == ctx["command"]


@then(parsers.parse('返ってきた本文は契約の例 "{file_name}" と同じ'))
def returned_example(ctx, file_name: str) -> None:
    assert ctx["returned"] == load_example(file_name)


@then(parsers.parse('返ってきた本文は "{text}"'))
def returned_text(ctx, text: str) -> None:
    assert ctx["returned"] == text


@then("命令を送ると、runner に届かないとされる")
def send_unavailable(http_runner: HttpRunner) -> None:
    with pytest.raises(RunnerUnavailable):
        http_runner.run(load_example("runner-command.json"))
