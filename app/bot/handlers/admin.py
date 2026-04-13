"""
Admin handlers - Full admin panel for bot management
"""
import logging
import asyncio
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.text_decorations import html_decoration
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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
    get_admin_main_keyboard,
    get_broadcast_keyboard,
    get_channels_keyboard,
    get_channel_add_kind_keyboard,
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
    waiting_channel_link = State()


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
    
    if edit and hasattr(message, 'edit_text'):
        await message.edit_text(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    """Back to admin panel"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.clear()
    await show_admin_panel(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin:refresh")
async def admin_refresh(callback: CallbackQuery, session: AsyncSession):
    """Refresh admin panel with updated stats"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    admin_repo = AdminRepository(session)
    stats = await admin_repo.get_stats()
    
    text = f"""🔐 <b>Admin Panel</b>

📊 <b>Tezkor statistika:</b>
├ 👥 Jami userlar: <b>{stats['total_users']}</b>
├ 🟢 Faol (24s): <b>{stats['active_24h']}</b>
├ 📥 Bugungi yuklashlar: <b>{stats['downloads_today']}</b>
└ 🆕 Bugun yangi: <b>{stats['new_today']}</b>
"""
    
    await callback.message.edit_text(text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")
    await callback.answer("✅ Yangilandi")


# ==================== STATISTICS ====================

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession):
    """Show detailed statistics"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    admin_repo = AdminRepository(session)
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
    
    await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


# ==================== CACHE STATISTICS ====================

@router.message(Command("cache"))
async def cmd_cache_stats(message: Message, session: AsyncSession):
    """Show cache statistics - how many points saved"""
    if not is_admin(message.from_user.id):
        return
    
    stats_repo = CacheStatsRepository(session)
    yt_cache_repo = YouTubeCacheRepository(session)
    music_cache_repo = MusicSearchCacheRepository(session)
    cache_repo = CacheRepository(session)
    
    # Get all stats
    total_stats = await stats_repo.get_total_stats()
    today_stats = await stats_repo.get_today_stats()
    
    yt_hits = await yt_cache_repo.get_total_hits()
    yt_saved = await yt_cache_repo.get_points_saved()
    music_hits = await music_cache_repo.get_total_hits()
    media_hits = await cache_repo.get_total_hits()
    
    # Calculate totals
    total_api_calls = (
        total_stats["api_calls"]["media"] +
        total_stats["api_calls"]["music"] +
        total_stats["api_calls"]["youtube"] +
        total_stats["api_calls"]["recognize"]
    )
    
    total_cache_hits = (
        total_stats["cache_hits"]["media"] +
        total_stats["cache_hits"]["music"] +
        total_stats["cache_hits"]["youtube"] +
        total_stats["cache_hits"]["recognize"]
    )
    
    efficiency = 0
    if total_api_calls + total_cache_hits > 0:
        efficiency = (total_cache_hits / (total_api_calls + total_cache_hits)) * 100
    
    text = f"""💾 <b>Kesh Statistikasi</b>

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
    
    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "admin:cache")
async def admin_cache_stats(callback: CallbackQuery, session: AsyncSession):
    """Show cache statistics via callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    stats_repo = CacheStatsRepository(session)
    yt_cache_repo = YouTubeCacheRepository(session)
    
    total_stats = await stats_repo.get_total_stats()
    today_stats = await stats_repo.get_today_stats()
    yt_saved = await yt_cache_repo.get_points_saved()
    
    total_saved = total_stats['points_saved']
    total_spent = total_stats['points_spent']
    
    efficiency = 0
    if total_saved + total_spent > 0:
        efficiency = (total_saved / (total_saved + total_spent)) * 100
    
    text = f"""💾 <b>Kesh Statistikasi</b>

📊 <b>Bugun:</b>
├ Sarflangan: <b>{today_stats.points_spent}</b> pt
└ Tejalgan: <b>{today_stats.points_saved}</b> pt ✅

📈 <b>Jami:</b>
├ Sarflangan: <b>{total_spent}</b> points
├ Tejalgan: <b>{total_saved}</b> points 💰
└ Effektivlik: <b>{efficiency:.1f}%</b>

🎬 <b>YouTube:</b>
└ Tejalgan: <b>{yt_saved}</b> points 🔥

💡 <i>Kesh avtomatik ishlaydi!</i>
"""
    
    await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


# ==================== USERS ANALYTICS ====================

@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery):
    """Users analytics menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    text = """👥 <b>Foydalanuvchilar analitikasi</b>

Quyidagi parametrlar bo'yicha ma'lumot olishingiz mumkin:
"""
    
    await callback.message.edit_text(text, reply_markup=get_users_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("users:"))
async def users_analytics(callback: CallbackQuery, session: AsyncSession):
    """Detailed user analytics"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
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
    await callback.answer()


# ==================== BROADCAST ====================

# Store broadcast data temporarily
broadcast_data = {}


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery):
    """Broadcast menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    text = """📢 <b>Broadcast - Xabar yuborish</b>

Xabar turini tanlang:
• 📝 <b>Matn</b> - faqat matn xabari
• 🖼 <b>Media + Matn</b> - rasm yoki video + caption

Yuborish usulini tanlang:
• 👥 <b>Hammaga</b> - barcha userlarga
• 🔢 <b>N ta userga</b> - belgilangan songa

💡 <i>HTML formatlash qo'llab-quvvatlanadi</i>
"""
    
    await callback.message.edit_text(text, reply_markup=get_broadcast_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "broadcast:text")
async def broadcast_text_start(callback: CallbackQuery, state: FSMContext):
    """Start text broadcast"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_text)
    broadcast_data[callback.from_user.id] = {"type": "text"}
    
    await callback.message.edit_text(
        "📝 <b>Broadcast xabarini yuboring</b>\n\nHTMLni qo'llab-quvvatlaydi.",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:photo")
async def broadcast_photo_start(callback: CallbackQuery, state: FSMContext):
    """Start photo/video broadcast"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
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
    await callback.answer()


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
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    if callback.from_user.id not in broadcast_data:
        await callback.answer("Avval xabar turini tanlang!", show_alert=True)
        return
    
    broadcast_data[callback.from_user.id]["limit"] = None
    admin_repo = AdminRepository(session)
    user_count = len(await admin_repo.get_all_user_ids())
    
    await callback.answer(f"✅ {user_count} ta userga yuboriladi")


@router.callback_query(F.data == "broadcast:limited")
async def broadcast_limited(callback: CallbackQuery, state: FSMContext):
    """Set limited broadcast"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_count)
    
    await callback.message.edit_text(
        "🔢 <b>Nechta userga yuborilsin?</b>\n\nSon kiriting:",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


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
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    data = broadcast_data.get(callback.from_user.id)
    if not data:
        await callback.answer("❌ Xabar topilmadi", show_alert=True)
        return
    
    await callback.answer("🚀 Broadcast boshlandi...")
    
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
    await callback.answer("❌ Bekor qilindi")


@router.callback_query(F.data == "broadcast:history")
async def broadcast_history(callback: CallbackQuery, session: AsyncSession):
    """Show broadcast history"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
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
    await callback.answer()


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
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    if await state.get_state() == AdminStates.waiting_channel_link.state:
        await state.clear()
    
    channel_repo = ChannelRepository(session)
    channels = await channel_repo.get_all_channels()
    text = _channels_admin_text(channels)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_channels_keyboard(channels),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "channel:add_limit")
async def channel_add_limit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    await callback.answer("Maksimal 5 ta majburiy kanal/guruh. Avval birini o'chiring.", show_alert=True)


@router.callback_query(F.data == "channel:add")
async def channel_add(callback: CallbackQuery, state: FSMContext):
    """Kanal yoki guruh qo'shish rejimini tanlash"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.clear()
    await callback.message.edit_text(
        "➕ <b>Majburiy kanal/guruh qo'shish</b>\n\n"
        "<b>📢 Kanal</b> — faqat kanal (broadcast).\n"
        "<b>👥 Guruh</b> — guruh yoki superguruh.\n\n"
        "Yoki <b>@username</b> bilan qo'lda qo'shing (ochiq kanal/guruh).",
        reply_markup=get_channel_add_kind_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("channel:link_kind:"))
async def channel_link_kind(callback: CallbackQuery, state: FSMContext):
    """Botni admin qilib ulash (my_chat_member)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    kind = callback.data.split(":")[2]
    if kind not in ("channel", "group"):
        await callback.answer()
        return
    
    await state.set_state(AdminStates.waiting_channel_link)
    await state.update_data(link_kind=kind)
    
    if kind == "channel":
        hint = (
            "1) Kanalingizga kiring → <b>Administratorlar</b> → botni qo'shing.\n"
            "2) Botga kamida <b>foydalanuvchilarni ko'rish</b> (yoki a'zolarni boshqarish) "
            "kabi huquqlar bering — obunani tekshirish uchun kerak.\n"
            "3) Admin qilganingizdan keyin bu yerga avtomatik xabar keladi.\n\n"
            "<i>Shu bosqichni faqat siz (admin) bajarishingiz kerak.</i>"
        )
    else:
        hint = (
            "1) Guruh/superguruhga botni qo'shing va <b>admin</b> qiling.\n"
            "2) Foydalanuvchilarni ko'rish / cheklovlar bo'yicha a'zolarni boshqarish "
            "huquqlaridan keraklisini yoqing.\n"
            "3) Admin qilganingizdan keyin bu yerga avtomatik xabar keladi.\n\n"
            "<i>Shu bosqichni faqat siz (admin) bajarishingiz kerak.</i>"
        )
    
    await callback.message.edit_text(
        "🔗 <b>Botni ulash</b>\n\n" + hint,
        reply_markup=get_channel_add_kind_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer("Kanal/guruhda botni admin qiling")


@router.callback_query(F.data == "channel:add_manual")
async def channel_add_manual(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_channel_username)
    await callback.message.edit_text(
        "✏️ <b>@username bilan qo'shish</b>\n\n"
        "Ochiq kanal yoki guruh username ni yuboring (@ bilan yoki @ siz):\n"
        "Masalan: <code>@kanal</code>\n\n"
        "⚠️ Bot ushbu chatda <b>admin</b> bo'lishi kerak.\n"
        "⚠️ Maksimal <b>5 ta</b> majburiy obuna.",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.my_chat_member()
async def admin_link_required_chat(
    event: ChatMemberUpdated,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
):
    """Admin botni kanal/guruhga admin qilganda chat_id ni bazaga yozish"""
    actor = event.from_user
    if not actor or actor.id not in settings.ADMIN_IDS:
        return
    
    current = await state.get_state()
    if current != AdminStates.waiting_channel_link.state:
        return
    
    if event.new_chat_member.user.id != bot.id:
        return
    
    new_status = event.new_chat_member.status
    if new_status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        return
    
    data = await state.get_data()
    kind = data.get("link_kind")
    chat = event.chat
    ctype = chat.type
    
    if kind == "channel" and ctype != "channel":
        try:
            await bot.send_message(
                actor.id,
                "❌ Tanlov: <b>Kanal</b> — lekin bu boshqa chat turi. Qaytadan tanlang.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return
    
    if kind == "group" and ctype not in ("group", "supergroup"):
        try:
            await bot.send_message(
                actor.id,
                "❌ Tanlov: <b>Guruh</b> — lekin bu kanal yoki boshqa chat. Qaytadan tanlang.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return
    
    channel_repo = ChannelRepository(session)
    invite_link: Optional[str] = None
    try:
        invite_link = await bot.export_chat_invite_link(chat.id)
    except Exception:
        try:
            full = await bot.get_chat(chat.id)
            invite_link = getattr(full, "invite_link", None)
        except Exception:
            invite_link = None
    
    username = (chat.username or "").strip() or "-"
    title = chat.title or ("Kanal" if ctype == "channel" else "Guruh")
    
    try:
        await channel_repo.add_channel(
            channel_id=chat.id,
            channel_username=username,
            channel_title=title,
            invite_link=invite_link,
        )
    except MaxRequiredChannelsError:
        try:
            await bot.send_message(
                actor.id,
                "❌ Majburiy kanallar limiti: maksimal <b>5 ta</b>. Avval keraksizini o'chiring.",
                parse_mode="HTML",
            )
        except Exception:
            pass
        await state.clear()
        return
    
    await state.clear()
    try:
        await bot.send_message(
            actor.id,
            "✅ <b>Qo'shildi</b>\n\n"
            f"📢 {html_decoration.quote(title)}\n"
            f"<code>{chat.id}</code>\n"
            + (f"\n🔗 Havola: {html_decoration.quote(invite_link)}" if invite_link else ""),
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard(),
        )
    except Exception as e:
        logger.warning("Could not notify admin after channel link: %s", e)


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
        await message.answer(
            f"✅ Qo'shildi!\n\n"
            f"📢 {chat.title}\n"
            f"<code>{chat.id}</code>\n@{username}",
            reply_markup=get_admin_back_keyboard(),
            parse_mode="HTML",
        )
        
    except Exception as e:
        logger.error(f"Error adding channel: {e}")
        await message.answer(
            f"❌ Xatolik: {str(e)}\n\n"
            "Chat topilmadi yoki bot admin emas.",
            reply_markup=get_admin_back_keyboard()
        )
        await state.clear()


@router.callback_query(F.data.startswith("channel:toggle:"))
async def channel_toggle(callback: CallbackQuery, session: AsyncSession):
    """Toggle channel active status"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    row_id = int(callback.data.split(":")[2])
    
    channel_repo = ChannelRepository(session)
    channel = await channel_repo.toggle_channel_by_row_id(row_id)
    
    if channel:
        status = "faollashtirildi ✅" if channel.is_active else "o'chirildi ❌"
        await callback.answer(f"Kanal {status}")
    
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
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    row_id = int(callback.data.split(":")[2])
    
    channel_repo = ChannelRepository(session)
    success = await channel_repo.remove_channel_by_row_id(row_id)
    
    if success:
        await callback.answer("🗑 O'chirildi")
    else:
        await callback.answer("❌ Topilmadi", show_alert=True)
    
    channels = await channel_repo.get_all_channels()
    await callback.message.edit_text(
        _channels_admin_text(channels),
        reply_markup=get_channels_keyboard(channels),
        parse_mode="HTML",
    )


# ==================== SUBSCRIPTION CHECK ====================


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot, session: AsyncSession, db_user: User):
    """Check subscription callback"""
    is_subscribed, not_subscribed = await check_user_subscription(bot, callback.from_user.id, session)
    
    if is_subscribed:
        lang = normalize_language_code(db_user.language_code)
        await callback.message.delete()
        await callback.message.answer(
            "✅ Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin.",
            reply_markup=get_main_menu_keyboard(lang)
        )
        await callback.answer("✅ Obuna tasdiqlandi!")
    else:
        await callback.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmagansiz!",
            show_alert=True
        )
