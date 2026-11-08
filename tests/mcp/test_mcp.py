"""MCP の入口の feature の手順。"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from mcp import Client, StdioServerParameters
from pytest_bdd import given, parsers, scenarios, then, when
from referencing import Resource
from referencing.jsonschema import DRAFT202012
from support import FakeRunner, load_example

from qata_server.application import Service, Store, load_apps
from qata_server.application.contract_check import problems, registry
from qata_server.mcp_server import MCP_TOOLS, create_server

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
def mcp(tmp_path: Path, runner: FakeRunner) -> Mcp:
    return Mcp(Service(load_apps(), Store(tmp_path / "data"), runner))


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


@then("qata-server-mcp を立ち上げてつなぐと、mcp-tools.json の道具がすべて出る")
def stdio_lists_tools(tmp_path: Path) -> None:
    command = Path(sys.executable).parent / "qata-server-mcp"
    params = StdioServerParameters(
        command=str(command),
        env={**os.environ, "QATA_DATA_DIR": str(tmp_path / "data")},
    )

    async def go():
        async with Client(params) as client:
            return [t.name for t in (await client.list_tools()).tools]

    assert anyio.run(go) == [t["name"] for t in contract_tools()]


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
