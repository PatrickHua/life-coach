"""The Telegram layer, with a fake bot (no network)."""
from types import SimpleNamespace

from harness import config as C
from harness.telegram_io import TelegramTransport, build_app


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))
        return SimpleNamespace(message_id=len(self.sent))


async def test_button_layout():
    bot = FakeBot()
    t = TelegramTransport(bot, 42)
    mid = await t.send("Pick", [("Red", "b1"), ("Green", "b2"), ("Blue", "b3"), ("A much longer label", "b4")])
    assert mid == "1"
    rows = bot.sent[0][2].inline_keyboard
    assert [[b.text for b in row] for row in rows] == [["Red", "Green"], ["Blue"], ["A much longer label"]]
    assert rows[0][0].callback_data == "b1"


def handler(app, cls_name):
    return next(h for h in app.handlers[0] if type(h).__name__ == cls_name).callback


def update(user_id, text, chat_type="private"):
    replies = []

    async def reply_text(msg):
        replies.append(msg)
    msg = SimpleNamespace(text=text, reply_text=reply_text)
    return SimpleNamespace(effective_user=SimpleNamespace(id=user_id), effective_message=msg,
                           effective_chat=SimpleNamespace(type=chat_type)), replies


class RecordingHarness:
    def __init__(self):
        self.calls = []

    async def on_text(self, text):
        self.calls.append(("text", text))

    async def on_command(self, cmd, args=""):
        self.calls.append(("cmd", cmd, args))


async def test_tells_unknown_user_their_id_until_configured():
    app = build_app(C.Settings(telegram_token="123:abc", allowed_user_id=0))
    upd, replies = update(777, "hi")
    await handler(app, "MessageHandler")(upd, SimpleNamespace(bot_data={}))
    assert "777" in replies[0] and "ALLOWED_USER_ID=777" in replies[0]


async def test_allowlist_and_routing():
    app = build_app(C.Settings(telegram_token="123:abc", allowed_user_id=5))
    h = RecordingHarness()
    ctx = SimpleNamespace(bot_data={"harness": h})
    on_message = handler(app, "MessageHandler")
    await on_message(update(6, "intruder")[0], ctx)
    await on_message(update(5, "in a group", chat_type="group")[0], ctx)
    assert h.calls == []
    await on_message(update(5, "hello")[0], ctx)
    await on_message(update(5, "/Goal@my_bot now")[0], ctx)
    assert h.calls == [("text", "hello"), ("cmd", "goal", "now")]
