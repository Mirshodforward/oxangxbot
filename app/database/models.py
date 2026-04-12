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
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Cache expiration
    
    def __repr__(self):
        return f"<CachedMedia(id={self.id}, platform={self.platform})>"


class RequiredChannel(Base):
    """Required subscription channels"""
    __tablename__ = "required_channels"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    channel_username: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_title: Mapped[str] = mapped_column(String(255), nullable=False)
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
