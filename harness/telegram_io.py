"""Telegram in and out. The only code that talks to Telegram."""
import asyncio
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from . import config as C
from .agent_process import AgentProcess
from .calendar import make_calendar
from .core import Harness
from .store import Store

log = logging.getLogger("lifecoach")


class TelegramTransport:
    def __init__(self, bot, chat_id: int):
        self.bot, self.chat_id = bot, chat_id

    async def send(self, text, buttons=None):
        markup = None
        if buttons:
            rows, row = [], []
            for label, data in buttons:  # two short buttons per row, long ones alone
                button = InlineKeyboardButton(label, callback_data=data)
                if len(label) > 12:
                    if row:
                        rows.append(row)
                        row = []
                    rows.append([button])
                    continue
                row.append(button)
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            markup = InlineKeyboardMarkup(rows)
        msg = await self.bot.send_message(self.chat_id, text, reply_markup=markup)
        return str(msg.message_id)

    async def clear_buttons(self, message_id):
        try:
            await self.bot.edit_message_reply_markup(self.chat_id, int(message_id), reply_markup=None)
        except TelegramError:
            pass  # already gone, or too old to edit

    async def typing(self):
        try:
            await self.bot.send_chat_action(self.chat_id, ChatAction.TYPING)
        except TelegramError:
            pass

    async def send_file(self, path: Path, caption=""):
        with open(path, "rb") as f:
            await self.bot.send_document(self.chat_id, f, caption=caption)


def build_app(settings: C.Settings) -> Application:
    async def post_init(app: Application):
        if not settings.allowed_user_id:
            log.warning("ALLOWED_USER_ID isn't set: the bot will only tell people their user ID.")
            return
        store = Store(settings.data_dir)
        agent = AgentProcess(Path(settings.agents_root), settings.agent, settings.state_root)
        harness = Harness(settings, TelegramTransport(app.bot, settings.allowed_user_id),
                          make_calendar(settings.calendar, store.calendar_dir, settings.timezone), agent, store)
        app.bot_data["harness"] = harness
        await harness.start()
        log.info("Harness running with agent %s", agent.version)

        async def clock():
            while True:
                await asyncio.sleep(C.TICK_SECONDS)
                try:
                    await harness.tick()
                except Exception:
                    log.exception("tick failed")
        app.bot_data["clock"] = asyncio.create_task(clock())

    async def post_shutdown(app: Application):
        harness = app.bot_data.get("harness")
        if harness:
            await harness.agent.stop()

    async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not settings.allowed_user_id:
            await update.effective_message.reply_text(
                f"Your Telegram user ID is {user.id}. Put ALLOWED_USER_ID={user.id} in .env and restart the bot.")
            return
        if user.id != settings.allowed_user_id or update.effective_chat.type != "private":
            return  # everyone else is ignored
        harness: Harness = ctx.bot_data["harness"]
        text = update.effective_message.text or ""
        if text.startswith("/"):
            cmd, _, args = text[1:].partition(" ")
            await harness.on_command(cmd.split("@")[0].lower(), args)
        else:
            await harness.on_text(text)

    async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if update.effective_user.id != settings.allowed_user_id:
            return
        await ctx.bot_data["harness"].on_button(query.data)

    async def on_error(update, ctx: ContextTypes.DEFAULT_TYPE):
        log.error("Error handling an update", exc_info=ctx.error)

    app = (Application.builder().token(settings.telegram_token)
           .post_init(post_init).post_shutdown(post_shutdown).concurrent_updates(False).build())
    app.add_handler(MessageHandler(filters.TEXT, on_message))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_error_handler(on_error)
    return app
