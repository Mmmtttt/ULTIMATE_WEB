import json
import os
import secrets
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import requests

from core.constants import (
    ACTOR_JSON_FILE,
    AUTHOR_JSON_FILE,
    JSON_FILE,
    LISTS_JSON_FILE,
    META_DIR,
    RECOMMENDATION_JSON_FILE,
    TAGS_JSON_FILE,
    USER_CONFIG_JSON_FILE,
    VIDEO_JSON_FILE,
    VIDEO_RECOMMENDATION_JSON_FILE,
)
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
        self._save_store(store)
        return peer

    def list_peers(self) -> List[Dict[str, Any]]:
        store = self._load_store()
        peers = list(store.get("peers", {}).values())
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

    def push_to_peer(self, peer_id: str) -> Dict[str, Any]:
        peer = self._peer_or_raise(peer_id)
        headers = {"X-Sync-Token": str(peer.get("auth_token", ""))}
        remote_inv = self._request_json("GET", self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/inventory"), headers, None)
        delta = self.delta_from_known(remote_inv.get("data", {}) if isinstance(remote_inv, dict) else {})
        datasets = delta.get("datasets", {}) if isinstance(delta, dict) else {}
        if not datasets:
            self._touch_peer(peer_id)
            return {"direction": "push", "peer_id": peer_id, "status": "no_change"}
        applied = self._request_json("POST", self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/apply"), headers, {"datasets": datasets})
        self._touch_peer(peer_id)
        return {"direction": "push", "peer_id": peer_id, "status": "completed", "remote_apply": applied.get("data") if isinstance(applied, dict) else None}

    def pull_from_peer(self, peer_id: str) -> Dict[str, Any]:
        peer = self._peer_or_raise(peer_id)
        headers = {"X-Sync-Token": str(peer.get("auth_token", ""))}
        local_inventory = self.inventory()
        remote_delta = self._request_json("POST", self._endpoint(peer["remote_base_url"], "/api/v1/sync/directional/delta"), headers, {"known_inventory": local_inventory})
        applied = self.apply_delta(remote_delta.get("data", {}) if isinstance(remote_delta, dict) else {})
        self._touch_peer(peer_id)
        return {"direction": "pull", "peer_id": peer_id, "status": "completed", "local_apply": applied}

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
        response = requests.request(method=method, url=url, headers=headers or {}, json=body, timeout=self.HTTP_TIMEOUT_SECONDS)
        payload = response.json()
        if response.status_code >= 400:
            raise RuntimeError(f"remote http {response.status_code}: {payload}")
        if int(payload.get("code", 500)) != 200:
            raise RuntimeError(f"remote api error: {payload.get('msg', 'unknown')}")
        return payload
