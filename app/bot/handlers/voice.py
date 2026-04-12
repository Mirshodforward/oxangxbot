"""
Voice command handler
Converts voice messages to text and searches music
"""
import logging
import tempfile
import os

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.gemini_voice import get_gemini_voice_service
from app.services.fastsaver_api import api
from app.database.models import User
from app.bot.keyboards import get_main_menu_keyboard, get_music_results_keyboard
from app.bot.locales import get_text, normalize_language_code

logger = logging.getLogger(__name__)
router = Router(name="voice")


@router.message(F.voice)
async def handle_voice_command(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    db_user: User
):
    """
    Handle voice messages - transcribe and search music
    
    Flow:
    1. User sends voice message (e.g., "Ummon guruhining qo'shiqlarini top")
    2. Bot transcribes using Gemini
    3. Extracts intent/query (artist: "Ummon")
    4. Searches music and returns results
    """
    lang = normalize_language_code(db_user.language_code)
    
    # Check if Gemini is available
    gemini = get_gemini_voice_service()
    if not gemini:
        await message.answer(
            get_text("voice_disabled", lang),
            reply_markup=get_main_menu_keyboard(lang)
        )
        return
    
    # Clear any existing state
    await state.clear()
    
    # Show processing status
    status_msg = await message.answer(get_text("voice_processing", lang))
    
    try:
        # Download voice file
        file = await bot.get_file(message.voice.file_id)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Download to temp file
            await bot.download_file(file.file_path, tmp_path)
            
            # Process voice message
            command = await gemini.process_voice_message(tmp_path)
            
            if not command:
                await status_msg.edit_text(
                    get_text("voice_not_recognized", lang),
                    reply_markup=get_main_menu_keyboard(lang)
                )
                return
            
            # Show recognized text
            await status_msg.edit_text(
                get_text("voice_recognized", lang, text=command.text, query=command.query),
                parse_mode="HTML"
            )
            
            # Search music with extracted query
            success, results, error = await api.search_music(command.query, page=1)
            
            if not success or not results:
                # Try with full transcription if query fails
                if command.query != command.text:
                    success, results, error = await api.search_music(command.text, page=1)
            
            if not success or not results:
                await message.answer(
                    get_text("search_no_results", lang),
                    reply_markup=get_main_menu_keyboard(lang)
                )
                return
            
            # Show results
            keyboard = get_music_results_keyboard(results, page=1, query=command.query)
            
            text = f"""🔍 <b>{get_text("search_results", lang)}</b> "{command.query}"

🎤 <i>Ovozli buyruq: "{command.text}"</i>

📄 Page: 1
"""
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Voice command error: {e}")
        await status_msg.edit_text(
            get_text("error", lang),
            reply_markup=get_main_menu_keyboard(lang)
        )
