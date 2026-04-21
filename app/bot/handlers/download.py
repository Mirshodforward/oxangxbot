import asyncio
import logging
import os
import re
import shutil
import tempfile
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
    extract_urls,
    extract_youtube_video_id,
    get_url_hash,
    truncate_text,
    get_platform_emoji,
    get_platform_name,
    normalize_fetch_url,
    fetch_media_is_video,
    fetch_media_is_image,
)
from app.config import settings

logger = logging.getLogger(__name__)
router = Router(name="download")

# Telegram URLInputFile ba'zi CDN (masalan Instagram) uchun 403 beradi — serverda yuklab yuboramiz
_MAX_REMOTE_MEDIA_BYTES = 80 * 1024 * 1024

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _clean_instagram_page_url(page_url: str) -> str:
    """CDN Referer uchun — instagram.com sahifa, igsh kabi querylarni soddalashtirish."""
    u = (page_url or "").strip().split("#")[0]
    if "instagram.com" not in u.lower():
        return ""
    u = re.sub(r"([?&])igsh[a-zA-Z0-9_]*=[^&]*", "", u, flags=re.IGNORECASE)
    u = re.sub(r"\?&+", "?", u)
    u = u.rstrip("&")
    if u.endswith("?"):
        u = u[:-1]
    return u or "https://www.instagram.com/"


def _meta_cdn_url(url: str) -> bool:
    low = url.lower()
    if "dl.fastsaver" in low:
        return False
    return any(
        x in low
        for x in (
            "cdninstagram.com",
            "fbcdn.net",
            "instagram.f",
            "instagram.c",
        )
    )


def _instagram_referer_chain(page_referer: Optional[str]) -> list[str]:
    """CDN uchun Refererlar: avval to‘liq URL (igsh bilan), keyin tozalangan, keyin umumiy."""
    out: list[str] = []
    raw = (page_referer or "").strip().split("#")[0]
    if raw and "instagram.com" in raw.lower() and raw not in out:
        out.append(raw)
    clean = _clean_instagram_page_url(page_referer) if page_referer else ""
    if clean and clean not in out:
        out.append(clean)
    if clean and "?" in clean:
        base = clean.split("?", 1)[0].rstrip("/") + "/"
        if base not in out:
            out.append(base)
    generic = "https://www.instagram.com/"
    if generic not in out:
        out.append(generic)
    return out


async def _prime_instagram_cookies(
    session: aiohttp.ClientSession,
    page_referer: str,
    *,
    proxy: Optional[str],
) -> None:
    """fbcdn 403 kamaytirish: avval reel/post sahifasini ochib cookie olish (anonim)."""
    page = (page_referer or "").strip().split("#")[0]
    if not page or "instagram.com" not in page.lower():
        return
    headers = {
        "User-Agent": _CHROME_UA,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    try:
        req_kw: dict = {
            "headers": headers,
            "allow_redirects": True,
            "max_redirects": 8,
        }
        if proxy:
            req_kw["proxy"] = proxy
        async with session.get(page, **req_kw) as pr:
            await pr.read()
    except Exception as exc:
        logger.debug("Instagram cookie prime: %s", exc)


async def _fetch_url_bytes_for_upload(
    url: str,
    *,
    page_referer: Optional[str] = None,
) -> Optional[bytes]:
    """Telegram o‘rniga bot serveri orqali havoladan baytlar (Instagram CDN 403 uchun Referer)."""
    low = url.lower()
    is_meta = _meta_cdn_url(url)

    timeout = aiohttp.ClientTimeout(total=180, sock_read=120)
    proxy = settings.HTTPS_PROXY or settings.HTTP_PROXY
    try:
        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(
            timeout=timeout,
            cookie_jar=jar,
            trust_env=True,
        ) as session:
            if is_meta and page_referer and "instagram.com" in page_referer.lower():
                await _prime_instagram_cookies(session, page_referer, proxy=proxy)

            referers = (
                _instagram_referer_chain(page_referer)
                if is_meta
                else ["https://www.instagram.com/"]
            )

            for ref in referers if is_meta else [None]:
                headers: dict[str, str] = {
                    "User-Agent": _CHROME_UA,
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate",
                    "DNT": "1",
                    "Connection": "keep-alive",
                }
                if is_meta and ref:
                    dest = "video" if any(
                        x in low for x in (".mp4", "/m86/", "/m82/", "/m85/", "video", "reel")
                    ) else "image"
                    headers.update(
                        {
                            "Referer": ref,
                            "Origin": "https://www.instagram.com",
                            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                            "Sec-Ch-Ua-Mobile": "?0",
                            "Sec-Ch-Ua-Platform": '"Windows"',
                            "Sec-Fetch-Dest": dest,
                            "Sec-Fetch-Mode": "no-cors",
                            "Sec-Fetch-Site": "cross-site",
                        }
                    )
                elif "instagram" in low or "fbcdn.net" in low or "cdninstagram" in low:
                    headers["Referer"] = "https://www.instagram.com/"
                    headers["Origin"] = "https://www.instagram.com"

                get_kw: dict = {"headers": headers, "allow_redirects": True}
                if proxy:
                    get_kw["proxy"] = proxy
                async with session.get(url, **get_kw) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "Remote GET %s -> HTTP %s (Referer=%s)",
                            url[:100],
                            resp.status,
                            (ref or "-")[:80] if is_meta else "-",
                        )
                        if is_meta and resp.status == 403 and ref == referers[-1]:
                            logger.warning(
                                "Instagram CDN 403 — ko‘p hostinglar IP bloklangan. "
                                ".env da HTTPS_PROXY (rezident proxy) yoki tizim HTTPS_PROXY; "
                                "yoki FastSaver dan tunnel/proxy URL so‘rang."
                            )
                        continue
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
            return None
    except Exception as exc:
        logger.warning("Remote download error: %s", exc)
        return None


async def _fetch_instagram_via_ytdlp(page_url: str) -> Optional[bytes]:
    """
    Instagram CDN 403 bo‘lganda: `yt-dlp` orqali to‘g‘ridan-to‘g‘ri sahifa URL dan yuklash.
    Serverda: pip install yt-dlp  (PATH da yt-dlp yoki yt-dlp.exe)
    """
    exe = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if not exe:
        return None

    out_dir = tempfile.mkdtemp(prefix="ytdlp_ig_")
    try:
        out_tmpl = os.path.join(out_dir, "out.%(ext)s")
        proc = await asyncio.create_subprocess_exec(
            exe,
            "--no-warnings",
            "--no-playlist",
            "-f",
            "best[ext=mp4]/best[height<=720]/best",
            "-o",
            out_tmpl,
            page_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning("yt-dlp: vaqt tugadi (300s)")
            return None

        if proc.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace")[:500]
            logger.warning("yt-dlp chiqish %s: %s", proc.returncode, err)
            return None

        files = [
            os.path.join(out_dir, f)
            for f in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, f))
        ]
        if not files:
            return None
        fp = max(files, key=os.path.getmtime)
        sz = os.path.getsize(fp)
        if sz > _MAX_REMOTE_MEDIA_BYTES:
            logger.warning("yt-dlp: fayl juda katta (%s bayt)", sz)
            return None
        with open(fp, "rb") as fh:
            return fh.read()
    except Exception as exc:
        logger.warning("yt-dlp: %s", exc)
        return None
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


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
            if cached.media_type == MediaType.VIDEO or fetch_media_is_video(media_info.media_type):
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
        
        media_type = (
            MediaType.VIDEO if fetch_media_is_video(media_info.media_type) else MediaType.IMAGE
        )

        await bot.send_chat_action(
            message.chat.id,
            ChatAction.UPLOAD_VIDEO if fetch_media_is_video(media_info.media_type) else ChatAction.UPLOAD_PHOTO,
        )

        file_id = None
        sent_msg = None
        upload = URLInputFile(download_url)

        try:
            if fetch_media_is_video(media_info.media_type):
                sent_msg = await message.answer_video(
                    video=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.video.file_id if sent_msg.video else None
            elif fetch_media_is_image(media_info.media_type):
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
            raw = await _fetch_url_bytes_for_upload(
                download_url,
                page_referer=original_url,
            )
            if not raw and platform == Platform.INSTAGRAM:
                logger.info("CDN 403 — yt-dlp bilan qayta urinilmoqda...")
                raw = await _fetch_instagram_via_ytdlp(original_url)
            if not raw:
                raise
            if fetch_media_is_video(media_info.media_type):
                upload = BufferedInputFile(raw, filename="video.mp4")
                sent_msg = await message.answer_video(
                    video=upload,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                file_id = sent_msg.video.file_id if sent_msg.video else None
            elif fetch_media_is_image(media_info.media_type):
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
                if fetch_media_is_video(str(item_type)):
                    await message.answer_video(video=upload)
                else:
                    await message.answer_photo(photo=upload)
            except Exception as first_err:
                logger.warning(
                    "Carousel item %s URLInputFile: %s; server yuklash...",
                    i + 1,
                    first_err,
                )
                raw = await _fetch_url_bytes_for_upload(
                    item_url,
                    page_referer=original_url,
                )
                if not raw:
                    raise
                if fetch_media_is_video(str(item_type)):
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
    
    url = normalize_fetch_url(urls[0])
    platform = detect_platform(url)
    lang = normalize_language_code(db_user.language_code)

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
                if platform == Platform.INSTAGRAM:
                    await message.answer(
                        get_text("media_download_failed_ig", lang),
                        parse_mode="HTML",
                    )
                else:
                    await message.answer(get_text("download_error", lang), parse_mode="HTML")
            return
        
        # Send single media
        await status_msg.delete()
        success = await send_media_to_user(bot, message, media_info, session, db_user, url)
        
        if not success:
            if platform == Platform.INSTAGRAM:
                await message.answer(
                    get_text("media_download_failed_ig", lang),
                    parse_mode="HTML",
                )
            else:
                await message.answer(get_text("download_error", lang), parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Error handling URL: {e}")
        try:
            await status_msg.edit_text("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")
        except:
            await message.answer("❌ Xatolik yuz berdi.")


@router.callback_query(F.data.startswith("yt_dl:"))
async def youtube_download_callback(callback: CallbackQuery, bot: Bot, session: AsyncSession, db_user: User):
    """YouTube sifat tanlash — kesh; audio ~7, video ~15 kredit (API bo'yicha)."""
    await callback.answer()
    
    # Parse callback data: yt_dl:video_id:format
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.message.edit_text("❌ Noto'g'ri so'rov")
        return
    
    _, video_id, format_quality = parts
    api_credit_cost = 7 if format_quality.lower() == "mp3" else 15
    
    # Initialize repositories
    yt_cache_repo = YouTubeCacheRepository(session)
    stats_repo = CacheStatsRepository(session)
    download_repo = DownloadRepository(session)
    user_repo = UserRepository(session)
    
    # 🚀 CHECK CACHE FIRST
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
            
            await stats_repo.log_cache_hit("youtube", api_credit_cost)
            
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
            
            logger.info(
                "YouTube cache hit: video_id=%s format=%s (~%s kredit tejaldi)",
                video_id,
                format_quality,
                api_credit_cost,
            )
            return
            
        except Exception as e:
            logger.warning(f"Cached file_id expired or invalid: {e}")
            # Continue to API call if cache failed
    
    # CACHE MISS — API chaqiruvi
    await callback.message.edit_text(f"⏳ YouTube {format_quality} formatda yuklanmoqda...")
    
    try:
        # Get bot username
        bot_info = await bot.get_me()
        bot_username = f"@{bot_info.username}"
        
        result = await api.download_youtube(
            video_id=video_id,
            format=format_quality,
            bot_username=bot_username
        )
        
        await stats_repo.log_api_call("youtube", api_credit_cost)
        
        if result.error:
            await callback.message.edit_text(
                f"❌ Xatolik: {result.error_message or 'Yuklab bolmadi'}"
            )
            return
        
        caption_v = f"▶️ <b>YouTube</b> | {format_quality}"
        caption_a = "🎵 <b>YouTube</b> | MP3"
        sent_file_id: Optional[str] = None
        sent_media = result.media_type

        if result.file_id:
            try:
                if result.media_type == "video":
                    sent = await callback.message.answer_video(
                        video=result.file_id,
                        caption=caption_v,
                        parse_mode="HTML"
                    )
                    sent_file_id = sent.video.file_id if sent.video else None
                else:
                    sent = await callback.message.answer_audio(
                        audio=result.file_id,
                        caption=caption_a,
                        parse_mode="HTML"
                    )
                    sent_file_id = sent.audio.file_id if sent.audio else None
                
                await callback.message.delete()
                
                if sent_file_id:
                    await yt_cache_repo.cache_download(
                        video_id=video_id,
                        format=format_quality,
                        file_id=sent_file_id,
                        media_type=sent_media,
                        expires_hours=240
                    )
                    logger.info(f"YouTube cached: video_id={video_id}, format={format_quality}")
                
                await download_repo.create(
                    user_id=db_user.id,
                    url=f"https://youtube.com/watch?v={video_id}",
                    platform=Platform.YOUTUBE,
                    shortcode=video_id,
                    media_type=MediaType.VIDEO if sent_media == "video" else MediaType.AUDIO,
                    file_id=sent_file_id or result.file_id,
                    is_success=True
                )
                await user_repo.increment_downloads(db_user.id)
                
            except Exception as e:
                logger.error(f"Error sending YouTube file: {e}")
                await callback.message.edit_text(
                    "❌ Faylni yuborib bo'lmadi. File_id muddati tugagan bo'lishi mumkin."
                )
        elif result.download_url:
            fn = (result.filename or f"yt_{video_id}_{format_quality}.mp4").replace("\x00", "")
            if len(fn) > 180:
                fn = f"{video_id}.mp4"
            try:
                upload = URLInputFile(result.download_url, filename=fn)
                sent = await callback.message.answer_video(
                    video=upload,
                    caption=caption_v,
                    parse_mode="HTML",
                )
                sent_file_id = sent.video.file_id if sent.video else None
            except Exception as first_err:
                logger.warning(
                    "YouTube URLInputFile yuborilmadi (%s); server orqali yuklanmoqda...",
                    first_err,
                )
                raw = await _fetch_url_bytes_for_upload(result.download_url)
                if not raw:
                    await callback.message.edit_text(
                        "❌ Video havolasidan yuklab bo'lmadi."
                    )
                    return
                upload = BufferedInputFile(raw, filename=fn or "video.mp4")
                sent = await callback.message.answer_video(
                    video=upload,
                    caption=caption_v,
                    parse_mode="HTML",
                )
                sent_file_id = sent.video.file_id if sent.video else None

            await callback.message.delete()

            if sent_file_id:
                await yt_cache_repo.cache_download(
                    video_id=video_id,
                    format=format_quality,
                    file_id=sent_file_id,
                    media_type="video",
                    expires_hours=240,
                )
            await download_repo.create(
                user_id=db_user.id,
                url=f"https://youtube.com/watch?v={video_id}",
                platform=Platform.YOUTUBE,
                shortcode=video_id,
                media_type=MediaType.VIDEO,
                file_id=sent_file_id,
                is_success=True,
            )
            await user_repo.increment_downloads(db_user.id)
        else:
            await callback.message.edit_text("❌ File ID yoki yuklash havolasi topilmadi")
            
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi")
