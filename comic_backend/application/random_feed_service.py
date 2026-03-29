from __future__ import annotations

import os
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from core.constants import COVER_DIR, DATA_DIR
from domain.comic.entity import Comic
from domain.recommendation.entity import Recommendation
from domain.video.entity import Video
from domain.video_recommendation.entity import VideoRecommendation
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.repositories.comic_repository_impl import ComicJsonRepository
from infrastructure.persistence.repositories.recommendation_repository_impl import RecommendationJsonRepository
from infrastructure.persistence.repositories.video_recommendation_repository_impl import (
    VideoRecommendationJsonRepository,
)
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.recommendation_cache_manager import recommendation_cache_manager


def _now_ts() -> float:
    return time.time()


def _sanitize_mode(value: str) -> str:
    text = str(value or "").strip().lower()
    return "video" if text == "video" else "comic"


def _normalize_limit(value: Optional[int], default: int = 16) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(128, parsed))


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_str(value) -> str:
    return str(value or "").strip()


def _clean_str_list(value) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    seen = set()
    for item in value:
        text = _clean_str(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _is_local_image_like(url: str) -> bool:
    text = _clean_str(url)
    if not text:
        return False
    lowered = text.lower()
    return (
        lowered.startswith("/media/")
        or lowered.startswith("/static/cover/")
        or lowered.startswith("/static/default/")
    )


def _resolve_local_image_path(url: str) -> str:
    text = _clean_str(url)
    if text.startswith("/media/"):
        rel = text[len("/media/"):].replace("/", os.sep)
        return os.path.abspath(os.path.join(DATA_DIR, rel))
    if text.startswith("/static/cover/"):
        rel = text[len("/static/cover/"):].replace("/", os.sep)
        return os.path.abspath(os.path.join(COVER_DIR, rel))
    return ""


def _is_existing_local_image(url: str) -> bool:
    if not _is_local_image_like(url):
        return False
    if url.startswith("/static/default/"):
        return True
    path = _resolve_local_image_path(url)
    if not path:
        return False
    return os.path.isfile(path)


@dataclass
class FeedWorkCandidate:
    mode: str
    source: str
    content_id: str
    title: str
    author: str
    score: float
    tag_ids: List[str] = field(default_factory=list)
    total_units: int = 0
    current_unit: int = 0
    page_numbers: List[int] = field(default_factory=list)
    image_urls: List[str] = field(default_factory=list)


class FeedWeightStrategy:
    """Weight strategy extension point for random feed scoring."""

    name = "base"

    def weight(self, candidate: FeedWorkCandidate) -> float:
        return 1.0


class PureRandomWeightStrategy(FeedWeightStrategy):
    name = "pure_random_v1"

    def weight(self, candidate: FeedWorkCandidate) -> float:
        return 1.0


class RandomPriorityWeightStrategy(FeedWeightStrategy):
    """
    Default strategy:
    - Keep randomness as the main signal.
    - Apply light bias using score/read progress/source so later overrides are easy.
    """

    name = "random_priority_v1"

    def weight(self, candidate: FeedWorkCandidate) -> float:
        base = 1.0

        normalized_score = max(0.0, min(12.0, _safe_float(candidate.score, 0.0))) / 12.0
        base += 0.18 * normalized_score

        if candidate.total_units > 0:
            progress_ratio = max(
                0.0,
                min(1.0, _safe_float(candidate.current_unit, 0.0) / float(candidate.total_units)),
            )
            base += 0.15 * (1.0 - progress_ratio)

        if candidate.source == "preview":
            base *= 0.96

        return max(0.05, base)


@dataclass
class FeedSession:
    session_id: str
    mode: str
    strategy_name: str
    seed: int
    created_at: float
    generated_count: int
    candidates: List[FeedWorkCandidate]
    rng: random.Random


class RandomFeedService:
    _MAX_SESSIONS = 128
    _SESSION_IDLE_SECONDS = 4 * 60 * 60

    def __init__(self):
        self._comic_repo = ComicJsonRepository()
        self._recommendation_repo = RecommendationJsonRepository()
        self._video_repo = VideoJsonRepository()
        self._video_recommendation_repo = VideoRecommendationJsonRepository()

        self._lock = threading.Lock()
        self._sessions: Dict[str, FeedSession] = {}
        self._startup_session_ids: Dict[str, str] = {}
        self._strategy_factories: Dict[str, Callable[[], FeedWeightStrategy]] = {}
        self._default_strategy_name = RandomPriorityWeightStrategy.name

        self.register_strategy(PureRandomWeightStrategy.name, PureRandomWeightStrategy)
        self.register_strategy(RandomPriorityWeightStrategy.name, RandomPriorityWeightStrategy)

        # Generate startup sequence snapshots for both modes.
        for mode in ("comic", "video"):
            session = self.create_session(mode=mode, strategy_name=self._default_strategy_name)
            if session:
                self._startup_session_ids[mode] = session["session_id"]

    def register_strategy(self, name: str, factory: Callable[[], FeedWeightStrategy]) -> None:
        strategy_name = _clean_str(name)
        if not strategy_name:
            raise ValueError("strategy name is required")
        self._strategy_factories[strategy_name] = factory

    def list_strategies(self) -> List[str]:
        names = sorted(self._strategy_factories.keys())
        return names

    def get_startup_session_id(self, mode: str) -> Optional[str]:
        mode_key = _sanitize_mode(mode)
        with self._lock:
            return self._startup_session_ids.get(mode_key)

    def _build_strategy(self, strategy_name: Optional[str]) -> FeedWeightStrategy:
        target_name = _clean_str(strategy_name) or self._default_strategy_name
        factory = self._strategy_factories.get(target_name)
        if factory is None:
            target_name = self._default_strategy_name
            factory = self._strategy_factories.get(target_name, RandomPriorityWeightStrategy)
        strategy = factory()
        if not getattr(strategy, "name", ""):
            strategy.name = target_name
        return strategy

    def _trim_sessions_locked(self) -> None:
        now = _now_ts()
        idle_limit = self._SESSION_IDLE_SECONDS
        stale_ids = []
        for session_id, session in self._sessions.items():
            if now - session.created_at > idle_limit:
                stale_ids.append(session_id)
        for session_id in stale_ids:
            self._sessions.pop(session_id, None)

        if len(self._sessions) <= self._MAX_SESSIONS:
            return

        ordered = sorted(self._sessions.values(), key=lambda s: s.created_at)
        keep_ids = {s.session_id for s in ordered[-self._MAX_SESSIONS:]}
        for session_id in list(self._sessions.keys()):
            if session_id not in keep_ids:
                self._sessions.pop(session_id, None)

    def create_session(self, mode: str, strategy_name: Optional[str] = None) -> Dict:
        mode_key = _sanitize_mode(mode)
        strategy = self._build_strategy(strategy_name)
        seed = random.SystemRandom().randint(1, 2_147_483_647)
        rng = random.Random(seed)
        candidates = self._build_candidates(mode_key)

        session = FeedSession(
            session_id=uuid.uuid4().hex,
            mode=mode_key,
            strategy_name=strategy.name,
            seed=seed,
            created_at=_now_ts(),
            generated_count=0,
            candidates=candidates,
            rng=rng,
        )
        with self._lock:
            self._trim_sessions_locked()
            self._sessions[session.session_id] = session
        return self._session_payload(session)

    def refresh_session(self, session_id: str) -> Optional[Dict]:
        key = _clean_str(session_id)
        if not key:
            return None

        with self._lock:
            existing = self._sessions.get(key)
            if not existing:
                return None
            mode_key = existing.mode
            strategy_name = existing.strategy_name

        strategy = self._build_strategy(strategy_name)
        seed = random.SystemRandom().randint(1, 2_147_483_647)
        rng = random.Random(seed)
        candidates = self._build_candidates(mode_key)

        with self._lock:
            current = self._sessions.get(key)
            if not current:
                return None
            current.seed = seed
            current.rng = rng
            current.candidates = candidates
            current.generated_count = 0
            current.created_at = _now_ts()
            current.strategy_name = strategy.name
            return self._session_payload(current)

    def next_items(self, session_id: str, limit: int) -> Optional[Dict]:
        key = _clean_str(session_id)
        if not key:
            return None
        max_items = _normalize_limit(limit, default=16)

        with self._lock:
            session = self._sessions.get(key)
            if not session:
                return None
            if not session.candidates:
                return {
                    "session_id": session.session_id,
                    "mode": session.mode,
                    "items": [],
                    "next_cursor": session.generated_count,
                }
            strategy = self._build_strategy(session.strategy_name)
            items = []
            for _ in range(max_items):
                candidate = self._pick_candidate(session.candidates, strategy, session.rng)
                if candidate is None:
                    continue
                session.generated_count += 1
                item = self._materialize_item(candidate, session.rng)
                item["sequence_index"] = session.generated_count
                items.append(item)

            return {
                "session_id": session.session_id,
                "mode": session.mode,
                "items": items,
                "next_cursor": session.generated_count,
            }

    def _pick_candidate(
        self,
        candidates: Sequence[FeedWorkCandidate],
        strategy: FeedWeightStrategy,
        rng: random.Random,
    ) -> Optional[FeedWorkCandidate]:
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        weights = []
        for candidate in candidates:
            weight = _safe_float(strategy.weight(candidate), 0.0)
            weights.append(max(0.0, weight))

        total_weight = sum(weights)
        if total_weight <= 0:
            return candidates[rng.randrange(len(candidates))]

        pick = rng.random() * total_weight
        running = 0.0
        for candidate, weight in zip(candidates, weights):
            running += weight
            if pick <= running:
                return candidate
        return candidates[-1]

    def _session_payload(self, session: FeedSession) -> Dict:
        return {
            "session_id": session.session_id,
            "mode": session.mode,
            "strategy_name": session.strategy_name,
            "seed": session.seed,
            "candidate_count": len(session.candidates),
            "created_at": session.created_at,
        }

    def _materialize_item(self, candidate: FeedWorkCandidate, rng: random.Random) -> Dict:
        if candidate.mode == "comic":
            page_num = 1
            image_url = ""
            if candidate.page_numbers:
                page_num = candidate.page_numbers[rng.randrange(len(candidate.page_numbers))]
            if candidate.source == "preview":
                image_url = (
                    f"/api/v1/recommendation/cache/image?recommendation_id={candidate.content_id}&page_num={page_num}"
                )
                detail_route_name = "RecommendationDetail"
            else:
                image_url = f"/api/v1/comic/image?comic_id={candidate.content_id}&page_num={page_num}"
                detail_route_name = "ComicDetail"
        else:
            page_num = 0
            image_url = candidate.image_urls[rng.randrange(len(candidate.image_urls))]
            detail_route_name = "VideoRecommendationDetail" if candidate.source == "preview" else "VideoDetail"

        return {
            "mode": candidate.mode,
            "source": candidate.source,
            "content_id": candidate.content_id,
            "title": candidate.title,
            "author": candidate.author,
            "score": candidate.score,
            "tag_ids": list(candidate.tag_ids or []),
            "image_url": image_url,
            "page_num": page_num,
            "detail_route_name": detail_route_name,
            "detail_id": candidate.content_id,
        }

    def _build_candidates(self, mode: str) -> List[FeedWorkCandidate]:
        if mode == "video":
            return self._build_video_candidates()
        return self._build_comic_candidates()

    def _build_comic_candidates(self) -> List[FeedWorkCandidate]:
        candidates: List[FeedWorkCandidate] = []

        try:
            local_comics: List[Comic] = self._comic_repo.get_all()
        except Exception as exc:
            error_logger.error(f"[random_feed] load local comics failed: {exc}")
            local_comics = []

        for comic in local_comics:
            if getattr(comic, "is_deleted", False):
                continue
            comic_id = _clean_str(getattr(comic, "id", ""))
            if not comic_id:
                continue
            total_page = max(0, _safe_int(getattr(comic, "total_page", 0), 0))
            if total_page <= 0:
                continue
            candidates.append(
                FeedWorkCandidate(
                    mode="comic",
                    source="local",
                    content_id=comic_id,
                    title=_clean_str(getattr(comic, "title", comic_id)),
                    author=_clean_str(getattr(comic, "author", "")),
                    score=_safe_float(getattr(comic, "score", 0.0), 0.0),
                    tag_ids=_clean_str_list(getattr(comic, "tag_ids", [])),
                    total_units=total_page,
                    current_unit=max(1, _safe_int(getattr(comic, "current_page", 1), 1)),
                    page_numbers=list(range(1, total_page + 1)),
                )
            )

        try:
            preview_recommendations: List[Recommendation] = self._recommendation_repo.get_all()
        except Exception as exc:
            error_logger.error(f"[random_feed] load preview recommendations failed: {exc}")
            preview_recommendations = []

        for recommendation in preview_recommendations:
            if getattr(recommendation, "is_deleted", False):
                continue
            recommendation_id = _clean_str(getattr(recommendation, "id", ""))
            if not recommendation_id:
                continue
            try:
                if not recommendation_cache_manager.is_cached(recommendation_id):
                    continue
                cached_pages = recommendation_cache_manager.get_cached_pages(recommendation_id)
            except Exception:
                continue
            cached_pages = [page for page in cached_pages if _safe_int(page, 0) > 0]
            if not cached_pages:
                continue

            candidates.append(
                FeedWorkCandidate(
                    mode="comic",
                    source="preview",
                    content_id=recommendation_id,
                    title=_clean_str(getattr(recommendation, "title", recommendation_id)),
                    author=_clean_str(getattr(recommendation, "author", "")),
                    score=_safe_float(getattr(recommendation, "score", 0.0), 0.0),
                    tag_ids=_clean_str_list(getattr(recommendation, "tag_ids", [])),
                    total_units=len(cached_pages),
                    current_unit=max(1, _safe_int(getattr(recommendation, "current_page", 1), 1)),
                    page_numbers=cached_pages,
                )
            )

        app_logger.info(
            "[random_feed] comic candidate pool ready: local=%s preview=%s total=%s",
            len([item for item in candidates if item.source == "local"]),
            len([item for item in candidates if item.source == "preview"]),
            len(candidates),
        )
        return candidates

    def _extract_video_local_images(self, entity) -> List[str]:
        values: List[str] = []
        for raw in (
            getattr(entity, "cover_path_local", ""),
            *list(getattr(entity, "thumbnail_images_local", []) or []),
            getattr(entity, "cover_path", ""),
            *list(getattr(entity, "thumbnail_images", []) or []),
        ):
            value = _clean_str(raw)
            if not value:
                continue
            if value in values:
                continue
            if not _is_local_image_like(value):
                continue
            if not _is_existing_local_image(value):
                continue
            values.append(value)
        return values

    def _build_video_candidates(self) -> List[FeedWorkCandidate]:
        candidates: List[FeedWorkCandidate] = []

        try:
            local_videos: List[Video] = self._video_repo.get_all()
        except Exception as exc:
            error_logger.error(f"[random_feed] load local videos failed: {exc}")
            local_videos = []

        for video in local_videos:
            if getattr(video, "is_deleted", False):
                continue
            video_id = _clean_str(getattr(video, "id", ""))
            if not video_id:
                continue
            image_urls = self._extract_video_local_images(video)
            if not image_urls:
                continue
            candidates.append(
                FeedWorkCandidate(
                    mode="video",
                    source="local",
                    content_id=video_id,
                    title=_clean_str(getattr(video, "title", video_id)),
                    author=_clean_str(getattr(video, "creator", "")),
                    score=_safe_float(getattr(video, "score", 0.0), 0.0),
                    tag_ids=_clean_str_list(getattr(video, "tag_ids", [])),
                    total_units=max(0, _safe_int(getattr(video, "total_units", 0), 0)),
                    current_unit=max(1, _safe_int(getattr(video, "current_unit", 1), 1)),
                    image_urls=image_urls,
                )
            )

        try:
            preview_videos: List[VideoRecommendation] = self._video_recommendation_repo.get_all()
        except Exception as exc:
            error_logger.error(f"[random_feed] load preview videos failed: {exc}")
            preview_videos = []

        for video in preview_videos:
            if getattr(video, "is_deleted", False):
                continue
            video_id = _clean_str(getattr(video, "id", ""))
            if not video_id:
                continue
            image_urls = self._extract_video_local_images(video)
            if not image_urls:
                continue
            candidates.append(
                FeedWorkCandidate(
                    mode="video",
                    source="preview",
                    content_id=video_id,
                    title=_clean_str(getattr(video, "title", video_id)),
                    author=_clean_str(getattr(video, "creator", "")),
                    score=_safe_float(getattr(video, "score", 0.0), 0.0),
                    tag_ids=_clean_str_list(getattr(video, "tag_ids", [])),
                    total_units=max(0, _safe_int(getattr(video, "total_units", 0), 0)),
                    current_unit=max(1, _safe_int(getattr(video, "current_unit", 1), 1)),
                    image_urls=image_urls,
                )
            )

        app_logger.info(
            "[random_feed] video candidate pool ready: local=%s preview=%s total=%s",
            len([item for item in candidates if item.source == "local"]),
            len([item for item in candidates if item.source == "preview"]),
            len(candidates),
        )
        return candidates


random_feed_service = RandomFeedService()

