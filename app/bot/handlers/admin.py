"""
Admin handlers - Full admin panel for bot management
"""
import logging
import asyncio
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.text_decorations import html_decoration
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.helpers import safe_callback_answer
from app.database.models import User
from app.database.repositories import (
    AdminRepository,
    ChannelRepository,
    BroadcastRepository,
    UserRepository,
    CacheStatsRepository,
    YouTubeCacheRepository,
    MusicSearchCacheRepository,
    CacheRepository,
    MaxRequiredChannelsError,
)
from app.bot.keyboards import (
    ADMIN_MAIN_REPLY_TEXTS,
    ADMIN_REPLY_BTN_BROADCAST,
    ADMIN_REPLY_BTN_CACHE,
    ADMIN_REPLY_BTN_CHANNELS,
    ADMIN_REPLY_BTN_STATS,
    ADMIN_REPLY_BTN_USERS,
    get_admin_main_keyboard,
    get_broadcast_keyboard,
    get_channels_keyboard,
    get_subscription_keyboard,
    get_broadcast_confirm_keyboard,
    get_admin_back_keyboard,
    get_users_keyboard,
    get_main_menu_keyboard,
)
from app.bot.subscription import check_user_subscription
from app.bot.locales import get_text, normalize_language_code

logger = logging.getLogger(__name__)
router = Router(name="admin")


class AdminStates(StatesGroup):
    """FSM states for admin operations"""
    waiting_broadcast_text = State()
    waiting_broadcast_photo = State()
    waiting_broadcast_count = State()
    waiting_channel_username = State()


def get_html_caption(message: Message) -> str:
    """
    Convert message caption with entities to HTML format.
    Works for photo, video, document, audio, voice messages.
    """
    if not message.caption:
        return ""
    
    if not message.caption_entities:
        # No formatting, just escape HTML
        return html_decoration.quote(message.caption)
    
    # Apply entities to get HTML
    return html_decoration.unparse(message.caption, message.caption_entities)


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in settings.ADMIN_IDS


# Inline klaviaturani xabardan olib tashlash (reply keyboard Telegramda edit bilan berilmaydi)
_CLEAR_INLINE = InlineKeyboardMarkup(inline_keyboard=[])


# ==================== ADMIN PANEL ====================

@router.message(Command("admin"))
async def cmd_admin(message: Message, db_user: User):
    """Admin panel command"""
    if not is_admin(message.from_user.id):
        return
    
    await show_admin_panel(message)


async def show_admin_panel(message: Message, edit: bool = False):
    """Show admin panel"""
    text = """🔐 <b>Admin Panel</b>

Botni boshqarish uchun quyidagi tugmalardan foydalaning:

📊 <b>Statistika</b> - Bot statistikasi
👥 <b>Foydalanuvchilar</b> - User analitikasi
📢 <b>Broadcast</b> - Xabar yuborish
📣 <b>Majburiy obuna</b> - Kanallar boshqaruvi
"""
    
    if edit and hasattr(message, "edit_text"):
        await message.edit_text(text, reply_markup=_CLEAR_INLINE, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    """Back to admin panel"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.clear()
    await show_admin_panel(callback.message, edit=True)
    await safe_callback_answer(callback)


# ==================== CACHE STATISTICS ====================

async def build_full_cache_stats_html(session: AsyncSession) -> str:
    """To'liq kesh statistikasi matni (/cache va admin tugmasi uchun)."""
    stats_repo = CacheStatsRepository(session)
    yt_cache_repo = YouTubeCacheRepository(session)
    music_cache_repo = MusicSearchCacheRepository(session)
    cache_repo = CacheRepository(session)

    total_stats = await stats_repo.get_total_stats()
    today_stats = await stats_repo.get_today_stats()

    yt_hits = await yt_cache_repo.get_total_hits()
    yt_saved = await yt_cache_repo.get_points_saved()
    music_hits = await music_cache_repo.get_total_hits()
    media_hits = await cache_repo.get_total_hits()

    total_api_calls = (
        total_stats["api_calls"]["media"]
        + total_stats["api_calls"]["music"]
        + total_stats["api_calls"]["youtube"]
        + total_stats["api_calls"]["recognize"]
    )

    total_cache_hits = (
        total_stats["cache_hits"]["media"]
        + total_stats["cache_hits"]["music"]
        + total_stats["cache_hits"]["youtube"]
        + total_stats["cache_hits"]["recognize"]
    )

    efficiency = 0.0
    if total_api_calls + total_cache_hits > 0:
        efficiency = (total_cache_hits / (total_api_calls + total_cache_hits)) * 100

    return f"""💾 <b>Kesh Statistikasi</b>

📊 <b>Bugungi natijalar:</b>
├ API so'rovlar: <b>{today_stats.api_calls_media + today_stats.api_calls_music + today_stats.api_calls_youtube}</b>
├ Kesh hitlar: <b>{today_stats.cache_hits_media + today_stats.cache_hits_music + today_stats.cache_hits_youtube}</b>
├ Sarflangan: <b>{today_stats.points_spent}</b> point
└ Tejalgan: <b>{today_stats.points_saved}</b> point ✅

📈 <b>Jami statistika:</b>
├ API so'rovlar: <b>{total_api_calls}</b>
├ Kesh hitlar: <b>{total_cache_hits}</b>
├ Sarflangan: <b>{total_stats['points_spent']}</b> points
├ Tejalgan: <b>{total_stats['points_saved']}</b> points 💰
└ Effektivlik: <b>{efficiency:.1f}%</b>

🎬 <b>YouTube keshi:</b> (20 point/hit)
├ Kesh hitlar: <b>{yt_hits}</b>
└ Tejalgan: <b>{yt_saved}</b> points 🔥

🎵 <b>Musiqa qidiruvi:</b> (1 point/hit)
└ Kesh hitlar: <b>{music_hits}</b>

📱 <b>Media (IG/TT/etc):</b> (1 point/hit)
└ Kesh hitlar: <b>{media_hits}</b>

💡 <i>Kesh tizimi har bir takroriy so'rovda API pointlarni tejaydi!</i>
"""


@router.message(Command("cache"))
async def cmd_cache_stats(message: Message, session: AsyncSession):
    """Show cache statistics - how many points saved"""
    if not is_admin(message.from_user.id):
        return

    text = await build_full_cache_stats_html(session)
    await message.answer(text, parse_mode="HTML")


# ==================== USERS ANALYTICS ====================


@router.callback_query(F.data.startswith("users:"))
async def users_analytics(callback: CallbackQuery, session: AsyncSession):
    """Detailed user analytics"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    action = callback.data.split(":")[1]
    admin_repo = AdminRepository(session)
    stats = await admin_repo.get_stats()
    
    if action == "weekly":
        text = f"""📈 <b>Haftalik faol foydalanuvchilar</b>

Oxirgi 7 kunda faol bo'lgan userlar: <b>{stats['active_7d']}</b>

💡 Faol user - oxirgi 7 kunda botdan foydalangan user.
"""
    elif action == "daily":
        text = f"""📊 <b>Kunlik faol foydalanuvchilar</b>

Oxirgi 24 soatda faol: <b>{stats['active_24h']}</b>
Oxirgi 7 kunda faol: <b>{stats['active_7d']}</b>
Oxirgi 30 kunda faol: <b>{stats['active_30d']}</b>
"""
    elif action == "new":
        text = f"""🆕 <b>Yangi foydalanuvchilar</b>

Bugun qo'shilgan: <b>{stats['new_today']}</b>
Shu hafta qo'shilgan: <b>{stats['new_this_week']}</b>
"""
    else:  # all
        text = f"""📋 <b>Barcha foydalanuvchilar</b>

Jami ro'yxatdagi userlar: <b>{stats['total_users']}</b>
├ Username ko'rsatganlar: <b>{stats['users_with_username']}</b> ({round(stats['users_with_username']/max(stats['total_users'],1)*100, 1)}%)
└ Username yo'qlar: <b>{stats['total_users'] - stats['users_with_username']}</b> ({round((stats['total_users'] - stats['users_with_username'])/max(stats['total_users'],1)*100, 1)}%)

📊 Faollik bo'yicha:
├ 24 soat: <b>{stats['active_24h']}</b> ({round(stats['active_24h']/max(stats['total_users'],1)*100, 1)}%)
├ 7 kun: <b>{stats['active_7d']}</b> ({round(stats['active_7d']/max(stats['total_users'],1)*100, 1)}%)
└ 30 kun: <b>{stats['active_30d']}</b> ({round(stats['active_30d']/max(stats['total_users'],1)*100, 1)}%)
"""
    
    await callback.message.edit_text(text, reply_markup=get_users_keyboard(), parse_mode="HTML")
    await safe_callback_answer(callback)


# ==================== BROADCAST ====================

# Store broadcast data temporarily
broadcast_data = {}


@router.callback_query(F.data == "broadcast:text")
async def broadcast_text_start(callback: CallbackQuery, state: FSMContext):
    """Start text broadcast"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_text)
    broadcast_data[callback.from_user.id] = {"type": "text"}
    
    await callback.message.edit_text(
        "📝 <b>Broadcast xabarini yuboring</b>\n\nHTMLni qo'llab-quvvatlaydi.",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data == "broadcast:photo")
async def broadcast_photo_start(callback: CallbackQuery, state: FSMContext):
    """Start photo/video broadcast"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_photo)
    broadcast_data[callback.from_user.id] = {"type": "photo"}
    
    await callback.message.edit_text(
        "🖼 <b>Media + Caption yuboring</b>\n\n"
        "📷 Rasm yoki 🎬 Video yuboring.\n"
        "Caption qo'shishingiz mumkin (HTML qo'llaniladi).",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)


@router.message(AdminStates.waiting_broadcast_text, F.text)
async def receive_broadcast_text(message: Message, state: FSMContext, session: AsyncSession):
    """Receive broadcast text"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_data[message.from_user.id]["text"] = message.text
    broadcast_data[message.from_user.id]["html"] = message.html_text
    
    admin_repo = AdminRepository(session)
    user_count = len(await admin_repo.get_all_user_ids())
    
    await state.clear()
    
    text = f"""📢 <b>Broadcast tasdiqlash</b>

📝 <b>Xabar:</b>
{message.text[:500]}{'...' if len(message.text) > 500 else ''}

👥 Yuboriladi: <b>{user_count}</b> ta userga
"""
    
    await message.answer(text, reply_markup=get_broadcast_confirm_keyboard(user_count), parse_mode="HTML")


@router.message(AdminStates.waiting_broadcast_photo, F.photo)
async def receive_broadcast_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Receive broadcast photo"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_data[message.from_user.id]["photo"] = message.photo[-1].file_id
    broadcast_data[message.from_user.id]["caption"] = message.caption or ""
    broadcast_data[message.from_user.id]["html_caption"] = get_html_caption(message)
    
    admin_repo = AdminRepository(session)
    user_count = len(await admin_repo.get_all_user_ids())
    
    await state.clear()
    
    text = f"""📢 <b>Broadcast tasdiqlash</b>

🖼 <b>Rasm yuklandi</b>
📝 <b>Caption:</b> {message.caption[:200] if message.caption else 'Yo\'q'}

👥 Yuboriladi: <b>{user_count}</b> ta userga
"""
    
    await message.answer(text, reply_markup=get_broadcast_confirm_keyboard(user_count), parse_mode="HTML")


@router.message(AdminStates.waiting_broadcast_photo, F.video)
async def receive_broadcast_video(message: Message, state: FSMContext, session: AsyncSession):
    """Receive broadcast video"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_data[message.from_user.id]["type"] = "video"
    broadcast_data[message.from_user.id]["video"] = message.video.file_id
    broadcast_data[message.from_user.id]["caption"] = message.caption or ""
    broadcast_data[message.from_user.id]["html_caption"] = get_html_caption(message)
    
    admin_repo = AdminRepository(session)
    user_count = len(await admin_repo.get_all_user_ids())
    
    await state.clear()
    
    text = f"""📢 <b>Broadcast tasdiqlash</b>

🎬 <b>Video yuklandi</b>
📝 <b>Caption:</b> {message.caption[:200] if message.caption else 'Yo\'q'}

👥 Yuboriladi: <b>{user_count}</b> ta userga
"""
    
    await message.answer(text, reply_markup=get_broadcast_confirm_keyboard(user_count), parse_mode="HTML")


@router.callback_query(F.data == "broadcast:all")
async def broadcast_all(callback: CallbackQuery, session: AsyncSession):
    """Set broadcast to all users"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    if callback.from_user.id not in broadcast_data:
        await safe_callback_answer(callback,"Avval xabar turini tanlang!", show_alert=True)
        return
    
    broadcast_data[callback.from_user.id]["limit"] = None
    admin_repo = AdminRepository(session)
    user_count = len(await admin_repo.get_all_user_ids())
    
    await safe_callback_answer(callback,f"✅ {user_count} ta userga yuboriladi")


@router.callback_query(F.data == "broadcast:limited")
async def broadcast_limited(callback: CallbackQuery, state: FSMContext):
    """Set limited broadcast"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_count)
    
    await callback.message.edit_text(
        "🔢 <b>Nechta userga yuborilsin?</b>\n\nSon kiriting:",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)


@router.message(AdminStates.waiting_broadcast_count, F.text)
async def receive_broadcast_count(message: Message, state: FSMContext, session: AsyncSession):
    """Receive broadcast user count"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        count = int(message.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri son. Qaytadan kiriting:")
        return
    
    if message.from_user.id not in broadcast_data:
        broadcast_data[message.from_user.id] = {}
    
    broadcast_data[message.from_user.id]["limit"] = count
    
    await state.clear()
    
    text = f"""📢 <b>Broadcast sozlandi</b>

🔢 Yuboriladi: <b>{count}</b> ta userga

Endi xabar turini tanlang va xabar yuboring.
"""
    
    await message.answer(text, reply_markup=get_broadcast_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "broadcast:confirm")
async def broadcast_confirm(callback: CallbackQuery, bot: Bot, session: AsyncSession):
    """Confirm and start broadcast - optimized for 100k+ users"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    data = broadcast_data.get(callback.from_user.id)
    if not data:
        await safe_callback_answer(callback,"❌ Xabar topilmadi", show_alert=True)
        return
    
    await safe_callback_answer(callback,"🚀 Broadcast boshlandi...")
    
    # Get users
    admin_repo = AdminRepository(session)
    limit = data.get("limit")
    user_ids = await admin_repo.get_all_user_ids(limit=limit)
    total = len(user_ids)
    
    # Determine message type for stats
    msg_type = data.get("type", "text")
    msg_type_display = {
        "text": "📝 MATN",
        "photo": "🖼 RASM",
        "video": "🎬 VIDEO"
    }.get(msg_type, "📝 MATN")
    
    # Create broadcast record
    broadcast_repo = BroadcastRepository(session)
    broadcast = await broadcast_repo.create_broadcast(
        admin_id=callback.from_user.id,
        message_text=data.get("text") or data.get("caption"),
        photo_file_id=data.get("photo") or data.get("video"),
        total_users=total
    )
    
    await broadcast_repo.update_broadcast(broadcast.id, status="running")
    
    # Statistics counters
    sent = 0
    failed = 0
    blocked = 0
    
    # Timing
    import time
    start_time = time.time()
    
    # Calculate optimal update interval based on total users
    update_interval = max(50, min(500, total // 100))
    
    # Send progress message
    progress_msg = await callback.message.edit_text(
        f"📢 <b>Broadcast jarayonda...</b>\n\n"
        f"📋 Turi: {msg_type_display}\n"
        f"👥 Jami: <b>{total:,}</b> ta user\n\n"
        f"📊 Progress: 0/{total:,} (0%)\n"
        f"✅ Yuborildi: 0\n"
        f"❌ Xato: 0\n"
        f"🚫 Bloklangan: 0\n\n"
        f"⏱ Taxminiy vaqt: hisoblanyapti...",
        parse_mode="HTML"
    )
    
    for i, user_id in enumerate(user_ids):
        try:
            if msg_type == "photo":
                await bot.send_photo(
                    chat_id=user_id,
                    photo=data["photo"],
                    caption=data.get("html_caption") or data.get("caption"),
                    parse_mode="HTML"
                )
            elif msg_type == "video":
                await bot.send_video(
                    chat_id=user_id,
                    video=data["video"],
                    caption=data.get("html_caption") or data.get("caption"),
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=data.get("html") or data.get("text"),
                    parse_mode="HTML"
                )
            sent += 1
            
        except Exception as e:
            error_msg = str(e).lower()
            # Detect blocked/deactivated users
            if any(x in error_msg for x in ['blocked', 'deactivated', 'user is deactivated', 
                                             'bot was blocked', 'chat not found', 'user not found',
                                             'forbidden', 'kicked']):
                blocked += 1
            else:
                failed += 1
            logger.debug(f"Broadcast failed for {user_id}: {e}")
        
        # Update progress at intervals
        if (i + 1) % update_interval == 0 or i == total - 1:
            progress = round((i + 1) / total * 100, 1)
            elapsed = time.time() - start_time
            
            # Calculate ETA
            if i > 0:
                rate = (i + 1) / elapsed  # users per second
                remaining = total - (i + 1)
                eta_seconds = remaining / rate if rate > 0 else 0
                
                if eta_seconds > 3600:
                    eta_str = f"{int(eta_seconds // 3600)}s {int((eta_seconds % 3600) // 60)}d"
                elif eta_seconds > 60:
                    eta_str = f"{int(eta_seconds // 60)}d {int(eta_seconds % 60)}s"
                else:
                    eta_str = f"{int(eta_seconds)}s"
            else:
                eta_str = "hisoblanyapti..."
            
            try:
                await progress_msg.edit_text(
                    f"📢 <b>Broadcast jarayonda...</b>\n\n"
                    f"📋 Turi: {msg_type_display}\n"
                    f"👥 Jami: <b>{total:,}</b> ta user\n\n"
                    f"📊 Progress: {i+1:,}/{total:,} ({progress}%)\n"
                    f"✅ Yuborildi: {sent:,}\n"
                    f"❌ Xato: {failed:,}\n"
                    f"🚫 Bloklangan: {blocked:,}\n\n"
                    f"⏱ Qolgan vaqt: ~{eta_str}",
                    parse_mode="HTML"
                )
            except:
                pass
        
        # Adaptive rate limiting
        # Telegram allows ~30 msg/sec, we use 25 to be safe
        await asyncio.sleep(0.04)  # ~25 messages per second
    
    # Calculate final stats
    elapsed_total = time.time() - start_time
    if elapsed_total > 3600:
        time_str = f"{int(elapsed_total // 3600)} soat {int((elapsed_total % 3600) // 60)} daqiqa"
    elif elapsed_total > 60:
        time_str = f"{int(elapsed_total // 60)} daqiqa {int(elapsed_total % 60)} soniya"
    else:
        time_str = f"{int(elapsed_total)} soniya"
    
    success_rate = round(sent / max(total, 1) * 100, 1)
    
    # Update broadcast record
    await broadcast_repo.update_broadcast(
        broadcast.id,
        sent_count=sent,
        failed_count=failed + blocked,
        status="completed"
    )
    
    # Final detailed result
    await progress_msg.edit_text(
        f"✅ <b>Xabar yuborish tugallandi!</b>\n\n"
        f"📋 <b>Yuborish turi:</b> {msg_type_display}\n"
        f"👥 <b>Barcha foydalanuvchilar:</b> {total:,} ta\n\n"
        f"📊 <b>Natijalar:</b>\n"
        f"├ ✅ Muvaffaqiyatli: <b>{sent:,}</b> ta\n"
        f"├ ❌ Muvaffaqiyatsiz: <b>{failed:,}</b> ta\n"
        f"└ 🚫 Bloklangan: <b>{blocked:,}</b> ta\n\n"
        f"📈 <b>Muvaffaqiyatli darajasi:</b> {success_rate}%\n"
        f"⏱ <b>Sarflangan vaqt:</b> {time_str}\n\n"
        f"💡 <i>Bloklangan userlar botni bloklaganlar yoki akkauntlari o'chirilganlar.</i>",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    
    # Cleanup
    del broadcast_data[callback.from_user.id]


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel broadcast"""
    if not is_admin(callback.from_user.id):
        return
    
    await state.clear()
    if callback.from_user.id in broadcast_data:
        del broadcast_data[callback.from_user.id]
    
    await show_admin_panel(callback.message, edit=True)
    await safe_callback_answer(callback,"❌ Bekor qilindi")


@router.callback_query(F.data == "broadcast:history")
async def broadcast_history(callback: CallbackQuery, session: AsyncSession):
    """Show broadcast history"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    broadcast_repo = BroadcastRepository(session)
    broadcasts = await broadcast_repo.get_last_broadcasts(10)
    
    if not broadcasts:
        text = "📋 <b>Broadcast tarixi</b>\n\nHali broadcast yuborilmagan."
    else:
        text = "📋 <b>Oxirgi 10 ta broadcast:</b>\n\n"
        for b in broadcasts:
            status_emoji = "✅" if b.status == "completed" else "🔄" if b.status == "running" else "⏳"
            text += (
                f"{status_emoji} #{b.id} | "
                f"👥 {b.sent_count}/{b.total_users} | "
                f"📅 {b.created_at.strftime('%d.%m %H:%M')}\n"
            )
    
    await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await safe_callback_answer(callback)


# ==================== REQUIRED CHANNELS ====================

def _channels_admin_text(channels: list) -> str:
    n = len(channels)
    text = f"""📣 <b>Majburiy obuna kanallari</b> ({n}/5)

Foydalanuvchi botdan foydalanishi uchun <b>barcha faol</b> kanal va guruhlarga a'zo bo'lishi kerak.

✅ — faol  |  ❌ — nofaol
"""
    if not channels:
        text += "\n<i>Hali kanal qo'shilmagan</i>"
    return text


@router.callback_query(F.data == "admin:channels")
async def admin_channels(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Manage required channels"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    await safe_callback_answer(callback)
    
    channel_repo = ChannelRepository(session)
    channels = await channel_repo.get_all_channels()
    text = _channels_admin_text(channels)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_channels_keyboard(channels),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "channel:add_limit")
async def channel_add_limit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    await safe_callback_answer(callback,"Maksimal 5 ta majburiy kanal/guruh. Avval birini o'chiring.", show_alert=True)


@router.callback_query(F.data == "channel:add")
async def channel_add(callback: CallbackQuery, state: FSMContext):
    """Majburiy kanal/guruhni @username orqali qo'shish"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    await safe_callback_answer(callback)
    
    await state.clear()
    await state.set_state(AdminStates.waiting_channel_username)
    await callback.message.edit_text(
        "➕ <b>Majburiy kanal/guruh qo'shish</b>\n\n"
        "Ochiq kanal yoki guruh <b>@username</b> ni yuboring (@ bilan yoki @ siz):\n"
        "Masalan: <code>@kanal</code>\n\n"
        "⚠️ Bot ushbu chatda <b>admin</b> bo'lishi kerak.\n"
        "⚠️ Maksimal <b>5 ta</b> majburiy obuna.",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_channel_username, F.text)
async def receive_channel_username(message: Message, bot: Bot, state: FSMContext, session: AsyncSession):
    """Receive channel username and add"""
    if not is_admin(message.from_user.id):
        return
    
    username = message.text.strip().replace("@", "").replace("https://t.me/", "")
    
    try:
        chat = await bot.get_chat(f"@{username}")
        
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.answer(
                "❌ Bot bu chatda admin emas!\n"
                "Avval botni admin qiling.",
                reply_markup=get_admin_back_keyboard()
            )
            await state.clear()
            return
        
        invite_link: Optional[str] = None
        try:
            invite_link = await bot.export_chat_invite_link(chat.id)
        except Exception:
            try:
                full = await bot.get_chat(chat.id)
                invite_link = getattr(full, "invite_link", None)
            except Exception:
                invite_link = None
        
        channel_repo = ChannelRepository(session)
        try:
            await channel_repo.add_channel(
                channel_id=chat.id,
                channel_username=username,
                channel_title=chat.title or username,
                invite_link=invite_link,
            )
        except MaxRequiredChannelsError:
            await message.answer(
                "❌ Maksimal 5 ta majburiy kanal. Avval birini o'chiring.",
                reply_markup=get_admin_back_keyboard(),
            )
            await state.clear()
            return
        
        await state.clear()
        safe_title = html_decoration.quote(chat.title or username)
        await message.answer(
            f"✅ Qo'shildi!\n\n"
            f"📢 {safe_title}\n"
            f"<code>{chat.id}</code>\n@{html_decoration.quote(username)}",
            reply_markup=get_admin_back_keyboard(),
            parse_mode="HTML",
        )
        
    except Exception as e:
        logger.exception("Error adding channel by username")
        await message.answer(
            "❌ Kanalni qo'shib bo'lmadi.\n\n"
            "Tekshiring: @username to'g'rimi, bot chatda adminmi.\n"
            "Agar xatolik davom etsa, serverda <code>pip install -r requirements.txt</code> "
            "(aiogram yangilanishi) qiling.",
            reply_markup=get_admin_back_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()


@router.callback_query(F.data.startswith("channel:toggle:"))
async def channel_toggle(callback: CallbackQuery, session: AsyncSession):
    """Toggle channel active status"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    row_id = int(callback.data.split(":")[2])
    
    channel_repo = ChannelRepository(session)
    channel = await channel_repo.toggle_channel_by_row_id(row_id)
    
    if channel:
        status = "faollashtirildi ✅" if channel.is_active else "o'chirildi ❌"
        await safe_callback_answer(callback,f"Kanal {status}")
    else:
        await safe_callback_answer(callback, "❌ Topilmadi", show_alert=True)
    
    channels = await channel_repo.get_all_channels()
    await callback.message.edit_text(
        _channels_admin_text(channels),
        reply_markup=get_channels_keyboard(channels),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("channel:delete:"))
async def channel_delete(callback: CallbackQuery, session: AsyncSession):
    """Delete channel"""
    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback,"❌ Ruxsat yo'q", show_alert=True)
        return
    
    row_id = int(callback.data.split(":")[2])
    
    channel_repo = ChannelRepository(session)
    success = await channel_repo.remove_channel_by_row_id(row_id)
    
    if success:
        await safe_callback_answer(callback,"🗑 O'chirildi")
    else:
        await safe_callback_answer(callback,"❌ Topilmadi", show_alert=True)
    
    channels = await channel_repo.get_all_channels()
    await callback.message.edit_text(
        _channels_admin_text(channels),
        reply_markup=get_channels_keyboard(channels),
        parse_mode="HTML",
    )


# ==================== ADMIN REPLY MENU (pastdagi tugmalar) ====================


@router.message(
    F.from_user.id.in_(settings.ADMIN_IDS),
    F.text.in_(ADMIN_MAIN_REPLY_TEXTS),
    ~StateFilter(
        AdminStates.waiting_broadcast_text,
        AdminStates.waiting_broadcast_photo,
        AdminStates.waiting_broadcast_count,
        AdminStates.waiting_channel_username,
    ),
)
async def admin_main_reply_menu(message: Message, session: AsyncSession):
    """Admin panel pastdagi reply tugmalari (faqat ADMIN_IDS, FSM kiritish holatida emas)."""
    label = (message.text or "").strip()
    admin_repo = AdminRepository(session)

    if label == ADMIN_REPLY_BTN_STATS:
        stats = await admin_repo.get_stats()
        text = f"""📊 <b>Bot Statistikasi</b>

👥 <b>Foydalanuvchilar:</b>
├ Jami: <b>{stats['total_users']}</b>
├ Username'i borlar: <b>{stats['users_with_username']}</b>
├ Faol (24 soat): <b>{stats['active_24h']}</b>
├ Faol (7 kun): <b>{stats['active_7d']}</b>
└ Faol (30 kun): <b>{stats['active_30d']}</b>

🆕 <b>Yangi userlar:</b>
├ Bugun: <b>{stats['new_today']}</b>
└ Shu hafta: <b>{stats['new_this_week']}</b>

📥 <b>Yuklashlar:</b>
├ Jami: <b>{stats['total_downloads']}</b>
└ Bugun: <b>{stats['downloads_today']}</b>

🎵 <b>Shazam:</b>
└ Jami: <b>{stats['total_shazams']}</b>
"""
        await message.answer(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
        return

    if label == ADMIN_REPLY_BTN_CACHE:
        cache_text = await build_full_cache_stats_html(session)
        await message.answer(
            cache_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode="HTML",
        )
        return

    if label == ADMIN_REPLY_BTN_USERS:
        text = """👥 <b>Foydalanuvchilar analitikasi</b>

Quyidagi parametrlar bo'yicha ma'lumot olishingiz mumkin:
"""
        await message.answer(text, reply_markup=get_users_keyboard(), parse_mode="HTML")
        return

    if label == ADMIN_REPLY_BTN_BROADCAST:
        text = """📢 <b>Broadcast - Xabar yuborish</b>

Xabar turini tanlang:
• 📝 <b>Matn</b> - faqat matn xabari
• 🖼 <b>Media + Matn</b> - rasm yoki video + caption

Yuborish usulini tanlang:
• 👥 <b>Hammaga</b> - barcha userlarga
• 🔢 <b>N ta userga</b> - belgilangan songa

💡 <i>HTML formatlash qo'llab-quvvatlanadi</i>
"""
        await message.answer(text, reply_markup=get_broadcast_keyboard(), parse_mode="HTML")
        return

    if label == ADMIN_REPLY_BTN_CHANNELS:
        channel_repo = ChannelRepository(session)
        channels = await channel_repo.get_all_channels()
        text = _channels_admin_text(channels)
        await message.answer(
            text,
            reply_markup=get_channels_keyboard(channels),
            parse_mode="HTML",
        )


# ==================== SUBSCRIPTION CHECK ====================


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot, session: AsyncSession, db_user: User):
    """Check subscription callback"""
    is_subscribed, not_subscribed = await check_user_subscription(bot, callback.from_user.id, session)
    
    if is_subscribed:
        await safe_callback_answer(callback, "✅ Obuna tasdiqlandi!")
        lang = normalize_language_code(db_user.language_code)
        await callback.message.delete()
        await callback.message.answer(
            "✅ Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin.",
            reply_markup=get_main_menu_keyboard(lang)
        )
    else:
        await safe_callback_answer(callback,
            "❌ Siz hali barcha kanallarga obuna bo'lmagansiz!",
            show_alert=True
        )
