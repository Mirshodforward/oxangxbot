import logging
from typing import Optional

import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import BufferedInputFile, Message, CallbackQuery, URLInputFile
from aiogram.enums import ChatAction
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fastsaver_api import api, MediaInfo
from app.database.models import User, Platform, MediaType
from app.database.repositories import (
    DownloadRepository, CacheRepository, UserRepository,
    YouTubeCacheRepository, CacheStatsRepository
)
from app.bot.locales import get_text, normalize_language_code
from app.bot.keyboards import get_youtube_quality_keyboard, get_download_keyboard
from app.utils.helpers import (
    detect_platform,
    is_valid_url,
    extract_urls,
    extract_youtube_video_id,
    get_url_hash,
    truncate_text,
    get_platform_emoji,
    get_platform_name
)
from app.config import settings

logger = logging.getLogger(__name__)
router = Router(name="download")

# Telegram URLInputFile ba'zi CDN (masalan Instagram) uchun 403 beradi — serverda yuklab yuboramiz
_MAX_REMOTE_MEDIA_BYTES = 80 * 1024 * 1024


async def _fetch_url_bytes_for_upload(url: str) -> Optional[bytes]:
    """Telegram o‘rniga bot serveri orqali havoladan baytlar (403 aylanishi uchun)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    low = url.lower()
    if "instagram" in low or "fbcdn.net" in low or "cdninstagram" in low:
        headers["Referer"] = "https://www.instagram.com/"
        headers["Origin"] = "https://www.instagram.com"

    timeout = aiohttp.ClientTimeout(total=180, sock_read=120)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning("Remote GET %s -> HTTP %s", url[:120], resp.status)
                    return None
                cl = resp.headers.get("Content-Length")
                if cl:
                    try:
                        if int(cl) > _MAX_REMOTE_MEDIA_BYTES:
                            logger.warning("Remote file too large (Content-Length)")
                            return None
                    except ValueError:
                        pass
                data = await resp.read()
                if len(data) > _MAX_REMOTE_MEDIA_BYTES:
                    logger.warning("Remote file too large (body)")
                    return None
                return data
    except Exception as exc:
        logger.warning("Remote download error: %s", exc)
        return None


async def send_media_to_user(
    bot: Bot,
    message: Message,
    media_info: MediaInfo,
    session: AsyncSession,
    db_user: User,
    original_url: str
) -> bool:
    """Send downloaded media to user"""
    platform = detect_platform(original_url)
    cache_repo = CacheRepository(session)
    download_repo = DownloadRepository(session)
    user_repo = UserRepository(session)
    lang = normalize_language_code(db_user.language_code)
    try:
        bot_me = await bot.get_me()
        bot_username = bot_me.username
    except Exception:
        bot_username = "Oxangxbot"
    
    caption_text = get_text("downloaded_via", lang, bot_username=bot_username)
    keyboard = get_download_keyboard(lang)
    
    url_hash = get_url_hash(original_url)
    
    # Check cache for file_id
    cached = await cache_repo.get_by_hash(url_hash)
    if cached and cached.file_id:
        try:
            # Send cached file
            if cached.media_type == MediaType.VIDEO or media_info.media_type == "video":
                await message.answer_video(
                    video=cached.file_id,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            elif cached.media_type == MediaType.IMAGE:
                await message.answer_photo(
                    photo=cached.file_id,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await message.answer_document(
                    document=cached.file_id,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
            # Log download
            await download_repo.create(
                user_id=db_user.id,
                url=original_url,
                platform=platform,
                shortcode=media_info.shortcode,
                media_type=cached.media_type,
                file_id=cached.file_id,
                is_success=True
            )
            await user_repo.increment_downloads(db_user.id)
            return True
        except Exception as e:
            logger.warning(f"Cached file_id failed: {e}")
    
    # Download and send new media
    try:
        download_url = media_info.download_url
        if not download_url:
            return False
        
        media_type = MediaType.VIDEO if media_info.media_type == "video" else MediaType.IMAGE

        await bot.send_chat_action(
            message.chat.id,
            ChatAction.UPLOAD_VIDEO if media_info.media_type == "video" else ChatAction.UPLOAD_PHOTO,
        )

        file_id = None
        sent_msg = None
        upload = URLInputFile(download_url)

        try:
            if media_info.media_type == "video":
                sent_msg = await message.answer_video(
                    video=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.video.file_id if sent_msg.video else None
            elif media_info.media_type == "image":
                sent_msg = await message.answer_photo(
                    photo=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.photo[-1].file_id if sent_msg.photo else None
            else:
                sent_msg = await message.answer_document(
                    document=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.document.file_id if sent_msg.document else None
        except Exception as first_err:
            logger.warning(
                "URLInputFile yuborish muvaffaqiyatsiz (%s); server orqali yuklab yuborilmoqda...",
                first_err,
            )
            raw = await _fetch_url_bytes_for_upload(download_url)
            if not raw:
                raise
            if media_info.media_type == "video":
                upload = BufferedInputFile(raw, filename="video.mp4")
                sent_msg = await message.answer_video(
                    video=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.video.file_id if sent_msg.video else None
            elif media_info.media_type == "image":
                upload = BufferedInputFile(raw, filename="photo.jpg")
                sent_msg = await message.answer_photo(
                    photo=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.photo[-1].file_id if sent_msg.photo else None
            else:
                upload = BufferedInputFile(raw, filename="media.bin")
                sent_msg = await message.answer_document(
                    document=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.document.file_id if sent_msg.document else None
        # Cache the file_id
        if file_id:
            await cache_repo.create_or_update(
                url_hash=url_hash,
                original_url=original_url,
                platform=platform,
                media_type=media_type,
                shortcode=media_info.shortcode,
                download_url=download_url,
                thumb_url=media_info.thumb,
                caption=media_info.caption,
                file_id=file_id
            )
        
        # Log download
        await download_repo.create(
            user_id=db_user.id,
            url=original_url,
            platform=platform,
            shortcode=media_info.shortcode,
            media_type=media_type,
            caption=media_info.caption,
            file_id=file_id,
            is_success=True
        )
        await user_repo.increment_downloads(db_user.id)
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending media: {e}")
        return False


async def send_carousel_media(
    bot: Bot,
    message: Message,
    media_info: MediaInfo,
    session: AsyncSession,
    db_user: User,
    original_url: str
) -> bool:
    """Send carousel (multiple items) to user"""
    if not media_info.items:
        return False
    
    platform = detect_platform(original_url)
    emoji = get_platform_emoji(platform)
    platform_name = get_platform_name(platform)
    
    await message.answer(f"{emoji} <b>{platform_name}</b>\n📸 {len(media_info.items)} ta media topildi...", parse_mode="HTML")
    
    download_repo = DownloadRepository(session)
    user_repo = UserRepository(session)
    
    success_count = 0
    for i, item in enumerate(media_info.items[:10]):  # Max 10 items
        try:
            await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
            
            item_url = item.get("download_url") or item.get("url")
            if not item_url:
                continue
            
            item_type = item.get("type", "image")
            upload = URLInputFile(item_url)
            try:
                if item_type == "video":
                    await message.answer_video(video=upload)
                else:
                    await message.answer_photo(photo=upload)
            except Exception as first_err:
                logger.warning(
                    "Carousel item %s URLInputFile: %s; server yuklash...",
                    i + 1,
                    first_err,
                )
                raw = await _fetch_url_bytes_for_upload(item_url)
                if not raw:
                    raise
                if item_type == "video":
                    await message.answer_video(
                        video=BufferedInputFile(raw, filename="video.mp4")
                    )
                else:
                    await message.answer_photo(
                        photo=BufferedInputFile(raw, filename="photo.jpg")
                    )

            success_count += 1

        except Exception as e:
            logger.warning(f"Failed to send carousel item {i + 1}: {e}")
    
    if success_count > 0:
        await download_repo.create(
            user_id=db_user.id,
            url=original_url,
            platform=platform,
            shortcode=media_info.shortcode,
            media_type=MediaType.CAROUSEL,
            is_success=True
        )
        await user_repo.increment_downloads(db_user.id)
        return True
    
    return False


@router.message(F.text.regexp(r'https?://'))
async def handle_url(message: Message, bot: Bot, session: AsyncSession, db_user: User):
    """Handle media URL"""
    # Extract URLs from message
    urls = extract_urls(message.text)
    if not urls:
        return
    
    url = urls[0]  # Process first URL
    platform = detect_platform(url)
    
    logger.info(f"User {db_user.id} requested: {url} (platform: {platform})")
    
    # Special handling for YouTube - show quality selection
    if platform == Platform.YOUTUBE:
        video_id = extract_youtube_video_id(url)
        if video_id:
            status_msg = await message.answer("▶️ <b>YouTube video topildi!</b>\n\nSifat tanlang:", 
                                               reply_markup=get_youtube_quality_keyboard(video_id),
                                               parse_mode="HTML")
            return
    
    # For other platforms - get info and download
    status_msg = await message.answer(f"⏳ {get_platform_emoji(platform)} Yuklanmoqda...")
    
    try:
        # Get media info from API
        media_info = await api.get_media_info(url)
        
        if media_info.error:
            await status_msg.edit_text(
                f"❌ Xatolik: {media_info.error_message or 'Media topilmadi'}"
            )
            return
        
        # Handle carousel (multiple items)
        if media_info.media_type == "carousel" or media_info.items:
            await status_msg.delete()
            success = await send_carousel_media(bot, message, media_info, session, db_user, url)
            if not success:
                await message.answer("❌ Media yuklab bo'lmadi.")
            return
        
        # Send single media
        await status_msg.delete()
        success = await send_media_to_user(bot, message, media_info, session, db_user, url)
        
        if not success:
            await message.answer("❌ Media yuklab bo'lmadi. Keyinroq urinib ko'ring.")
            
    except Exception as e:
        logger.error(f"Error handling URL: {e}")
        try:
            await status_msg.edit_text("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")
        except:
            await message.answer("❌ Xatolik yuz berdi.")


@router.callback_query(F.data.startswith("yt_dl:"))
async def youtube_download_callback(callback: CallbackQuery, bot: Bot, session: AsyncSession, db_user: User):
    """Handle YouTube download with quality selection - with caching (saves 20 points!)"""
    await callback.answer()
    
    # Parse callback data: yt_dl:video_id:format
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.message.edit_text("❌ Noto'g'ri so'rov")
        return
    
    _, video_id, format_quality = parts
    
    # Initialize repositories
    yt_cache_repo = YouTubeCacheRepository(session)
    stats_repo = CacheStatsRepository(session)
    download_repo = DownloadRepository(session)
    user_repo = UserRepository(session)
    
    # 🚀 CHECK CACHE FIRST - saves 20 points!
    cached = await yt_cache_repo.get_cached(video_id, format_quality)
    
    if cached:
        # CACHE HIT! Send from cache
        try:
            if cached.media_type == "video":
                await callback.message.answer_video(
                    video=cached.file_id,
                    caption=f"▶️ <b>YouTube</b> | {format_quality}\n⚡ <i>Keshdan yuklandi</i>",
                    parse_mode="HTML"
                )
            else:
                await callback.message.answer_audio(
                    audio=cached.file_id,
                    caption=f"🎵 <b>YouTube</b> | MP3\n⚡ <i>Keshdan yuklandi</i>",
                    parse_mode="HTML"
                )
            
            await callback.message.delete()
            
            # Log cache hit - we saved 20 points!
            await stats_repo.log_cache_hit("youtube", 20)
            
            await download_repo.create(
                user_id=db_user.id,
                url=f"https://youtube.com/watch?v={video_id}",
                platform=Platform.YOUTUBE,
                shortcode=video_id,
                media_type=MediaType.VIDEO if cached.media_type == "video" else MediaType.AUDIO,
                file_id=cached.file_id,
                is_success=True
            )
            await user_repo.increment_downloads(db_user.id)
            
            logger.info(f"YouTube cache hit! video_id={video_id}, format={format_quality}, 20 points saved!")
            return
            
        except Exception as e:
            logger.warning(f"Cached file_id expired or invalid: {e}")
            # Continue to API call if cache failed
    
    # CACHE MISS - need to call API (costs 20 points)
    await callback.message.edit_text(f"⏳ YouTube {format_quality} formatda yuklanmoqda...")
    
    try:
        # Get bot username
        bot_info = await bot.get_me()
        bot_username = f"@{bot_info.username}"
        
        # Download from API - costs 20 points
        result = await api.download_youtube(
            video_id=video_id,
            format=format_quality,
            bot_username=bot_username
        )
        
        # Log API call
        await stats_repo.log_api_call("youtube", 20)
        
        if result.error:
            await callback.message.edit_text(
                f"❌ Xatolik: {result.error_message or 'Yuklab bolmadi'}"
            )
            return
        
        # Send using file_id
        if result.file_id:
            try:
                if result.media_type == "video":
                    await callback.message.answer_video(
                        video=result.file_id,
                        caption=f"▶️ <b>YouTube</b> | {format_quality}",
                        parse_mode="HTML"
                    )
                else:
                    await callback.message.answer_audio(
                        audio=result.file_id,
                        caption=f"🎵 <b>YouTube</b> | MP3",
                        parse_mode="HTML"
                    )
                
                await callback.message.delete()
                
                # 💾 CACHE THE RESULT for future requests!
                await yt_cache_repo.cache_download(
                    video_id=video_id,
                    format=format_quality,
                    file_id=result.file_id,
                    media_type=result.media_type,
                    expires_hours=240  # Cache for 10 days
                )
                logger.info(f"YouTube cached: video_id={video_id}, format={format_quality}")
                
                await download_repo.create(
                    user_id=db_user.id,
                    url=f"https://youtube.com/watch?v={video_id}",
                    platform=Platform.YOUTUBE,
                    shortcode=video_id,
                    media_type=MediaType.VIDEO if result.media_type == "video" else MediaType.AUDIO,
                    file_id=result.file_id,
                    is_success=True
                )
                await user_repo.increment_downloads(db_user.id)
                
            except Exception as e:
                logger.error(f"Error sending YouTube file: {e}")
                await callback.message.edit_text(
                    "❌ Faylni yuborib bo'lmadi. File_id muddati tugagan bo'lishi mumkin."
                )
        else:
            await callback.message.edit_text("❌ File ID topilmadi")
            
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi")
