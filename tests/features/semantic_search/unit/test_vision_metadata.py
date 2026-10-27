from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[4] / "comic_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_sample_page_indexes_keeps_gap_under_limit():
    from application.vision_metadata_service import sample_page_indexes

    assert sample_page_indexes(0) == []
    # 页数少 → 间隔小
    assert sample_page_indexes(20) == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
    # 页数多 → 间隔涨到上限 8，但不会超过
    pages = sample_page_indexes(100)
    assert pages[1] - pages[0] == 8
    big = sample_page_indexes(371)
    assert big[1] - big[0] <= 8
    assert len(big) <= 48


def test_sample_page_indexes_respects_lower_gap_setting():
    from application.vision_metadata_service import sample_page_indexes

    pages = sample_page_indexes(120, max_gap=4)
    assert pages[1] - pages[0] <= 4


def test_parse_draft_text_tolerates_code_fence_and_chatter():
    from application.vision_metadata_service import parse_draft_text

    raw = "好的，结果如下：\n```json\n" + json.dumps(
        {
            "title": "某本书",
            "vibe": "气质梗概",
            "catalog": "篇名速览",
            "tags": [{"name": "女仆", "kind": "人物"}, {"name": "女仆", "kind": "人物"}, "双胞胎"],
        },
        ensure_ascii=False,
    ) + "\n```\n以上。"
    parsed = parse_draft_text(raw)
    assert parsed["title"] == "某本书"
    assert parsed["vibe"] == "气质梗概"
    assert [tag["name"] for tag in parsed["tags"]] == ["女仆", "双胞胎"]
    assert parsed["tags"][1]["kind"] == "题材"


def test_parse_draft_text_rejects_non_json():
    from application.vision_metadata_service import parse_draft_text

    with pytest.raises(ValueError):
        parse_draft_text("我无法识别这些图片")


class _FakeConfigRepo:
    def __init__(self, vision_config=None):
        from domain.config.entity import UserConfig, VisionConfig

        self._config = UserConfig()
        self._config.vision_config = vision_config or VisionConfig()

    def get(self):
        return self._config


class _FakeComicRepo:
    def __init__(self, comic):
        self.comic = comic
        self.saved = None

    def get_by_id(self, comic_id):
        return self.comic if str(comic_id) == str(self.comic.id) else None

    def save(self, comic):
        self.comic = comic
        self.saved = comic
        return True


class _FakeTagRepo:
    def __init__(self):
        self.tags = {}

    def get_all(self, content_type=None):
        return list(self.tags.values())

    def create(self, name, content_type=None):
        from domain.tag.entity import Tag

        tag = Tag(id=f"t{len(self.tags) + 1}", name=name)
        self.tags[tag.id] = tag
        return tag

    def save(self, tag):
        self.tags[tag.id] = tag
        return True


@pytest.fixture()
def draft_service(tmp_path, monkeypatch):
    import application.vision_metadata_service as module
    from domain.comic import Comic

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    comic = Comic(id="c1", title="原始书名", vibe="", catalog="")
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(),
        comic_repo=_FakeComicRepo(comic),
        tag_repo=_FakeTagRepo(),
    )
    return service


def test_apply_draft_writes_vibe_catalog_and_tags(draft_service):
    service = draft_service
    service._write_drafts({
        "c1": {
            "comic_id": "c1",
            "title": "模型给的书名",
            "status": "ready",
            "draft": {
                "vibe": "双胞胎女仆的甜腻日常",
                "catalog": "楓與鈴2；女仆的一天",
                "tags": [{"name": "女仆", "kind": "人物"}, {"name": "双胞胎", "kind": "人物"}],
            },
        }
    })

    result = service.apply_draft("c1", {})
    assert result["vibe"] == "双胞胎女仆的甜腻日常"
    assert result["applied_tags"] == 2

    comic = service._comic_repo.comic
    assert comic.vibe == "双胞胎女仆的甜腻日常"
    assert comic.catalog == "楓與鈴2；女仆的一天"
    assert set(comic.tag_ids) == {"t1", "t2"}
    assert service.get_draft("c1") is None
    assert {tag.kind for tag in service._tag_repo.get_all()} == {"人物"}


def test_apply_draft_can_skip_fields(draft_service):
    service = draft_service
    service._write_drafts({
        "c1": {
            "comic_id": "c1",
            "status": "ready",
            "draft": {"vibe": "v", "catalog": "c", "tags": []},
        }
    })
    service.apply_draft("c1", {"vibe": False, "catalog": True})
    comic = service._comic_repo.comic
    assert comic.vibe == ""
    assert comic.catalog == "c"


def test_vision_status_reports_configuration(draft_service):
    status = draft_service.status()
    assert status["configured"] is False
    assert status["draft_count"] == 0
    assert status["max_gap"] == 8


def test_config_api_masks_api_key():
    from api.v1.config import _mask_vision_config

    payload = _mask_vision_config({
        "vision_config": {
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-1234567890abcdef",
            "model": "qwen-vl-max",
        }
    })
    vision = payload["vision_config"]
    assert vision["api_key"] != "sk-1234567890abcdef"
    assert "*" in vision["api_key"]
    assert vision["has_api_key"] is True
    assert vision["ready"] is True


def test_vision_config_validation():
    from domain.config.entity import VisionConfig

    config = VisionConfig()
    assert config.update(max_gap=9) is False
    assert config.update(max_gap=6) is True
    assert config.max_gap == 6

    config.update(base_url="https://api.example.com/v1", api_key="sk-key", model="m")
    assert config.ready is True

    # 前端回传掩码 → 保留原 key
    config.update(api_key="sk-1******cdef")
    assert config.api_key == "sk-key"


def test_vision_client_posts_openai_compatible_payload(tmp_path):
    """起一个本地假接口，验证请求形状（system 上下文、Bearer、image_url、data URI）与响应解析。"""
    import base64
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            captured["path"] = self.path
            captured["auth"] = self.headers.get("Authorization")
            captured["body"] = body
            content = json.dumps({
                "vibe": "梗概",
                "catalog": "速览",
                "tags": [{"name": "女仆", "kind": "人物"}],
            }, ensure_ascii=False)
            response = json.dumps({
                "choices": [{"message": {"content": content}}],
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *args):  # 静音
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    image_path = tmp_path / "1.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xd9")  # 最小 jpg 头

    try:
        from infrastructure.vision import call_vision_model

        text = call_vision_model(
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="sk-test",
            model="fake-vl",
            prompt="请输出 JSON",
            image_paths=[str(image_path)],
            timeout_seconds=10,
            system_prompt="我是上下文文件",
        )
    finally:
        server.shutdown()

    assert captured["path"] == "/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    body = captured["body"]
    assert body["model"] == "fake-vl"
    messages = body["messages"]
    assert messages[0] == {"role": "system", "content": "我是上下文文件"}
    content = messages[1]["content"]
    assert content[0]["type"] == "text"
    assert "【硬性底线】" in content[0]["text"]
    data_url = content[1]["image_url"]["url"]
    assert data_url.startswith("data:image/jpeg;base64,")
    base64.b64decode(data_url.split(",", 1)[1])

    parsed = parse_draft_text_for_test(text)
    assert parsed["vibe"] == "梗概"


def test_vision_client_without_system_prompt_keeps_single_message(tmp_path):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            captured["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            payload = json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    image_path = tmp_path / "1.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xd9")
    try:
        from infrastructure.vision import call_vision_model

        call_vision_model(
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="k",
            model="m",
            prompt="p",
            image_paths=[str(image_path)],
            timeout_seconds=10,
        )
    finally:
        server.shutdown()

    assert [m["role"] for m in captured["body"]["messages"]] == ["user"]


def test_vision_providers_presets_are_usable():
    from application.vision_providers import list_vision_providers

    providers = list_vision_providers()
    assert len(providers) >= 8
    ids = {provider["id"] for provider in providers}
    assert {"openai", "siliconflow", "dashscope", "zhipu", "ollama", "deepseek"} <= ids

    for provider in providers:
        assert provider["base_url"].startswith("http")
        assert provider["models"]
        assert isinstance(provider["vision"], bool)

    deepseek = next(p for p in providers if p["id"] == "deepseek")
    assert deepseek["vision"] is True  # deepseek-flash 已支持图像理解
    assert "deepseek-flash" in deepseek["models"]


def test_fetch_models_reads_provider_model_list(tmp_path, monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            payload = json.dumps({
                "data": [{"id": "deepseek-flash"}, {"id": "deepseek-v4-pro"}, {"id": "deepseek-flash"}]
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    import application.vision_metadata_service as module
    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(),
        comic_repo=_FakeComicRepo(None),
        tag_repo=_FakeTagRepo(),
    )
    try:
        result = service.fetch_models(base_url=f"http://127.0.0.1:{port}/v1", api_key="sk-test")
    finally:
        server.shutdown()

    assert seen["path"] == "/v1/models"
    assert seen["auth"] == "Bearer sk-test"
    assert result["live"] is True
    assert result["models"] == ["deepseek-flash", "deepseek-v4-pro"]


def test_fetch_models_falls_back_to_preset_when_unauthorized(tmp_path, monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            payload = json.dumps({"error": {"message": "invalid key"}}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    import application.vision_metadata_service as module
    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(),
        comic_repo=_FakeComicRepo(None),
        tag_repo=_FakeTagRepo(),
    )
    try:
        result = service.fetch_models(base_url=f"http://127.0.0.1:{port}/v1", api_key="bad")
    finally:
        server.shutdown()

    assert result["live"] is False
    assert result["error"]
    assert result["models"] == result["preset_models"]


def test_context_file_is_loaded_from_project(tmp_path, monkeypatch):
    import application.vision_metadata_service as module
    from domain.config.entity import VisionConfig

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    service = module.VisionMetadataService(config_repo=_FakeConfigRepo(), comic_repo=_FakeComicRepo(None), tag_repo=_FakeTagRepo())

    context = service.load_context_text()
    assert context["exists"] is True
    assert context["chars"] > 1000
    assert "prompt" in context["path"].lower()

    custom = tmp_path / "custom_context.md"
    custom.write_text("自定义上下文", encoding="utf-8")
    config = VisionConfig(prompt_file=str(custom))
    custom_context = service.load_context_text(config)
    assert custom_context["text"] == "自定义上下文"

    disabled = service.load_context_text(VisionConfig(context_enabled=False))
    assert disabled["text"] == ""


def test_blocked_response_is_rejected():
    from application.vision_metadata_service import parse_draft_text

    with pytest.raises(ValueError) as exc_info:
        parse_draft_text('{"blocked": true, "reason": "疑似未成年角色"}')
    assert "疑似未成年角色" in str(exc_info.value)


class _BatchComicRepo:
    def __init__(self, comics):
        self.comics = comics

    def get_all(self):
        return list(self.comics)

    def get_by_id(self, comic_id):
        return next((c for c in self.comics if str(c.id) == str(comic_id)), None)

    def save(self, comic):
        return True


def test_list_missing_comics_skips_filled_ones(tmp_path, monkeypatch):
    import application.vision_metadata_service as module
    from domain.comic import Comic

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    comics = [
        Comic(id="c1", title="空的", total_units=10),
        Comic(id="c2", title="已填", total_units=5, vibe="有梗概", catalog="有速览"),
        Comic(id="c3", title="只填了梗概", total_units=3, vibe="有梗概"),
        Comic(id="c4", title="已删除", total_units=2, is_deleted=True),
    ]
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(),
        comic_repo=_BatchComicRepo(comics),
        tag_repo=_FakeTagRepo(),
    )

    missing = service.list_missing_comics()
    # 先排「连梗概都没有」的，再按页数从少到多
    assert [item["comic_id"] for item in missing] == ["c1", "c3"]
    assert missing[0]["missing_vibe"] is True and missing[0]["missing_catalog"] is True
    assert missing[1]["missing_vibe"] is False and missing[1]["missing_catalog"] is True


def test_start_batch_queues_and_writes_drafts(tmp_path, monkeypatch):
    import time

    import application.vision_metadata_service as module
    from domain.comic import Comic

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    monkeypatch.setattr(module, "BATCH_DELAY_SECONDS", 0)
    monkeypatch.delenv("BACKEND_RUNTIME_PROFILE", raising=False)

    comics = [Comic(id="c1", title="一", total_units=8), Comic(id="c2", title="二", total_units=4)]
    from domain.config.entity import VisionConfig

    config = VisionConfig(base_url="https://example.com/v1", api_key="sk-key", model="fake-vl")
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(config),
        comic_repo=_BatchComicRepo(comics),
        tag_repo=_FakeTagRepo(),
    )

    def fake_build_draft(comic_id, cfg, state):
        state["pages"] = [1]
        return {
            "comic_id": comic_id,
            "title": f"草稿-{comic_id}",
            "status": "ready",
            "draft": {"vibe": "梗概", "catalog": "速览", "tags": []},
        }

    monkeypatch.setattr(service, "_build_draft", fake_build_draft)

    state = service.start_batch(only_missing=True)
    assert state["running"] is True
    assert state["total"] == 2

    deadline = time.time() + 5
    while time.time() < deadline and service.batch_state()["running"]:
        time.sleep(0.05)

    final = service.batch_state()
    assert final["running"] is False
    assert final["done"] == 2
    assert final["failed"] == 0
    assert service.get_draft("c1")["draft"]["vibe"] == "梗概"


def test_start_batch_requires_vision_config(tmp_path, monkeypatch):
    import application.vision_metadata_service as module

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    monkeypatch.delenv("BACKEND_RUNTIME_PROFILE", raising=False)
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(),
        comic_repo=_BatchComicRepo([]),
        tag_repo=_FakeTagRepo(),
    )
    with pytest.raises(ValueError):
        service.start_batch()


def test_start_batch_rejects_mobile_core(monkeypatch):
    import application.vision_metadata_service as module

    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "mobile_core")
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(),
        comic_repo=_BatchComicRepo([]),
        tag_repo=_FakeTagRepo(),
    )
    with pytest.raises(ValueError):
        service.start_batch()


def test_prompt_includes_safety_rule():
    """底线规则在传输层强制追加，不依赖上层 prompt。"""
    from infrastructure.vision.openai_client import SAFETY_RULE, apply_safety_rule

    assert "未成年" in SAFETY_RULE
    assert "blocked" in SAFETY_RULE

    merged = apply_safety_rule("普通任务提示词")
    assert merged.startswith("普通任务提示词")
    assert "【硬性底线】" in merged
    # 幂等：已经带过就不再重复追加
    assert apply_safety_rule(merged) == merged


def test_usage_is_parsed_from_provider_response(tmp_path):
    """DeepSeek 与 OpenAI 两种用量字段都要能读出缓存命中数。"""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            payload = json.dumps({
                "choices": [{"message": {"content": '{"vibe": "v"}'}}],
                "usage": {
                    "prompt_tokens": 30000,
                    "completion_tokens": 400,
                    "total_tokens": 30400,
                    "prompt_cache_hit_tokens": 28000,
                },
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    image_path = tmp_path / "1.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xd9")
    try:
        from infrastructure.vision import call_vision_model_ex

        result = call_vision_model_ex(
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="k",
            model="deepseek-flash",
            prompt="p",
            image_paths=[str(image_path)],
            timeout_seconds=10,
            system_prompt="ctx",
        )
    finally:
        server.shutdown()

    assert result["text"] == '{"vibe": "v"}'
    assert result["usage"]["prompt_tokens"] == 30000
    assert result["usage"]["cached_tokens"] == 28000


def test_batch_accumulates_usage(tmp_path, monkeypatch):
    import time

    import application.vision_metadata_service as module
    from domain.comic import Comic
    from domain.config.entity import VisionConfig

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    monkeypatch.setattr(module, "BATCH_DELAY_SECONDS", 0)
    monkeypatch.delenv("BACKEND_RUNTIME_PROFILE", raising=False)

    config = VisionConfig(base_url="https://example.com/v1", api_key="sk-key", model="fake-vl")
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(config),
        comic_repo=_BatchComicRepo([Comic(id="c1", title="一", total_units=5)]),
        tag_repo=_FakeTagRepo(),
    )
    monkeypatch.setattr(
        service,
        "_build_draft",
        lambda comic_id, cfg, state: {
            "comic_id": comic_id,
            "draft": {"vibe": "v", "catalog": "c", "tags": []},
            "usage": {"prompt_tokens": 1000, "completion_tokens": 50, "cached_tokens": 900},
        },
    )

    service.start_batch()
    deadline = time.time() + 5
    while time.time() < deadline and service.batch_state()["running"]:
        time.sleep(0.05)

    usage = service.batch_state()["usage"]
    assert usage["prompt_tokens"] == 1000
    assert usage["cached_tokens"] == 900


def parse_draft_text_for_test(text):
    from application.vision_metadata_service import parse_draft_text

    return parse_draft_text(text)


def test_failure_is_recorded_listed_and_cleared(tmp_path, monkeypatch):
    import application.vision_metadata_service as module
    from domain.comic import Comic

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(),
        comic_repo=_BatchComicRepo([Comic(id="c1", title="某本", total_units=5)]),
        tag_repo=_FakeTagRepo(),
    )

    service.record_failure("c1", "接口返回 401: invalid key")
    failures = service.list_failures()
    assert len(failures) == 1
    assert failures[0]["comic_id"] == "c1"
    assert failures[0]["title"] == "某本"
    assert "401" in failures[0]["error"]

    assert service.clear_failure("c1") is True
    assert service.list_failures() == []
    assert service.clear_failure("c1") is False


def test_batch_failure_keeps_reason(tmp_path, monkeypatch):
    import time

    import application.vision_metadata_service as module
    from domain.comic import Comic
    from domain.config.entity import VisionConfig

    monkeypatch.setattr(module, "get_meta_dir", lambda mode=None: str(tmp_path))
    monkeypatch.setattr(module, "BATCH_DELAY_SECONDS", 0)
    monkeypatch.delenv("BACKEND_RUNTIME_PROFILE", raising=False)

    config = VisionConfig(base_url="https://example.com/v1", api_key="sk-key", model="fake-vl")
    service = module.VisionMetadataService(
        config_repo=_FakeConfigRepo(config),
        comic_repo=_BatchComicRepo([Comic(id="c1", title="会失败的", total_units=3)]),
        tag_repo=_FakeTagRepo(),
    )

    def boom(comic_id, cfg, state):
        raise RuntimeError("模型返回里没有 JSON 对象")

    monkeypatch.setattr(service, "_build_draft", boom)

    service.start_batch()
    deadline = time.time() + 5
    while time.time() < deadline and service.batch_state()["running"]:
        time.sleep(0.05)

    state = service.batch_state()
    assert state["failed"] == 1
    assert "JSON" in state["items"][0]["error"]
    failures = service.list_failures()
    assert len(failures) == 1
    assert "JSON" in failures[0]["error"]
