import logging
import os
import re
import tempfile
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fastsaver_api import api, MusicSearchResult
from app.database.models import User, Platform, MediaType
from app.database.repositories import (
    MusicRepository,
    MusicSearchCacheRepository,
    CacheStatsRepository,
    YouTubeCacheRepository,
    DownloadRepository,
    UserRepository,
)
from app.bot.keyboards import (
    get_main_menu_keyboard,
    get_music_results_keyboard,
    get_top_music_keyboard,
    get_recognized_music_keyboard,
    get_youtube_quality_keyboard,
)
from app.bot.locales import get_text, normalize_language_code
from app.utils.helpers import truncate_text

logger = logging.getLogger(__name__)
router = Router(name="music")


def _shazam_upload_suffix(message: Message, telegram_file_path: Optional[str]) -> str:
    """
    Telegram getFile path ba'zan kengaytmasiz (.dat) — Shazam esa mp4/m4a kabi tur kutadi.
    mime_type bo'yicha to'g'ri kengaytma tanlanadi.
    """
    path_ext = (os.path.splitext(telegram_file_path or "")[1] or "").lower()
    if path_ext and path_ext != ".dat":
        return path_ext

    mime = ""
    if message.video and message.video.mime_type:
        mime = message.video.mime_type.lower()
    elif message.document and message.document.mime_type:
        mime = message.document.mime_type.lower()
    elif message.video_note and getattr(message.video_note, "mime_type", None):
        mime = str(message.video_note.mime_type).lower()
    elif message.audio and message.audio.mime_type:
        mime = message.audio.mime_type.lower()

    mime_map = {
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/ogg": ".ogg",
        "audio/opus": ".ogg",
    }
    if mime in mime_map:
        return mime_map[mime]
    if mime.startswith("video/"):
        return ".mp4"
    if mime.startswith("audio/"):
        return ".mp3"
    if message.video or message.video_note:
        return ".mp4"
    if message.audio or message.voice:
        return ".ogg"
    return ".mp4"


def _looks_like_youtube_video_id(vid: str) -> bool:
    s = (vid or "").strip()
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]{11}", s))


def _first_youtube_id_from_results(musics: list[MusicSearchResult]) -> Optional[str]:
    for m in musics:
        if _looks_like_youtube_video_id(m.shortcode):
            return m.shortcode.strip()
    return None


async def _try_auto_mp3_after_shazam(
    bot: Bot,
    message: Message,
    session: AsyncSession,
    db_user: User,
    video_id: str,
) -> None:
    """Shazam / qidiruv natijasidagi YouTube video uchun MP3 (tg-bot file_id), kesh bilan."""
    if not _looks_like_youtube_video_id(video_id):
        return
    try:
        bot_me = await bot.get_me()
        bot_username = f"@{bot_me.username}"
    except Exception:
        return

    yt_cache = YouTubeCacheRepository(session)
    stats_repo = CacheStatsRepository(session)
    download_repo = DownloadRepository(session)
    user_repo = UserRepository(session)
    api_cost = 7

    cached = await yt_cache.get_cached(video_id, "mp3")
    if cached and cached.file_id:
        try:
            await stats_repo.log_cache_hit("youtube", api_cost)
            await message.answer_audio(
                audio=cached.file_id,
                caption=(
                    "🎵 <b>MP3</b> <i>(kesh)</i>\n"
                    "Shazam / YouTube natijasidagi 1-top"
                ),
                parse_mode="HTML",
            )
            await download_repo.create(
                user_id=db_user.id,
                url=f"https://youtube.com/watch?v={video_id}",
                platform=Platform.YOUTUBE,
                shortcode=video_id,
                media_type=MediaType.AUDIO,
                file_id=cached.file_id,
                is_success=True,
            )
            await user_repo.increment_downloads(db_user.id)
        except Exception as exc:
            logger.warning("Shazam auto MP3 (kesh): %s", exc)
        return

    try:
        result = await api.download_youtube(video_id, "mp3", bot_username)
        await stats_repo.log_api_call("youtube", api_cost)
    except Exception as exc:
        logger.warning("Shazam auto MP3 API: %s", exc)
        return

    if result.error or not result.file_id:
        return

    try:
        sent = await message.answer_audio(
            audio=result.file_id,
            caption=(
                "🎵 <b>MP3</b>\n"
                "Shazam / YouTube natijasidagi 1-top"
            ),
            parse_mode="HTML",
        )
        sent_fid = sent.audio.file_id if sent and sent.audio else result.file_id
        await yt_cache.cache_download(
            video_id=video_id,
            format="mp3",
            file_id=sent_fid or result.file_id,
            media_type="audio",
            expires_hours=240,
        )
        await download_repo.create(
            user_id=db_user.id,
            url=f"https://youtube.com/watch?v={video_id}",
            platform=Platform.YOUTUBE,
            shortcode=video_id,
            media_type=MediaType.AUDIO,
            file_id=sent_fid or result.file_id,
            is_success=True,
        )
        await user_repo.increment_downloads(db_user.id)
    except Exception as exc:
        logger.warning("Shazam auto MP3 yuborish: %s", exc)


class MusicStates(StatesGroup):
    """FSM states for music features"""
    waiting_for_audio = State()
    waiting_for_search_query = State()


def _normalize_search_query(raw: str) -> str:
    s = (raw or "").strip()
    return re.sub(r"\s+", " ", s)


def _parse_shazam_id(raw: str) -> str:
    """Shazam track ID yoki shazam.com/track/... havolasidan ID."""
    s = (raw or "").strip()
    if s.lower().startswith("shazam:"):
        return s.split(":", 1)[1].strip()
    m = re.search(r"shazam\.com/track/(\d+)", s, re.IGNORECASE)
    if m:
        return m.group(1)
    return s


def _cached_rows_to_results(rows: list[dict]) -> list[MusicSearchResult]:
    return [
        MusicSearchResult(
            title=d.get("title", "") or "",
            shortcode=d.get("shortcode", "") or "",
            duration=d.get("duration", "") or "",
            thumb=d.get("thumb", "") or "",
            thumb_best=d.get("thumb_best"),
        )
        for d in rows
    ]


# ==================== SHAZAM ====================

@router.message(Command("shazam"))
async def cmd_shazam(message: Message, state: FSMContext, db_user: User):
    """Start Shazam recognition flow - /shazam"""
    lang = normalize_language_code(db_user.language_code)
    await state.set_state(MusicStates.waiting_for_audio)
    
    await message.answer(
        get_text("shazam_send_audio", lang),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode="HTML"
    )


@router.message(MusicStates.waiting_for_audio, F.voice)
async def recognize_voice(message: Message, bot: Bot, state: FSMContext, session: AsyncSession, db_user: User):
    """Recognize music from voice message"""
    await state.clear()
    await _recognize_from_file(message, bot, session, db_user)


@router.message(MusicStates.waiting_for_audio, F.audio)
async def recognize_audio(message: Message, bot: Bot, state: FSMContext, session: AsyncSession, db_user: User):
    """Recognize music from audio file"""
    await state.clear()
    await _recognize_from_file(message, bot, session, db_user)


@router.message(MusicStates.waiting_for_audio, F.video)
async def recognize_video(message: Message, bot: Bot, state: FSMContext, session: AsyncSession, db_user: User):
    """Recognize music from video"""
    await state.clear()
    await _recognize_from_file(message, bot, session, db_user)


@router.message(MusicStates.waiting_for_audio, F.video_note)
async def recognize_video_note(message: Message, bot: Bot, state: FSMContext, session: AsyncSession, db_user: User):
    """Recognize music from video note (round video)"""
    await state.clear()
    await _recognize_from_file(message, bot, session, db_user)


@router.callback_query(F.data == "shazam_this")
async def callback_shazam_this(callback: CallbackQuery, bot: Bot, session: AsyncSession, db_user: User):
    """Recognize music from downloaded media inline button"""
    lang = normalize_language_code(db_user.language_code)
    await callback.answer(get_text("shazam_analyzing", lang))
    await _recognize_from_file(callback.message, bot, session, db_user)


async def _recognize_from_file(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    db_user: User
):
    """Common function to recognize music from any file type"""
    lang = normalize_language_code(db_user.language_code)
    
    # Get file_id based on message type
    if message.voice:
        file_id = message.voice.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    else:
        await message.answer(get_text("error", lang), reply_markup=get_main_menu_keyboard(lang))
        return
    
    status_msg = await message.answer(
        get_text("shazam_analyzing", lang)
    )
    
    try:
        tg_file = await bot.get_file(file_id)
        suffix = _shazam_upload_suffix(message, tg_file.file_path)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await bot.download_file(tg_file.file_path, tmp_path)
            result = await api.recognize_music_file(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if result.error:
            await status_msg.edit_text(get_text("shazam_not_found", lang))
            return
        
        # Save to database
        music_repo = MusicRepository(session)
        await music_repo.create(
            user_id=db_user.id,
            title=result.title,
            artist=result.artist,
            track_id=result.track_id,
            track_url=result.track_url,
            is_success=True
        )

        musics: list[MusicSearchResult] = list(result.musics or [])
        if not musics and (result.title or result.artist):
            fb_q = _normalize_search_query(
                f"{result.artist or ''} {result.title or ''}".strip()
            )
            if len(fb_q) >= 2:
                stats_repo = CacheStatsRepository(session)
                ok, found, _ = await api.search_music(fb_q, page=1)
                await stats_repo.log_api_call("music", 1)
                if ok and found:
                    musics = found[:5]

        # Format response
        text = f"""🎵 <b>{get_text("download_success", lang)}</b>

🎤 <b>Artist:</b> {result.artist or 'Unknown'}
🎶 <b>Track:</b> {result.title or 'Unknown'}
"""
        if musics and not (result.musics or []):
            text += "\n🔎 <i>YouTube qidiruv orqali variantlar</i>"

        keyboard = None
        if musics or result.track_id:
            keyboard = get_recognized_music_keyboard(musics, result.track_id)

        await status_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

        primary_vid = _first_youtube_id_from_results(musics)
        if primary_vid:
            await _try_auto_mp3_after_shazam(bot, message, session, db_user, primary_vid)
        
    except Exception as e:
        logger.error(f"Error recognizing music: {e}")
        await status_msg.edit_text(get_text("error", lang))


# ==================== MUSIC SEARCH ====================

@router.message(Command("search", "s"))
async def cmd_search(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
):
    """Musiqa qidiruv — /search yoki /s [so'z]"""
    lang = normalize_language_code(db_user.language_code)

    if command.args:
        await state.clear()
    
    if not command.args:
        # No query provided, ask for it
        await state.set_state(MusicStates.waiting_for_search_query)
        await message.answer(
            get_text("search_enter_query", lang),
            reply_markup=get_main_menu_keyboard(lang),
            parse_mode="HTML"
        )
        return
    
    query = _normalize_search_query(command.args)
    await _search_music(message, query, session, db_user, page=1)


@router.message(MusicStates.waiting_for_search_query, F.text)
async def process_search_query(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
):
    """Process music search query from state (bekor: /cancel — common handler)."""
    raw = (message.text or "").strip()
    if raw.startswith("/"):
        return

    await state.clear()

    query = _normalize_search_query(message.text)
    await _search_music(message, query, session, db_user, page=1)


async def _search_music(
    message: Message,
    query: str,
    session: AsyncSession,
    db_user: User,
    page: int = 1,
):
    """Musiqa qidiruvi — GET /youtube/search (query, page 1–3), kesh."""
    query = _normalize_search_query(query)
    lang = normalize_language_code(db_user.language_code)

    if len(query) < 2:
        await message.answer(
            get_text("search_no_results", lang),
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    # Initialize repositories
    cache_repo = MusicSearchCacheRepository(session)
    stats_repo = CacheStatsRepository(session)
    
    status_msg = await message.answer(
        get_text("downloading", lang)
    )
    
    try:
        # 🚀 CHECK CACHE FIRST - saves 1 point per hit
        cached_raw = await cache_repo.get_cached_results(query, page)

        if cached_raw:
            await stats_repo.log_cache_hit("music", 1)
            logger.info(f"Music search cache hit: query='{query}', page={page}")

            cached_results = _cached_rows_to_results(cached_raw)
            keyboard = get_music_results_keyboard(cached_results, page=page, query=query)
            text = f"""🔍 <b>{get_text("search_results", lang)}</b> "{query}"

📄 Page: {page}
⚡ <i>Keshdan yuklandi</i>
"""
            await status_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            return
        
        # CACHE MISS - call API (costs 1 point)
        success, results, error = await api.search_music(query, page=page)
        
        # Log API call
        await stats_repo.log_api_call("music", 1)
        
        if not success or not results:
            await status_msg.edit_text(get_text("search_no_results", lang))
            return
        
        # 💾 CACHE THE RESULTS
        results_for_cache = [
            {
                "title": r.title,
                "shortcode": r.shortcode,
                "duration": r.duration,
                "thumb": r.thumb,
                "thumb_best": r.thumb_best
            }
            for r in results
        ]
        await cache_repo.cache_results(query, page, results_for_cache)  # 10 kun default
        
        keyboard = get_music_results_keyboard(results, page=page, query=query)
        
        text = f"""🔍 <b>{get_text("search_results", lang)}</b> "{query}"

📄 Page: {page}
"""
        await status_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Music search error: {e}")
        await status_msg.edit_text(get_text("error", lang))


@router.callback_query(F.data.startswith("music_page:"))
async def music_search_pagination(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
):
    """Handle music search pagination - WITH CACHING"""
    await callback.answer()
    lang = normalize_language_code(db_user.language_code)
    
    # Parse: music_page:page:query
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        return
    
    _, page_str, query = parts
    try:
        page = max(1, min(3, int(page_str)))
    except (TypeError, ValueError):
        page = 1
    query = _normalize_search_query(query)

    cache_repo = MusicSearchCacheRepository(session)
    stats_repo = CacheStatsRepository(session)

    try:
        cached_raw = await cache_repo.get_cached_results(query, page)

        if cached_raw:
            await stats_repo.log_cache_hit("music", 1)

            cached_results = _cached_rows_to_results(cached_raw)
            keyboard = get_music_results_keyboard(cached_results, page=page, query=query)
            text = f"""🔍 <b>{get_text("search_results", lang)}</b> "{query}"

📄 Page: {page}
⚡ <i>Keshdan</i>
"""
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            return
        
        # CACHE MISS - call API
        success, results, error = await api.search_music(query, page=page)
        await stats_repo.log_api_call("music", 1)
        
        if not success or not results:
            await callback.message.edit_text(get_text("search_no_results", lang))
            return
        
        # Cache results
        results_for_cache = [
            {
                "title": r.title,
                "shortcode": r.shortcode,
                "duration": r.duration,
                "thumb": r.thumb,
                "thumb_best": r.thumb_best
            }
            for r in results
        ]
        await cache_repo.cache_results(query, page, results_for_cache)  # 10 kun default
        
        keyboard = get_music_results_keyboard(results, page=page, query=query)
        
        text = f"""🔍 <b>{get_text("search_results", lang)}</b> "{query}"

📄 Page: {page}
"""
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Pagination error: {e}")


# ==================== TOP MUSICS ====================

@router.message(Command("top"))
async def cmd_top(message: Message, command: CommandObject, db_user: User):
    """Top musiqalar — /top (dunyo chart); ixtiyoriy: /top UZ|RU|US|GB|TR|world"""
    country = "world"
    if command.args:
        c = command.args.strip().upper()
        if c == "WORLD":
            country = "world"
        elif c in ("UZ", "RU", "US", "GB", "TR"):
            country = c

    await _show_top_musics(message, country, db_user, page=1)


async def _show_top_musics(message: Message, country: str, db_user: User, page: int = 1):
    """Common function to show top musics"""
    lang = normalize_language_code(db_user.language_code)
    
    status_msg = await message.answer(
        get_text("downloading", lang)
    )
    
    try:
        success, musics, error = await api.get_top_musics(country=country, page=page)
        
        if not success or not musics:
            await status_msg.edit_text(get_text("search_no_results", lang))
            return
        
        keyboard = get_top_music_keyboard(musics, page=page, country=country)
        
        country_names = {
            "world": "🌍 World",
            "UZ": "🇺🇿 Uzbekistan",
            "RU": "🇷🇺 Russia",
            "US": "🇺🇸 USA",
            "GB": "🇬🇧 UK",
            "TR": "🇹🇷 Turkey"
        }
        
        text = f"""🔝 <b>Top Music</b> - {country_names.get(country, country)}

📄 Page: {page}
"""
        await status_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Top musics error: {e}")
        await status_msg.edit_text(get_text("error", lang))


@router.callback_query(F.data.startswith("top_country:"))
async def top_musics_by_country(callback: CallbackQuery, db_user: User):
    """Show top musics by country"""
    await callback.answer()
    lang = normalize_language_code(db_user.language_code)
    
    country = callback.data.split(":")[1]
    
    await callback.message.edit_text(get_text("downloading", lang))
    
    try:
        success, musics, error = await api.get_top_musics(country=country, page=1)
        
        if not success or not musics:
            await callback.message.edit_text(get_text("search_no_results", lang))
            return
        
        keyboard = get_top_music_keyboard(musics, page=1, country=country)
        
        country_names = {
            "world": "🌍 World",
            "UZ": "🇺🇿 Uzbekistan",
            "RU": "🇷🇺 Russia",
            "US": "🇺🇸 USA",
            "GB": "🇬🇧 UK",
            "TR": "🇹🇷 Turkey"
        }
        
        text = f"""🔝 <b>Top Music</b> - {country_names.get(country, country)}

📄 Page: 1
"""
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Top musics error: {e}")
        await callback.message.edit_text(get_text("error", lang))


@router.callback_query(F.data.startswith("top_page:"))
async def top_musics_pagination(callback: CallbackQuery, db_user: User):
    """Handle top musics pagination"""
    await callback.answer()
    lang = normalize_language_code(db_user.language_code)
    
    # Parse: top_page:page:country
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    
    _, page_str, country = parts
    page = int(page_str)
    
    try:
        success, musics, error = await api.get_top_musics(country=country, page=page)
        
        if not success or not musics:
            await callback.message.edit_text(get_text("search_no_results", lang))
            return
        
        keyboard = get_top_music_keyboard(musics, page=page, country=country)
        
        country_names = {
            "world": "🌍 World",
            "UZ": "🇺🇿 Uzbekistan",
            "RU": "🇷🇺 Russia",
            "US": "🇺🇸 USA",
            "GB": "🇬🇧 UK",
            "TR": "🇹🇷 Turkey"
        }
        
        text = f"""🔝 <b>Top Music</b> - {country_names.get(country, country)}

📄 Page: {page}
"""
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Pagination error: {e}")


# ==================== DOWNLOAD MUSIC ====================

@router.callback_query(F.data.startswith("music:"))
async def download_music(callback: CallbackQuery, db_user: User):
    """Show YouTube download options for selected music"""
    await callback.answer()
    lang = normalize_language_code(db_user.language_code)
    
    shortcode = callback.data.split(":")[1]
    
    text = f"""🎵 <b>{get_text("choose_quality", lang)}</b>
"""
    keyboard = get_youtube_quality_keyboard(shortcode)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ==================== LYRICS ====================

@router.message(Command("lyrics"))
async def cmd_lyrics(message: Message, command: CommandObject, db_user: User):
    """Get lyrics — /lyrics <shazam_id yoki shazam.com/track/...>"""
    if not command.args:
        await message.answer(
            "Foydalanish: /lyrics <shazam_id>\n\nMisol: /lyrics 316840701\nyoki Shazam havolasi.",
            parse_mode="HTML"
        )
        return
    
    shazam_id = _parse_shazam_id(command.args)
    await _get_lyrics(message, shazam_id, db_user)


@router.callback_query(F.data.startswith("lyrics:"))
async def callback_lyrics(callback: CallbackQuery, db_user: User):
    """Get and show lyrics from callback"""
    await callback.answer(get_text("downloading", normalize_language_code(db_user.language_code)))
    
    shazam_id = callback.data.split(":", 1)[1].strip()
    await _get_lyrics(callback.message, shazam_id, db_user, edit=False)


async def _get_lyrics(message: Message, shazam_id: str, db_user: User, edit: bool = False):
    """GET /shazam/lyrics — shazam_id."""
    lang = normalize_language_code(db_user.language_code)
    
    try:
        if not shazam_id:
            await message.answer(get_text("search_no_results", lang))
            return
        success, lyrics, error = await api.get_music_lyrics(shazam_id)
        
        if not success or not lyrics:
            text = get_text("search_no_results", lang)
            if edit:
                await message.edit_text(text)
            else:
                await message.answer(text)
            return
        
        # Format lyrics
        lyrics_text = f"📝 <b>Lyrics:</b>\n\n{lyrics}"
        
        # Split if too long (Telegram limit is 4096)
        if len(lyrics_text) > 4000:
            parts = [lyrics_text[i:i+4000] for i in range(0, len(lyrics_text), 4000)]
            for part in parts:
                await message.answer(part, parse_mode="HTML")
        else:
            await message.answer(lyrics_text, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Lyrics error: {e}")
        await message.answer(get_text("error", lang))


