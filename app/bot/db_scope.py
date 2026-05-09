"""Ikki bot bir bazada: har bir polling task uchun qaysi users/tarix jadvallari ishlatilishini belgilaydi."""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Optional, Type


@dataclass(frozen=True)
class BotDbScope:
    user_model: Type[Any]
    download_model: Type[Any]
    music_model: Type[Any]
    broadcast_model: Type[Any]


_scopes_ready = False
OXANG_SCOPE: BotDbScope
TARONJA_SCOPE: BotDbScope

_scope_ctx: ContextVar[Optional[BotDbScope]] = ContextVar("bot_db_scope")


def _init_scopes() -> None:
    global _scopes_ready, OXANG_SCOPE, TARONJA_SCOPE
    if _scopes_ready:
        return
    from app.database.models import (
        User,
        Download,
        MusicRecognition,
        BroadcastMessage,
        UserTaronja,
        DownloadTaronja,
        MusicRecognitionTaronja,
        BroadcastMessageTaronja,
    )

    OXANG_SCOPE = BotDbScope(User, Download, MusicRecognition, BroadcastMessage)
    TARONJA_SCOPE = BotDbScope(
        UserTaronja,
        DownloadTaronja,
        MusicRecognitionTaronja,
        BroadcastMessageTaronja,
    )
    _scopes_ready = True


def get_scope() -> BotDbScope:
    _init_scopes()
    try:
        s = _scope_ctx.get()
    except LookupError:
        return OXANG_SCOPE
    return s if s is not None else OXANG_SCOPE


def scope_token(scope: BotDbScope) -> Token:
    _init_scopes()
    return _scope_ctx.set(scope)


def reset_scope(token: Token) -> None:
    _scope_ctx.reset(token)


_init_scopes()
