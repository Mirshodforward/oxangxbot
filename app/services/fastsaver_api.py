import aiohttp
import asyncio
from typing import Optional, Any
from dataclasses import dataclass
from urllib.parse import urlencode
import logging

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MediaInfo:
    """Media information response"""
    error: bool
    hosting: Optional[str] = None
    shortcode: Optional[str] = None
    caption: Optional[str] = None
    media_type: Optional[str] = None  # video, image, carousel
    download_url: Optional[str] = None
    thumb: Optional[str] = None
    # For carousel (multiple items)
    items: Optional[list[dict]] = None
    error_message: Optional[str] = None
    raw_data: Optional[dict] = None


@dataclass
class YouTubeDownload:
    """YouTube download response"""
    error: bool
    hosting: Optional[str] = None
    shortcode: Optional[str] = None
    file_id: Optional[str] = None
    media_type: Optional[str] = None
    bot_username: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class MusicSearchResult:
    """Music search result"""
    title: str
    shortcode: str
    duration: str
    thumb: str
    thumb_best: Optional[str] = None


@dataclass
class MusicRecognitionResult:
    """Music recognition result"""
    error: bool
    track_id: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    thumb: Optional[str] = None
    track_url: Optional[str] = None
    musics: Optional[list[MusicSearchResult]] = None
    error_message: Optional[str] = None


@dataclass
class UsageStats:
    """API usage statistics"""
    error: bool
    last_hour: int = 0
    last_day: int = 0
    last_week: int = 0
    last_month: int = 0
    points: int = 0
    end_date: Optional[str] = None


class FastSaverAPI:
    """FastSaverAPI client for media downloading"""
    
    def __init__(
        self,
        token: str = None,
        base_url: str = None,
        timeout: int = 60
    ):
        self.token = token or settings.TOKEN
        self.base_url = base_url or settings.API_BASE_URL
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Oxangxbot/1.0",
                    "Accept": "application/json"
                }
            )
        return self._session
    
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _request(
        self,
        endpoint: str,
        params: dict = None,
        retries: int = 3
    ) -> dict:
        """Make a request to the API"""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        # Add token to params
        params = params or {}
        params["token"] = self.token
        
        for attempt in range(retries):
            try:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    
                    if response.status == 422:
                        logger.error(f"Validation error: {data}")
                        return {"error": True, "message": data.get("detail", "Validation error")}
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status}: {data}")
                        error_msg = data.get("message", f"API error: {response.status}")
                        return {"error": True, "message": error_msg}
                    
                    return data
                    
            except aiohttp.ClientError as e:
                logger.error(f"Request error (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return {"error": True, "message": str(e)}
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return {"error": True, "message": str(e)}
        
        return {"error": True, "message": "Max retries exceeded"}
    
    async def get_media_info(self, url: str) -> MediaInfo:
        """
        Get media info from URL
        
        Supports: Instagram, YouTube, TikTok, Facebook, Twitter, 
                  Pinterest, Threads, Snapchat, Likee
        
        Cost: 1 point
        """
        data = await self._request("/get-info", {"url": url})
        
        if data.get("error", True):
            return MediaInfo(
                error=True,
                error_message=data.get("message", "Unknown error")
            )
        
        # Handle carousel (multiple items)
        items = None
        if data.get("type") == "carousel" or "medias" in data:
            items = data.get("medias", [])
        
        return MediaInfo(
            error=False,
            hosting=data.get("hosting"),
            shortcode=data.get("shortcode"),
            caption=data.get("caption"),
            media_type=data.get("type"),
            download_url=data.get("download_url"),
            thumb=data.get("thumb"),
            items=items,
            raw_data=data
        )
    
    async def download_youtube(
        self,
        video_id: str,
        format: str,
        bot_username: str
    ) -> YouTubeDownload:
        """
        Download YouTube video/audio
        
        Formats: 1080p, 720p, 480p, 360p, 240p, 144p, mp3
        
        Cost: 20 points
        """
        params = {
            "video_id": video_id,
            "format": format,
            "bot_username": bot_username
        }
        
        data = await self._request("/download", params)
        
        if data.get("error", True):
            error_msg = data.get("message", "Unknown error")
            if "Expecting value" in error_msg:
                error_msg = "Ushbu musiqani yuklab olish imkonsiz (server xatoligi)."
            elif "Not enough points" in error_msg:
                error_msg = "Bot API balansi tugagan (0 points)."
                
            return YouTubeDownload(
                error=True,
                error_message=error_msg
            )
        
        return YouTubeDownload(
            error=False,
            hosting=data.get("hosting"),
            shortcode=data.get("shortcode"),
            file_id=data.get("file_id"),
            media_type=data.get("media_type"),
            bot_username=data.get("bot_username")
        )
    
    async def search_music(self, query: str, page: int = 1) -> tuple[bool, list[MusicSearchResult], Optional[str]]:
        """
        Search for music on YouTube
        
        Cost: 1 point
        
        Returns: (success, results, error_message)
        """
        params = {"query": query, "page": page}
        data = await self._request("/search-music", params)
        
        if data.get("error", True):
            return False, [], data.get("message")
        
        results = []
        for item in data.get("results", []):
            results.append(MusicSearchResult(
                title=item.get("title", ""),
                shortcode=item.get("shortcode", ""),
                duration=item.get("duration", ""),
                thumb=item.get("thumb", ""),
                thumb_best=item.get("thumb_best")
            ))
        
        return True, results, None
    
    async def recognize_music(self, file_url: str) -> MusicRecognitionResult:
        """
        Recognize music from audio/video file (Shazam)
        
        Cost: 5 points
        """
        data = await self._request("/recognize-music", {"file_url": file_url})
        
        if data.get("error", True):
            return MusicRecognitionResult(
                error=True,
                error_message=data.get("message", "Music not recognized")
            )
        
        musics = []
        for item in data.get("musics", []):
            musics.append(MusicSearchResult(
                title=item.get("title", ""),
                shortcode=item.get("shortcode", ""),
                duration=item.get("duration", ""),
                thumb=item.get("thumb", ""),
                thumb_best=item.get("thumb_best")
            ))
        
        return MusicRecognitionResult(
            error=False,
            track_id=data.get("id"),
            title=data.get("title"),
            artist=data.get("artist"),
            thumb=data.get("thumb"),
            track_url=data.get("track_url"),
            musics=musics
        )
    
    # Fallback top musics data (used when API fails)
    FALLBACK_TOP_MUSICS = [
        {"shortcode": "HfWLgELllZs", "title": "Kendrick Lamar & SZA - luther"},
        {"shortcode": "H58vbez_m4E", "title": "Kendrick Lamar - Not Like Us"},
        {"shortcode": "k-k2_Liofy8", "title": "Lola Young - Messy"},
        {"shortcode": "GfCqMv--ncA", "title": "Kendrick Lamar, SZA - All The Stars"},
        {"shortcode": "ekr2nIex040", "title": "ROSÉ & Bruno Mars - APT."},
        {"shortcode": "kPa7bsKwL-c", "title": "Lady Gaga & Bruno Mars - Die With A Smile"},
        {"shortcode": "U8F5G5wR1mk", "title": "Kendrick Lamar - tv off (feat. Lefty Gunplay)"},
        {"shortcode": "fuV4yQWdn_4", "title": "Kendrick Lamar - squabble up"},
        {"shortcode": "cbHkzwa0QmM", "title": "Kendrick Lamar - peekaboo (feat. AzChike)"},
        {"shortcode": "ckM_TklU_AQ", "title": "Yeah Yeah Yeahs - Spitting Off the Edge of the World (feat. Perfume Genius)"}
    ]
    
    async def get_top_musics(
        self,
        country: str = "world",
        page: int = 1
    ) -> tuple[bool, list[dict], Optional[str]]:
        """
        Get top musics from Shazam
        
        Cost: 1 point
        
        Returns: (success, musics, error_message)
        Note: Falls back to cached top musics if API fails
        """
        params = {"country": country, "page": page}
        data = await self._request("/get-top-musics", params)
        
        if data.get("error", True):
            # Use fallback data when API fails
            logger.warning(f"Top musics API failed: {data.get('message')}, using fallback data")
            return True, self.FALLBACK_TOP_MUSICS, None
        
        return True, data.get("musics", []), None
    
    async def get_music_lyrics(self, track_url: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Get music lyrics from Shazam track URL
        
        Cost: 5 points
        
        Returns: (success, lyrics, error_message)
        """
        data = await self._request("/get-music-lyrics", {"track_url": track_url})
        
        if data.get("error", True):
            return False, None, data.get("message", "Lyrics not found")
        
        return True, data.get("lyrics"), None
    
    async def get_usage_stats(self, filter_by_token: bool = True) -> UsageStats:
        """
        Get usage statistics
        """
        params = {"filter_by_token": str(filter_by_token).lower()}
        data = await self._request("/get-usage-stats", params)
        
        if data.get("error", True):
            return UsageStats(error=True)
        
        usage = data.get("usage", {})
        return UsageStats(
            error=False,
            last_hour=usage.get("last_hour", 0),
            last_day=usage.get("last_day", 0),
            last_week=usage.get("last_week", 0),
            last_month=usage.get("last_month", 0),
            points=data.get("points", 0),
            end_date=data.get("end_date")
        )


# Global API instance with mock support
if settings.MOCK_MODE:
    logger.warning("MOCK MODE ENABLED - Using test data instead of real API")
    from app.services.mock_api import mock_api
    api = mock_api
else:
    api = FastSaverAPI()
