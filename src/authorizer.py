import json
import os
import time
from typing import Any, Dict, Optional

try:
    import boto3  # type: ignore
except ModuleNotFoundError:  # local/unit-test environments may not include boto3
    boto3 = None  # type: ignore


_ssm = boto3.client("ssm") if boto3 is not None else None
_cached_token: Optional[str] = None
_cached_token_expiry_ms: int = 0


def _now_ms() -> int:
    return int(time.time() * 1000)


def _log(level: str, msg: str, **fields: Any) -> None:
    record = {"level": level, "message": msg, "ts_ms": _now_ms(), **fields}
    print(json.dumps(record, separators=(",", ":"), ensure_ascii=False))


def _get_bearer(headers: Dict[str, Any]) -> Optional[str]:
    # API Gateway can normalize header casing unpredictably.
    auth = headers.get("authorization") or headers.get("Authorization")
    if not isinstance(auth, str) or not auth.strip():
        return None
    parts = auth.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0], parts[1]
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def _load_expected_token() -> Optional[str]:
    """
    Expected token is loaded from:
    - AUTH_TOKEN env var (preferred for local/dev), otherwise
    - SSM parameter named by AUTH_TOKEN_SSM_PARAM_NAME
    Cached in-memory for a short period to reduce SSM calls.
    """
    global _cached_token, _cached_token_expiry_ms

    env_token = os.environ.get("AUTH_TOKEN")
    if isinstance(env_token, str) and env_token.strip():
        return env_token.strip()

    if _cached_token and _cached_token_expiry_ms > _now_ms():
        return _cached_token

    param_name = os.environ.get("AUTH_TOKEN_SSM_PARAM_NAME")
    if not isinstance(param_name, str) or not param_name.strip():
        return None
    if _ssm is None:
        raise RuntimeError("boto3/ssm client not available in this environment")

    resp = _ssm.get_parameter(Name=param_name.strip(), WithDecryption=True)
    token = resp.get("Parameter", {}).get("Value")
    if not isinstance(token, str) or not token.strip():
        return None

    _cached_token = token.strip()
    _cached_token_expiry_ms = _now_ms() + 5 * 60 * 1000  # 5 minutes
    return _cached_token


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # HTTP API Lambda authorizer (simple response), payload format v2.0
    _log("INFO", "authorizer.start", event_keys=list(event.keys()))
    headers = event.get("headers") or {}
    token = _get_bearer(headers if isinstance(headers, dict) else {})
    _log("INFO", "authorizer.token", has_token=bool(token))

    try:
        expected = _load_expected_token()
    except Exception as e:
        _log("ERROR", "authorizer.error", error=str(e))
        return {"isAuthorized": False}

    if not expected:
        _log("ERROR", "authorizer.misconfigured", reason="No expected token configured")
        return {"isAuthorized": False}

    if token and token == expected:
        _log("INFO", "authorizer.allow")
        return {
            "isAuthorized": True,
            "context": {
                "principalId": "example-user",
            },
        }

    _log("WARN", "authorizer.deny", reason="Token mismatch or missing")
    return {"isAuthorized": False}


