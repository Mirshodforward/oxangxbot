from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.enums import ChatMemberStatus
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import async_session
from app.database.repositories import UserRepository, ChannelRepository
from app.config import settings


class DatabaseMiddleware(BaseMiddleware):
    """Middleware to inject database session into handlers"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """Middleware to register/update user on each request"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if user and not user.is_bot:
            session: AsyncSession = data.get("session")
            if session:
                user_repo = UserRepository(session)
                db_user, is_new = await user_repo.get_or_create(
                    user_id=user.id,
                    username=user.username,
                    # Don't override user's saved language preference
                    language_code=None
                )
                
                data["db_user"] = db_user
                data["is_new_user"] = is_new
                data["lang"] = db_user.language_code or "uz"
        
        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Simple throttling middleware to prevent spam"""
    
    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.user_last_request: Dict[int, float] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        import time
        
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if user:
            user_id = user.id
            current_time = time.time()
            last_request = self.user_last_request.get(user_id, 0)
            
            if current_time - last_request < self.rate_limit:
                # Too fast, skip this request
                if isinstance(event, CallbackQuery):
                    await event.answer("⏳ Iltimos, biroz kuting...", show_alert=False)
                return None
            
            self.user_last_request[user_id] = current_time
        
        return await handler(event, data)


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware to check required channel subscriptions"""
    
    # Commands/callbacks that should bypass subscription check
    BYPASS_COMMANDS = {"/start", "/language"}
    BYPASS_CALLBACKS = {"set_lang:", "check_subscription", "admin:"}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get user from event
        user = None
        should_check = True
        
        if isinstance(event, Message):
            user = event.from_user
            # Bypass for certain commands
            if event.text:
                for cmd in self.BYPASS_COMMANDS:
                    if event.text.startswith(cmd):
                        should_check = False
                        break
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            # Bypass for certain callbacks
            if event.data:
                for cb in self.BYPASS_CALLBACKS:
                    if event.data.startswith(cb):
                        should_check = False
                        break
        
        # Skip check for admins
        if user and user.id in settings.ADMIN_IDS:
            should_check = False
        
        if not should_check or not user:
            return await handler(event, data)
        
        # Check subscription
        session: AsyncSession = data.get("session")
        bot: Bot = data.get("bot")
        
        if session and bot:
            channel_repo = ChannelRepository(session)
            channels = await channel_repo.get_active_channels()
            
            if channels:
                not_subscribed = []
                
                for channel in channels:
                    try:
                        member = await bot.get_chat_member(channel.channel_id, user.id)
                        if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.RESTRICTED]:
                            not_subscribed.append(channel)
                    except Exception:
                        not_subscribed.append(channel)
                
                if not_subscribed:
                    # User not subscribed - show subscription message
                    from app.bot.keyboards import get_subscription_keyboard
                    
                    text = (
                        "📢 <b>Majburiy obuna</b>\n\n"
                        "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n"
                    )
                    
                    keyboard = get_subscription_keyboard(not_subscribed)
                    
                    if isinstance(event, Message):
                        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("❌ Avval kanallarga obuna bo'ling!", show_alert=True)
                    
                    return None
        
        return await handler(event, data)
