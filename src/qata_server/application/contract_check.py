"""外から来るデータを、親の契約（JSON Schema）に照らして判定する（S1）。

生成した型は `contains` や `if`/`then` を表せないので、判定はここで行い、
合格したものだけを型に読み込む。
"""

import json
from collections import defaultdict
from collections.abc import Mapping
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from qata_server.settings import Settings

# 親の契約。親のリポジトリの場所は設定（QATA_PARENT_DIR）から取る。
# 判定の道具はプロセスの間使い回すので、場所は読み込んだときに決める（S10）。
SCHEMAS_DIR = Settings().parent_dir / "contracts" / "schemas"


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
        raise FileNotFoundError(f"親の契約が見つからない：{SCHEMAS_DIR}")
    return Registry().with_resources(resources)


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
