"""
Majburiy obuna tekshiruvi (barcha faol kanallarga a'zo bo'lish).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import ChannelRepository

if TYPE_CHECKING:
    from app.database.models import RequiredChannel

logger = logging.getLogger(__name__)


def is_user_member_of_chat(member) -> bool:
    """True agar foydalanuvchi chat a'zosi (yoki cheklovlangan lekin a'zo)."""
    status = member.status
    if status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        return False
    if status == ChatMemberStatus.RESTRICTED:
        return bool(getattr(member, "is_member", False))
    return True


async def check_user_subscription(
    bot: Bot, user_id: int, session: AsyncSession
) -> tuple[bool, list["RequiredChannel"]]:
    """
    Barcha faol majburiy kanallarga obuna bo'lganligini tekshiradi.
    Qaytaradi: (hammasiga obuna, obuna bo'lmagan kanallar ro'yxati).
    """
    channel_repo = ChannelRepository(session)
    channels = await channel_repo.get_active_channels()

    if not channels:
        return True, []

    not_subscribed: list = []

    for channel in channels:
        try:
            member = await bot.get_chat_member(channel.channel_id, user_id)
            if not is_user_member_of_chat(member):
                not_subscribed.append(channel)
        except Exception as e:
            logger.debug(
                "Obuna tekshiruvi xatolik: channel_id=%s user=%s err=%s",
                channel.channel_id,
                user_id,
                e,
            )
            not_subscribed.append(channel)

    return len(not_subscribed) == 0, not_subscribed
