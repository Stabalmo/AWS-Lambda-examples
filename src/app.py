import base64
import json
import os
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

try:
    import boto3  # type: ignore
except ModuleNotFoundError:  # local/unit-test environments may not include boto3
    boto3 = None  # type: ignore


def _decimal_default(obj: Any) -> Any:
    """Convert Decimal to int or float for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError


_table = None
if boto3 is not None and "ITEMS_TABLE_NAME" in os.environ:
    _dynamodb = boto3.resource("dynamodb")
    _table = _dynamodb.Table(os.environ["ITEMS_TABLE_NAME"])


def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_request_id(event: Dict[str, Any]) -> str:
    # HTTP API v2: requestContext.requestId is present for API Gateway.
    rc = event.get("requestContext") or {}
    return (rc.get("requestId") or rc.get("request_id") or "unknown").strip()


def _log(level: str, msg: str, **fields: Any) -> None:
    record = {"level": level, "message": msg, "ts_ms": _now_ms(), **fields}
    print(json.dumps(record, separators=(",", ":"), ensure_ascii=False))


def _response(status_code: int, body: Optional[Dict[str, Any]], request_id: str) -> Dict[str, Any]:
    headers = {"x-request-id": request_id}
    if status_code != 204:
        headers["content-type"] = "application/json"

    resp: Dict[str, Any] = {"statusCode": status_code, "headers": headers}
    if status_code != 204:
        resp["body"] = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False, default=_decimal_default)
    return resp


def _parse_json_body(event: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    body = event.get("body")
    if body is None:
        return None, "Missing request body"

    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception:
            return None, "Invalid base64 body"

    if not isinstance(body, str) or not body.strip():
        return None, "Empty request body"

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None, "Invalid JSON"

    if not isinstance(parsed, dict):
        return None, "JSON body must be an object"

    return parsed, None


def _get_http_method_and_path(event: Dict[str, Any]) -> Tuple[str, str]:
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    method = (http.get("method") or "").upper()
    path = event.get("rawPath") or ""
    
    # Strip stage name from path if present (e.g., /dev/health -> /health)
    stage = rc.get("stage")
    if stage and path.startswith(f"/{stage}/"):
        path = path[len(stage) + 1:]
    
    return method, path


def _path_param(event: Dict[str, Any], name: str) -> Optional[str]:
    params = event.get("pathParameters") or {}
    val = params.get(name)
    return val if isinstance(val, str) and val else None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = _get_request_id(event)
    method, path = _get_http_method_and_path(event)

    _log("INFO", "request.start", request_id=request_id, method=method, path=path, raw_event=json.dumps(event)[:500])

    try:
        if _table is None:
            return _response(
                500,
                {"error": {"code": "Misconfigured", "message": "ITEMS_TABLE_NAME not configured"}},
                request_id,
            )

        if method == "GET" and path == "/health":
            return _response(200, {"ok": True}, request_id)

        if method == "POST" and path == "/items":
            payload, err = _parse_json_body(event)
            if err:
                return _response(400, {"error": {"code": "BadRequest", "message": err}}, request_id)

            name = payload.get("name")
            if not isinstance(name, str) or not name.strip():
                return _response(
                    400,
                    {"error": {"code": "BadRequest", "message": "Field 'name' must be a non-empty string"}},
                    request_id,
                )

            item_id = str(uuid.uuid4())
            item = {"id": item_id, "name": name.strip(), "createdAtMs": _now_ms()}
            _table.put_item(Item=item)
            return _response(201, {"item": item}, request_id)

        if method == "GET" and path.startswith("/items/"):
            item_id = _path_param(event, "id") or path.split("/items/", 1)[1]
            if not item_id:
                return _response(400, {"error": {"code": "BadRequest", "message": "Missing item id"}}, request_id)

            resp = _table.get_item(Key={"id": item_id})
            item = resp.get("Item")
            if not item:
                return _response(404, {"error": {"code": "NotFound", "message": "Item not found"}}, request_id)
            return _response(200, {"item": item}, request_id)

        if method == "DELETE" and path.startswith("/items/"):
            item_id = _path_param(event, "id") or path.split("/items/", 1)[1]
            if not item_id:
                return _response(400, {"error": {"code": "BadRequest", "message": "Missing item id"}}, request_id)

            _table.delete_item(Key={"id": item_id})
            return _response(204, None, request_id)

        return _response(404, {"error": {"code": "NotFound", "message": "Route not found"}}, request_id)
    except Exception as e:
        _log("ERROR", "request.error", request_id=request_id, error=str(e))
        return _response(500, {"error": {"code": "InternalError", "message": "Internal server error"}}, request_id)
    finally:
        _log("INFO", "request.end", request_id=request_id)


