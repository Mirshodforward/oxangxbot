import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.fastsaver_api import api
from app.database.models import User
from app.database.repositories import MusicRepository, MusicSearchCacheRepository, CacheStatsRepository
from app.bot.keyboards import (
    get_main_menu_keyboard,
    get_cancel_keyboard,
    get_music_results_keyboard,
    get_top_music_keyboard,
    get_recognized_music_keyboard,
    get_country_selection_keyboard,
    get_youtube_quality_keyboard
)
from app.bot.locales import (
    get_text, LANG_UZ, LANG_UZ_CYRL, LANG_RU, LANG_EN, normalize_language_code
)
from app.utils.helpers import truncate_text

logger = logging.getLogger(__name__)
router = Router(name="music")


class MusicStates(StatesGroup):
    """FSM states for music features"""
    waiting_for_audio = State()
    waiting_for_search_query = State()


# ==================== SHAZAM ====================

@router.message(Command("shazam"))
@router.message(F.text.in_({get_text("btn_shazam", LANG_UZ),
                            get_text("btn_shazam", LANG_UZ_CYRL),
                            get_text("btn_shazam", LANG_RU),
                            get_text("btn_shazam", LANG_EN)}))
async def cmd_shazam(message: Message, state: FSMContext, db_user: User):
    """Start Shazam recognition flow - /shazam"""
    lang = normalize_language_code(db_user.language_code)
    await state.set_state(MusicStates.waiting_for_audio)
    
    await message.answer(
        get_text("shazam_send_audio", lang),
        reply_markup=get_cancel_keyboard(lang),
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
        # Get file URL from Telegram
        file = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        
        # Recognize music via API
        result = await api.recognize_music(file_url)
        
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
        
        # Format response
        text = f"""🎵 <b>{get_text("download_success", lang)}</b>

🎤 <b>Artist:</b> {result.artist or 'Unknown'}
🎶 <b>Track:</b> {result.title or 'Unknown'}
"""
        
        # Add keyboard with download options
        keyboard = None
        if result.musics:
            keyboard = get_recognized_music_keyboard(result.musics, result.track_url)
        
        await status_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error recognizing music: {e}")
        await status_msg.edit_text(get_text("error", lang))


# ==================== MUSIC SEARCH ====================

@router.message(Command("search", "s"))
async def cmd_search(message: Message, command: CommandObject, state: FSMContext, session: AsyncSession, db_user: User):
    """Search music - /search <query> or /s <query>"""
    lang = normalize_language_code(db_user.language_code)
    
    if not command.args:
        # No query provided, ask for it
        await state.set_state(MusicStates.waiting_for_search_query)
        await message.answer(
            get_text("search_enter_query", lang),
            reply_markup=get_cancel_keyboard(lang),
            parse_mode="HTML"
        )
        return
    
    # Query provided, search directly
    query = command.args.strip()
    await _search_music(message, query, session, db_user, page=1)


@router.message(F.text.in_({get_text("btn_search_music", LANG_UZ),
                            get_text("btn_search_music", LANG_UZ_CYRL),
                            get_text("btn_search_music", LANG_RU),
                            get_text("btn_search_music", LANG_EN)}))
async def btn_search_music(message: Message, state: FSMContext, db_user: User):
    """Start music search via button"""
    lang = normalize_language_code(db_user.language_code)
    await state.set_state(MusicStates.waiting_for_search_query)
    
    await message.answer(
        get_text("search_enter_query", lang),
        reply_markup=get_cancel_keyboard(lang),
        parse_mode="HTML"
    )


@router.message(MusicStates.waiting_for_search_query, F.text)
async def process_search_query(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    """Process music search query from state"""
    # Check for cancel buttons
    cancel_texts = {
        get_text("btn_cancel", LANG_UZ),
        get_text("btn_cancel", LANG_UZ_CYRL),
        get_text("btn_cancel", LANG_RU),
        get_text("btn_cancel", LANG_EN)
    }
    if message.text in cancel_texts:
        await state.clear()
        return
    
    await state.clear()
    
    query = message.text.strip()
    await _search_music(message, query, session, db_user, page=1)


async def _search_music(message: Message, query: str, session: AsyncSession, db_user: User, page: int = 1):
    """Common function to search music - WITH CACHING"""
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
        cached_results = await cache_repo.get_cached_results(query, page)
        
        if cached_results:
            # CACHE HIT!
            await stats_repo.log_cache_hit("music", 1)
            logger.info(f"Music search cache hit: query='{query}', page={page}")
            
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
async def music_search_pagination(callback: CallbackQuery, session: AsyncSession, db_user: User):
    """Handle music search pagination - WITH CACHING"""
    await callback.answer()
    lang = normalize_language_code(db_user.language_code)
    
    # Parse: music_page:page:query
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        return
    
    _, page_str, query = parts
    page = int(page_str)
    
    # Initialize repositories
    cache_repo = MusicSearchCacheRepository(session)
    stats_repo = CacheStatsRepository(session)
    
    try:
        # 🚀 CHECK CACHE FIRST
        cached_results = await cache_repo.get_cached_results(query, page)
        
        if cached_results:
            # CACHE HIT!
            await stats_repo.log_cache_hit("music", 1)
            
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
    """Show top musics - /top [country]
    
    Countries: world, UZ, RU, US, GB, TR
    """
    lang = normalize_language_code(db_user.language_code)
    
    # Check if country provided
    country = "world"
    if command.args:
        country = command.args.strip().upper()
        if country not in ["WORLD", "UZ", "RU", "US", "GB", "TR"]:
            country = "world"
        if country == "WORLD":
            country = "world"
    
    await _show_top_musics(message, country, db_user, page=1)


@router.message(F.text.in_({get_text("btn_top_music", LANG_UZ),
                            get_text("btn_top_music", LANG_UZ_CYRL),
                            get_text("btn_top_music", LANG_RU),
                            get_text("btn_top_music", LANG_EN)}))
async def btn_top_music(message: Message, db_user: User):
    """Show top musics country selection via button"""
    lang = normalize_language_code(db_user.language_code)
    
    text = f"""🔝 <b>{get_text("btn_top_music", lang)}</b>

🌍 Select country:
"""
    await message.answer(text, reply_markup=get_country_selection_keyboard(), parse_mode="HTML")


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
    """Get lyrics - /lyrics <track_url>"""
    lang = normalize_language_code(db_user.language_code)
    
    if not command.args:
        await message.answer(
            "Usage: /lyrics <shazam_track_url>\n\nExample:\n/lyrics https://www.shazam.com/track/316840701/...",
            parse_mode="HTML"
        )
        return
    
    track_url = command.args.strip()
    await _get_lyrics(message, track_url, db_user)


@router.callback_query(F.data.startswith("lyrics:"))
async def callback_lyrics(callback: CallbackQuery, db_user: User):
    """Get and show lyrics from callback"""
    await callback.answer(get_text("downloading", normalize_language_code(db_user.language_code)))
    
    # The track_url is in callback data
    track_url = callback.data.split(":", 1)[1]
    await _get_lyrics(callback.message, track_url, db_user, edit=False)


async def _get_lyrics(message: Message, track_url: str, db_user: User, edit: bool = False):
    """Common function to get lyrics"""
    lang = normalize_language_code(db_user.language_code)
    
    try:
        success, lyrics, error = await api.get_music_lyrics(track_url)
        
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

@router.message(Command("lyrics"))
async def cmd_lyrics(message: Message, command: CommandObject, db_user: User):
    """Get lyrics - /lyrics <track_url>"""
    lang = normalize_language_code(db_user.language_code)
    
    if not command.args:
        await message.answer(
            "Usage: /lyrics <shazam_track_url>\n\nExample:\n/lyrics https://www.shazam.com/track/316840701/...",
            parse_mode="HTML"
        )
        return
    
    track_url = command.args.strip()
    await _get_lyrics(message, track_url, db_user)


@router.callback_query(F.data.startswith("lyrics:"))
async def callback_lyrics(callback: CallbackQuery, db_user: User):
    """Get and show lyrics from callback"""
    await callback.answer(get_text("downloading", normalize_language_code(db_user.language_code)))
    
    # The track_url is in callback data
    track_url = callback.data.split(":", 1)[1]
    await _get_lyrics(callback.message, track_url, db_user, edit=False)


async def _get_lyrics(message: Message, track_url: str, db_user: User, edit: bool = False):
    """Common function to get lyrics"""
    lang = normalize_language_code(db_user.language_code)
    
    try:
        success, lyrics, error = await api.get_music_lyrics(track_url)
        
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
import logging
