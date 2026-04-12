"""
Mock FastSaverAPI for testing purposes
When MOCK_MODE is enabled, returns test data instead of calling real API
"""

from typing import Optional, List
from dataclasses import dataclass
from app.services.fastsaver_api import (
    MediaInfo,
    YouTubeDownload,
    MusicSearchResult,
    MusicRecognitionResult,
    UsageStats
)


class MockFastSaverAPI:
    """Mock API for testing without real API calls"""
    
    async def get_media_info(self, url: str) -> MediaInfo:
        """Mock: Get media info"""
        return MediaInfo(
            error=False,
            hosting="instagram",
            shortcode="DFVEK6PJA9p",
            caption="Test Instagram post caption",
            media_type="video",
            download_url="https://via.placeholder.com/640x480.mp4",
            thumb="https://via.placeholder.com/320x240.jpg"
        )
    
    async def download_youtube(
        self,
        video_id: str,
        format: str,
        bot_username: str
    ) -> YouTubeDownload:
        """Mock: Download YouTube"""
        return YouTubeDownload(
            error=False,
            hosting="youtube",
            shortcode=video_id,
            file_id="BAACAgIAAxkDAAP8Z7Q1L-ZbXz1DE7uB2pmWiDEflFAAAsR7AAKphpBJdbI1QOvAvPYeBA",
            media_type="video",
            bot_username=bot_username
        )
    
    async def search_music(self, query: str, page: int = 1) -> tuple[bool, list[MusicSearchResult], Optional[str]]:
        """Mock: Search music"""
        results = [
            MusicSearchResult(
                title="The Weeknd - Blinding Lights (Official Video)",
                shortcode="4NRXx6U8ABQ",
                duration="4:23",
                thumb="https://i.ytimg.com/vi/4NRXx6U8ABQ/mqdefault.jpg",
                thumb_best="https://i.ytimg.com/vi/4NRXx6U8ABQ/maxresdefault.jpg"
            ),
            MusicSearchResult(
                title="The Weeknd - The Hills",
                shortcode="yzTuBuRdAyA",
                duration="3:55",
                thumb="https://i.ytimg.com/vi/yzTuBuRdAyA/mqdefault.jpg",
                thumb_best="https://i.ytimg.com/vi/yzTuBuRdAyA/maxresdefault.jpg"
            ),
        ]
        return True, results, None
    
    async def recognize_music(self, file_url: str) -> MusicRecognitionResult:
        """Mock: Recognize music"""
        musics = [
            MusicSearchResult(
                title="Shahzoda va Shohruhxon - Allo",
                shortcode="dnBUJJ7RUIs",
                duration="3:21",
                thumb="https://i.ytimg.com/vi/dnBUJJ7RUIs/mqdefault.jpg",
                thumb_best="https://i.ytimg.com/vi/dnBUJJ7RUIs/maxresdefault.jpg"
            ),
        ]
        
        return MusicRecognitionResult(
            error=False,
            track_id="316840701",
            title="Alo (feat. Shoxruhxon)",
            artist="Shakhzoda",
            thumb="https://is1-ssl.mzstatic.com/image/thumb/Music128/v4/28/87/2e/28872e4f-ebc3-9b8c-3b33-3a9a5c97a0db/190295813147.jpg/1000x1000cc.jpg",
            track_url="https://www.shazam.com/track/316840701/alo-feat-shoxruhxon",
            musics=musics
        )
    
    async def get_top_musics(
        self,
        country: str = "world",
        page: int = 1
    ) -> tuple[bool, list[dict], Optional[str]]:
        """Mock: Get top musics"""
        musics = [
            {"shortcode": "HfWLgELllZs", "title": "Kendrick Lamar & SZA - luther"},
            {"shortcode": "H58vbez_m4E", "title": "Kendrick Lamar - Not Like Us"},
            {"shortcode": "k-k2_Liofy8", "title": "Lola Young - Messy"},
            {"shortcode": "GfCqMv--ncA", "title": "Kendrick Lamar, SZA - All The Stars"},
            {"shortcode": "ekr2nIex040", "title": "ROSÉ & Bruno Mars - APT."},
        ]
        return True, musics, None
    
    async def get_music_lyrics(self, track_url: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Mock: Get music lyrics"""
        lyrics = """Davomiy qo'ng'iroqlarim javobsiz nega
Sog'inganimni yollamoqchi edim senga

Devonaman hayronaman ishqingda yonaman
So'ginaman talpinaman o'zimdan tonaman
Alo alo javob bermaysan nega
Alo alo nega indamaysan yonasan"""
        
        return True, lyrics, None
    
    async def get_usage_stats(self, filter_by_token: bool = True) -> UsageStats:
        """Mock: Get usage stats"""
        return UsageStats(
            error=False,
            last_hour=5,
            last_day=50,
            last_week=300,
            last_month=1000,
            points=99999,
            end_date="2026-04-06T23:59:59+00:00"
        )
    
    async def close(self):
        """Close session"""
        pass


# Instance
mock_api = MockFastSaverAPI()
