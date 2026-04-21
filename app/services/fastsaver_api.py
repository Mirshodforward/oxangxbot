import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from app.config import settings
from app.utils.helpers import extract_instagram_media_code

logger = logging.getLogger(__name__)

# GET /fetch ba'zan "id": "reel" kabi noaniq qiymat qaytaradi — kesh/DB uchun URLdan kod olamiz.
_FETCH_ID_PLACEHOLDERS = frozenset(
    {
        "reel",
        "reels",
        "post",
        "p",
        "tv",
        "story",
        "stories",
        "carousel",
        "media",
        "video",
        "image",
        "clip",
        "",
    }
)


def _api_ok(data: dict) -> bool:
    return bool(data) and data.get("ok") is True


def _error_message_from_body(data: dict[str, Any], status: int) -> str:
    """FastSaver yoki FastAPI: message / error / detail."""
    detail = data.get("detail")
    if isinstance(detail, list):
        parts = []
        for x in detail:
            if isinstance(x, dict):
                parts.append(str(x.get("msg") or x))
            else:
                parts.append(str(x))
        detail = "; ".join(parts) if parts else None
    elif detail is not None and not isinstance(detail, str):
        detail = str(detail)
    return (
        (data.get("message") or data.get("error") or detail or "").strip()
        or f"HTTP {status}"
    )


@dataclass
class MediaInfo:
    """GET /fetch — ijtimoiy tarmoq media"""

    error: bool
    hosting: Optional[str] = None
    shortcode: Optional[str] = None
    caption: Optional[str] = None
    media_type: Optional[str] = None
    download_url: Optional[str] = None
    thumb: Optional[str] = None
    items: Optional[list[dict]] = None
    error_message: Optional[str] = None
    raw_data: Optional[dict] = None


@dataclass
class YouTubeDownload:
    """YouTube: tg-bot (file_id) yoki /youtube/download (download_url)"""

    error: bool
    hosting: Optional[str] = None
    shortcode: Optional[str] = None
    file_id: Optional[str] = None
    media_type: Optional[str] = None
    bot_username: Optional[str] = None
    error_message: Optional[str] = None
    download_url: Optional[str] = None
    filename: Optional[str] = None


@dataclass
class MusicSearchResult:
    title: str
    shortcode: str  # YouTube video_id
    duration: str
    thumb: str
    thumb_best: Optional[str] = None


@dataclass
class MusicRecognitionResult:
    error: bool
    track_id: Optional[str] = None  # Shazam id
    title: Optional[str] = None
    artist: Optional[str] = None
    thumb: Optional[str] = None
    track_url: Optional[str] = None  # ixtiyoriy (UI uchun)
    musics: Optional[list[MusicSearchResult]] = None
    error_message: Optional[str] = None


@dataclass
class UsageStats:
    error: bool
    last_hour: int = 0
    last_day: int = 0
    last_week: int = 0
    last_month: int = 0
    points: int = 0
    end_date: Optional[str] = None


class FastSaverAPI:
    """FastSaver API v1 — https://api.fastsaver.io/v1 , X-Api-Key"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        self.api_key = (api_key or settings.TOKEN or "").strip()
        self.base_url = (base_url or settings.API_BASE_URL or "").rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    def _headers_base(self) -> dict[str, str]:
        """JSON va multipart uchun (Content-Type qo'shilmaydi — FormData o'zi qo'yadi)."""
        h = {
            "User-Agent": "Oxangxbot/1.0",
            "Accept": "application/json",
        }
        if self.api_key:
            h["X-Api-Key"] = self.api_key
        return h

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self._headers_base(),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _read_json_response(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        raw = await response.read()
        try:
            text = raw.decode("utf-8") if raw else ""
            return json.loads(text) if text.strip() else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            preview = raw[:300] if raw else b""
            logger.error("JSON emas: status=%s body=%r", response.status, preview)
            return {"ok": False, "message": f"JSON emas (HTTP {response.status})"}

    async def _get(self, path: str, params: Optional[dict] = None, retries: int = 3) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        params = params or {}
        for attempt in range(retries):
            try:
                async with session.get(url, params=params, headers=self._headers_base()) as response:
                    data = await self._read_json_response(response)
                    if response.status == 422:
                        return {"ok": False, "message": _error_message_from_body(data, 422)}
                    if response.status != 200:
                        msg = _error_message_from_body(data, response.status)
                        if response.status == 404:
                            logger.warning(
                                "GET %s -> 404 (%s). API_BASE_URL to'g'ri ekanini tekshiring (masalan https://api.fastsaver.io/v1).",
                                path,
                                msg,
                            )
                        return {"ok": False, "message": msg}
                    return data
            except aiohttp.ClientError as e:
                logger.error("GET %s (urinish %s): %s", path, attempt + 1, e)
                if attempt < retries - 1:
                    await asyncio.sleep(2**attempt)
                else:
                    return {"ok": False, "message": str(e)}
        return {"ok": False, "message": "Max retries"}

    async def _post_json(self, path: str, body: dict, retries: int = 3) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        for attempt in range(retries):
            try:
                async with session.post(url, json=body, headers=self._headers_base()) as response:
                    data = await self._read_json_response(response)
                    if response.status not in (200, 201):
                        msg = _error_message_from_body(data, response.status)
                        return {"ok": False, "message": msg}
                    return data
            except aiohttp.ClientError as e:
                logger.error("POST %s: %s", path, e)
                if attempt < retries - 1:
                    await asyncio.sleep(2**attempt)
                else:
                    return {"ok": False, "message": str(e)}
        return {"ok": False, "message": "Max retries"}

    async def get_media_info(self, url: str) -> MediaInfo:
        """GET /fetch — Instagram, TikTok, ..."""
        data = await self._get("/fetch", {"url": url})
        if not _api_ok(data):
            return MediaInfo(
                error=True,
                error_message=data.get("message") or data.get("error") or "Media topilmadi",
            )

        raw_list = data.get("medias") or data.get("items") or data.get("slides") or []
        if not isinstance(raw_list, list):
            raw_list = []

        download_url = data.get("download_url")
        media_type = data.get("type")
        caption = data.get("caption")

        # Bir dona story/slide — ba'zan download_url faqat items[0] ichida
        if not download_url and len(raw_list) == 1:
            only = raw_list[0]
            if isinstance(only, dict):
                download_url = only.get("download_url") or only.get("url")
                media_type = media_type or only.get("type")
                caption = caption or only.get("caption")

        if data.get("type") == "carousel" or len(raw_list) > 1:
            items: Optional[list[dict]] = raw_list or None
        else:
            items = None

        api_id = data.get("id")
        sid = str(api_id).strip() if api_id is not None else ""
        if sid.lower() in _FETCH_ID_PLACEHOLDERS:
            sid = ""
        shortcode = sid or extract_instagram_media_code(url)
        if not shortcode and api_id is not None:
            fb = str(api_id).strip()
            if fb.lower() not in _FETCH_ID_PLACEHOLDERS:
                shortcode = fb

        return MediaInfo(
            error=False,
            hosting=data.get("source"),
            shortcode=shortcode,
            caption=caption,
            media_type=media_type,
            download_url=download_url,
            thumb=data.get("thumbnail_url") or data.get("thumbnail"),
            items=items,
            raw_data=data,
        )

    async def download_youtube(
        self,
        video_id: str,
        format: str,
        bot_username: str,
    ) -> YouTubeDownload:
        """
        MP3/audio: POST /youtube/audio/tg-bot (file_id)
        Video: POST /youtube/download (download_url yoki file_id)
        """
        fmt = (format or "").strip().lower()
        if fmt == "mp3":
            fmt = "audio"

        bot_un = bot_username.strip()
        if not bot_un.startswith("@"):
            bot_un = f"@{bot_un}"

        if fmt == "audio":
            data = await self._post_json(
                "/youtube/audio/tg-bot",
                {"video_id": video_id, "bot_username": bot_un},
            )
            if not _api_ok(data):
                msg = data.get("message", "Unknown error")
                if "point" in msg.lower() or "credit" in msg.lower() or "balance" in msg.lower():
                    msg = "API balansi yetarli emas."
                return YouTubeDownload(error=True, error_message=msg, shortcode=video_id)
            return YouTubeDownload(
                error=False,
                hosting="youtube",
                shortcode=video_id,
                file_id=data.get("file_id"),
                media_type="audio",
                bot_username=bot_un,
            )

        watch = f"https://www.youtube.com/watch?v={video_id}"
        data = await self._post_json(
            "/youtube/download",
            {"url": watch, "format": format},
        )
        if not _api_ok(data):
            msg = data.get("message", "Unknown error")
            return YouTubeDownload(error=True, error_message=msg, shortcode=video_id)

        return YouTubeDownload(
            error=False,
            hosting="youtube",
            shortcode=data.get("video_id") or video_id,
            file_id=data.get("file_id"),
            media_type="video",
            download_url=data.get("download_url"),
            filename=data.get("filename"),
        )

    async def search_music(
        self, query: str, page: int = 1
    ) -> tuple[bool, list[MusicSearchResult], Optional[str]]:
        """GET /youtube/search"""
        q = (query or "").strip()
        if not q:
            return False, [], "Bo'sh qidiruv"
        try:
            page = max(1, min(3, int(page)))
        except (TypeError, ValueError):
            page = 1

        data = await self._get("/youtube/search", {"query": q, "page": page})
        if not _api_ok(data):
            return False, [], data.get("message")

        results: list[MusicSearchResult] = []
        for item in data.get("results", []):
            vid = item.get("video_id") or item.get("shortcode") or ""
            results.append(
                MusicSearchResult(
                    title=item.get("title", ""),
                    shortcode=vid,
                    duration=str(item.get("duration", "")),
                    thumb=item.get("thumbnail", "") or item.get("thumb", "") or "",
                    thumb_best=item.get("thumbnail_max") or item.get("thumb_best"),
                )
            )
        return True, results, None

    async def recognize_music_file(self, file_path: str) -> MusicRecognitionResult:
        """POST /shazam/identify — fayl yuklash"""
        if not os.path.isfile(file_path):
            return MusicRecognitionResult(
                error=True,
                error_message="Fayl topilmadi",
            )

        session = await self._get_session()
        url = f"{self.base_url}/shazam/identify"
        try:
            with open(file_path, "rb") as fh:
                raw = fh.read()
        except OSError as e:
            return MusicRecognitionResult(error=True, error_message=str(e))

        form = aiohttp.FormData()
        ext = os.path.splitext(file_path)[1] or ".ogg"
        form.add_field(
            "file",
            raw,
            filename=f"upload{ext}",
            content_type="application/octet-stream",
        )

        try:
            async with session.post(url, data=form, headers=self._headers_base()) as response:
                data = await self._read_json_response(response)
                if response.status != 200 or not _api_ok(data):
                    msg = data.get("message") or "Tanilmadi"
                    return MusicRecognitionResult(error=True, error_message=msg)

                musics: list[MusicSearchResult] = []
                for item in data.get("results", []):
                    vid = item.get("video_id") or ""
                    musics.append(
                        MusicSearchResult(
                            title=item.get("title", ""),
                            shortcode=vid,
                            duration=str(item.get("duration", "")),
                            thumb=item.get("thumbnail", "")
                            or item.get("thumbnail_url", "")
                            or "",
                            thumb_best=item.get("thumbnail_max"),
                        )
                    )

                sid = str(data.get("id", "") or "")
                return MusicRecognitionResult(
                    error=False,
                    track_id=sid,
                    title=data.get("title"),
                    artist=data.get("artist"),
                    thumb=data.get("thumbnail"),
                    track_url=f"shazam:{sid}" if sid else None,
                    musics=musics,
                )
        except Exception as e:
            logger.exception("shazam/identify")
            return MusicRecognitionResult(error=True, error_message=str(e))

    FALLBACK_TOP_MUSICS = [
        {"shortcode": "HfWLgELllZs", "title": "Kendrick Lamar & SZA - luther"},
        {"shortcode": "H58vbez_m4E", "title": "Kendrick Lamar - Not Like Us"},
        {"shortcode": "k-k2_Liofy8", "title": "Lola Young - Messy"},
    ]

    async def get_top_musics(
        self,
        country: str = "world",
        page: int = 1,
    ) -> tuple[bool, list[dict], Optional[str]]:
        """GET /shazam/top"""
        try:
            page = max(1, min(3, int(page)))
        except (TypeError, ValueError):
            page = 1

        c = (country or "world").strip().lower()
        if c == "world":
            c_api = "world"
        else:
            c_api = c.lower().replace("_", "")

        data = await self._get("/shazam/top", {"country": c_api, "page": page})
        if not _api_ok(data):
            logger.warning("shazam/top: %s", data.get("message"))
            return True, list(self.FALLBACK_TOP_MUSICS), None

        out: list[dict] = []
        for item in data.get("results", []):
            vid = item.get("video_id") or item.get("shortcode") or ""
            out.append(
                {
                    "shortcode": vid,
                    "title": item.get("title", ""),
                    "duration": item.get("duration"),
                    "thumb": item.get("thumbnail_url") or item.get("thumbnail"),
                }
            )
        return True, out, None

    async def get_music_lyrics(self, shazam_id: str) -> tuple[bool, Optional[str], Optional[str]]:
        """GET /shazam/lyrics?shazam_id="""
        sid = (shazam_id or "").strip()
        if not sid:
            return False, None, "shazam_id bo'sh"
        data = await self._get("/shazam/lyrics", {"shazam_id": sid})
        if not _api_ok(data):
            return False, None, data.get("message", "Lyrics topilmadi")
        lyrics = data.get("lyrics")
        if lyrics is None:
            return False, None, "Lyrics bo'sh"
        return True, str(lyrics), None

    async def get_usage_stats(self, filter_by_token: bool = True) -> UsageStats:
        """v1 hujjatda alohida credits endpoint ko'rsatilmagan."""
        _ = filter_by_token
        return UsageStats(error=False, points=0)


if settings.MOCK_MODE:
    logger.warning("MOCK MODE ENABLED - Using test data instead of real API")
    from app.services.mock_api import mock_api

    api = mock_api
else:
    api = FastSaverAPI()
