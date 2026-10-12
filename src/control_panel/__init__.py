"""Full-screen terminal control panel for running the bot locally.

Start it with ``python -X utf8 -m src.control_panel`` (``run_bot.bat`` does).
Only the standard library, ``psutil`` and ``rich`` are used, so the panel never
imports the bot itself and is safe to open while the bot is running.
"""
