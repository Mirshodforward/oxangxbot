from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.bot.keyboards import (
    get_main_menu_keyboard, 
    get_language_selection_keyboard,
    get_settings_keyboard,
    get_admin_main_keyboard
)
from app.bot.locales import (
    get_text, LANG_UZ, LANG_UZ_CYRL, LANG_RU, LANG_EN,
    LANGUAGES, normalize_language_code
)
from app.database.models import User
from app.database.repositories import UserRepository, DownloadRepository, AdminRepository

router = Router(name="common")


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in settings.ADMIN_IDS


def get_language_selection_message() -> str:
    """
    Generate multi-language selection prompt
    Shows message in all 4 languages at once
    """
    return f"""{get_text('choose_language', LANG_UZ)}
{get_text('choose_language', LANG_UZ_CYRL)}
{get_text('choose_language', LANG_RU)}
{get_text('choose_language', LANG_EN)}"""


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, is_new_user: bool, session: AsyncSession):
    """Handle /start command"""
    
    # 1. Update user explicitly on every start
    db_user.username = message.from_user.username
    from app.database.models import get_uzb_time
    db_user.updated_at = get_uzb_time()
    await session.commit()
    
    # Check if admin
    if is_admin(message.from_user.id):
        # Get stats for admin welcome
        admin_repo = AdminRepository(session)
        stats = await admin_repo.get_stats()
        
        admin_welcome = f"""🔐 <b>Xush kelibsiz, Admin!</b>

📊 <b>Bot statistikasi:</b>
├ 👥 Jami userlar: <b>{stats['total_users']}</b>
├ 🟢 Faol (24s): <b>{stats['active_24h']}</b>
├ 🆕 Bugun yangi: <b>{stats['new_today']}</b>
└ 📥 Bugungi yuklashlar: <b>{stats['downloads_today']}</b>

Quyidagi tugmalardan foydalanib botni boshqaring:
"""
        await message.answer(
            admin_welcome,
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # 2. Always ask for language on /start to update their profile fully
    await message.answer(
        get_language_selection_message(),
        reply_markup=get_language_selection_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def callback_set_language(callback: CallbackQuery, session: AsyncSession, db_user: User):
    """Handle language selection callback"""
    lang_code = callback.data.split(":")[1]
    
    # Validate language code
    if lang_code not in (LANG_UZ, LANG_UZ_CYRL, LANG_RU, LANG_EN):
        lang_code = LANG_UZ
    
    # Update user language in database
    user_repo = UserRepository(session)
    await user_repo.update_language(db_user.id, lang_code)
    
    # Send confirmation and welcome message
    await callback.message.edit_text(
        get_text("language_selected", lang_code),
        parse_mode="HTML"
    )
    
    # Send welcome message with the new language
    welcome_text = get_text("welcome", lang_code, name=callback.from_user.first_name)
    welcome_text += get_text("welcome_new_user", lang_code)
    
    await callback.message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(lang_code),
        parse_mode="HTML"
    )
    
    await callback.answer()


@router.callback_query(F.data == "change_language")
async def callback_change_language(callback: CallbackQuery):
    """Show language selection"""
    await callback.message.edit_text(
        get_language_selection_message(),
        reply_markup=get_language_selection_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("language"))
async def cmd_language(message: Message):
    """Handle /language command"""
    await message.answer(
        get_language_selection_message(),
        reply_markup=get_language_selection_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
@router.message(F.text.in_({get_text("btn_help", LANG_UZ), 
                            get_text("btn_help", LANG_UZ_CYRL),
                            get_text("btn_help", LANG_RU), 
                            get_text("btn_help", LANG_EN)}))
async def cmd_help(message: Message, db_user: User):
    """Handle /help command"""
    lang = normalize_language_code(db_user.language_code)
    await message.answer(get_text("help", lang), parse_mode="HTML")


@router.message(Command("stats"))
@router.message(F.text.in_({get_text("btn_statistics", LANG_UZ),
                            get_text("btn_statistics", LANG_UZ_CYRL),
                            get_text("btn_statistics", LANG_RU),
                            get_text("btn_statistics", LANG_EN)}))
async def cmd_stats(message: Message, session: AsyncSession, db_user: User):
    """Show user statistics"""
    lang = normalize_language_code(db_user.language_code)
    user_repo = UserRepository(session)
    download_repo = DownloadRepository(session)
    
    total_users = await user_repo.get_total_users()
    active_users = await user_repo.get_active_users(days=7)
    total_downloads = await download_repo.get_total_downloads()
    
    # User's personal stats
    user_downloads_items = await download_repo.get_user_downloads(db_user.id, limit=99999)
    user_downloads = len(user_downloads_items)
    registered_date = db_user.created_at.strftime('%d.%m.%Y')
    
    stats_text = get_text(
        "statistics", 
        lang,
        user_downloads=user_downloads,
        registered_date=registered_date,
        total_users=total_users,
        active_users=active_users,
        total_downloads=total_downloads
    )
    
    await message.answer(stats_text, parse_mode="HTML")


@router.message(F.text.in_({get_text("btn_settings", LANG_UZ),
                            get_text("btn_settings", LANG_UZ_CYRL),
                            get_text("btn_settings", LANG_RU),
                            get_text("btn_settings", LANG_EN)}))
async def cmd_settings(message: Message, db_user: User):
    """Settings menu"""
    lang = normalize_language_code(db_user.language_code)
    await message.answer(
        get_text("settings", lang),
        reply_markup=get_settings_keyboard(lang),
        parse_mode="HTML"
    )


@router.message(F.text.in_({get_text("btn_cancel", LANG_UZ),
                            get_text("btn_cancel", LANG_UZ_CYRL),
                            get_text("btn_cancel", LANG_RU),
                            get_text("btn_cancel", LANG_EN)}))
async def cancel_action(message: Message, db_user: User):
    """Cancel current action"""
    lang = normalize_language_code(db_user.language_code)
    await message.answer(
        "❌",
        reply_markup=get_main_menu_keyboard(lang)
    )
