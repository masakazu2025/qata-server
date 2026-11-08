"""MCP の入口（AI 用）。application 層の Service を薄く包む。

道具の名前・説明・入力・出力の形は、親の `mcp-tools.json` をそのまま使う。
`$ref` は親の JSON Schema を展開して、それだけで読める形にして出す（S7）。
"""

import json
from collections.abc import Callable
from functools import cache
from typing import Any

import anyio.to_thread
import mcp_types as types
from jsonschema import Draft202012Validator
from mcp.server.lowlevel import Server
from pydantic import BaseModel

from qata_server.application import Service, ServiceError
from qata_server.application.contract_check import SCHEMAS_DIR, pointer, registry

MCP_TOOLS = SCHEMAS_DIR.parent / "mcp-tools.json"

INSTRUCTIONS = (
    "Windows のアプリのテストケースを作り、登録して実行する道具。"
    "list_apps でアプリを選び、get_part_dictionary の部品の名前でステップを書く。"
    "validate_testcase で確かめてから register_testcase で登録し、"
    "run_testcase で実行する。"
)


@cache
def tool_definitions() -> list[dict[str, Any]]:
    """親の mcp-tools.json の道具。$ref を展開したもの。"""
    contract = json.loads(MCP_TOOLS.read_text(encoding="utf-8"))
    resolver = registry().resolver(base_uri=MCP_TOOLS.as_uri())
    return [_expand(tool, resolver) for tool in contract["tools"]]


def _expand(node: Any, resolver) -> Any:
    """$ref を、指す先の中身に置き換える。契約の $ref は循環しない。"""
    if isinstance(node, list):
        return [_expand(v, resolver) for v in node]
    if not isinstance(node, dict):
        return node
    if "$ref" not in node:
        return {k: _expand(v, resolver) for k, v in node.items()}
    resolved = resolver.lookup(node["$ref"])
    target = _expand(resolved.contents, resolved.resolver)
    # 中身を展開したので、文書の鍵（$schema・$id・$defs）は要らない
    target = {k: v for k, v in target.items() if k not in ("$schema", "$id", "$defs")}
    siblings = {k: _expand(v, resolver) for k, v in node.items() if k != "$ref"}
    return {**target, **siblings}


def _handlers(service: Service) -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "list_apps": lambda a: {"apps": service.list_apps()},
        "get_part_dictionary": lambda a: service.get_part_dictionary(a["app_id"]),
        "validate_testcase": lambda a: service.validate_testcase(a["testcase"]),
        "register_testcase": lambda a: service.register_testcase(a["testcase"]),
        "list_testcases": lambda a: {
            "testcases": service.list_testcases(a.get("app_id"))
        },
        "run_testcase": lambda a: service.run_testcase(a["testcase_id"]),
        "get_run": lambda a: service.get_run(a["run_id"]),
    }


def _arguments_validator(tool: dict[str, Any]) -> Draft202012Validator:
    """引数の検査。テストケースの中身は見ない。

    形式の誤りも、Service が validation_result・register_result で返すため
    （S6 と同じ）。
    """
    schema = dict(tool["inputSchema"])
    if "testcase" in schema.get("properties", {}):
        schema["properties"] = {**schema["properties"], "testcase": {}}
    return Draft202012Validator(schema)


def create_server(service: Service) -> Server:
    tools = {t["name"]: t for t in tool_definitions()}
    handlers = _handlers(service)
    if set(handlers) != set(tools):
        raise RuntimeError(
            "MCP の道具が契約と合わない："
            f"契約 {sorted(tools)}、server {sorted(handlers)}"
        )
    validators = {name: _arguments_validator(t) for name, t in tools.items()}
    listed = types.ListToolsResult(
        tools=[types.Tool.model_validate(t) for t in tools.values()]
    )

    async def list_tools(_ctx, _params) -> types.ListToolsResult:
        return listed

    async def call_tool(_ctx, params: types.CallToolRequestParams):
        name = params.name
        arguments = params.arguments or {}
        if name not in tools:
            return _error("unknown_tool", f"道具 {name!r} はない")
        problems = sorted(
            f"{pointer(e.absolute_path) or '/'}：{e.message}"
            for e in validators[name].iter_errors(arguments)
        )
        if problems:
            return _error("invalid_arguments", "引数が合わない：" + "、".join(problems))
        try:
            # 実行は終わるまで待つので、スレッドで動かす
            value = await anyio.to_thread.run_sync(handlers[name], arguments)
        except ServiceError as exc:
            return _error(exc.code, exc.message)
        content = _jsonable(value)
        return types.CallToolResult(
            content=[_text(content)], structured_content=content
        )

    return Server(
        "qata-server",
        version="0.1.0",
        instructions=INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def _error(code: str, message: str) -> types.CallToolResult:
    """エラーは、契約の error_response の形を文字で返す。"""
    body = {"error": {"code": code, "message": message}}
    return types.CallToolResult(content=[_text(body)], is_error=True)


def _text(value: Any) -> types.TextContent:
    return types.TextContent(type="text", text=json.dumps(value, ensure_ascii=False))


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value
