from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    KeyboardButtonRequestChat,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import Optional, List
import html
import re

from app.services.fastsaver_api import MusicSearchResult
from app.bot.locales import (
    get_text, LANGUAGES, LANG_UZ, LANG_UZ_CYRL, LANG_RU, LANG_EN
)

# Telegram «Choose a Channel» — chat_shared.request_id (xabar ichida noyob bo‘lishi kerak)
REQUEST_CHAT_ADD_REQUIRED_CHANNEL = 1
TG_CHANNEL_PICK_CANCEL = "❌ Bekor"


def get_mandatory_channel_request_chat_keyboard() -> ReplyKeyboardMarkup:
    """
    Faqat maxfiy kanallar (@ yo‘q) va bot allaqachon ichida bo‘lganlar — get_chat / taklif havolasi ishlashi uchun.
    """
    req = KeyboardButtonRequestChat(
        request_id=REQUEST_CHAT_ADD_REQUIRED_CHANNEL,
        chat_is_channel=True,
        chat_has_username=False,
        bot_is_member=True,
        request_title=True,
        request_username=True,
    )
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📢 Kanal ulash",
                    request_chat=req,
                ),
            ],
            [KeyboardButton(text=TG_CHANNEL_PICK_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
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


def get_main_menu_keyboard(lang: str = LANG_UZ) -> ReplyKeyboardRemove:
    """Musiqa menyusi reply-tugmasiz; /top va /search buyruqlari ishlatiladi."""
    _ = lang
    return ReplyKeyboardRemove()


def get_settings_keyboard(lang: str = LANG_UZ) -> InlineKeyboardMarkup:
    """Settings keyboard with language change option"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text=get_text("btn_language", lang),
        callback_data="change_language"
    ))
    return builder.as_markup()


def _youtube_id_ok(v: str) -> bool:
    s = (v or "").strip()
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]{11}", s))


def format_numbered_tracks_message(
    header: str,
    musics: List[MusicSearchResult],
    *,
    max_lines: int = 10,
    footer_html: Optional[str] = None,
) -> str:
    """Skrinshotdagi kabi: sarlavha + raqamli ro'yxat (nomi + davomiylik)."""
    h = html.escape((header or "").strip() or "—")
    lines = [f"🎵 <b>{h}</b>"]
    for i, m in enumerate(musics[:max_lines], 1):
        tit = html.escape((m.title or "—").strip())
        dur = html.escape(str(m.duration or "").strip())
        suf = f" {dur}" if dur else ""
        lines.append(f"{i}. {tit}{suf}")
    body = "\n".join(lines)
    if footer_html:
        return f"{body}\n\n{footer_html}"
    return body


def _dict_to_music_result(d: dict) -> MusicSearchResult:
    return MusicSearchResult(
        title=d.get("title", "") or "",
        shortcode=d.get("shortcode", "") or "",
        duration=str(d.get("duration", "") or ""),
        thumb=d.get("thumb", "") or "",
        thumb_best=d.get("thumb_best"),
    )


def get_track_pick_keyboard(
    musics: List[MusicSearchResult],
    shazam_id: Optional[str] = None,
    nav_row: Optional[List[InlineKeyboardButton]] = None,
) -> InlineKeyboardMarkup:
    """
    Video — birinchi trek uchun sifat tanlash (mavjud music: handler).
    1..N — pick_mp3:video_id (to'g'ridan-to'g'ri MP3).
    """
    builder = InlineKeyboardBuilder()
    valid = [m for m in musics[:10] if _youtube_id_ok(m.shortcode)]
    if not valid:
        if shazam_id:
            builder.row(
                InlineKeyboardButton(
                    text="📝 Matnini ko'rish",
                    callback_data=f"lyrics:{shazam_id}",
                )
            )
        if nav_row:
            builder.row(*nav_row)
        return builder.as_markup()

    first_id = valid[0].shortcode.strip()
    builder.row(
        InlineKeyboardButton(text="🎞️ Video", callback_data=f"music:{first_id}")
    )
    row: List[InlineKeyboardButton] = []
    for i, m in enumerate(valid):
        row.append(
            InlineKeyboardButton(
                text=str(i + 1),
                callback_data=f"pick_mp3:{m.shortcode.strip()}",
            )
        )
        if len(row) == 5:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    if shazam_id:
        builder.row(
            InlineKeyboardButton(
                text="📝 Matnini ko'rish",
                callback_data=f"lyrics:{shazam_id}",
            )
        )
    if nav_row:
        builder.row(*nav_row)
    return builder.as_markup()


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
) -> Optional[InlineKeyboardMarkup]:
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
    """YouTube qidiruv: Video + raqamlar + pagination."""
    nav_buttons: List[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"music_page:{page - 1}:{query}",
            )
        )
    if len(results) >= 10 and page < 3:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"music_page:{page + 1}:{query}",
            )
        )
    return get_track_pick_keyboard(
        results[:10],
        shazam_id=None,
        nav_row=nav_buttons if nav_buttons else None,
    )


def get_top_music_keyboard(
    musics: list[dict],
    page: int = 1,
    country: str = "world"
) -> InlineKeyboardMarkup:
    """Top chart: Video + raqamlar + pagination."""
    ms = [_dict_to_music_result(m) for m in musics[:10]]
    nav_buttons: List[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"top_page:{page - 1}:{country}",
            )
        )
    if len(musics) >= 10 and page < 3:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"top_page:{page + 1}:{country}",
            )
        )
    return get_track_pick_keyboard(
        ms,
        shazam_id=None,
        nav_row=nav_buttons if nav_buttons else None,
    )


def get_recognized_music_keyboard(
    musics: list[MusicSearchResult],
    shazam_id: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Shazam natijasi: Video + raqamlar + lyrics."""
    return get_track_pick_keyboard(musics[:10], shazam_id=shazam_id, nav_row=None)


def get_country_selection_keyboard() -> InlineKeyboardMarkup:
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


def get_download_keyboard(
    lang: str, youtube_video_id: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Download keyboard: YouTube — to'g'ridan-to'g'ri MP3 (tg-bot file_id); boshqa — Shazam."""
    builder = InlineKeyboardBuilder()
    vid = (youtube_video_id or "").strip()
    audio_cb = f"yt_dl:{vid}:mp3" if vid else "shazam_this"
    builder.row(
        InlineKeyboardButton(
            text=get_text("btn_download_audio", lang),
            callback_data=audio_cb,
        )
    )
    
    # "Do'stlarga tarqatish"
    builder.row(InlineKeyboardButton(
        text=get_text("btn_share", lang),
        switch_inline_query=""
    ))
    
    return builder.as_markup()


# ==================== ADMIN KEYBOARDS ====================
# Reply tugmalar matni handlerlar bilan bir xil bo'lishi shart (faqat admin chatda).

ADMIN_REPLY_BTN_STATS = "📊 Statistika"
ADMIN_REPLY_BTN_USERS = "👥 Foydalanuvchilar"
ADMIN_REPLY_BTN_BROADCAST = "📢 Post yuborish"
ADMIN_REPLY_BTN_CHANNELS = "📣 Majburiy obuna"
ADMIN_REPLY_BTN_CACHE = "🗄️ Kesh statistikasi"
# User Info bot uslubi: KeyboardButtonRequestChat → chat_shared (chat_id majburiy obunaga)
ADMIN_REPLY_BTN_LINK_CHANNEL_TG = "🔐 Maxfiy kanal"


ADMIN_MAIN_REPLY_TEXTS: frozenset[str] = frozenset(
    {
        ADMIN_REPLY_BTN_STATS,
        ADMIN_REPLY_BTN_USERS,
        ADMIN_REPLY_BTN_BROADCAST,
        ADMIN_REPLY_BTN_CHANNELS,
        ADMIN_REPLY_BTN_CACHE,
        ADMIN_REPLY_BTN_LINK_CHANNEL_TG,
    }
)


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Admin panel asosiy tugmalari (pastdagi reply keyboard, faqat admin uchun)."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=ADMIN_REPLY_BTN_STATS),
        KeyboardButton(text=ADMIN_REPLY_BTN_USERS),
    )
    builder.row(
        KeyboardButton(text=ADMIN_REPLY_BTN_BROADCAST),
        KeyboardButton(text=ADMIN_REPLY_BTN_CHANNELS),
    )
    builder.row(KeyboardButton(text=ADMIN_REPLY_BTN_CACHE))
    builder.row(KeyboardButton(text=ADMIN_REPLY_BTN_LINK_CHANNEL_TG))

    return builder.as_markup(resize_keyboard=True)


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
    add_text = "➕ Limit (5/5)" if at_limit else None
    if at_limit:
        builder.row(
            InlineKeyboardButton(text=add_text, callback_data="channel:add_limit")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="➕ @username", callback_data="channel:add"),
            InlineKeyboardButton(text="🔐 Maxfiy kanal", callback_data="channel:add_tg_pick"),
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:back")
    )

    return builder.as_markup()


def get_discovered_private_pick_keyboard(
    rows: list,
    required_chat_ids: Optional[set] = None,
) -> InlineKeyboardMarkup:
    """Maxfiy kanallar ro'yxati (bot admin bo'lgan). required_chat_ids — majburiy obunada bor chat_id lar."""
    required_chat_ids = required_chat_ids or set()
    builder = InlineKeyboardBuilder()
    for row in rows:
        raw = (row.chat_title or "Kanal").strip() or "Kanal"
        short = raw if len(raw) <= 36 else raw[:33] + "…"
        linked = row.chat_id in required_chat_ids
        if linked:
            builder.row(
                InlineKeyboardButton(
                    text=f"✅ {short}",
                    callback_data=f"chpkv:{row.id}",
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text=f"🔗 {short}",
                    callback_data=f"chpk:{row.id}",
                )
            )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:channels")
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
