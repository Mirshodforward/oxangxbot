"""
Admin handlers - Full admin panel for bot management
"""
import logging
import asyncio
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.database.repositories import (
    AdminRepository, ChannelRepository, BroadcastRepository, UserRepository
)
from app.bot.keyboards import (
    get_admin_main_keyboard,
    get_broadcast_keyboard,
    get_channels_keyboard,
    get_subscription_keyboard,
    get_broadcast_confirm_keyboard,
    get_admin_back_keyboard,
    get_users_keyboard,
    get_main_menu_keyboard
)
from app.bot.locales import get_text, normalize_language_code

logger = logging.getLogger(__name__)
router = Router(name="admin")


class AdminStates(StatesGroup):
    """FSM states for admin operations"""
    waiting_broadcast_text = State()
    waiting_broadcast_photo = State()
    waiting_broadcast_count = State()
    waiting_channel_username = State()


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
• 🖼 <b>Rasm + Matn</b> - rasm va caption

Yuborish usulini tanlang:
• 👥 <b>Hammaga</b> - barcha userlarga
• 🔢 <b>N ta userga</b> - belgilangan songa
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
    """Start photo broadcast"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_photo)
    broadcast_data[callback.from_user.id] = {"type": "photo"}
    
    await callback.message.edit_text(
        "🖼 <b>Rasm + Caption yuboring</b>\n\nRasm yuboring, caption qo'shing.",
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
    broadcast_data[message.from_user.id]["html_caption"] = message.html_text or ""
    
    admin_repo = AdminRepository(session)
    user_count = len(await admin_repo.get_all_user_ids())
    
    await state.clear()
    
    text = f"""📢 <b>Broadcast tasdiqlash</b>

🖼 <b>Rasm yuklandi</b>
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
    """Confirm and start broadcast"""
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
    
    # Create broadcast record
    broadcast_repo = BroadcastRepository(session)
    broadcast = await broadcast_repo.create_broadcast(
        admin_id=callback.from_user.id,
        message_text=data.get("text") or data.get("caption"),
        photo_file_id=data.get("photo"),
        total_users=total
    )
    
    await broadcast_repo.update_broadcast(broadcast.id, status="running")
    
    # Send progress message
    progress_msg = await callback.message.edit_text(
        f"📢 <b>Broadcast jarayonda...</b>\n\n"
        f"📊 Progress: 0/{total} (0%)\n"
        f"✅ Yuborildi: 0\n"
        f"❌ Xato: 0",
        parse_mode="HTML"
    )
    
    sent = 0
    failed = 0
    
    for i, user_id in enumerate(user_ids):
        try:
            if data.get("type") == "photo":
                await bot.send_photo(
                    chat_id=user_id,
                    photo=data["photo"],
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
            failed += 1
            logger.debug(f"Broadcast failed for {user_id}: {e}")
        
        # Update progress every 50 users
        if (i + 1) % 50 == 0 or i == total - 1:
            progress = round((i + 1) / total * 100, 1)
            try:
                await progress_msg.edit_text(
                    f"📢 <b>Broadcast jarayonda...</b>\n\n"
                    f"📊 Progress: {i+1}/{total} ({progress}%)\n"
                    f"✅ Yuborildi: {sent}\n"
                    f"❌ Xato: {failed}",
                    parse_mode="HTML"
                )
            except:
                pass
        
        # Rate limiting
        await asyncio.sleep(0.035)  # ~28 messages per second
    
    # Update broadcast record
    await broadcast_repo.update_broadcast(
        broadcast.id,
        sent_count=sent,
        failed_count=failed,
        status="completed"
    )
    
    # Final result
    await progress_msg.edit_text(
        f"✅ <b>Broadcast yakunlandi!</b>\n\n"
        f"📊 Jami: {total}\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Xato: {failed}\n"
        f"📈 Muvaffaqiyat: {round(sent/max(total,1)*100, 1)}%",
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

@router.callback_query(F.data == "admin:channels")
async def admin_channels(callback: CallbackQuery, session: AsyncSession):
    """Manage required channels"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    channel_repo = ChannelRepository(session)
    channels = await channel_repo.get_all_channels()
    
    text = """📣 <b>Majburiy obuna kanallari</b>

Foydalanuvchilar botdan foydalanish uchun quyidagi kanallarga obuna bo'lishi kerak:

✅ - faol
❌ - nofaol
"""
    
    if not channels:
        text += "\n<i>Hali kanal qo'shilmagan</i>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_channels_keyboard(channels),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "channel:add")
async def channel_add(callback: CallbackQuery, state: FSMContext):
    """Add new channel"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_channel_username)
    
    await callback.message.edit_text(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Kanal username ni kiriting (@ bilan yoki @ siz):\n"
        "Masalan: <code>@kanal_nomi</code> yoki <code>kanal_nomi</code>\n\n"
        "⚠️ Bot kanalda admin bo'lishi kerak!",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.waiting_channel_username, F.text)
async def receive_channel_username(message: Message, bot: Bot, state: FSMContext, session: AsyncSession):
    """Receive channel username and add"""
    if not is_admin(message.from_user.id):
        return
    
    username = message.text.strip().replace("@", "").replace("https://t.me/", "")
    
    try:
        # Get channel info
        chat = await bot.get_chat(f"@{username}")
        
        # Check if bot is admin
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.answer(
                "❌ Bot bu kanalda admin emas!\n"
                "Avval botni kanalga admin qiling.",
                reply_markup=get_admin_back_keyboard()
            )
            await state.clear()
            return
        
        # Add channel
        channel_repo = ChannelRepository(session)
        await channel_repo.add_channel(
            channel_id=chat.id,
            channel_username=username,
            channel_title=chat.title
        )
        
        await state.clear()
        await message.answer(
            f"✅ Kanal qo'shildi!\n\n"
            f"📢 {chat.title}\n"
            f"@{username}",
            reply_markup=get_admin_back_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error adding channel: {e}")
        await message.answer(
            f"❌ Xatolik: {str(e)}\n\n"
            "Kanal topilmadi yoki bot admin emas.",
            reply_markup=get_admin_back_keyboard()
        )
        await state.clear()


@router.callback_query(F.data.startswith("channel:toggle:"))
async def channel_toggle(callback: CallbackQuery, session: AsyncSession):
    """Toggle channel active status"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    channel_id = int(callback.data.split(":")[2])
    
    channel_repo = ChannelRepository(session)
    channel = await channel_repo.toggle_channel(channel_id)
    
    if channel:
        status = "faollashtirildi ✅" if channel.is_active else "o'chirildi ❌"
        await callback.answer(f"Kanal {status}")
    
    # Refresh list
    channels = await channel_repo.get_all_channels()
    await callback.message.edit_reply_markup(reply_markup=get_channels_keyboard(channels))


@router.callback_query(F.data.startswith("channel:delete:"))
async def channel_delete(callback: CallbackQuery, session: AsyncSession):
    """Delete channel"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return
    
    channel_id = int(callback.data.split(":")[2])
    
    channel_repo = ChannelRepository(session)
    success = await channel_repo.remove_channel(channel_id)
    
    if success:
        await callback.answer("🗑 Kanal o'chirildi")
    else:
        await callback.answer("❌ Kanal topilmadi", show_alert=True)
    
    # Refresh list
    channels = await channel_repo.get_all_channels()
    
    text = """📣 <b>Majburiy obuna kanallari</b>

Foydalanuvchilar botdan foydalanish uchun quyidagi kanallarga obuna bo'lishi kerak:

✅ - faol
❌ - nofaol
"""
    
    if not channels:
        text += "\n<i>Hali kanal qo'shilmagan</i>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_channels_keyboard(channels),
        parse_mode="HTML"
    )


# ==================== SUBSCRIPTION CHECK ====================

async def check_user_subscription(bot: Bot, user_id: int, session: AsyncSession) -> tuple[bool, list]:
    """
    Check if user is subscribed to all required channels
    Returns (is_subscribed, list of channels user needs to join)
    """
    channel_repo = ChannelRepository(session)
    channels = await channel_repo.get_active_channels()
    
    if not channels:
        return True, []
    
    not_subscribed = []
    
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel.channel_id, user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.RESTRICTED]:
                not_subscribed.append(channel)
        except Exception as e:
            logger.debug(f"Error checking subscription for channel {channel.channel_id}: {e}")
            # If we can't check, assume not subscribed
            not_subscribed.append(channel)
    
    return len(not_subscribed) == 0, not_subscribed


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
