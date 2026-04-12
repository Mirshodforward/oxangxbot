from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, Download, MusicRecognition, CachedMedia, Platform, MediaType, get_uzb_time, RequiredChannel, BroadcastMessage


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
        expires_hours: int = 24
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


class ChannelRepository:
    """Repository for required channel operations"""
    
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
    
    async def add_channel(
        self,
        channel_id: int,
        channel_username: str,
        channel_title: str
    ) -> RequiredChannel:
        """Add new required channel"""
        channel = RequiredChannel(
            channel_id=channel_id,
            channel_username=channel_username,
            channel_title=channel_title
        )
        self.session.add(channel)
        await self.session.commit()
        await self.session.refresh(channel)
        return channel
    
    async def remove_channel(self, channel_id: int) -> bool:
        """Remove channel by ID"""
        result = await self.session.execute(
            select(RequiredChannel).where(RequiredChannel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        if channel:
            await self.session.delete(channel)
            await self.session.commit()
            return True
        return False
    
    async def toggle_channel(self, channel_id: int) -> Optional[RequiredChannel]:
        """Toggle channel active status"""
        result = await self.session.execute(
            select(RequiredChannel).where(RequiredChannel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
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
        
        return {
            "total_users": total_users,
            "active_24h": active_24h,
            "active_7d": active_7d,
            "active_30d": active_30d,
            "new_today": new_today,
            "new_this_week": new_this_week,
            "total_downloads": total_downloads,
            "downloads_today": downloads_today,
            "total_shazams": total_shazams
        }
