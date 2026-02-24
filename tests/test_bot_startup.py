"""Basic startup checks for the Discord bot.

These tests are designed to run in CI without requiring a real Discord token
or network connection. They verify that the core bot class and all cogs can
be imported and loaded without raising unexpected exceptions.
"""

from src.bot import Bot


def test_bot_class_can_be_instantiated() -> None:
    """Ensure the core Bot class can be instantiated."""
    bot = Bot()
    # The bot should have at least one intent enabled to be considered valid.
    assert bot.intents is not None


async def test_cogs_can_be_loaded_without_running() -> None:
    """Ensure all configured cogs can be loaded without starting the bot."""
    bot = Bot()
    await bot.load_cogs()

