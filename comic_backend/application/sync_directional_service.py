import json
import os
import secrets
import shutil
import socket
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import requests

from core.constants import (
    ACTOR_JSON_FILE,
    AUTHOR_JSON_FILE,
    CACHE_ROOT_DIR,
    COMIC_DIR,
    DATA_DIR,
    JSON_FILE,
    LISTS_JSON_FILE,
    META_DIR,
    RECOMMENDATION_JSON_FILE,
    RECOMMENDATION_CACHE_DIR,
    STATIC_DIR,
    TAGS_JSON_FILE,
    USER_CONFIG_JSON_FILE,
    VIDEO_DIR,
    VIDEO_JSON_FILE,
    VIDEO_RECOMMENDATION_JSON_FILE,
)
from infrastructure.logger import app_logger
from infrastructure.persistence.json_storage import JsonStorage


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


class DirectionalSyncService:
    STORE_FILE = os.path.join(META_DIR, "sync_pairing.json")
    SCHEMA_VERSION = 1
    HTTP_TIMEOUT_SECONDS = 12
    INVITE_TTL_MINUTES = 10
    INVITE_TTL_MINUTES_MAX = 60

    DATASETS: Dict[str, Dict[str, Any]] = {
        "comics": {"file": JSON_FILE, "root_key": "comics", "id_key": "id", "count_key": "total_comics", "kind": "list"},
        "recommendations": {"file": RECOMMENDATION_JSON_FILE, "root_key": "recommendations", "id_key": "id", "count_key": "total_recommendations", "kind": "list"},
        "videos": {"file": VIDEO_JSON_FILE, "root_key": "videos", "id_key": "id", "kind": "list"},
        "video_recommendations": {"file": VIDEO_RECOMMENDATION_JSON_FILE, "root_key": "video_recommendations", "id_key": "id", "kind": "list"},
        "tags": {"file": TAGS_JSON_FILE, "root_key": "tags", "id_key": "id", "kind": "list"},
        "lists": {"file": LISTS_JSON_FILE, "root_key": "lists", "id_key": "id", "kind": "list"},
        "actors": {"file": ACTOR_JSON_FILE, "root_key": "actors", "id_key": "id", "kind": "list"},
        "authors": {"file": AUTHOR_JSON_FILE, "root_key": "authors", "id_key": "id", "kind": "list"},
        "user_config": {"file": USER_CONFIG_JSON_FILE, "root_key": "user_config", "kind": "dict"},
    }

    UNION_LIST_FIELDS: Set[str] = {"tag_ids", "list_ids", "actors"}
    ASSET_ROOT_DIRS: List[str] = [COMIC_DIR, VIDEO_DIR, STATIC_DIR, CACHE_ROOT_DIR, RECOMMENDATION_CACHE_DIR]
    ASSET_ALLOWED_PREFIXES: tuple = ("comic/", "video/", "static/", "cache/", "recommendation_cache/")

    def __init__(self) -> None:
        os.makedirs(os.path.dirname(self.STORE_FILE), exist_ok=True)

    def create_invite(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ttl = int(payload.get("ttl_minutes", self.INVITE_TTL_MINUTES) or self.INVITE_TTL_MINUTES)
        ttl = max(1, min(ttl, self.INVITE_TTL_MINUTES_MAX))
        now = _utc_now()

        store = self._load_store()
        self._cleanup_invites(store)
        code = self._new_code(store)
        invite = {
            "invite_id": uuid.uuid4().hex,
            "code": code,
            "status": "open",
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(minutes=ttl)),
        }
        store["invites"][code] = invite
        self._save_store(store)
        return {
            "invite_id": invite["invite_id"],
            "pairing_code": code,
            "created_at": invite["created_at"],
            "expires_at": invite["expires_at"],
            "device": store["device"],
        }

    def claim_invite(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        code = str(payload.get("pairing_code", "")).strip()
        if not code:
            return None
        store = self._load_store()
        self._cleanup_invites(store)
        invite = store["invites"].get(code)
        if not invite or invite.get("status") != "open":
            return None

        requester_id = str(payload.get("requester_device_id", "")).strip() or f"peer_{uuid.uuid4().hex[:12]}"
        requester_name = str(payload.get("requester_device_name", "")).strip() or "Unknown Device"
        requester_url = self._normalize_url(str(payload.get("requester_base_url", "")).strip())
        now_iso = _iso(_utc_now())
        token = secrets.token_urlsafe(32)

        peer = store["peers"].get(requester_id, {})
        peer.update(
            {
                "peer_id": requester_id,
                "display_name": requester_name,
                "remote_base_url": requester_url or str(peer.get("remote_base_url", "")).strip(),
                "auth_token": token,
                "status": "active",
                "created_at": str(peer.get("created_at", "")).strip() or now_iso,
                "updated_at": now_iso,
                "last_seen_at": now_iso,
                "last_sync_at": str(peer.get("last_sync_at", "")).strip(),
            }
        )
        store["peers"][requester_id] = peer
        invite["status"] = "claimed"
        invite["claimed_at"] = now_iso
        invite["claimed_by"] = requester_id
        store["invites"][code] = invite
        self._save_store(store)

        return {
            "peer_id": store["device"]["device_id"],
            "peer_name": store["device"]["device_name"],
            "auth_token": token,
            "paired_at": now_iso,
        }

    def connect_peer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        remote_base = self._normalize_url(str(payload.get("remote_base_url", "")).strip())
        pairing_code = str(payload.get("pairing_code", "")).strip()
        requester_url = self._normalize_url(str(payload.get("requester_base_url", "")).strip())
        if not remote_base:
            raise ValueError("remote_base_url is required")
        if not pairing_code:
            raise ValueError("pairing_code is required")

        store = self._load_store()
        claim_payload = {
            "pairing_code": pairing_code,
            "requester_device_id": store["device"]["device_id"],
            "requester_device_name": store["device"]["device_name"],
            "requester_base_url": requester_url,
        }
        result = self._request_json("POST", self._endpoint(remote_base, "/api/v1/sync/pairing/claim"), None, claim_payload)
        data = result.get("data", {}) if isinstance(result, dict) else {}
        peer_id = str(data.get("peer_id", "")).strip()
        token = str(data.get("auth_token", "")).strip()
        peer_name = str(data.get("peer_name", "")).strip() or remote_base
        if not peer_id or not token:
            raise RuntimeError("pairing response invalid")

        now_iso = _iso(_utc_now())
        peer = store["peers"].get(peer_id, {})
        peer.update(
            {
                "peer_id": peer_id,
                "display_name": peer_name,
                "remote_base_url": remote_base,
                "auth_token": token,
                "status": "active",
                "created_at": str(peer.get("created_at", "")).strip() or now_iso,
                "updated_at": now_iso,
                "last_seen_at": now_iso,
                "last_sync_at": str(peer.get("last_sync_at", "")).strip(),
            }
        )
        store["peers"][peer_id] = peer

        # Remove stale peers pointing to the same remote URL to avoid duplicate entries
        # with expired tokens after repeated pairing.
        for existing_id, existing_peer in list(store.get("peers", {}).items()):
            if existing_id == peer_id:
                continue
            existing_url = self._normalize_url(str(existing_peer.get("remote_base_url", "")).strip())
            if existing_url and existing_url == remote_base:
                store["peers"].pop(existing_id, None)

        self._save_store(store)
        return peer

    def list_peers(self) -> List[Dict[str, Any]]:
        store = self._load_store()
        deduped: Dict[str, Dict[str, Any]] = {}
        for peer in store.get("peers", {}).values():
            peer_id = str(peer.get("peer_id", "")).strip()
            key_url = self._normalize_url(str(peer.get("remote_base_url", "")).strip())
            dedupe_key = key_url or f"peer:{peer_id}"
            current = deduped.get(dedupe_key)
            if current is None:
                deduped[dedupe_key] = peer
                continue

            current_updated = str(current.get("updated_at", "")).strip()
            candidate_updated = str(peer.get("updated_at", "")).strip()
            if candidate_updated > current_updated:
                deduped[dedupe_key] = peer

        if len(deduped) != len(store.get("peers", {})):
            new_peers: Dict[str, Dict[str, Any]] = {}
            for peer in deduped.values():
                pid = str(peer.get("peer_id", "")).strip()
                if pid:
                    new_peers[pid] = peer
            store["peers"] = new_peers
            self._save_store(store)

        peers = list(deduped.values())
        peers.sort(key=lambda x: str(x.get("display_name", "")).lower())
        return peers

    def remove_peer(self, peer_id: str) -> bool:
        store = self._load_store()
        if peer_id not in store.get("peers", {}):
            return False
        store["peers"].pop(peer_id, None)
        self._save_store(store)
        return True

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        token = str(token or "").strip()
        if not token:
            return None
        for peer in self._load_store().get("peers", {}).values():
            if str(peer.get("auth_token", "")).strip() == token and str(peer.get("status", "")) == "active":
                return peer
        return None

    def inventory(self) -> Dict[str, Any]:
        datasets = {}
        for name, cfg in self.DATASETS.items():
            payload = self._read_dataset(cfg)
            if cfg.get("kind") == "dict":
                datasets[name] = {"count": 1 if isinstance(payload, dict) and payload else 0}
                continue
            ids = []
            for item in payload if isinstance(payload, list) else []:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get(cfg.get("id_key", "id"), "")).strip()
                if item_id:
                    ids.append(item_id)
            datasets[name] = {"count": len(set(ids)), "ids": sorted(set(ids))}
        return {"generated_at": _iso(_utc_now()), "device": self._load_store().get("device", {}), "datasets": datasets}

    def asset_inventory(self) -> Dict[str, Any]:
        files = self._collect_asset_index()
        return {
            "generated_at": _iso(_utc_now()),
            "file_count": len(files),
            "files": files,
        }

    def delta_from_known(self, known_inventory: Dict[str, Any]) -> Dict[str, Any]:
        known = known_inventory.get("datasets", {}) if isinstance(known_inventory, dict) else {}
        out = {}
        for name, cfg in self.DATASETS.items():
            payload = self._read_dataset(cfg)
            if cfg.get("kind") == "dict":
                if isinstance(payload, dict) and payload:
                    out[name] = payload
                continue
            known_ids = set()
            if isinstance(known.get(name), dict):
                for raw in known[name].get("ids", []):
                    rid = str(raw or "").strip()
                    if rid:
                        known_ids.add(rid)
            rows = []
            for item in payload if isinstance(payload, list) else []:
                if not isinstance(item, dict):
                    continue
                row_id = str(item.get(cfg.get("id_key", "id"), "")).strip()
                if row_id and row_id not in known_ids:
                    rows.append(item)
            if rows:
                out[name] = rows
        return {"generated_at": _iso(_utc_now()), "datasets": out}

    def apply_delta(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        incoming = payload.get("datasets", {}) if isinstance(payload, dict) else {}
        if not isinstance(incoming, dict):
            incoming = {}
        summary = {"applied_at": _iso(_utc_now()), "dataset_stats": {}, "total_added": 0, "total_updated": 0, "total_skipped": 0}
        for name, incoming_payload in incoming.items():
            cfg = self.DATASETS.get(name)
            if not cfg:
                continue
            stats = self._apply_dataset(cfg, incoming_payload)
            summary["dataset_stats"][name] = stats
            summary["total_added"] += int(stats.get("added", 0))
            summary["total_updated"] += int(stats.get("updated", 0))
            summary["total_skipped"] += int(stats.get("skipped", 0))
        return summary

    def estimate_delta_for_known(self, known_inventory: Dict[str, Any], known_files: Dict[str, str]) -> Dict[str, Any]:
        delta = self.delta_from_known(known_inventory if isinstance(known_inventory, dict) else {})
        datasets = delta.get("datasets", {}) if isinstance(delta, dict) else {}
        data_sync = self._summarize_dataset_delta(datasets if isinstance(datasets, dict) else {})
        asset_sync = self._estimate_asset_delta(known_files if isinstance(known_files, dict) else {})
        return {
            "estimated_at": _iso(_utc_now()),
            "data_sync": data_sync,
            "asset_sync": asset_sync,
        }

    def estimate_peer_sync(self, peer_id: str, direction: str) -> Dict[str, Any]:
        peer = self._peer_or_raise(peer_id)
        headers = {"X-Sync-Token": str(peer.get("auth_token", ""))}
        direction_key = str(direction or "").strip().lower()
        if direction_key not in {"push", "pull"}:
            raise ValueError("direction must be push or pull")

        if direction_key == "push":
            remote_inv = self._request_json(
                "GET",
                self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/inventory"),
                headers,
                None,
            )
            remote_known_inventory = remote_inv.get("data", {}) if isinstance(remote_inv, dict) else {}
            remote_files: Dict[str, str] = {}
            asset_supported = True
            asset_message = ""
            try:
                remote_asset_inv = self._request_json(
                    "GET",
                    self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/assets/inventory"),
                    headers,
                    None,
                )
                remote_files = (
                    remote_asset_inv.get("data", {}).get("files", {})
                    if isinstance(remote_asset_inv, dict) and isinstance(remote_asset_inv.get("data"), dict)
                    else {}
                )
            except RuntimeError as exc:
                if self._is_http_status_error(exc, (404, 405)):
                    asset_supported = False
                    asset_message = str(exc)
                else:
                    raise

            estimate = self.estimate_delta_for_known(
                remote_known_inventory if isinstance(remote_known_inventory, dict) else {},
                remote_files if isinstance(remote_files, dict) else {},
            )
            if not asset_supported:
                estimate["asset_sync"] = {
                    "status": "unsupported_remote",
                    "file_count": 0,
                    "total_bytes": 0,
                    "total_mb": 0.0,
                    "message": asset_message or "remote assets inventory endpoint not available",
                }
            return {
                "direction": "push",
                "peer_id": peer_id,
                **estimate,
            }

        local_inventory = self.inventory()
        local_files = self.asset_inventory().get("files", {})

        try:
            remote_estimate = self._request_json(
                "POST",
                self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/estimate"),
                headers,
                {
                    "known_inventory": local_inventory,
                    "known_files": local_files if isinstance(local_files, dict) else {},
                },
            )
            remote_data = remote_estimate.get("data", {}) if isinstance(remote_estimate, dict) else {}
            if not isinstance(remote_data, dict):
                remote_data = {}
            return {
                "direction": "pull",
                "peer_id": peer_id,
                **remote_data,
            }
        except RuntimeError as exc:
            # Backward compatibility with peers without /directional/estimate
            if not self._is_http_status_error(exc, (404, 405)):
                raise
            remote_delta = self._request_json(
                "POST",
                self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/delta"),
                headers,
                {"known_inventory": local_inventory},
            )
            remote_delta_data = remote_delta.get("data", {}) if isinstance(remote_delta, dict) else {}
            datasets = (
                remote_delta_data.get("datasets", {})
                if isinstance(remote_delta_data, dict)
                else {}
            )
            data_sync = self._summarize_dataset_delta(datasets if isinstance(datasets, dict) else {})
            asset_sync = {
                "status": "unsupported_remote",
                "file_count": 0,
                "total_bytes": 0,
                "total_mb": 0.0,
                "message": "remote does not support assets estimate endpoint",
            }
            try:
                remote_asset_inv = self._request_json(
                    "GET",
                    self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/assets/inventory"),
                    headers,
                    None,
                )
                remote_files = (
                    remote_asset_inv.get("data", {}).get("files", {})
                    if isinstance(remote_asset_inv, dict) and isinstance(remote_asset_inv.get("data"), dict)
                    else {}
                )
                if isinstance(remote_files, dict):
                    asset_sync = self._estimate_pull_assets_from_remote(
                        remote_files=remote_files,
                        local_files=local_files if isinstance(local_files, dict) else {},
                    )
            except RuntimeError as asset_exc:
                if self._is_http_status_error(asset_exc, (404, 405)):
                    asset_sync = {
                        "status": "unsupported_remote",
                        "file_count": 0,
                        "total_bytes": 0,
                        "total_mb": 0.0,
                        "message": "remote does not support assets inventory endpoint",
                    }
                else:
                    asset_sync = {
                        "status": "estimate_failed",
                        "file_count": 0,
                        "total_bytes": 0,
                        "total_mb": 0.0,
                        "message": str(asset_exc),
                    }
            return {
                "direction": "pull",
                "peer_id": peer_id,
                "estimated_at": _iso(_utc_now()),
                "data_sync": data_sync,
                "asset_sync": asset_sync,
            }

    def push_to_peer(self, peer_id: str) -> Dict[str, Any]:
        peer = self._peer_or_raise(peer_id)
        headers = {"X-Sync-Token": str(peer.get("auth_token", ""))}
        app_logger.info(
            f"[sync] push start peer_id={peer_id} remote={peer.get('remote_base_url', '')}"
        )
        remote_inv = self._request_json("GET", self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/inventory"), headers, None)
        delta = self.delta_from_known(remote_inv.get("data", {}) if isinstance(remote_inv, dict) else {})
        datasets = delta.get("datasets", {}) if isinstance(delta, dict) else {}

        remote_asset_files = {}
        asset_supported = True
        try:
            remote_asset_inv = self._request_json(
                "GET",
                self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/assets/inventory"),
                headers,
                None,
            )
            if isinstance(remote_asset_inv, dict) and isinstance(remote_asset_inv.get("data"), dict):
                remote_asset_files = remote_asset_inv["data"].get("files", {}) or {}
        except RuntimeError as exc:
            if self._is_http_status_error(exc, (404, 405)):
                asset_supported = False
            else:
                raise

        applied = None
        if datasets:
            applied = self._request_json("POST", self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/apply"), headers, {"datasets": datasets})

        if asset_supported:
            asset_sync = self._push_assets_to_peer(peer["remote_base_url"], headers, remote_asset_files)
        else:
            asset_sync = {
                "status": "unsupported_remote",
                "file_count": 0,
                "message": "remote assets inventory endpoint not available",
            }
        if not datasets and int(asset_sync.get("file_count", 0)) == 0:
            self._touch_peer(peer_id)
            app_logger.info(
                f"[sync] push done peer_id={peer_id} status=no_change asset_status={asset_sync.get('status')} asset_files={asset_sync.get('file_count', 0)}"
            )
            return {"direction": "push", "peer_id": peer_id, "status": "no_change", "asset_sync": asset_sync}

        self._touch_peer(peer_id)
        app_logger.info(
            f"[sync] push done peer_id={peer_id} status=completed dataset_count={len(datasets)} asset_status={asset_sync.get('status')} asset_files={asset_sync.get('file_count', 0)}"
        )
        return {
            "direction": "push",
            "peer_id": peer_id,
            "status": "completed",
            "remote_apply": applied.get("data") if isinstance(applied, dict) else None,
            "asset_sync": asset_sync,
        }

    def pull_from_peer(self, peer_id: str) -> Dict[str, Any]:
        peer = self._peer_or_raise(peer_id)
        headers = {"X-Sync-Token": str(peer.get("auth_token", ""))}
        app_logger.info(
            f"[sync] pull start peer_id={peer_id} remote={peer.get('remote_base_url', '')}"
        )
        local_inventory = self.inventory()
        remote_delta = self._request_json("POST", self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/delta"), headers, {"known_inventory": local_inventory})
        applied = self.apply_delta(remote_delta.get("data", {}) if isinstance(remote_delta, dict) else {})

        local_asset_inventory = self.asset_inventory()
        asset_pull = self._pull_assets_from_peer(peer["remote_base_url"], headers, local_asset_inventory.get("files", {}))
        self._touch_peer(peer_id)
        app_logger.info(
            f"[sync] pull done peer_id={peer_id} status=completed added={applied.get('total_added', 0)} updated={applied.get('total_updated', 0)} asset_status={asset_pull.get('status')} asset_files={asset_pull.get('file_count', 0)}"
        )
        return {
            "direction": "pull",
            "peer_id": peer_id,
            "status": "completed",
            "local_apply": applied,
            "asset_sync": asset_pull,
        }

    def build_asset_delta_zip(self, known_files: Dict[str, str]) -> Dict[str, Any]:
        local_files = self._collect_asset_index()
        delta_paths = [path for path, sig in local_files.items() if str((known_files or {}).get(path, "")) != sig]
        if not delta_paths:
            return {"zip_path": "", "file_count": 0}

        zip_path = self._create_asset_zip(delta_paths)
        return {"zip_path": zip_path, "file_count": len(delta_paths)}

    def apply_asset_zip_file(self, zip_path: str) -> Dict[str, Any]:
        if not zip_path or not os.path.isfile(zip_path):
            return {"file_count": 0, "status": "no_change"}
        applied = self._extract_asset_zip(zip_path)
        return {"file_count": applied, "status": "completed" if applied > 0 else "no_change"}

    def _push_assets_to_peer(self, remote_base_url: str, headers: Dict[str, str], remote_files: Dict[str, str]) -> Dict[str, Any]:
        delta = self.build_asset_delta_zip(remote_files if isinstance(remote_files, dict) else {})
        zip_path = str(delta.get("zip_path", "")).strip()
        file_count = int(delta.get("file_count", 0))
        if not zip_path or file_count <= 0:
            return {"status": "no_change", "file_count": 0}

        try:
            zip_size = 0
            try:
                zip_size = int(os.path.getsize(zip_path))
            except Exception:
                zip_size = 0
            app_logger.info(
                f"[sync] push assets upload start remote={remote_base_url} files={file_count} bytes={zip_size}"
            )
            with open(zip_path, "rb") as fp:
                files = {"package": ("assets_delta.zip", fp, "application/zip")}
                response = requests.post(
                    self._endpoint(remote_base_url, "/api/v1/sync/directional/assets/apply"),
                    headers=headers,
                    files=files,
                    timeout=self.HTTP_TIMEOUT_SECONDS * 4,
                )
            if response.status_code in (404, 405):
                return {
                    "status": "unsupported_remote",
                    "file_count": 0,
                    "message": f"remote assets apply endpoint http {response.status_code}",
                }
            if response.status_code >= 400:
                body_preview = self._response_body_preview(response)
                raise RuntimeError(f"remote assets apply http {response.status_code}: {body_preview}")
            payload = self._decode_json_payload(response, "remote assets apply")
            if int(payload.get("code", 500)) != 200:
                raise RuntimeError(f"remote assets apply failed: {payload.get('msg', 'unknown')}")
            app_logger.info(
                f"[sync] push assets upload done remote={remote_base_url} files={file_count}"
            )
            return {
                "status": "completed",
                "file_count": file_count,
                "remote_apply": payload.get("data"),
            }
        finally:
            if zip_path and os.path.isfile(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass

    def _pull_assets_from_peer(self, remote_base_url: str, headers: Dict[str, str], known_files: Dict[str, str]) -> Dict[str, Any]:
        temp_zip = ""
        try:
            endpoint = self._endpoint(remote_base_url, "/api/v1/sync/directional/assets/delta/download")
            app_logger.info(
                f"[sync] pull assets request remote={remote_base_url} known_files={len(known_files or {})}"
            )
            response = requests.post(
                endpoint,
                headers=headers,
                json={"known_files": known_files or {}},
                timeout=self.HTTP_TIMEOUT_SECONDS * 8,
                stream=True,
            )
            if response.status_code == 204:
                return {"status": "no_change", "file_count": 0}
            if response.status_code in (404, 405):
                if response.status_code == 405:
                    # Backward compatibility: try GET for older peers.
                    response = requests.get(
                        endpoint,
                        headers=headers,
                        timeout=self.HTTP_TIMEOUT_SECONDS * 8,
                        stream=True,
                    )
                    if response.status_code == 204:
                        return {"status": "no_change", "file_count": 0}
                if response.status_code in (404, 405):
                    return {
                        "status": "unsupported_remote",
                        "file_count": 0,
                        "message": f"remote assets delta endpoint http {response.status_code}",
                    }
            if response.status_code >= 400:
                body_preview = self._response_body_preview(response)
                raise RuntimeError(f"remote assets delta http {response.status_code}: {body_preview}")

            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "application/json" in content_type:
                payload = self._decode_json_payload(response, "remote assets delta")
                if int(payload.get("code", 500)) != 200:
                    raise RuntimeError(f"remote assets delta failed: {payload.get('msg', 'unknown')}")
                payload_data = payload.get("data")
                declared_files = 0
                if isinstance(payload_data, dict):
                    try:
                        declared_files = int(payload_data.get("file_count", 0) or 0)
                    except Exception:
                        declared_files = 0
                if declared_files > 0:
                    raise RuntimeError(
                        f"remote assets delta returned json metadata file_count={declared_files}, expected zip stream"
                    )
                return {"status": "no_change", "file_count": 0}

            if content_type and "zip" not in content_type and "octet-stream" not in content_type:
                body_preview = self._response_body_preview(response)
                raise RuntimeError(
                    f"remote assets delta returned non-zip content-type={content_type}: {body_preview}"
                )

            temp_zip = self._save_stream_to_temp_zip(response)
            if not zipfile.is_zipfile(temp_zip):
                with open(temp_zip, "rb") as fp:
                    head = fp.read(256)
                head_preview = head.decode("utf-8", errors="ignore").replace("\n", " ").strip()[:220]
                raise RuntimeError(
                    f"remote assets delta returned invalid zip, content-type={content_type}, head={head_preview}"
                )
            applied = self._extract_asset_zip(temp_zip)
            app_logger.info(
                f"[sync] pull assets apply done remote={remote_base_url} files={applied}"
            )
            return {"status": "completed" if applied > 0 else "no_change", "file_count": applied}
        finally:
            if temp_zip and os.path.isfile(temp_zip):
                try:
                    os.remove(temp_zip)
                except Exception:
                    pass

    @staticmethod
    def _is_http_status_error(exc: Exception, status_codes: tuple) -> bool:
        message = str(exc or "")
        return any(f"http {code}" in message for code in status_codes)

    def _summarize_dataset_delta(self, datasets: Dict[str, Any]) -> Dict[str, Any]:
        dataset_counts: Dict[str, int] = {}
        total_records = 0
        for name, payload in (datasets or {}).items():
            if isinstance(payload, list):
                count = len(payload)
            elif isinstance(payload, dict):
                count = 1 if payload else 0
            else:
                count = 0
            dataset_counts[name] = count
            total_records += count
        return {
            "dataset_counts": dataset_counts,
            "total_records": total_records,
        }

    def _estimate_asset_delta(self, known_files: Dict[str, str]) -> Dict[str, Any]:
        local_files = self._collect_asset_index()
        file_count = 0
        total_bytes = 0
        data_root = os.path.abspath(DATA_DIR)
        known = known_files if isinstance(known_files, dict) else {}

        for rel_path, signature in local_files.items():
            if str(known.get(rel_path, "")) == signature:
                continue
            abs_path = os.path.abspath(os.path.join(data_root, rel_path.replace("/", os.sep)))
            try:
                size = int(os.path.getsize(abs_path))
            except Exception:
                size = 0
            file_count += 1
            total_bytes += max(size, 0)

        return {
            "status": "estimated",
            "file_count": file_count,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
        }

    def _estimate_pull_assets_from_remote(self, remote_files: Dict[str, str], local_files: Dict[str, str]) -> Dict[str, Any]:
        file_count = 0
        total_bytes = 0
        local_map = local_files if isinstance(local_files, dict) else {}

        for rel_path, remote_sig in (remote_files or {}).items():
            rel = str(rel_path or "").replace("\\", "/").lstrip("/")
            if not rel or not rel.startswith(self.ASSET_ALLOWED_PREFIXES):
                continue
            local_sig = str(local_map.get(rel, ""))
            if local_sig == str(remote_sig):
                continue
            file_count += 1
            total_bytes += self._signature_size(remote_sig)

        return {
            "status": "estimated",
            "file_count": file_count,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
        }

    @staticmethod
    def _signature_size(signature: Any) -> int:
        text = str(signature or "").strip()
        if not text:
            return 0
        head = text.split(":", 1)[0]
        try:
            size = int(head)
        except Exception:
            return 0
        return size if size > 0 else 0

    def _collect_asset_index(self) -> Dict[str, str]:
        index: Dict[str, str] = {}
        visited: Set[str] = set()
        data_root = os.path.abspath(DATA_DIR)

        for base_dir in self.ASSET_ROOT_DIRS:
            if not base_dir:
                continue
            root = os.path.abspath(base_dir)
            if root in visited:
                continue
            visited.add(root)
            if not os.path.isdir(root):
                continue

            for current_root, _, files in os.walk(root):
                for filename in files:
                    abs_path = os.path.abspath(os.path.join(current_root, filename))
                    if not abs_path.startswith(data_root):
                        continue
                    rel_path = os.path.relpath(abs_path, data_root).replace("\\", "/")
                    if rel_path.startswith("meta_data/"):
                        continue
                    try:
                        stat = os.stat(abs_path)
                    except Exception:
                        continue
                    index[rel_path] = f"{int(stat.st_size)}:{int(stat.st_mtime)}"
        return index

    def _create_asset_zip(self, rel_paths: List[str]) -> str:
        os.makedirs(os.path.join(CACHE_ROOT_DIR, "sync_assets"), exist_ok=True)
        fd, zip_path = tempfile.mkstemp(prefix="sync_assets_", suffix=".zip", dir=os.path.join(CACHE_ROOT_DIR, "sync_assets"))
        os.close(fd)

        data_root = os.path.abspath(DATA_DIR)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in rel_paths:
                normalized = str(rel or "").replace("\\", "/").lstrip("/")
                if not normalized:
                    continue
                abs_path = os.path.abspath(os.path.join(data_root, normalized))
                if not abs_path.startswith(data_root):
                    continue
                if not os.path.isfile(abs_path):
                    continue
                zf.write(abs_path, arcname=normalized)
        return zip_path

    def _save_stream_to_temp_zip(self, response: requests.Response) -> str:
        os.makedirs(os.path.join(CACHE_ROOT_DIR, "sync_assets"), exist_ok=True)
        fd, zip_path = tempfile.mkstemp(prefix="sync_pull_", suffix=".zip", dir=os.path.join(CACHE_ROOT_DIR, "sync_assets"))
        os.close(fd)
        total_bytes = 0
        with open(zip_path, "wb") as fp:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fp.write(chunk)
                    total_bytes += len(chunk)
        app_logger.info(
            f"[sync] pull assets downloaded bytes={total_bytes} temp_zip={zip_path}"
        )
        return zip_path

    def _extract_asset_zip(self, zip_path: str) -> int:
        if not os.path.isfile(zip_path):
            return 0
        applied = 0
        data_root = os.path.abspath(DATA_DIR)
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                rel = member.filename.replace("\\", "/").lstrip("/")
                if not rel or rel.startswith("../") or "/../" in rel:
                    continue
                if not rel.startswith(self.ASSET_ALLOWED_PREFIXES):
                    continue

                target = os.path.abspath(os.path.join(data_root, rel))
                if not target.startswith(data_root):
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                applied += 1
        return applied

    def _apply_dataset(self, cfg: Dict[str, Any], payload: Any) -> Dict[str, Any]:
        if cfg.get("kind") == "dict":
            incoming = payload if isinstance(payload, dict) else {}
            storage = JsonStorage(cfg["file"])
            stats = {"added": 0, "updated": 0, "skipped": 0, "status": "applied"}

            def _updater(data: Dict[str, Any]) -> Dict[str, Any]:
                if not isinstance(data, dict):
                    data = {}
                current = data.get(cfg["root_key"], {})
                if not isinstance(current, dict):
                    current = {}
                changed = self._merge_dict_missing(current, incoming)
                if changed:
                    data[cfg["root_key"]] = current
                    data["last_updated"] = _iso(_utc_now())
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
                return data

            storage.atomic_update(_updater)
            return stats

        incoming_rows = payload if isinstance(payload, list) else []
        storage = JsonStorage(cfg["file"])
        stats = {"added": 0, "updated": 0, "skipped": 0, "status": "applied"}
        id_key = cfg.get("id_key", "id")

        def _updater(data: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(data, dict):
                data = {}
            rows = data.get(cfg["root_key"], [])
            if not isinstance(rows, list):
                rows = []
            idx = {}
            for row in rows:
                if isinstance(row, dict):
                    rid = str(row.get(id_key, "")).strip()
                    if rid:
                        idx[rid] = row
            for row in incoming_rows:
                if not isinstance(row, dict):
                    stats["skipped"] += 1
                    continue
                rid = str(row.get(id_key, "")).strip()
                if not rid:
                    stats["skipped"] += 1
                    continue
                existing = idx.get(rid)
                if existing is None:
                    new_row = dict(row)
                    rows.append(new_row)
                    idx[rid] = new_row
                    stats["added"] += 1
                    continue
                if self._merge_row(existing, row):
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            data[cfg["root_key"]] = rows
            count_key = str(cfg.get("count_key", "")).strip()
            if count_key:
                data[count_key] = len(rows)
            data["last_updated"] = _iso(_utc_now())
            return data

        storage.atomic_update(_updater)
        return stats

    def _merge_row(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> bool:
        changed = False
        for key, value in incoming.items():
            if key == "id":
                continue
            if key in self.UNION_LIST_FIELDS and isinstance(existing.get(key), list) and isinstance(value, list):
                before = len(existing[key])
                self._extend_unique(existing[key], value)
                if len(existing[key]) != before:
                    changed = True
                continue
            if existing.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                existing[key] = value
                changed = True
        return changed

    def _merge_dict_missing(self, target: Dict[str, Any], incoming: Dict[str, Any]) -> bool:
        changed = False
        for key, value in incoming.items():
            if key not in target:
                target[key] = value
                changed = True
                continue
            if isinstance(target[key], dict) and isinstance(value, dict):
                if self._merge_dict_missing(target[key], value):
                    changed = True
            elif isinstance(target[key], list) and isinstance(value, list):
                before = len(target[key])
                self._extend_unique(target[key], value)
                if len(target[key]) != before:
                    changed = True
            elif target[key] in (None, "", [], {}) and value not in (None, "", [], {}):
                target[key] = value
                changed = True
        return changed

    @staticmethod
    def _extend_unique(target: List[Any], incoming: List[Any]) -> None:
        seen = {DirectionalSyncService._marker(v) for v in target}
        for value in incoming:
            marker = DirectionalSyncService._marker(value)
            if marker in seen:
                continue
            target.append(value)
            seen.add(marker)

    @staticmethod
    def _marker(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return repr(value)

    def _read_dataset(self, cfg: Dict[str, Any]) -> Any:
        data = JsonStorage(cfg["file"]).read()
        if not isinstance(data, dict):
            return {} if cfg.get("kind") == "dict" else []
        payload = data.get(cfg["root_key"])
        if cfg.get("kind") == "dict":
            return payload if isinstance(payload, dict) else {}
        return payload if isinstance(payload, list) else []

    def _peer_or_raise(self, peer_id: str) -> Dict[str, Any]:
        peer = self._load_store().get("peers", {}).get(peer_id)
        if not isinstance(peer, dict):
            raise ValueError("peer not found")
        if str(peer.get("status", "")) != "active":
            raise RuntimeError("peer is not active")
        if not str(peer.get("remote_base_url", "")).strip():
            raise RuntimeError("peer remote_base_url is empty")
        return peer

    def _touch_peer(self, peer_id: str) -> None:
        store = self._load_store()
        peer = store.get("peers", {}).get(peer_id)
        if not isinstance(peer, dict):
            return
        now_iso = _iso(_utc_now())
        peer["last_sync_at"] = now_iso
        peer["last_seen_at"] = now_iso
        peer["updated_at"] = now_iso
        store["peers"][peer_id] = peer
        self._save_store(store)

    def _load_store(self) -> Dict[str, Any]:
        if not os.path.exists(self.STORE_FILE):
            store = self._default_store()
            self._save_store(store)
            return store
        try:
            with open(self.STORE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception:
            loaded = {}
        if not isinstance(loaded, dict):
            loaded = {}
        store = self._default_store()
        store.update(loaded)
        if not isinstance(store.get("device"), dict):
            store["device"] = self._default_store()["device"]
        if not isinstance(store.get("invites"), dict):
            store["invites"] = {}
        if not isinstance(store.get("peers"), dict):
            store["peers"] = {}
        return store

    def _save_store(self, store: Dict[str, Any]) -> None:
        with open(self.STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)

    def _default_store(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "device": {
                "device_id": f"device_{uuid.uuid4().hex[:16]}",
                "device_name": socket.gethostname() or "UnknownHost",
            },
            "invites": {},
            "peers": {},
        }

    def _cleanup_invites(self, store: Dict[str, Any]) -> None:
        now = _utc_now()
        cleaned = {}
        for code, invite in store.get("invites", {}).items():
            if not isinstance(invite, dict):
                continue
            expires = _parse_iso(str(invite.get("expires_at", "")))
            status = str(invite.get("status", "")).strip().lower()
            if status == "open" and expires and expires <= now:
                continue
            cleaned[code] = invite
        store["invites"] = cleaned

    def _new_code(self, store: Dict[str, Any]) -> str:
        invites = store.get("invites", {})
        for _ in range(100):
            code = f"{secrets.randbelow(900000) + 100000:06d}"
            if code not in invites:
                return code
        return uuid.uuid4().hex[:8].upper()

    @staticmethod
    def _normalize_url(url: str) -> str:
        value = str(url or "").strip()
        if not value:
            return ""
        if not value.startswith("http://") and not value.startswith("https://"):
            value = f"http://{value}"
        return value.rstrip("/")

    @staticmethod
    def _endpoint(base_url: str, path: str) -> str:
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{base_url.rstrip('/')}{suffix}"

    def _request_json(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]],
        body: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        response = requests.request(
            method=method,
            url=url,
            headers=headers or {},
            json=body,
            timeout=self.HTTP_TIMEOUT_SECONDS,
        )
        status = int(response.status_code)
        content_type = str(response.headers.get("Content-Type", "")).lower()

        payload: Any = None
        if "application/json" in content_type:
            try:
                payload = self._decode_json_payload(response, "remote api")
            except Exception as exc:
                text_preview = (response.text or "").strip().replace("\n", " ")[:260]
                raise RuntimeError(f"remote invalid json http {status}: {exc}; body={text_preview}") from exc
        else:
            if response.content:
                try:
                    payload = self._decode_json_payload(response, "remote api")
                except Exception:
                    text_preview = (response.text or "").strip().replace("\n", " ")[:260]
                    if status >= 400:
                        raise RuntimeError(f"remote http {status}: {text_preview}")
                    raise RuntimeError(f"remote non-json response http {status}: {text_preview}")
            else:
                payload = {}

        if status >= 400:
            raise RuntimeError(f"remote http {status}: {payload}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"remote api payload is not object: type={type(payload).__name__}")
        if int(payload.get("code", 500)) != 200:
            raise RuntimeError(f"remote api error: {payload.get('msg', 'unknown')}")
        return payload

    @staticmethod
    def _decode_json_payload(response: requests.Response, context: str) -> Dict[str, Any]:
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(
                f"{context} invalid json http {int(response.status_code)}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{context} payload is not object: type={type(payload).__name__}")
        return payload

    @staticmethod
    def _response_body_preview(response: requests.Response, max_len: int = 260) -> str:
        try:
            text = response.text
        except Exception:
            try:
                text = bytes(response.content or b"").decode("utf-8", errors="ignore")
            except Exception:
                text = ""
        return str(text or "").strip().replace("\n", " ")[:max_len]
