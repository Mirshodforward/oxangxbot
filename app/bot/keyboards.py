from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import Optional, List

from app.services.fastsaver_api import MusicSearchResult
from app.bot.locales import (
    get_text, LANGUAGES, LANG_UZ, LANG_UZ_CYRL, LANG_RU, LANG_EN
)


def get_language_selection_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard (2x2 grid like in the image)"""
    builder = InlineKeyboardBuilder()
    
    # Row 1: Uzbek Latin and Uzbek Cyrillic
    builder.row(
        InlineKeyboardButton(
            text=f"{LANGUAGES[LANG_UZ]['flag']} {LANGUAGES[LANG_UZ]['native_name']}",
            callback_data=f"set_lang:{LANG_UZ}"
        ),
        InlineKeyboardButton(
            text=f"{LANGUAGES[LANG_UZ_CYRL]['flag']} {LANGUAGES[LANG_UZ_CYRL]['native_name']}",
            callback_data=f"set_lang:{LANG_UZ_CYRL}"
        )
    )
    
    # Row 2: Russian and English
    builder.row(
        InlineKeyboardButton(
            text=f"{LANGUAGES[LANG_RU]['flag']} {LANGUAGES[LANG_RU]['native_name']}",
            callback_data=f"set_lang:{LANG_RU}"
        ),
        InlineKeyboardButton(
            text=f"{LANGUAGES[LANG_EN]['flag']} {LANGUAGES[LANG_EN]['native_name']}",
            callback_data=f"set_lang:{LANG_EN}"
        )
    )
    
    return builder.as_markup()


def get_main_menu_keyboard(lang: str = LANG_UZ) -> ReplyKeyboardMarkup:
    """Asosiy menyu (startdan keyin): faol funksiyalar."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=get_text("btn_top_music", lang)),
        KeyboardButton(text=get_text("btn_search_music", lang)),
    )
    return builder.as_markup(resize_keyboard=True)


def get_settings_keyboard(lang: str = LANG_UZ) -> InlineKeyboardMarkup:
    """Settings keyboard with language change option"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text=get_text("btn_language", lang),
        callback_data="change_language"
    ))
    return builder.as_markup()


def get_cancel_keyboard(lang: str = LANG_UZ) -> ReplyKeyboardMarkup:
    """Cancel keyboard with localization support"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=get_text("btn_cancel", lang)))
    return builder.as_markup(resize_keyboard=True)


def get_youtube_quality_keyboard(video_id: str) -> InlineKeyboardMarkup:
    """YouTube video quality selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    qualities = [
        ("🎬 1080p", f"yt_dl:{video_id}:1080p"),
        ("📹 720p", f"yt_dl:{video_id}:720p"),
        ("📱 480p", f"yt_dl:{video_id}:480p"),
        ("📺 360p", f"yt_dl:{video_id}:360p"),
    ]
    
    for text, callback_data in qualities:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    # Add audio option
    builder.add(InlineKeyboardButton(
        text="🎵 MP3 (audio)",
        callback_data=f"yt_dl:{video_id}:mp3"
    ))
    
    builder.adjust(2, 2, 1)  # 2 buttons per row, last row 1 button
    return builder.as_markup()


def get_media_actions_keyboard(
    url: str,
    has_audio: bool = False,
    platform: str = ""
) -> InlineKeyboardMarkup:
    """Media action buttons (download audio, etc.)"""
    builder = InlineKeyboardBuilder()
    
    # For non-YouTube platforms
    if has_audio or platform.lower() in ["instagram", "tiktok", "likee"]:
        builder.add(InlineKeyboardButton(
            text="🎵 Audio yuklash",
            callback_data="extract_audio"
        ))
    
    return builder.as_markup() if builder.buttons else None


def get_music_results_keyboard(
    results: List[MusicSearchResult],
    page: int = 1,
    query: str = ""
) -> InlineKeyboardMarkup:
    """Music search results keyboard"""
    builder = InlineKeyboardBuilder()
    
    for i, result in enumerate(results[:10]):  # Max 10 results
        # Truncate title if too long
        title = result.title[:35] + "..." if len(result.title) > 35 else result.title
        builder.add(InlineKeyboardButton(
            text=f"{i + 1}. {title}",
            callback_data=f"music:{result.shortcode}"
        ))
    
    builder.adjust(1)  # 1 button per row
    
    # Pagination
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Oldingi",
            callback_data=f"music_page:{page - 1}:{query}"
        ))
    if len(results) >= 10 and page < 3:
        nav_buttons.append(InlineKeyboardButton(
            text="Keyingi ➡️",
            callback_data=f"music_page:{page + 1}:{query}"
        ))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    return builder.as_markup()


def get_top_music_keyboard(
    musics: list[dict],
    page: int = 1,
    country: str = "world"
) -> InlineKeyboardMarkup:
    """Top musics keyboard"""
    builder = InlineKeyboardBuilder()
    
    for i, music in enumerate(musics[:10]):
        title = music.get("title", "Unknown")
        title = title[:35] + "..." if len(title) > 35 else title
        shortcode = music.get("shortcode", "")
        builder.add(InlineKeyboardButton(
            text=f"{i + 1}. {title}",
            callback_data=f"music:{shortcode}"
        ))
    
    builder.adjust(1)
    
    # Pagination
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Oldingi",
            callback_data=f"top_page:{page - 1}:{country}"
        ))
    if len(musics) >= 10 and page < 3:
        nav_buttons.append(InlineKeyboardButton(
            text="Keyingi ➡️",
            callback_data=f"top_page:{page + 1}:{country}"
        ))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    return builder.as_markup()


def get_recognized_music_keyboard(
    musics: list[MusicSearchResult],
    track_url: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Keyboard for recognized music results"""
    builder = InlineKeyboardBuilder()
    
    # Add download options for found musics
    for i, music in enumerate(musics[:5]):
        title = music.title[:30] + "..." if len(music.title) > 30 else music.title
        builder.add(InlineKeyboardButton(
            text=f"🎵 {title}",
            callback_data=f"music:{music.shortcode}"
        ))
    
    builder.adjust(1)
    
    # Add lyrics button if track_url available
    if track_url:
        builder.row(InlineKeyboardButton(
            text="📝 Matnini ko'rish",
            callback_data=f"lyrics:{track_url[:50]}"  # Truncate URL for callback
        ))
    
    return builder.as_markup()


def get_country_selection_keyboard() -> InlineKeyboardMarkup:
    """Country selection for top musics"""
    builder = InlineKeyboardBuilder()
    
    countries = [
        ("🌍 Dunyo", "world"),
        ("🇺🇿 O'zbekiston", "UZ"),
        ("🇷🇺 Rossiya", "RU"),
        ("🇺🇸 AQSH", "US"),
        ("🇬🇧 Britaniya", "GB"),
        ("🇹🇷 Turkiya", "TR"),
    ]
    
    for text, code in countries:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"top_country:{code}"
        ))
    
    builder.adjust(2)
    return builder.as_markup()


def get_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm:{action}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel")
    )
    return builder.as_markup()


def get_back_keyboard(callback_data: str = "back") -> InlineKeyboardMarkup:
    """Back button keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=callback_data)]
    ])


def get_download_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Download keyboard with download song and share buttons"""
    builder = InlineKeyboardBuilder()
    
    # "Qo'shiqni yuklab olish"
    builder.row(InlineKeyboardButton(
        text=get_text("btn_download_audio", lang),
        callback_data="shazam_this"
    ))
    
    # "Do'stlarga tarqatish"
    builder.row(InlineKeyboardButton(
        text=get_text("btn_share", lang),
        switch_inline_query=""
    ))
    
    return builder.as_markup()


# ==================== ADMIN KEYBOARDS ====================

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin panel main keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Post yuborish", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="📣 Majburiy obuna", callback_data="admin:channels")
    )
    builder.row(
        InlineKeyboardButton(text="🗄 Kesh statistikasi", callback_data="admin:cache")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:refresh")
    )
    
    return builder.as_markup()


def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Broadcast options keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📝 Matn yuborish", callback_data="broadcast:text"),
        InlineKeyboardButton(text="🖼 Media + Matn", callback_data="broadcast:photo")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Hammaga", callback_data="broadcast:all"),
        InlineKeyboardButton(text="🔢 N ta userga", callback_data="broadcast:limited")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Yuborishlar tarixi", callback_data="broadcast:history")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:back")
    )
    
    return builder.as_markup()


def _required_channel_open_url(channel) -> str | None:
    """Obuna uchun ochiladigan havola (invite yoki @username)."""
    link = getattr(channel, "invite_link", None)
    if link:
        return link
    un = (channel.channel_username or "").strip().lstrip("@")
    if un and un not in ("-", "private", "_") and not un.startswith("-100"):
        return f"https://t.me/{un}"
    return None


def get_channels_keyboard(channels: list) -> InlineKeyboardMarkup:
    """Required channels management keyboard"""
    builder = InlineKeyboardBuilder()
    
    for channel in channels:
        status = "✅" if channel.is_active else "❌"
        un = (channel.channel_username or "").strip()
        label = f"@{un}" if un and un not in ("-", "private", "_") and not un.startswith("-100") else channel.channel_title
        short = label if len(label) <= 28 else label[:25] + "…"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {short}",
                callback_data=f"channel:toggle:{channel.id}"
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"channel:delete:{channel.id}"
            )
        )
    
    at_limit = len(channels) >= 5
    add_text = "➕ Kanal qo'shish" if not at_limit else "➕ Limit (5/5)"
    add_cb = "channel:add" if not at_limit else "channel:add_limit"
    builder.row(InlineKeyboardButton(text=add_text, callback_data=add_cb))
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:back")
    )
    
    return builder.as_markup()


def get_subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    """Forced subscription keyboard for users"""
    builder = InlineKeyboardBuilder()
    
    for channel in channels:
        url = _required_channel_open_url(channel)
        title = channel.channel_title
        short = title if len(title) <= 30 else title[:27] + "…"
        if url:
            builder.row(
                InlineKeyboardButton(
                    text=f"📢 {short}",
                    url=url,
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text=f"📢 {short}",
                    callback_data="subscription:no_link",
                )
            )
    
    builder.row(
        InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")
    )
    
    return builder.as_markup()


def get_broadcast_confirm_keyboard(user_count: int) -> InlineKeyboardMarkup:
    """Broadcast confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Yuborish ({user_count} ta user)",
            callback_data="broadcast:confirm"
        )
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast:cancel")
    )
    
    return builder.as_markup()


def get_admin_back_keyboard() -> InlineKeyboardMarkup:
    """Admin back button"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:back")]
    ])


def get_users_keyboard() -> InlineKeyboardMarkup:
    """Users analytics keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📈 Haftalik faollar", callback_data="users:weekly"),
        InlineKeyboardButton(text="📊 Kunlik faollar", callback_data="users:daily")
    )
    builder.row(
        InlineKeyboardButton(text="🆕 Yangi userlar", callback_data="users:new"),
        InlineKeyboardButton(text="📋 Barchasi", callback_data="users:all")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:back")
    )
    
    return builder.as_markup()


# Remove keyboard helper
remove_keyboard = ReplyKeyboardRemove()
