from __future__ import annotations

import base64
import json
import mimetypes
import os
from typing import Any, Dict, List, Optional, Sequence

import requests


class VisionClientError(Exception):
    """多模态接口调用失败。"""

def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("image/"):
        return mime
    ext = os.path.splitext(str(path))[1].lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(ext, "image/jpeg")


def encode_image(path: str) -> str:
    with open(path, "rb") as fp:
        payload = fp.read()
    return f"data:{_guess_mime(path)};base64,{base64.b64encode(payload).decode('ascii')}"


def _endpoint(base_url: str) -> str:
    url = str(base_url or "").strip().rstrip("/")
    if not url:
        raise VisionClientError("视觉模型 Base URL 未配置")
    if url.endswith("/chat/completions"):
        return url
    return f"{url}/chat/completions"


def _models_endpoint(base_url: str) -> str:
    url = str(base_url or "").strip().rstrip("/")
    if not url:
        raise VisionClientError("视觉模型 Base URL 未配置")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")]
    if url.endswith("/models"):
        return url
    return f"{url}/models"


def fetch_model_ids(
    *,
    base_url: str,
    api_key: str,
    timeout_seconds: int = 15,
) -> List[str]:
    """拉取服务商的模型列表（OpenAI 兼容 GET /models）。"""
    if not str(api_key or "").strip():
        raise VisionClientError("缺少 API Key")
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(
            _models_endpoint(base_url),
            headers=headers,
            timeout=max(5, int(timeout_seconds or 15)),
        )
    except requests.RequestException as exc:
        raise VisionClientError(f"请求模型列表失败: {exc}") from exc

    if response.status_code >= 400:
        detail = (response.text or "")[:200]
        try:
            payload = response.json()
            detail = json.dumps(payload, ensure_ascii=False)[:200]
        except ValueError:
            pass
        raise VisionClientError(f"接口返回 {response.status_code}: {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise VisionClientError("模型列表不是 JSON") from exc

    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise VisionClientError("模型列表格式不符合预期")

    model_ids: List[str] = []
    for item in items:
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("model") or "").strip()
        else:
            model_id = ""
        if model_id and model_id not in model_ids:
            model_ids.append(model_id)
    return sorted(model_ids)



def _extract_content(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise VisionClientError("接口返回里没有 choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content or "")


def _extract_usage(payload: Dict[str, Any]) -> Dict[str, int]:
    """兼容 OpenAI / DeepSeek 两种用量字段，抽出「输入 / 命中缓存 / 输出」。"""
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return {}

    def _int(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    details = usage.get("prompt_tokens_details") or {}
    cached = _int(usage.get("prompt_cache_hit_tokens"))
    if not cached:
        cached = _int(details.get("cached_tokens")) if isinstance(details, dict) else 0
    return {
        "prompt_tokens": _int(usage.get("prompt_tokens")),
        "completion_tokens": _int(usage.get("completion_tokens")),
        "total_tokens": _int(usage.get("total_tokens")),
        "cached_tokens": cached,
    }


def call_vision_model_ex(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    image_paths: Sequence[str],
    timeout_seconds: int = 120,
    extra_headers: Optional[Dict[str, str]] = None,
    max_tokens: int = 1600,
    temperature: float = 0.2,
    system_prompt: str = "",
) -> Dict[str, Any]:
    """同 call_vision_model，但额外返回用量（含缓存命中 token）。"""
    images = list(image_paths or [])
    if not images:
        raise VisionClientError("没有可发送的图片")

    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    for path in images:
        try:
            url = encode_image(path)
        except OSError as exc:
            raise VisionClientError(f"读取图片失败: {path} ({exc})") from exc
        content.append({"type": "image_url", "image_url": {"url": url}})

    messages: List[Dict[str, Any]] = []
    if str(system_prompt or "").strip():
        messages.append({"role": "system", "content": str(system_prompt)})
    messages.append({"role": "user", "content": content})

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update({str(k): str(v) for k, v in extra_headers.items()})

    try:
        response = requests.post(
            _endpoint(base_url),
            headers=headers,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            timeout=max(10, int(timeout_seconds or 120)),
        )
    except requests.RequestException as exc:
        raise VisionClientError(f"请求失败: {exc}") from exc

    if response.status_code >= 400:
        detail = ""
        try:
            detail = json.dumps(response.json(), ensure_ascii=False)[:400]
        except ValueError:
            detail = (response.text or "")[:400]
        raise VisionClientError(f"接口返回 {response.status_code}: {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise VisionClientError("接口返回不是 JSON") from exc

    text = _extract_content(payload)
    if not text.strip():
        raise VisionClientError("模型没有返回内容")
    return {"text": text, "usage": _extract_usage(payload), "model": model}


def call_vision_model(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    image_paths: Sequence[str],
    timeout_seconds: int = 120,
    extra_headers: Optional[Dict[str, str]] = None,
    max_tokens: int = 1600,
    temperature: float = 0.2,
    system_prompt: str = "",
) -> str:
    """调用 OpenAI 兼容的 chat/completions，把上下文、提示词和图片一起发过去。"""
    return call_vision_model_ex(
        base_url=base_url,
        api_key=api_key,
        model=model,
        prompt=prompt,
        image_paths=image_paths,
        timeout_seconds=timeout_seconds,
        extra_headers=extra_headers,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
    )["text"]
