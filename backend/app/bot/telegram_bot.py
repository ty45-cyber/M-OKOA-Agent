"""
Telegram Bot — primary user interface for M-Okoa Agent.

Architecture:
- Each incoming message is routed to AgentService.handle_message()
- Conversation history is maintained per chat_id in Redis (last 20 turns)
- User identity is resolved via telegram_chat_id → users.telegram_chat_id
- Unlinked users receive a registration deep-link
- All Telegram errors are caught — the bot never crashes on a bad message

Commands:
  /start    — welcome message + registration link
  /link     — link Telegram to an existing M-Okoa account
  /reset    — clear conversation history
  /tills    — list tills and current balances
  /help     — show available commands
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.redis_client import get_redis
from app.models.agent_session import SessionSource
from app.models.user import User
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService
from app.services.daraja_service import get_daraja_service
from app.services.till_service import TillService

logger = structlog.get_logger(__name__)
settings = get_settings()

# Conversation history TTL: 2 hours of inactivity clears history
HISTORY_TTL_SECONDS = 7200
MAX_HISTORY_TURNS = 20


# ── Redis helpers ─────────────────────────────────────────────

def _history_key(chat_id: int) -> str:
    return f"tg:history:{chat_id}"


async def _get_history(chat_id: int) -> list[dict]:
    redis = get_redis()
    raw = await redis.get(_history_key(chat_id))
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


async def _append_history(chat_id: int, role: str, content: str) -> None:
    redis = get_redis()
    history = await _get_history(chat_id)
    history.append({"role": role, "content": content})
    # Keep last N turns
    history = history[-MAX_HISTORY_TURNS:]
    await redis.setex(
        _history_key(chat_id),
        HISTORY_TTL_SECONDS,
        json.dumps(history),
    )


async def _clear_history(chat_id: int) -> None:
    redis = get_redis()
    await redis.delete(_history_key(chat_id))


# ── User resolution ───────────────────────────────────────────

async def _resolve_user(
    chat_id: int,
    db: AsyncSession,
) -> User | None:
    """Fetch the M-Okoa user linked to this Telegram chat_id."""
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(
            User.telegram_chat_id == chat_id,
            User.is_active == True,
        )
    )
    return result.scalar_one_or_none()


# ── Typing indicator context ──────────────────────────────────

async def _send_typing(bot: Bot, chat_id: int) -> None:
    try:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass


# ── Registration prompt ───────────────────────────────────────

async def _prompt_registration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Sent to users who haven't linked their Telegram to an M-Okoa account.
    Provides a deep-link to the web app registration page.
    """
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📱 Sajili / Register",
            url=f"https://mokoa.co.ke/register?tg_chat_id={update.effective_chat.id}",
        )],
        [InlineKeyboardButton(
            "🔗 Link existing account",
            callback_data=f"link:{update.effective_chat.id}",
        )],
    ])

    await update.message.reply_text(
        "🌟 *Karibu M-Okoa Agent!*\n\n"
        "Mimi ni msaidizi wako wa fedha za biashara Kenya.\n"
        "Ninaweza kukusaidia:\n"
        "• Angalia balances za M-Pesa tills zako zote\n"
        "• Lipa bili za KPLC, maji na kadhalika\n"
        "• Hamisha pesa kwa SACCO au benki\n"
        "• Kuhesabu kodi ya KRA automatically\n\n"
        "Bado hujasajili. Bonyeza kitufe hapa chini kuanza. 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


# ── Command Handlers ──────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message."""
    chat_id = update.effective_chat.id

    async with AsyncSessionFactory() as db:
        user = await _resolve_user(chat_id, db)

    if not user:
        await _prompt_registration(update, context)
        return

    first_name = user.full_name.split()[0]
    await update.message.reply_text(
        f"🤝 *Habari {first_name}!*\n\n"
        f"M-Okoa Agent yako iko tayari.\n"
        f"Niambie — unataka kufanya nini leo?\n\n"
        f"Unaweza kuandika kwa Kiswahili, Sheng au Kiingereza. 😊\n\n"
        f"_Mfano: 'Uko na pesa ngapi kwa till zote?' au 'Lipa KPLC 1000'_",
        parse_mode=ParseMode.MARKDOWN,
    )
    logger.info("telegram.start", user_id=user.id, chat_id=chat_id)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset — clear conversation history."""
    chat_id = update.effective_chat.id
    await _clear_history(chat_id)
    await update.message.reply_text(
        "🔄 Mazungumzo yamefutwa. Tunaanza upya!\n"
        "Niambie — unataka nini?"
    )
    logger.info("telegram.history_reset", chat_id=chat_id)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — show available commands."""
    await update.message.reply_text(
        "📋 *Amri zinazopatikana:*\n\n"
        "/start — Anzisha mazungumzo\n"
        "/tills — Angalia tills na balances\n"
        "/reset — Futa historia ya mazungumzo\n"
        "/help — Amri hizi\n\n"
        "*Mifano ya maswali:*\n"
        "• _'Uko na pesa ngapi kwa till zote?'_\n"
        "• _'Lipa KPLC 1000 kama balance iko juu ya 5k'_\n"
        "• _'Hamisha 3000 kwa 0712345678'_\n"
        "• _'Nionyeshe transactions za wiki iliyopita'_\n"
        "• _'Kodi yangu ya KRA ni ngapi mwezi huu?'_",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_tills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tills — list tills with cached balances."""
    chat_id = update.effective_chat.id

    async with AsyncSessionFactory() as db:
        user = await _resolve_user(chat_id, db)
        if not user:
            await _prompt_registration(update, context)
            return

        await _send_typing(update.get_bot(), chat_id)

        till_service = TillService(db, get_daraja_service())
        try:
            tills = await till_service.list_tills(user.id)
            if not tills:
                await update.message.reply_text(
                    "Huna till yoyote iliyosajiliwa.\n"
                    "Ongeza till kwenye https://mokoa.co.ke/tills"
                )
                return

            lines = ["💰 *Tills zako:*\n"]
            for t in tills:
                balance_str = (
                    f"KES {t.last_known_balance_kes:,.2f}"
                    if t.last_known_balance_kes is not None
                    else "Balance haijulikani"
                )
                lines.append(f"• *{t.display_name}*\n  {t.till_number} — {balance_str}")

            await update.message.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as exc:
            logger.error("telegram.tills_error", error=str(exc))
            await update.message.reply_text(
                "Imeshindwa kupata tills. Jaribu tena baadaye."
            )


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /link <phone> <password> — link Telegram to existing account.
    Usage: /link +254712345678 MyPassword1
    """
    chat_id = update.effective_chat.id
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            "Tumia: `/link <nambari_ya_simu> <nenosiri>`\n"
            "Mfano: `/link +254712345678 Password1`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    phone, password = args[0], args[1]

    # Delete the command message immediately — passwords in chat are a risk
    try:
        await update.message.delete()
    except Exception:
        pass

    async with AsyncSessionFactory() as db:
        auth_service = AuthService(db)
        from app.schemas.auth import LoginRequest

        try:
            login_result = await auth_service.login(
                LoginRequest(phone_number=phone, password=password),
                ip_address="telegram",
            )
            await auth_service.bind_telegram_chat(
                user_id=int(login_result.user.public_id[:8], 16) if False else
                await _get_user_id_from_public_id(db, login_result.user.public_id),
                telegram_chat_id=chat_id,
                ip_address="telegram",
            )
            await db.commit()
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"✅ *Akaunti imefungwa!*\n"
                    f"Karibu {login_result.user.full_name.split()[0]}!\n\n"
                    f"Sasa unaweza kuuliza M-Okoa Agent chochote. 🎉"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info(
                "telegram.account_linked",
                user_public_id=login_result.user.public_id,
                chat_id=chat_id,
            )
        except Exception as exc:
            logger.warning("telegram.link_failed", error=str(exc), chat_id=chat_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "❌ Imeshindwa kufunga akaunti.\n"
                    "Hakikisha nambari na nenosiri ni sahihi.\n"
                    "Jaribu tena: `/link <simu> <nenosiri>`"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )


async def _get_user_id_from_public_id(db: AsyncSession, public_id: str) -> int:
    from sqlalchemy import select
    result = await db.execute(
        select(User.id).where(User.public_id == public_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ValueError(f"User not found for public_id: {public_id}")
    return row


# ── Message Handler ───────────────────────────────────────────

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Core message handler — routes every non-command text message to the agent.

    Flow:
    1. Resolve user from chat_id
    2. Show typing indicator
    3. Load conversation history from Redis
    4. Run AgentService.handle_message()
    5. Persist turn to Redis history
    6. Reply with agent response
    """
    chat_id = update.effective_chat.id
    user_message = update.message.text

    if not user_message or not user_message.strip():
        return

    async with AsyncSessionFactory() as db:
        user = await _resolve_user(chat_id, db)

        if not user:
            await _prompt_registration(update, context)
            return

        await _send_typing(context.bot, chat_id)

        history = await _get_history(chat_id)

        try:
            agent_service = AgentService(db, get_daraja_service())
            response = await agent_service.handle_message(
                user_id=user.id,
                user_name=user.full_name,
                message_text=user_message.strip(),
                session_source=SessionSource.telegram,
                conversation_history=history,
            )
            await db.commit()

        except Exception as exc:
            logger.error(
                "telegram.agent_error",
                error=str(exc),
                user_id=user.id,
                chat_id=chat_id,
            )
            response = (
                "😔 Samahani, kuna tatizo la kiufundi.\n"
                "Jaribu tena baadaye au wasiliana na msaada: support@mokoa.co.ke"
            )

    # Persist conversation turn to Redis
    await _append_history(chat_id, "user", user_message.strip())
    await _append_history(chat_id, "assistant", response)

    # Telegram message length limit is 4096 chars
    if len(response) <= 4096:
        await update.message.reply_text(response)
    else:
        # Split long responses into chunks at paragraph boundaries
        chunks = _split_response(response, max_length=4000)
        for chunk in chunks:
            await update.message.reply_text(chunk)
            await asyncio.sleep(0.3)

    logger.info(
        "telegram.message_handled",
        user_id=user.id,
        chat_id=chat_id,
        response_length=len(response),
    )


# ── Callback query handler (inline buttons) ───────────────────

async def handle_callback_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data: str = query.data or ""

    if data.startswith("link:"):
        await query.edit_message_text(
            "Tumia amri hii kujiunga na akaunti yako:\n\n"
            "`/link <nambari_ya_simu> <nenosiri>`\n\n"
            "Mfano: `/link +254712345678 Password1`",
            parse_mode=ParseMode.MARKDOWN,
        )


# ── Response splitter ─────────────────────────────────────────

def _split_response(text: str, max_length: int = 4000) -> list[str]:
    """Split a long response at paragraph boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current = ""

    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 <= max_length:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks or [text[:max_length]]


# ── Bot factory ───────────────────────────────────────────────

def build_telegram_application() -> Application:
    """
    Build and configure the Telegram bot application.
    Called once at startup from the FastAPI lifespan.
    """
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    # Commands
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("reset", cmd_reset))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("tills", cmd_tills))
    application.add_handler(CommandHandler("link", cmd_link))

    # Inline keyboard callbacks
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # All other text messages → agent
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    return application