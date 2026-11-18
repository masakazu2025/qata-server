"""外から来るデータを、読む版の契約（JSON Schema）に照らして判定する（S1）。

生成した型は `contains` や `if`/`then` を表せないので、判定はここで行い、
合格したものだけを型に読み込む。
"""

import json
from collections import defaultdict
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

# 読む版の契約。リポジトリの直下の qata-contracts/ に、親のタグから写したもの（S14）。
# 隣に並べた ../qata/ は読まない
CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "qata-contracts"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
MCP_TOOLS = CONTRACTS_DIR / "mcp-tools.json"

# 立ち上げたときに確かめる契約。実行の間に、判定と MCP の道具の形に使うもの
USED_CONTRACTS = [
    SCHEMAS_DIR / "testcase.schema.json",
    SCHEMAS_DIR / "part-dictionary.schema.json",
    SCHEMAS_DIR / "runner-command.schema.json",
    SCHEMAS_DIR / "runner-result.schema.json",
    SCHEMAS_DIR / "server.schema.json",
    MCP_TOOLS,
]


@cache
def registry() -> Registry:
    resources = [
        (
            path.as_uri(),
            Resource(
                contents=json.loads(path.read_text(encoding="utf-8")),
                specification=DRAFT202012,
            ),
        )
        for path in sorted(SCHEMAS_DIR.glob("*.schema.json"))
    ]
    if not resources:
        raise FileNotFoundError(f"読む版の契約が見つからない：{SCHEMAS_DIR}")
    return Registry().with_resources(resources)


def clear_cache() -> None:
    """読み込んだ契約を捨てる。テストで読む場所を差し替えるときに使う。"""
    registry.cache_clear()
    _validator.cache_clear()


def _refs(node: Any) -> list[str]:
    if isinstance(node, dict):
        found = [node["$ref"]] if isinstance(node.get("$ref"), str) else []
        return found + [r for v in node.values() for r in _refs(v)]
    if isinstance(node, list):
        return [r for v in node for r in _refs(v)]
    return []


def ensure_ready() -> None:
    """使う契約がそろっていることを確かめる。そろっていなければ FileNotFoundError。

    立ち上げたときに呼び、最初の呼び出しが来てから気づくことがないようにする。
    $ref の解決は判定のときまで遅れるので、使う契約から $ref をたどり、
    指す先（ほかのファイルも）がすべて引けることを確かめる。
    """
    resolver = registry().resolver()
    pending: list[str] = []
    for path in USED_CONTRACTS:
        if not path.is_file():
            raise FileNotFoundError(f"読む版の契約が見つからない：{path}")
        contents = json.loads(path.read_text(encoding="utf-8"))
        pending += [urljoin(path.as_uri(), ref) for ref in _refs(contents)]
    seen: set[str] = set()
    while pending:
        uri = pending.pop()
        if uri in seen:
            continue
        seen.add(uri)
        try:
            resolved = resolver.lookup(uri)
        except Unresolvable as e:
            raise FileNotFoundError(f"読む版の契約で、指す先が引けない：{uri}") from e
        base = uri.partition("#")[0]
        pending += [urljoin(base, ref) for ref in _refs(resolved.contents)]


@cache
def _validator(contract: str) -> Draft202012Validator:
    file_name, _, fragment = contract.partition("#")
    uri = (SCHEMAS_DIR / file_name).as_uri() + (f"#{fragment}" if fragment else "")
    return Draft202012Validator(
        {"$ref": uri}, registry=registry(), format_checker=FormatChecker()
    )


def pointer(path) -> str:
    """jsonschema の場所を JSON Pointer にする。"""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in path)


def problems(contract: str, data: Any) -> list[tuple[str, str]]:
    """契約に合わない場所と、その説明の一覧。合えば空。

    contract は 'testcase.schema.json' や 'server.schema.json#/$defs/run' の形。
    """
    found = []
    for error in _validator(contract).iter_errors(data):
        for cause in _explain(error):
            found.append((pointer(cause.absolute_path), cause.message))
    return sorted(set(found))


def _explain(error: ValidationError) -> list[ValidationError]:
    """oneOf に discriminator があれば、種類の合う枝の問題を返す。

    jsonschema は「どの枝にも合わない」としか言わず、どこが悪いかが読めないため。
    """
    schema = error.schema if isinstance(error.schema, Mapping) else {}
    prop = (schema.get("discriminator") or {}).get("propertyName")
    if error.validator != "oneOf" or not error.context or prop is None:
        return [error]
    if not isinstance(error.instance, dict) or prop not in error.instance:
        return [error]
    branches: dict[Any, list[ValidationError]] = defaultdict(list)
    for sub in error.context:
        branches[sub.schema_path[0]].append(sub)
    allowed = []
    for subs in branches.values():
        wrong_kind = [
            s
            for s in subs
            if s.validator == "const" and list(s.relative_path) == [prop]
        ]
        if not wrong_kind:
            return [cause for s in subs for cause in _explain(s)]
        allowed.append(wrong_kind[0].validator_value)
    error.message = (
        f"{error.instance[prop]!r} は {prop} に使えない。使えるのは {allowed}"
    )
    error.path.append(prop)
    return [error]
