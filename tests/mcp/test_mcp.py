"""MCP の入口の feature の手順。"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from mcp import Client
from pytest_bdd import given, parsers, scenarios, then, when
from referencing import Resource
from referencing.jsonschema import DRAFT202012
from support import FakeRunner, load_example

from qata_server.application import Service, Store, load_apps
from qata_server.application.contract_check import problems, registry
from qata_server.mcp_server import MCP_TOOLS, create_server
from qata_server.rest import create_app

scenarios("mcp.feature")


def contract_tools() -> list[dict[str, Any]]:
    return json.loads(MCP_TOOLS.read_text(encoding="utf-8"))["tools"]


def contract_validator(tool: str, *pointer: str) -> Draft202012Validator:
    """mcp-tools.json のその場所を、親の JSON Schema の $ref のまま使う検査。

    server の展開（mcp_server._expand）とは別に、referencing で $ref をたどる。
    """
    document = json.loads(MCP_TOOLS.read_text(encoding="utf-8"))
    index = next(i for i, t in enumerate(document["tools"]) if t["name"] == tool)
    uri = MCP_TOOLS.as_uri()
    reg = registry().with_resource(
        uri, Resource(contents=document, specification=DRAFT202012)
    )
    path = "/".join(["#", "tools", str(index), *pointer])
    return Draft202012Validator(
        {"$ref": uri + path}, registry=reg, format_checker=FormatChecker()
    )


class Mcp:
    """同じプロセスの中で server につなぐ MCP のクライアント。"""

    def __init__(self, service: Service) -> None:
        self.server = create_server(service)

    def _session(self, use):
        async def go():
            async with Client(self.server, raise_exceptions=True) as client:
                return await use(client)

        return anyio.run(go)

    def list_tools(self) -> list[dict[str, Any]]:
        async def use(client):
            result = await client.list_tools()
            return [
                t.model_dump(by_alias=True, exclude_none=True) for t in result.tools
            ]

        return self._session(use)

    def call(self, name: str, arguments: dict[str, Any]):
        async def use(client):
            # 一覧を読んでおくと、クライアントが結果を outputSchema で確かめる
            await client.list_tools()
            return await client.call_tool(name, arguments)

        return self._session(use)


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def service(tmp_path: Path, runner: FakeRunner) -> Service:
    return Service(load_apps(), Store(tmp_path / "data"), runner)


@pytest.fixture
def mcp(service: Service) -> Mcp:
    return Mcp(service)


@pytest.fixture
def rest(service: Service) -> TestClient:
    """MCP と同じ Service を使う REST の入口。二つの答えを比べるため。"""
    return TestClient(create_app(service))


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def listed(mcp: Mcp, name: str) -> dict[str, Any]:
    return next(t for t in mcp.list_tools() if t["name"] == name)


def call(mcp: Mcp, ctx, name: str, arguments: dict[str, Any]) -> None:
    result = mcp.call(name, arguments)
    ctx["tool"] = name
    ctx["result"] = result
    structured = result.structured_content
    if not result.is_error and name == "register_testcase" and structured["registered"]:
        ctx["testcase_id"] = structured["testcase_record"]["id"]
    if not result.is_error and name == "run_testcase":
        ctx["run_id"] = structured["id"]


# 道具の定義


@then("qata-server を立ち上げると、同じプロセスが REST と MCP の両方に答える")
def one_process_answers_rest_and_mcp(tmp_path: Path) -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [str(Path(sys.executable).parent / "qata-server")],
        env={
            **os.environ,
            "QATA_PORT": str(port),
            "QATA_DATA_DIR": str(tmp_path / "data"),
        },
    )
    try:
        apps = _wait_for_apps(base, process)
        assert [a["app_id"] for a in apps] == ["calculator"]

        async def go():
            async with Client(f"{base}/mcp") as client:
                names = [t.name for t in (await client.list_tools()).tools]
                return names, await client.call_tool("list_apps", {})

        names, result = anyio.run(go)
        assert names == [t["name"] for t in contract_tools()]
        assert not result.is_error
        assert result.structured_content == {"apps": apps}

        # 手元で待ち受けるので、ほかの名前で届いた MCP の呼び出しは断る（DNS rebinding）
        foreign = httpx.post(
            f"{base}/mcp", headers={"Host": "attacker.example"}, json={}, timeout=5
        )
        assert foreign.status_code == 421
    finally:
        process.terminate()
        process.wait(timeout=10)


def _wait_for_apps(base: str, process: subprocess.Popen) -> list[dict[str, Any]]:
    """立ち上がるまで REST の /apps を読み直す。"""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert process.poll() is None, "qata-server が立ち上がる前に終わった"
        try:
            response = httpx.get(f"{base}/apps", timeout=1)
        except httpx.TransportError:
            time.sleep(0.2)
            continue
        assert response.status_code == 200
        return response.json()
    raise AssertionError("qata-server が 30 秒で立ち上がらなかった")


@then("道具の一覧の名前と説明は、mcp-tools.json と同じ")
def names_and_descriptions(mcp: Mcp) -> None:
    actual = [(t["name"], t["description"]) for t in mcp.list_tools()]
    expected = [(t["name"], t["description"]) for t in contract_tools()]
    assert actual == expected


def walk(node: Any):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


@then("どの道具の inputSchema と outputSchema にも $ref が残っていない")
def no_refs(mcp: Mcp) -> None:
    for tool in mcp.list_tools():
        for key in ("inputSchema", "outputSchema"):
            refs = [n["$ref"] for n in walk(tool[key]) if "$ref" in n]
            assert not refs, (tool["name"], key, refs)


@then("どの道具の inputSchema と outputSchema も、JSON Schema として正しい")
def valid_schemas(mcp: Mcp) -> None:
    for tool in mcp.list_tools():
        for key in ("inputSchema", "outputSchema"):
            Draft202012Validator.check_schema(tool[key])


def example_testcase(kind: str) -> dict[str, Any]:
    testcase = load_example("testcase.add.json")
    if kind == "確認事項のない":
        testcase["steps"] = [s for s in testcase["steps"] if s["type"] != "expect_text"]
    elif kind == "ステップのない":
        testcase["steps"] = []
    return testcase


@then(
    parsers.parse(
        '道具 "{tool}" の inputSchema で、{kind}テストケースは契約と同じく {verdict}'
    )
)
def same_verdict(mcp: Mcp, tool: str, kind: str, verdict: str) -> None:
    arguments = {"testcase": example_testcase(kind)}
    ours = Draft202012Validator(
        listed(mcp, tool)["inputSchema"], format_checker=FormatChecker()
    )
    contract = contract_validator(tool, "inputSchema")
    expected = verdict == "通る"
    assert contract.is_valid(arguments) is expected
    assert ours.is_valid(arguments) is expected


# 呼ぶ


@given("runner に届かない")
def runner_unreachable(runner: FakeRunner) -> None:
    runner.mode = "unreachable"


@given("server の中で想定していない誤りが起きる")
def runner_crashes(runner: FakeRunner) -> None:
    runner.mode = "crash"


@given("runner はほかの実行の最中")
def runner_busy(runner: FakeRunner) -> None:
    runner.mode = "busy"


@then("実行の結果は残っていない")
def no_runs(tmp_path: Path) -> None:
    # mcp と同じ置き場所を開き直して数える
    assert Store(tmp_path / "data").list_runs() == []


@when(parsers.parse('道具 "{name}" を呼ぶ'))
def call_plain(mcp: Mcp, ctx, name: str) -> None:
    call(mcp, ctx, name, {})


@when(parsers.parse('道具 "{name}" を app_id "{app_id}" で呼ぶ'))
def call_with_app(mcp: Mcp, ctx, name: str, app_id: str) -> None:
    call(mcp, ctx, name, {"app_id": app_id})


@when(parsers.parse('道具 "{name}" を引数 {arguments} で呼ぶ'))
def call_with_arguments(mcp: Mcp, ctx, name: str, arguments: str) -> None:
    call(mcp, ctx, name, json.loads(arguments))


@when(parsers.parse('人の確認が{need}例で、道具 "{name}" を呼ぶ'))
def call_with_example(mcp: Mcp, ctx, need: str, name: str) -> None:
    testcase = {**load_example("testcase.add.json"), "needs_review": need == "要る"}
    call(mcp, ctx, name, {"testcase": testcase})


@given(parsers.parse("タグ {tags} の例を、道具 register_testcase で登録した"))
def register_tagged(mcp: Mcp, ctx, tags: str) -> None:
    testcase = {**load_example("testcase.add.json"), "tags": json.loads(tags)}
    call(mcp, ctx, "register_testcase", {"testcase": testcase})
    assert ctx["result"].structured_content["registered"]


@given("タグのない例を、道具 register_testcase で登録した")
def register_untagged(mcp: Mcp, ctx) -> None:
    testcase = load_example("testcase.add.json")
    del testcase["tags"]
    call(mcp, ctx, "register_testcase", {"testcase": testcase})
    assert ctx["result"].structured_content["registered"]


@when(parsers.parse("道具 list_testcases を tags {tags} で呼ぶ"))
def call_with_tags(mcp: Mcp, ctx, tags: str) -> None:
    call(mcp, ctx, "list_testcases", {"tags": json.loads(tags)})


@when(parsers.parse('部品を "{part}" にした例で、道具 "{name}" を呼ぶ'))
def call_with_unknown_part(mcp: Mcp, ctx, part: str, name: str) -> None:
    testcase = load_example("testcase.add.json")
    testcase["steps"][0]["part"] = part
    call(mcp, ctx, name, {"testcase": testcase})


@when(parsers.parse('登録したテストケースで、道具 "{name}" を呼ぶ'))
def call_with_registered(mcp: Mcp, ctx, name: str) -> None:
    call(mcp, ctx, name, {"testcase_id": ctx["testcase_id"]})


@when(parsers.parse('実行の結果で、道具 "{name}" を呼ぶ'))
def call_with_run(mcp: Mcp, ctx, name: str) -> None:
    call(mcp, ctx, name, {"run_id": ctx["run_id"]})


# 結果


@then("結果は契約の outputSchema に通る")
def result_matches(ctx) -> None:
    result = ctx["result"]
    assert not result.is_error, result.content
    validator = contract_validator(ctx["tool"], "outputSchema")
    errors = [e.message for e in validator.iter_errors(result.structured_content)]
    assert not errors, errors
    # 文字でも同じものを返す（structuredContent を読まないクライアントのため）
    assert json.loads(result.content[0].text) == result.structured_content


@then(parsers.parse('結果の "{key}" は {value}'))
def result_value(ctx, key: str, value: str) -> None:
    structured = ctx["result"].structured_content
    if value.endswith(" 件"):
        assert len(structured[key]) == int(value.removesuffix(" 件"))
    else:
        assert structured[key] == json.loads(value)


@then(
    parsers.parse("REST の /testcases を tag {tags} で読むと、同じ {count:d} 件を返す")
)
def same_as_rest(rest: TestClient, ctx, tags: str, count: int) -> None:
    response = rest.get("/testcases", params={"tag": json.loads(tags)})
    assert response.status_code == 200
    testcases = ctx["result"].structured_content["testcases"]
    assert response.json() == testcases
    assert len(testcases) == count


@then(parsers.parse("REST の /testcases を引数なしで読むと、同じ {count:d} 件を返す"))
def same_as_rest_unfiltered(rest: TestClient, ctx, count: int) -> None:
    response = rest.get("/testcases")
    assert response.status_code == 200
    assert response.json() == ctx["result"].structured_content["testcases"]
    assert len(response.json()) == count


@then("タグのない記録には、REST でも MCP でも tags が出ない")
def no_tags_in_untagged(rest: TestClient, ctx) -> None:
    untagged = [
        r
        for r in ctx["result"].structured_content["testcases"]
        if "tags" not in r["testcase"]
    ]
    assert len(untagged) == 1
    response = rest.get(f"/testcases/{untagged[0]['id']}")
    assert "tags" not in response.json()["testcase"]


@then(parsers.parse('問題の code は "{code}"'))
def validation_code(ctx, code: str) -> None:
    errors = ctx["result"].structured_content["errors"]
    assert [e["code"] for e in errors] == [code]


@then(parsers.parse('道具はエラーを返し、code は "{code}"'))
def tool_error(ctx, code: str) -> None:
    result = ctx["result"]
    assert result.is_error
    body = json.loads(result.content[0].text)
    found = problems("server.schema.json#/$defs/error_response", body)
    assert not found, found
    assert body["error"]["code"] == code
