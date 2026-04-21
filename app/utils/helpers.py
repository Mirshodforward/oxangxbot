import re
import hashlib
from typing import Optional, Tuple
from app.database.models import Platform


# Platform URL patterns
PLATFORM_PATTERNS = {
    Platform.INSTAGRAM: [
        # Stories: /stories/{user}/{id}/ yoki /stories/highlights/{id}/
        r'(?:https?://)?(?:www\.)?instagram\.com/stories/(?:highlights/)?[\w.-]+/[\w-]+/?(?:[?#][^\s]*)?',
        r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|reels|stories|tv)/[\w.-]+(?:/[\w.-]+)?/?(?:[?#][^\s]*)?',
        r'(?:https?://)?(?:www\.)?instagram\.com/[\w.]+(?:/[\w-]+)?',
        r'(?:https?://)?instagr\.am/[\w-]+',
    ],
    Platform.YOUTUBE: [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+',
        r'(?:https?://)?youtu\.be/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
        r'(?:https?://)?m\.youtube\.com/watch\?v=[\w-]+',
    ],
    Platform.TIKTOK: [
        r'(?:https?://)?(?:www\.)?tiktok\.com/@[\w.]+/video/\d+',
        r'(?:https?://)?(?:vm|vt)\.tiktok\.com/[\w]+',
        r'(?:https?://)?(?:www\.)?tiktok\.com/t/[\w]+',
    ],
    Platform.PINTEREST: [
        r'(?:https?://)?(?:www\.)?pinterest\.com/pin/\d+',
        r'(?:https?://)?pin\.it/[\w]+',
    ],
    Platform.THREADS: [
        r'(?:https?://)?(?:www\.)?threads\.net/@[\w.]+/post/[\w]+',
        r'(?:https?://)?(?:www\.)?threads\.net/t/[\w]+',
    ],
    Platform.SNAPCHAT: [
        r'(?:https?://)?(?:www\.)?snapchat\.com/spotlight/[\w]+',
        r'(?:https?://)?story\.snapchat\.com/[\w/@]+',
        r'(?:https?://)?t\.snapchat\.com/[\w]+',
    ],
    Platform.LIKEE: [
        r'(?:https?://)?(?:www\.)?likee\.video/[\w]+',
        r'(?:https?://)?l\.likee\.video/v/[\w]+',
    ],
    Platform.FACEBOOK: [
        r'(?:https?://)?(?:www\.)?facebook\.com/[\w.]+/videos/\d+',
        r'(?:https?://)?(?:www\.)?facebook\.com/watch\?v=\d+',
        r'(?:https?://)?fb\.watch/[\w]+',
        r'(?:https?://)?(?:www\.)?facebook\.com/reel/\d+',
    ],
    Platform.TWITTER: [
        r'(?:https?://)?(?:www\.)?twitter\.com/[\w]+/status/\d+',
        r'(?:https?://)?(?:www\.)?x\.com/[\w]+/status/\d+',
    ],
}


def detect_platform(url: str) -> Platform:
    """Detect platform from URL"""
    url = url.strip().lower()
    
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return platform
    
    return Platform.OTHER


def is_valid_url(text: str) -> bool:
    """Check if text is a valid URL"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ip
        r'(?::\d+)?'  # port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(text.strip()))


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text"""
    url_pattern = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )
    return url_pattern.findall(text)


def extract_instagram_media_code(url: str) -> Optional[str]:
    """
    instagram.com/reel/XX…/, /p/…, /tv/… yoki instagr.am/… dan media kodini ajratadi.
    API ba'zan \"id\": \"reel\" kabi umumiy qiymat qaytaradi — shunda URL ishonchli manba.
    """
    u = (url or "").strip()
    if not u:
        return None
    patterns = [
        r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)",
        r"instagr\.am/([A-Za-z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, u, re.IGNORECASE)
        if m:
            code = m.group(1)
            if code.lower() not in ("reels", "reel", "p", "tv", "stories", "story"):
                return code
    return None


def normalize_fetch_url(url: str) -> str:
    """
    FastSaver GET /fetch uchun to‘liq https havola.
    Ba’zan foydalanuvchi www... yoki instagram.com (skeimsiz) yuboradi.
    """
    u = (url or "").strip()
    if not u:
        return u
    low = u.lower()
    if low.startswith("www.instagram.com"):
        return "https://" + u
    if low.startswith("instagram.com/"):
        return "https://www." + u
    if low.startswith("instagr.am/") and not low.startswith("http"):
        return "https://" + u
    return u


def fetch_media_is_video(media_type: Optional[str]) -> bool:
    """API `type` — post, reel, story va hokazo."""
    t = (media_type or "").lower()
    return t in ("video", "story", "reel", "clips", "short")


def fetch_media_is_image(media_type: Optional[str]) -> bool:
    t = (media_type or "").lower()
    return t in ("image", "photo", "picture")


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def get_url_hash(url: str) -> str:
    """Generate hash for URL (used for caching)"""
    # Normalize URL
    url = url.strip().lower()
    # Remove tracking parameters
    url = re.sub(r'[?&](utm_[^&]+|ref=[^&]+)', '', url)
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS"""
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to max length"""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """Escape special markdown characters for Telegram"""
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def get_platform_emoji(platform: Platform) -> str:
    """Get emoji for platform"""
    emojis = {
        Platform.INSTAGRAM: "📸",
        Platform.YOUTUBE: "▶️",
        Platform.TIKTOK: "🎵",
        Platform.PINTEREST: "📌",
        Platform.THREADS: "🧵",
        Platform.SNAPCHAT: "👻",
        Platform.LIKEE: "❤️",
        Platform.FACEBOOK: "📘",
        Platform.TWITTER: "🐦",
        Platform.OTHER: "🔗",
    }
    return emojis.get(platform, "🔗")


def get_platform_name(platform: Platform) -> str:
    """Get display name for platform"""
    names = {
        Platform.INSTAGRAM: "Instagram",
        Platform.YOUTUBE: "YouTube",
        Platform.TIKTOK: "TikTok",
        Platform.PINTEREST: "Pinterest",
        Platform.THREADS: "Threads",
        Platform.SNAPCHAT: "Snapchat",
        Platform.LIKEE: "Likee",
        Platform.FACEBOOK: "Facebook",
        Platform.TWITTER: "Twitter",
        Platform.OTHER: "Other",
    }
    return names.get(platform, "Unknown")


async def safe_callback_answer(callback, *args, **kwargs) -> None:
    """
    Telegram callback.answer() — eski tugma, timeout yoki takroriy javobda
    «query is too old» xatosini logga chiqarmasdan yutib qo'yadi.
    """
    from aiogram.exceptions import TelegramBadRequest

    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest as e:
        msg = (getattr(e, "message", None) or str(e)).lower()
        if any(
            s in msg
            for s in (
                "query is too old",
                "query id is invalid",
                "response timeout expired",
            )
        ):
            return
        raise
