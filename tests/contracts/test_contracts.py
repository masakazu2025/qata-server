"""contracts.feature の手順。"""

import copy
import importlib
import json
from pathlib import Path

import yaml
from generate_contracts import CONTRACTS_DIR, GENERATED_DIR, SCHEMAS_DIR, generate
from jsonschema import Draft202012Validator, FormatChecker
from pytest_bdd import given, parsers, scenarios, then, when
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

scenarios("contracts.feature")

EXAMPLES_DIR = CONTRACTS_DIR / "examples"
OTHER_DOCUMENTS = [CONTRACTS_DIR / "openapi.yaml", CONTRACTS_DIR / "mcp-tools.json"]


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text) if path.suffix == ".yaml" else json.loads(text)


def schema_files() -> list[Path]:
    return sorted(SCHEMAS_DIR.glob("*.schema.json"))


def build_registry() -> Registry:
    """契約のすべての文書を、ファイルの URI で引けるようにする。"""
    resources = [
        (path.as_uri(), Resource(contents=load(path), specification=DRAFT202012))
        for path in [*schema_files(), *OTHER_DOCUMENTS]
    ]
    return Registry().with_resources(resources)


def validator_for(contract: str) -> Draft202012Validator:
    """'server.schema.json#/$defs/run' のような名前から、検証の道具を作る。"""
    file_name, _, fragment = contract.partition("#")
    uri = (SCHEMAS_DIR / file_name).as_uri() + (f"#{fragment}" if fragment else "")
    return Draft202012Validator(
        {"$ref": uri}, registry=build_registry(), format_checker=FormatChecker()
    )


def walk_to_parent(document, pointer: str):
    """JSON Pointer の指す場所の、親と最後の鍵を返す。"""
    *parents, last = [
        p.replace("~1", "/").replace("~0", "~") for p in pointer.split("/")[1:]
    ]
    node = document
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node, (int(last) if isinstance(node, list) else last)


def find_refs(node) -> list[str]:
    if isinstance(node, dict):
        return [
            ref
            for key, value in node.items()
            for ref in ([value] if key == "$ref" else find_refs(value))
        ]
    if isinstance(node, list):
        return [ref for value in node for ref in find_refs(value)]
    return []


@given(parsers.parse('契約の例 "{file_name}"'), target_fixture="example")
def given_example(file_name: str):
    return load(EXAMPLES_DIR / file_name)


@when(parsers.parse('"{pointer}" を {value} に変える'))
def change_value(example, pointer: str, value: str) -> None:
    parent, key = walk_to_parent(example, pointer)
    parent[key] = json.loads(value)


@when(parsers.parse('"{pointer}" を消す'))
def remove_value(example, pointer: str) -> None:
    parent, key = walk_to_parent(example, pointer)
    del parent[key]


@then("すべての JSON Schema が draft 2020-12 の形式に合う")
def schemas_are_valid() -> None:
    files = schema_files()
    assert files, f"JSON Schema が見つからない：{SCHEMAS_DIR}"
    for path in files:
        Draft202012Validator.check_schema(load(path))


@then("JSON Schema・openapi.yaml・mcp-tools.json のすべての $ref が解決できる")
def refs_resolve() -> None:
    registry = build_registry()
    unresolved = []
    for path in [*schema_files(), *OTHER_DOCUMENTS]:
        resolver = registry.resolver(base_uri=path.as_uri())
        for ref in find_refs(load(path)):
            try:
                resolver.lookup(ref)
            except Unresolvable:
                unresolved.append(f"{path.name}: {ref}")
    assert not unresolved, "解決できない $ref：\n" + "\n".join(unresolved)


@then(parsers.parse('契約 "{contract}" に通る'))
def passes(example, contract: str) -> None:
    errors = [e.message for e in validator_for(contract).iter_errors(example)]
    assert not errors, errors


@then(parsers.parse('契約 "{contract}" ではじかれる'))
def rejected(example, contract: str) -> None:
    assert not validator_for(contract).is_valid(example)


@then(parsers.parse('生成した型 "{type_path}" で読める'))
def generated_type_reads(example, type_path: str) -> None:
    module_name, _, class_name = type_path.partition(".")
    module = importlib.import_module(f"qata_server.contracts.{module_name}")
    model = getattr(module, class_name)
    parsed = model.model_validate(copy.deepcopy(example))
    assert parsed.model_dump(mode="json", exclude_unset=True) == example


@then("契約から生成し直した型が、コミットした型と同じ")
def generated_types_are_up_to_date(tmp_path: Path) -> None:
    fresh = tmp_path / "contracts"
    generate(fresh)

    def files(root: Path) -> dict[str, str]:
        return {
            p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(root.rglob("*.py"))
        }

    assert files(fresh) == files(GENERATED_DIR), (
        "生成した型が契約と合わない。"
        "uv run python scripts/generate_contracts.py で生成し直してコミットする。"
    )
