from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime, Boolean, Text, Integer, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database.connection import Base

def get_uzb_time():
    """Get current time in Uzbekistan Timezone (UTC +5) without tzinfo for DB compatibility"""
    return (datetime.now(timezone.utc) + timedelta(hours=5)).replace(tzinfo=None)


class MediaType(enum.Enum):
    """Media type enum"""
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    CAROUSEL = "carousel"


class Platform(enum.Enum):
    """Supported platforms"""
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    PINTEREST = "pinterest"
    THREADS = "threads"
    SNAPCHAT = "snapchat"
    LIKEE = "likee"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    OTHER = "other"


class User(Base):
    """User model"""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)  # Telegram user ID
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="uz")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_uzb_time)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_uzb_time, onupdate=get_uzb_time)
    
    # Relationships
    downloads: Mapped[list["Download"]] = relationship(back_populates="user", lazy="selectin")
    
    def __repr__(self):
        return f"<User(id={self.id}, user_id={self.user_id}, username={self.username})>"


class Download(Base):
    """Download history model"""
    __tablename__ = "downloads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    
    url: Mapped[str] = mapped_column(Text)
    shortcode: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), default=Platform.OTHER)
    media_type: Mapped[Optional[MediaType]] = mapped_column(Enum(MediaType), nullable=True)
    
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Telegram file_id for caching
    
    is_success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="downloads")
    
    def __repr__(self):
        return f"<Download(id={self.id}, platform={self.platform}, user_id={self.user_id})>"


class MusicRecognition(Base):
    """Music recognition history model"""
    __tablename__ = "music_recognitions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    artist: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    track_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    track_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    is_success: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<MusicRecognition(id={self.id}, title={self.title}, artist={self.artist})>"


class CachedMedia(Base):
    """Cached media model for avoiding duplicate API calls"""
    __tablename__ = "cached_media"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # Hash of original URL
    original_url: Mapped[str] = mapped_column(Text)
    
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    media_type: Mapped[Optional[MediaType]] = mapped_column(Enum(MediaType), nullable=True)
    shortcode: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    download_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumb_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    file_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Telegram file_id
    file_id_audio: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Audio file_id
    
    # Point tejash statistikasi
    hit_count: Mapped[int] = mapped_column(Integer, default=0)  # Necha marta keshdan foydalanildi
    points_cost: Mapped[int] = mapped_column(Integer, default=1)  # API so'rov narxi (point)
    api_response_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # To'liq API javobi
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Cache expiration
    
    def __repr__(self):
        return f"<CachedMedia(id={self.id}, platform={self.platform}, hits={self.hit_count})>"


class MusicSearchCache(Base):
    """Cached music search results to save API points"""
    __tablename__ = "music_search_cache"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)  # Hash of search query
    query: Mapped[str] = mapped_column(String(255))  # Original search query
    page: Mapped[int] = mapped_column(Integer, default=1)
    
    results_json: Mapped[str] = mapped_column(Text)  # JSON array of results
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    
    hit_count: Mapped[int] = mapped_column(Integer, default=0)  # Cache hit counter
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    
    def __repr__(self):
        return f"<MusicSearchCache(query={self.query}, hits={self.hit_count})>"


class YouTubeCache(Base):
    """Cached YouTube downloads - saves 20 points per hit!"""
    __tablename__ = "youtube_cache"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(20), index=True)
    format: Mapped[str] = mapped_column(String(10))  # 720p, mp3, etc.
    
    file_id: Mapped[str] = mapped_column(String(500))  # Telegram file_id
    media_type: Mapped[str] = mapped_column(String(20))  # video, audio
    
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    
    def __repr__(self):
        return f"<YouTubeCache(video_id={self.video_id}, format={self.format}, hits={self.hit_count})>"


class CacheStats(Base):
    """Daily cache statistics for monitoring point savings"""
    __tablename__ = "cache_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime, unique=True, index=True)
    
    # API so'rovlar
    api_calls_media: Mapped[int] = mapped_column(Integer, default=0)  # get-info
    api_calls_music: Mapped[int] = mapped_column(Integer, default=0)  # search-music
    api_calls_youtube: Mapped[int] = mapped_column(Integer, default=0)  # download (20 points!)
    api_calls_recognize: Mapped[int] = mapped_column(Integer, default=0)  # recognize (5 points)
    
    # Cache hits (tejalgan so'rovlar)
    cache_hits_media: Mapped[int] = mapped_column(Integer, default=0)
    cache_hits_music: Mapped[int] = mapped_column(Integer, default=0)
    cache_hits_youtube: Mapped[int] = mapped_column(Integer, default=0)
    cache_hits_recognize: Mapped[int] = mapped_column(Integer, default=0)
    
    # Tejalgan pointlar
    points_spent: Mapped[int] = mapped_column(Integer, default=0)
    points_saved: Mapped[int] = mapped_column(Integer, default=0)
    
    def __repr__(self):
        return f"<CacheStats(date={self.date}, saved={self.points_saved})>"


class RequiredChannel(Base):
    """Required subscription channels"""
    __tablename__ = "required_channels"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    channel_username: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_title: Mapped[str] = mapped_column(String(255), nullable=False)
    invite_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_uzb_time)
    
    def __repr__(self):
        return f"<RequiredChannel(id={self.id}, username={self.channel_username})>"


class BroadcastMessage(Base):
    """Broadcast message tracking"""
    __tablename__ = "broadcast_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, cancelled
    
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_uzb_time)
    
    def __repr__(self):
        return f"<BroadcastMessage(id={self.id}, status={self.status})>"
