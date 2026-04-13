from datetime import datetime, timedelta
from typing import Optional
import json
import hashlib
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    User, Download, MusicRecognition, CachedMedia, Platform, MediaType, 
    get_uzb_time, RequiredChannel, BroadcastMessage, MusicSearchCache, 
    YouTubeCache, CacheStats
)


class UserRepository:
    """Repository for User operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> tuple[User, bool]:
        """Get existing user or create new one. Returns (user, is_new)"""
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update user info
            user.username = username
            user.updated_at = get_uzb_time()
            if language_code:
                user.language_code = language_code
            await self.session.commit()
            return user, False
        
        # Create new user
        user = User(
            user_id=user_id,
            username=username,
            language_code=language_code or "uz"
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, True
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def increment_downloads(self, user_id: int) -> None:
        """Increment user's download count obsolete"""
        pass
    
    async def get_total_users(self) -> int:
        """Get total number of users"""
        result = await self.session.execute(
            select(func.count(User.id))
        )
        return result.scalar() or 0
    
    async def get_active_users(self, days: int = 7) -> int:
        """Get number of active users in last N days"""
        since = get_uzb_time() - timedelta(days=days)
        result = await self.session.execute(
            select(func.count(User.id)).where(User.updated_at >= since)
        )
        return result.scalar() or 0

    
    async def update_language(self, user_id: int, language_code: str) -> None:
        """Update user's preferred language"""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(language_code=language_code, updated_at=get_uzb_time())
        )
        await self.session.commit()

class DownloadRepository:
    """Repository for Download operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: int,
        url: str,
        platform: Platform,
        shortcode: Optional[str] = None,
        media_type: Optional[MediaType] = None,
        caption: Optional[str] = None,
        file_id: Optional[str] = None,
        is_success: bool = True,
        error_message: Optional[str] = None
    ) -> Download:
        """Create download record"""
        download = Download(
            user_id=user_id,
            url=url,
            shortcode=shortcode,
            platform=platform,
            media_type=media_type,
            caption=caption[:500] if caption else None,  # Truncate caption
            file_id=file_id,
            is_success=is_success,
            error_message=error_message
        )
        self.session.add(download)
        await self.session.commit()
        await self.session.refresh(download)
        return download
    
    async def get_user_downloads(self, user_id: int, limit: int = 10) -> list[Download]:
        """Get user's recent downloads"""
        result = await self.session.execute(
            select(Download)
            .where(Download.user_id == user_id)
            .order_by(Download.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_total_downloads(self) -> int:
        """Get total downloads count"""
        result = await self.session.execute(
            select(func.count(Download.id))
        )
        return result.scalar() or 0
    
    async def get_downloads_by_platform(self) -> dict[str, int]:
        """Get downloads grouped by platform"""
        result = await self.session.execute(
            select(Download.platform, func.count(Download.id))
            .group_by(Download.platform)
        )
        return {row[0].value: row[1] for row in result.all()}


class CacheRepository:
    """Repository for cached media operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_hash(self, url_hash: str) -> Optional[CachedMedia]:
        """Get cached media by URL hash"""
        result = await self.session.execute(
            select(CachedMedia).where(
                CachedMedia.url_hash == url_hash,
                (CachedMedia.expires_at.is_(None)) | (CachedMedia.expires_at > datetime.utcnow())
            )
        )
        return result.scalar_one_or_none()
    
    async def create_or_update(
        self,
        url_hash: str,
        original_url: str,
        platform: Platform,
        media_type: Optional[MediaType] = None,
        shortcode: Optional[str] = None,
        download_url: Optional[str] = None,
        thumb_url: Optional[str] = None,
        caption: Optional[str] = None,
        file_id: Optional[str] = None,
        file_id_audio: Optional[str] = None,
        expires_hours: int = 240  # 10 kun
    ) -> CachedMedia:
        """Create or update cached media"""
        from datetime import timedelta
        
        existing = await self.get_by_hash(url_hash)
        if existing:
            # Update existing
            existing.download_url = download_url or existing.download_url
            existing.file_id = file_id or existing.file_id
            existing.file_id_audio = file_id_audio or existing.file_id_audio
            existing.expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            await self.session.commit()
            return existing
        
        # Create new
        cached = CachedMedia(
            url_hash=url_hash,
            original_url=original_url,
            platform=platform,
            media_type=media_type,
            shortcode=shortcode,
            download_url=download_url,
            thumb_url=thumb_url,
            caption=caption[:500] if caption else None,
            file_id=file_id,
            file_id_audio=file_id_audio,
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours)
        )
        self.session.add(cached)
        await self.session.commit()
        await self.session.refresh(cached)
        return cached
    
    async def update_file_id(self, url_hash: str, file_id: str, is_audio: bool = False) -> None:
        """Update file_id for cached media"""
        field = CachedMedia.file_id_audio if is_audio else CachedMedia.file_id
        await self.session.execute(
            update(CachedMedia)
            .where(CachedMedia.url_hash == url_hash)
            .values(**{field.key: file_id})
        )
        await self.session.commit()
    
    async def increment_hit(self, url_hash: str) -> None:
        """Increment cache hit counter"""
        await self.session.execute(
            update(CachedMedia)
            .where(CachedMedia.url_hash == url_hash)
            .values(hit_count=CachedMedia.hit_count + 1)
        )
        await self.session.commit()
    
    async def get_total_hits(self) -> int:
        """Get total cache hits across all media"""
        result = await self.session.execute(
            select(func.sum(CachedMedia.hit_count))
        )
        return result.scalar() or 0
    
    async def get_total_points_saved(self) -> int:
        """Calculate total points saved from cache hits"""
        result = await self.session.execute(
            select(func.sum(CachedMedia.hit_count * CachedMedia.points_cost))
        )
        return result.scalar() or 0


class MusicSearchCacheRepository:
    """Repository for music search cache - saves 1 point per hit"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    @staticmethod
    def get_query_hash(query: str, page: int = 1) -> str:
        """Generate hash for search query"""
        key = f"{query.lower().strip()}:{page}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]
    
    async def get_cached_results(self, query: str, page: int = 1) -> Optional[list[dict]]:
        """Get cached search results if available"""
        query_hash = self.get_query_hash(query, page)
        
        result = await self.session.execute(
            select(MusicSearchCache).where(
                MusicSearchCache.query_hash == query_hash,
                MusicSearchCache.expires_at > datetime.utcnow()
            )
        )
        cached = result.scalar_one_or_none()
        
        if cached:
            # Increment hit counter
            cached.hit_count += 1
            await self.session.commit()
            return json.loads(cached.results_json)
        
        return None
    
    async def cache_results(
        self, 
        query: str, 
        page: int, 
        results: list[dict],
        expires_hours: int = 240  # 10 kun
    ) -> MusicSearchCache:
        """Cache search results"""
        query_hash = self.get_query_hash(query, page)
        
        # Check if exists
        existing = await self.session.execute(
            select(MusicSearchCache).where(MusicSearchCache.query_hash == query_hash)
        )
        cached = existing.scalar_one_or_none()
        
        if cached:
            cached.results_json = json.dumps(results, ensure_ascii=False)
            cached.results_count = len(results)
            cached.expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            await self.session.commit()
            return cached
        
        # Create new
        cached = MusicSearchCache(
            query_hash=query_hash,
            query=query[:255],
            page=page,
            results_json=json.dumps(results, ensure_ascii=False),
            results_count=len(results),
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours)
        )
        self.session.add(cached)
        await self.session.commit()
        await self.session.refresh(cached)
        return cached
    
    async def get_total_hits(self) -> int:
        """Get total search cache hits"""
        result = await self.session.execute(
            select(func.sum(MusicSearchCache.hit_count))
        )
        return result.scalar() or 0


class YouTubeCacheRepository:
    """Repository for YouTube cache - saves 20 POINTS per hit!"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_cached(self, video_id: str, format: str) -> Optional[YouTubeCache]:
        """Get cached YouTube download"""
        result = await self.session.execute(
            select(YouTubeCache).where(
                YouTubeCache.video_id == video_id,
                YouTubeCache.format == format,
                YouTubeCache.expires_at > datetime.utcnow()
            )
        )
        cached = result.scalar_one_or_none()
        
        if cached:
            cached.hit_count += 1
            await self.session.commit()
        
        return cached
    
    async def cache_download(
        self,
        video_id: str,
        format: str,
        file_id: str,
        media_type: str,
        title: Optional[str] = None,
        duration: Optional[str] = None,
        expires_hours: int = 240  # 10 kun
    ) -> YouTubeCache:
        """Cache YouTube download"""
        # Check if exists
        existing = await self.session.execute(
            select(YouTubeCache).where(
                YouTubeCache.video_id == video_id,
                YouTubeCache.format == format
            )
        )
        cached = existing.scalar_one_or_none()
        
        if cached:
            cached.file_id = file_id
            cached.expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            await self.session.commit()
            return cached
        
        # Create new
        cached = YouTubeCache(
            video_id=video_id,
            format=format,
            file_id=file_id,
            media_type=media_type,
            title=title,
            duration=duration,
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours)
        )
        self.session.add(cached)
        await self.session.commit()
        await self.session.refresh(cached)
        return cached
    
    async def get_total_hits(self) -> int:
        """Get total YouTube cache hits"""
        result = await self.session.execute(
            select(func.sum(YouTubeCache.hit_count))
        )
        return result.scalar() or 0
    
    async def get_points_saved(self) -> int:
        """Get total points saved (20 per hit)"""
        hits = await self.get_total_hits()
        return hits * 20


class CacheStatsRepository:
    """Repository for cache statistics"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def _get_or_create_today(self) -> CacheStats:
        """Get or create today's stats record"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await self.session.execute(
            select(CacheStats).where(CacheStats.date == today)
        )
        stats = result.scalar_one_or_none()
        
        if not stats:
            stats = CacheStats(date=today)
            self.session.add(stats)
            await self.session.commit()
            await self.session.refresh(stats)
        
        return stats
    
    async def log_api_call(self, call_type: str, points: int) -> None:
        """Log an API call"""
        stats = await self._get_or_create_today()
        
        if call_type == "media":
            stats.api_calls_media += 1
        elif call_type == "music":
            stats.api_calls_music += 1
        elif call_type == "youtube":
            stats.api_calls_youtube += 1
        elif call_type == "recognize":
            stats.api_calls_recognize += 1
        
        stats.points_spent += points
        await self.session.commit()
    
    async def log_cache_hit(self, cache_type: str, points_saved: int) -> None:
        """Log a cache hit"""
        stats = await self._get_or_create_today()
        
        if cache_type == "media":
            stats.cache_hits_media += 1
        elif cache_type == "music":
            stats.cache_hits_music += 1
        elif cache_type == "youtube":
            stats.cache_hits_youtube += 1
        elif cache_type == "recognize":
            stats.cache_hits_recognize += 1
        
        stats.points_saved += points_saved
        await self.session.commit()
    
    async def get_today_stats(self) -> CacheStats:
        """Get today's statistics"""
        return await self._get_or_create_today()
    
    async def get_total_stats(self) -> dict:
        """Get totals across all time"""
        result = await self.session.execute(
            select(
                func.sum(CacheStats.api_calls_media).label("api_media"),
                func.sum(CacheStats.api_calls_music).label("api_music"),
                func.sum(CacheStats.api_calls_youtube).label("api_youtube"),
                func.sum(CacheStats.api_calls_recognize).label("api_recognize"),
                func.sum(CacheStats.cache_hits_media).label("hits_media"),
                func.sum(CacheStats.cache_hits_music).label("hits_music"),
                func.sum(CacheStats.cache_hits_youtube).label("hits_youtube"),
                func.sum(CacheStats.cache_hits_recognize).label("hits_recognize"),
                func.sum(CacheStats.points_spent).label("spent"),
                func.sum(CacheStats.points_saved).label("saved")
            )
        )
        row = result.one()
        
        return {
            "api_calls": {
                "media": row.api_media or 0,
                "music": row.api_music or 0,
                "youtube": row.api_youtube or 0,
                "recognize": row.api_recognize or 0
            },
            "cache_hits": {
                "media": row.hits_media or 0,
                "music": row.hits_music or 0,
                "youtube": row.hits_youtube or 0,
                "recognize": row.hits_recognize or 0
            },
            "points_spent": row.spent or 0,
            "points_saved": row.saved or 0
        }


class MusicRepository:
    """Repository for music recognition operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_id: int,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        track_id: Optional[str] = None,
        track_url: Optional[str] = None,
        is_success: bool = True
    ) -> MusicRecognition:
        """Create music recognition record"""
        record = MusicRecognition(
            user_id=user_id,
            title=title,
            artist=artist,
            track_id=track_id,
            track_url=track_url,
            is_success=is_success
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record


class MaxRequiredChannelsError(Exception):
    """Majburiy kanallar soni limitdan oshdi (5)."""


class ChannelRepository:
    """Repository for required channel operations"""
    
    MAX_REQUIRED_CHANNELS = 5
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_active_channels(self) -> list[RequiredChannel]:
        """Get all active required channels"""
        result = await self.session.execute(
            select(RequiredChannel).where(RequiredChannel.is_active == True)
        )
        return list(result.scalars().all())
    
    async def get_all_channels(self) -> list[RequiredChannel]:
        """Get all channels (active and inactive)"""
        result = await self.session.execute(
            select(RequiredChannel).order_by(RequiredChannel.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def count_all_channels(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(RequiredChannel))
        return int(result.scalar_one() or 0)
    
    async def get_by_telegram_chat_id(self, channel_id: int) -> Optional[RequiredChannel]:
        result = await self.session.execute(
            select(RequiredChannel).where(RequiredChannel.channel_id == channel_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_row_id(self, row_id: int) -> Optional[RequiredChannel]:
        result = await self.session.execute(select(RequiredChannel).where(RequiredChannel.id == row_id))
        return result.scalar_one_or_none()
    
    async def add_channel(
        self,
        channel_id: int,
        channel_username: str,
        channel_title: str,
        invite_link: Optional[str] = None,
    ) -> RequiredChannel:
        """Yangi majburiy kanal/guruh (maksimal 5 ta jami)."""
        existing = await self.get_by_telegram_chat_id(channel_id)
        if existing:
            existing.channel_username = channel_username
            existing.channel_title = channel_title
            if invite_link:
                existing.invite_link = invite_link
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        
        if await self.count_all_channels() >= self.MAX_REQUIRED_CHANNELS:
            raise MaxRequiredChannelsError()
        
        channel = RequiredChannel(
            channel_id=channel_id,
            channel_username=channel_username,
            channel_title=channel_title,
            invite_link=invite_link,
        )
        self.session.add(channel)
        await self.session.commit()
        await self.session.refresh(channel)
        return channel
    
    async def remove_channel_by_row_id(self, row_id: int) -> bool:
        channel = await self.get_by_row_id(row_id)
        if channel:
            await self.session.delete(channel)
            await self.session.commit()
            return True
        return False
    
    async def toggle_channel_by_row_id(self, row_id: int) -> Optional[RequiredChannel]:
        channel = await self.get_by_row_id(row_id)
        if channel:
            channel.is_active = not channel.is_active
            await self.session.commit()
            return channel
        return None


class BroadcastRepository:
    """Repository for broadcast operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_broadcast(
        self,
        admin_id: int,
        message_text: Optional[str] = None,
        photo_file_id: Optional[str] = None,
        total_users: int = 0
    ) -> BroadcastMessage:
        """Create new broadcast record"""
        broadcast = BroadcastMessage(
            admin_id=admin_id,
            message_text=message_text,
            photo_file_id=photo_file_id,
            total_users=total_users
        )
        self.session.add(broadcast)
        await self.session.commit()
        await self.session.refresh(broadcast)
        return broadcast
    
    async def update_broadcast(
        self,
        broadcast_id: int,
        sent_count: int = None,
        failed_count: int = None,
        status: str = None
    ) -> None:
        """Update broadcast progress"""
        values = {}
        if sent_count is not None:
            values["sent_count"] = sent_count
        if failed_count is not None:
            values["failed_count"] = failed_count
        if status:
            values["status"] = status
            if status == "running":
                values["started_at"] = get_uzb_time()
            elif status == "completed":
                values["completed_at"] = get_uzb_time()
        
        await self.session.execute(
            update(BroadcastMessage)
            .where(BroadcastMessage.id == broadcast_id)
            .values(**values)
        )
        await self.session.commit()
    
    async def get_last_broadcasts(self, limit: int = 10) -> list[BroadcastMessage]:
        """Get last N broadcasts"""
        result = await self.session.execute(
            select(BroadcastMessage)
            .order_by(BroadcastMessage.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class AdminRepository:
    """Repository for admin analytics"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all_user_ids(self, limit: Optional[int] = None) -> list[int]:
        """Get all user telegram IDs for broadcast"""
        query = select(User.user_id)
        if limit:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return [row[0] for row in result.all()]
    
    async def get_stats(self) -> dict:
        """Get comprehensive bot statistics"""
        # Total users
        total_users = await self.session.execute(select(func.count(User.id)))
        total_users = total_users.scalar() or 0
        
        # Active users (last 24h, 7d, 30d)
        now = get_uzb_time()
        
        active_24h = await self.session.execute(
            select(func.count(User.id)).where(User.updated_at >= now - timedelta(hours=24))
        )
        active_24h = active_24h.scalar() or 0
        
        active_7d = await self.session.execute(
            select(func.count(User.id)).where(User.updated_at >= now - timedelta(days=7))
        )
        active_7d = active_7d.scalar() or 0
        
        active_30d = await self.session.execute(
            select(func.count(User.id)).where(User.updated_at >= now - timedelta(days=30))
        )
        active_30d = active_30d.scalar() or 0
        
        # New users today, this week
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        
        new_today = await self.session.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )
        new_today = new_today.scalar() or 0
        
        new_this_week = await self.session.execute(
            select(func.count(User.id)).where(User.created_at >= week_start)
        )
        new_this_week = new_this_week.scalar() or 0
        
        # Total downloads
        total_downloads = await self.session.execute(select(func.count(Download.id)))
        total_downloads = total_downloads.scalar() or 0
        
        # Downloads today
        downloads_today = await self.session.execute(
            select(func.count(Download.id)).where(Download.created_at >= today_start)
        )
        downloads_today = downloads_today.scalar() or 0
        
        # Music recognitions
        total_shazams = await self.session.execute(select(func.count(MusicRecognition.id)))
        total_shazams = total_shazams.scalar() or 0
        
        # Total users with username
        users_with_username = await self.session.execute(
            select(func.count(User.id)).where(User.username.is_not(None))
        )
        users_with_username = users_with_username.scalar() or 0
        
        return {
            "total_users": total_users,
            "users_with_username": users_with_username,
            "active_24h": active_24h,
            "active_7d": active_7d,
            "active_30d": active_30d,
            "new_today": new_today,
            "new_this_week": new_this_week,
            "total_downloads": total_downloads,
            "downloads_today": downloads_today,
            "total_shazams": total_shazams
        }
