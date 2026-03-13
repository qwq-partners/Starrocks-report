"""Tests for Telegram notifier (unit tests without actual API calls)."""

from src.distribution.telegram_notifier import TelegramNotifier


def test_is_configured_true():
    n = TelegramNotifier(bot_token="fake_token", chat_id="12345")
    assert n.is_configured is True


def test_is_configured_false_no_token():
    n = TelegramNotifier(bot_token="", chat_id="12345")
    assert n.is_configured is False


def test_is_configured_false_no_chat_id():
    n = TelegramNotifier(bot_token="fake_token", chat_id="")
    assert n.is_configured is False


def test_escape_html():
    assert TelegramNotifier._escape_html('<b>test</b>') == '&lt;b&gt;test&lt;/b&gt;'
    assert TelegramNotifier._escape_html('A & B') == 'A &amp; B'


def test_split_message_short():
    chunks = TelegramNotifier._split_message("short message")
    assert len(chunks) == 1
    assert chunks[0] == "short message"


def test_split_message_long():
    # Create a message longer than 4096
    long_msg = "\n".join(f"Line {i}: " + "x" * 50 for i in range(100))
    assert len(long_msg) > 4096
    chunks = TelegramNotifier._split_message(long_msg)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 4096


async def test_send_message_unconfigured():
    n = TelegramNotifier(bot_token="", chat_id="")
    result = await n.send_message("test")
    assert result is False
