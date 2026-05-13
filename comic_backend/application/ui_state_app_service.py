from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from core.constants import UI_STATE_JSON_FILE
from infrastructure.common.result import ServiceResult
from infrastructure.logger import error_logger
from infrastructure.persistence.json_storage import JsonStorage


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UiStateAppService:
    def __init__(self, storage: JsonStorage | None = None):
        self._storage = storage or JsonStorage(UI_STATE_JSON_FILE)

    @staticmethod
    def _empty_payload() -> Dict[str, Any]:
        return {
            "version": 1,
            "last_updated": "",
            "clients": {},
        }

    @staticmethod
    def _normalize_client_id(raw_value: Any) -> str:
        value = str(raw_value or "").strip()
        if not value:
            raise ValueError("缺少参数: client_id")
        if len(value) > 128:
            raise ValueError("client_id 过长")
        return value

    @staticmethod
    def _normalize_scope(raw_value: Any) -> str:
        value = str(raw_value or "").strip()
        if not value:
            raise ValueError("缺少参数: scope")
        if len(value) > 128:
            raise ValueError("scope 过长")
        return value

    @staticmethod
    def _normalize_state(raw_value: Any) -> Dict[str, Any]:
        if raw_value is None:
            return {}
        if not isinstance(raw_value, dict):
            raise ValueError("state 必须是对象")
        return dict(raw_value)

    def _read_payload(self) -> Dict[str, Any]:
        payload = self._storage.read()
        if not isinstance(payload, dict):
            return self._empty_payload()

        clients = payload.get("clients")
        if not isinstance(clients, dict):
            payload = self._empty_payload()
        else:
            payload = dict(payload)
            payload["version"] = int(payload.get("version") or 1)
            payload["last_updated"] = str(payload.get("last_updated") or "").strip()
            payload["clients"] = clients
        return payload

    @staticmethod
    def _prune_empty_client(payload: Dict[str, Any], client_id: str) -> None:
        client_bucket = payload.get("clients", {}).get(client_id)
        if not isinstance(client_bucket, dict):
            payload.get("clients", {}).pop(client_id, None)
            return

        scopes = client_bucket.get("scopes")
        if isinstance(scopes, dict) and scopes:
            return
        payload.get("clients", {}).pop(client_id, None)

    def get_state(self, client_id: str, scope: str) -> ServiceResult:
        try:
            normalized_client = self._normalize_client_id(client_id)
            normalized_scope = self._normalize_scope(scope)
            payload = self._read_payload()
            client_bucket = payload.get("clients", {}).get(normalized_client) or {}
            scopes = client_bucket.get("scopes") or {}
            state = scopes.get(normalized_scope)
            return ServiceResult.ok({
                "scope": normalized_scope,
                "client_id": normalized_client,
                "state": dict(state) if isinstance(state, dict) else None,
                "exists": isinstance(state, dict),
            })
        except ValueError as exc:
            return ServiceResult.error(str(exc))
        except Exception as exc:
            error_logger.error(f"读取 UI 状态失败: {exc}")
            return ServiceResult.error("读取 UI 状态失败")

    def save_state(self, client_id: str, scope: str, state: Dict[str, Any]) -> ServiceResult:
        try:
            normalized_client = self._normalize_client_id(client_id)
            normalized_scope = self._normalize_scope(scope)
            normalized_state = self._normalize_state(state)
            payload = self._read_payload()
            clients = payload.setdefault("clients", {})
            client_bucket = clients.setdefault(normalized_client, {})
            scopes = client_bucket.setdefault("scopes", {})

            if normalized_state:
                scopes[normalized_scope] = normalized_state
            else:
                scopes.pop(normalized_scope, None)
                self._prune_empty_client(payload, normalized_client)

            payload["last_updated"] = _now_iso()
            saved = self._storage.write(payload)
            if not saved:
                return ServiceResult.error("保存 UI 状态失败")

            return ServiceResult.ok({
                "scope": normalized_scope,
                "client_id": normalized_client,
                "state": normalized_state if normalized_state else None,
                "deleted": not bool(normalized_state),
            })
        except ValueError as exc:
            return ServiceResult.error(str(exc))
        except Exception as exc:
            error_logger.error(f"保存 UI 状态失败: {exc}")
            return ServiceResult.error("保存 UI 状态失败")

    def delete_state(self, client_id: str, scope: str) -> ServiceResult:
        return self.save_state(client_id, scope, {})
