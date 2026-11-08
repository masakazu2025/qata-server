"""REST の入口（web 用）。application 層の Service を薄く包む。

形の正は親の `openapi.yaml`。FastAPI が出す OpenAPI がそれと合うことを、
テストで確かめる（S6）。
"""

import json
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from qata_server.application import (
    Conflict,
    NotFound,
    RunnerUnavailable,
    Service,
    ServiceError,
)
from qata_server.contracts.part_dictionary_schema import PartDictionary
from qata_server.contracts.server_schema import (
    AppSummary,
    ErrorResponse,
    Run,
    TestcaseRecord,
    ValidationResult,
)
from qata_server.contracts.testcase_schema import Testcase

_STATUS = {NotFound: 404, Conflict: 409, RunnerUnavailable: 502}

_TESTCASE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Testcase"},
            },
        },
    },
}


def _error(description: str) -> dict[str, Any]:
    return {"description": description, "model": ErrorResponse}


_NOT_FOUND = {404: _error("見つからない")}


def create_app(service: Service) -> FastAPI:
    app = FastAPI(title="qata-server API", version="0.1.0")

    @app.exception_handler(ServiceError)
    def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        status = next(s for t, s in _STATUS.items() if isinstance(exc, t))
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}}, status_code=status
        )

    @app.exception_handler(HTTPException)
    def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        # 道がないときなども、契約の error_response の形で返す
        code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
        return JSONResponse(
            {"error": {"code": code, "message": str(exc.detail)}},
            status_code=exc.status_code,
        )

    # 部品の辞書

    @app.get("/apps", operation_id="listApps", response_model=list[AppSummary])
    def list_apps():
        return service.list_apps()

    @app.get(
        "/apps/{app_id}/parts",
        operation_id="getPartDictionary",
        response_model=PartDictionary,
        response_model_exclude_none=True,
        responses=_NOT_FOUND,
    )
    def get_part_dictionary(app_id: str):
        return service.get_part_dictionary(app_id)

    # テストケース
    # 本文は FastAPI で検証しない。形式の誤りも、Service が validation_result で
    # 返すため。

    @app.post(
        "/testcases/validate",
        operation_id="validateTestcase",
        response_model=ValidationResult,
        openapi_extra=_TESTCASE_BODY,
    )
    async def validate_testcase(request: Request):
        return service.validate_testcase(await _json(request))

    @app.get(
        "/testcases",
        operation_id="listTestcases",
        response_model=list[TestcaseRecord],
        response_model_exclude_none=True,
    )
    def list_testcases(app_id: str | None = None):
        return service.list_testcases(app_id)

    @app.post(
        "/testcases",
        operation_id="registerTestcase",
        status_code=201,
        response_model=TestcaseRecord,
        response_model_exclude_none=True,
        responses={
            422: {
                "description": "検証を通らなかった（登録しない）",
                "model": ValidationResult,
            }
        },
        openapi_extra=_TESTCASE_BODY,
    )
    async def register_testcase(request: Request):
        result = service.register_testcase(await _json(request))
        if not result.registered:
            body = {"valid": False, "errors": _dump(result)["errors"]}
            return JSONResponse(body, status_code=422)
        return result.testcase_record

    @app.get(
        "/testcases/{testcase_id}",
        operation_id="getTestcase",
        response_model=TestcaseRecord,
        response_model_exclude_none=True,
        responses=_NOT_FOUND,
    )
    def get_testcase(testcase_id: str):
        return service.get_testcase(testcase_id)

    @app.delete(
        "/testcases/{testcase_id}",
        operation_id="deleteTestcase",
        status_code=204,
        response_class=Response,
        responses=_NOT_FOUND,
    )
    def delete_testcase(testcase_id: str):
        service.delete_testcase(testcase_id)
        return Response(status_code=204)

    @app.post(
        "/testcases/{testcase_id}/approve",
        operation_id="approveTestcase",
        response_model=TestcaseRecord,
        response_model_exclude_none=True,
        responses={
            **_NOT_FOUND,
            409: _error("確認の要らないテストケースだった"),
        },
    )
    def approve_testcase(testcase_id: str):
        return service.approve_testcase(testcase_id)

    # 実行。終わるまで待つので、同期の関数にしてスレッドで動かす

    @app.post(
        "/testcases/{testcase_id}/runs",
        operation_id="runTestcase",
        status_code=201,
        response_model=Run,
        response_model_exclude_none=True,
        responses={
            **_NOT_FOUND,
            409: _error("人の確認待ち、またはいまの部品の辞書に合わない"),
            502: _error("runner に届かない"),
        },
    )
    def run_testcase(testcase_id: str):
        return service.run_testcase(testcase_id)

    # 実行の結果

    @app.get(
        "/runs",
        operation_id="listRuns",
        response_model=list[Run],
        response_model_exclude_none=True,
    )
    def list_runs(testcase_id: str | None = None):
        return service.list_runs(testcase_id)

    @app.get(
        "/runs/{run_id}",
        operation_id="getRun",
        response_model=Run,
        response_model_exclude_none=True,
        responses=_NOT_FOUND,
    )
    def get_run(run_id: str):
        return service.get_run(run_id)

    @app.get(
        "/screenshots/{screenshot_id}",
        operation_id="getScreenshot",
        response_class=Response,
        responses={
            200: {
                "description": "PNG",
                "content": {
                    "image/png": {
                        "schema": {"type": "string", "contentMediaType": "image/png"}
                    }
                },
            },
            **_NOT_FOUND,
        },
    )
    def get_screenshot(screenshot_id: str):
        return Response(service.get_screenshot(screenshot_id), media_type="image/png")

    app.openapi = lambda: _openapi(app)
    return app


async def _json(request: Request) -> Any:
    """本文を JSON として読む。読めなければ、契約に合わない値（None）として扱う。"""
    try:
        return json.loads(await request.body())
    except ValueError:
        return None


def _dump(model) -> Any:
    return model.model_dump(mode="json", exclude_none=True)


def _openapi(app: FastAPI) -> dict[str, Any]:
    """FastAPI の OpenAPI を、実際の応答に合わせて整える。

    - 引数はどれも文字列で受け、FastAPI の検証で 422 になることはないので、
      FastAPI が足す 422（HTTPValidationError）を外す。
    - 本文は Request で受けるため、テストケースの形を components に足す。
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for operations in schema["paths"].values():
        for operation in operations.values():
            response = operation.get("responses", {}).get("422")
            if response and "HTTPValidationError" in json.dumps(response):
                del operation["responses"]["422"]
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.pop("HTTPValidationError", None)
    # FastAPI の ValidationError（loc・msg）が、契約の validation_error と同じ名前で
    # 上書きしてしまうので、契約の側に戻す
    components.pop("ValidationError", None)
    for model in (Testcase, ValidationResult):
        _add_component(components, model)
    app.openapi_schema = schema
    return schema


def _add_component(components: dict[str, Any], model) -> None:
    definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
    for name, nested in definition.pop("$defs", {}).items():
        components[name] = nested
    components[model.__name__] = definition
