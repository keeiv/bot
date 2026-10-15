<div align="center">

**EN** | [CN](../README.md)

<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../assets/logo/bot-logo-wordmark-light.png">
    <img src="../assets/logo/bot-logo-wordmark.png" alt="BOT." width="320">
  </picture>
</h1>

**A Discord bot that guards the door, greets your guests, and tidies up after itself.**

Anti-spam and moderation, welcome messages and auto roles, temporary voice channels, tickets, mini-games and achievements, osu! / HoYoLAB / GitHub integrations, file tools,<br>
plus a web dashboard where you can set most of it up.

[![CI](https://github.com/keeiv/bot/actions/workflows/ci.yml/badge.svg)](https://github.com/keeiv/bot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB)
![discord.py](https://img.shields.io/badge/discord.py-2.7-5865F2)
![License](https://img.shields.io/badge/license-AGPL--3.0--only-F99549)

[Website & dashboard](https://botweb.shizune.life) ·
[Features](#features) ·
[Quick start](#quick-start) ·
[Development guide](DEVELOPMENT.md) ·
[Documentation](Home.md)

</div>

> [!NOTE]
> This is a translation of the [Chinese README](../README.md), which remains the primary version. Pages marked (Chinese) are only available in Chinese for now.

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Terminal console (Windows)](#terminal-console-windows)
- [Permissions](#permissions)
- [Data and storage](#data-and-storage)
- [Project layout](#project-layout)
- [License](#license)

## Features

| Area | What it does | Main commands |
| --- | --- | --- |
| Protection & moderation | Seven spam detectors, automatic escalation, blacklist and appeals, reports, message and audit logs | `/anti_spam` `/blacklist` `/appeal` `/clear` `/kick` `/ban` `/mute` `/warn` |
| Welcoming members | Welcome message templates, auto roles, age guard | `/welcome` `/auto_role` `/age_guard` |
| Server services | Tickets, temporary voice, giveaways, roles and emojis, a server settings panel | `>>>ticket` `/temp_voice` `/giveaway` `/role` `/emoji` `/settings` |
| Games & achievements | Two two-player mini-games, 18 achievements | `/deep-sea-oxygen` `/russian-roulette` `/achievements` |
| Account integrations | osu!, HoYoLAB / Miyoushe, GitHub repository notifications | `/osu` `/mhy` `/repo_watch` `/repo_track` |
| Tools | File conversion and compression (NovaGrid), message translation | `/convert` `/compress` `/usage` `Translate message` |
| Language | English and Chinese interface, set per server and per user | `/language` |

Details for each area are below.

> [!TIP]
> Type `/help` in Discord for a multi-page guide. Welcome messages, anti-spam, tickets and more can also be set up on the [web dashboard](https://botweb.shizune.life).

### Protection & moderation

**Anti-spam**: the `/anti_spam` group has 11 subcommands (`setup`, `flood`, `duplicate`, `mention`, `link`, `raid`, `escalation`, `whitelist`, `lockdown_off`, `status`, `mute_duration`).

| Detector | Default threshold | Default action |
| --- | --- | --- |
| Flood | More than 10 messages in 10 seconds | Mute |
| Duplicates | The same content 4 times in 30 seconds | Delete message |
| Mass mentions | 8 mentions in one message | Mute |
| Links | 5 links in 15 seconds (Discord invites are deleted on sight) | Delete message |
| Emoji | 20 emojis in one message | Delete message |
| Line breaks | 30 line breaks in one message | Delete message |
| Raid | 10 members joining within 30 seconds | Lock channel |

Six actions are available: warn, delete message, mute, kick, ban and lock channel. If a member racks up 3 violations within 10 minutes (the default; adjustable with `escalation`), the response goes one level above the harshest action triggered this time (up to locking the channel). Flood, duplicate, mention, link and raid thresholds are adjustable, and you can whitelist roles and channels; emoji and line-break detection use fixed defaults for now.

**Blacklist and appeals**: `/blacklist add` / `remove` / `list` / `info` manage the local blacklist and look users up on the CatHome API (developer only). Blocked users can file an appeal with `/appeal` and check on it with `/appeal_status`; a developer reviews each one. Appeals carry over the original block reason, so there is no form to fill in. Accepting an appeal only removes the local entry; a block on the CatHome API has to be lifted by CatHome. See the [blacklist guide](../BLACKLIST_GUIDE.md) (Chinese).

**Reports**: right-click a message → Apps → `Report message`. Reports go to the channel chosen with `/report_channel set`, where admins can mute, ban or warn straight from the buttons (each opens a form). `/report_channel status` shows the current setup.

**Logs**: `/message_log_settings` picks a channel for logging edits and single-message deletions by non-bot members, as long as the bot has the message cached. Scope and limits are covered in the [message log guide](../MESSAGE_LOGGER_README.md) (Chinese). The audit log records members joining and leaving, voice activity, role and nickname changes, and channels being created, deleted or edited.

**Moderation commands**: `/clear` (bulk-delete messages), `/kick`, `/ban`, `/mute`, `/warn`.

### Welcoming members

- **Welcome message**: `/welcome setup` sets the channel and template, with the placeholders `{user}` (mention), `{username}` (display name), `{server}`, `{count}` (member count) and `{created_at}` (server creation date). `/welcome templates` lists the built-in templates, `/welcome preview` shows a preview, and `/welcome disable` turns it off.
- **Auto role**: `/auto_role setup` / `list` / `remove` manage the roles given to new members when they join.
- **Age guard**: spots messages where someone states an underage age (a number followed by 歲, Chinese for "years old"), then removes the adult role and adds a role of your choice, depending on settings. `/age_guard set_adult_role`, `set_punishment_role`, `toggle`, `status`.

### Server services

- **Tickets**: `>>>ticket setup #channel @role` creates the panel. When a member presses "Open ticket", the bot opens a private thread and pings the staff role. Tickets can be closed with or without a reason; the thread is then locked and kept for the record.
- **Temporary voice**: `/temp_voice setup` sets the trigger channel, category and name template (default `{username}'s room`, or `{username}的家` in Chinese); `status` shows the setup and `disable` turns it off. Anyone who joins the trigger channel gets a voice channel of their own, which is deleted once everyone has left. Owners manage their channel with `envc*` prefix commands:

  | Type | Commands |
  | --- | --- |
  | Basics | `envc*name`, `envc*limit`, `envc*bitrate` |
  | Privacy | `envc*hide` / `unhide`, `envc*lock` / `unlock` |
  | Members | `envc*kick`, `envc*ban` / `unban` |
  | Ownership | `envc*transfer`, `envc*claim` |

- **Giveaways**: `/giveaway start` (durations like `1d12h30m`), `end` to finish early, `reroll`, `list`. Members enter with a button, and winners are drawn automatically when time runs out.
- **Roles and emojis**: `/role assign` / `remove`, `/emoji get` / `upload`.
- **Settings panel**: `/settings` lets you view and change the log channel, report channel, anti-spam and welcome message through menus and buttons.
- **Bot appearance**: `/bot_appearance name` changes the bot's nickname in the server, and `reset` restores the default avatar or banner. Once an [AI image review node](image-review.md) (Chinese) is set up, images for `avatar` / `banner` are checked by three local models in turn; if they can't reach a verdict, or no node is set up, a developer reviews the image by hand.

### Games & achievements

- `/deep-sea-oxygen`: a turn-based co-op game for two, with shared oxygen and items.
- `/russian-roulette`: a two-player duel with chips and items.
- 18 achievements (6 common, 7 uncommon, 5 rare) covering chat, games and social activity. `/achievements` shows your progress, `/achievement_codex` lists them all, and `/achievement_info` shows the details of one.

### Account integrations

- **osu!**: `/osu bind` / `unbind` to link your account, `/osu best` and `/osu recent` for scores, `/user_info_osu` for a player profile.
- **HoYoLAB / Miyoushe**: supports Genshin Impact, Honkai: Star Rail, Zenless Zone Zero and Honkai Impact 3rd (endgame challenge records such as Spiral Abyss cover the first three only), on both global and China servers.
  - Account: `/mhy bind` (your cookie is stored encrypted), `unbind`, `status`, `tutorial` (how to get your cookie).
  - Daily: `/mhy toggle_autosignin` for automatic daily check-in, `checkin` to check in manually, `notes` for real-time notes, `redeem` for redemption codes.
  - Records: `/mhy stats` for game stats, `/mhy abyss` for challenge records.
- **GitHub**: `/repo_watch set` / `status` / `disable` follow commits on any repository; `/repo_track add` / `remove` / `status` follow new commits and newly opened PRs on keeiv/bot (merges are not reported). Requests use `GITHUB_TOKEN`, a shared cache and ETags, and back off for the retry period when rate-limited.

### Tools

**File tools**

| Command | What it does |
| --- | --- |
| `/convert` | Converts still images to PNG / JPG / WebP / PDF, and flat UTF-8 tables between CSV / TSV / JSON |
| `/compress` | Compresses images with the NovaGrid engine, with adjustable quality and maximum size; no points are charged if the file doesn't shrink |
| `/usage` | Shows your tier, weekly usage and a chart of the last three hours |
| `/ir` | Shows your reset tickets and their usage history |

- All tools are free; points only exist to meter usage. Everyone starts on the Free. tier and moves up to Run. after 30 days of use, Dash. after 60, Grow. after 120 and Ultra. after 180.
- The website's `/tools` page and Discord draw from the same quota. Batch processing is available on the website or with `!convert [format]`, within your tier's limits.
- Jobs can be offloaded to another computer on the local network. See [file tools](file-tools.md), [the NovaGrid engine](novagrid.md) and [LAN worker nodes](tool-worker.md) (all Chinese).

**Translation**: right-click a message → Apps → `Translate message`, with 14 target languages: Traditional Chinese, Simplified Chinese, English, Japanese, Korean, French, German, Spanish, Russian, Portuguese, Thai, Vietnamese, Indonesian and Arabic.

### Language (English / Chinese)

- Slash command names are always in English; descriptions, options and context menu items follow the Discord client language.
- Replies, menus, buttons and forms come in both English and Chinese. In servers the bot is in, the server language is used. In DMs, or when you use the bot as a personal app in a server it hasn't joined, your personal setting is used, or your Discord client language if you haven't set one.
- New servers default to English and get a `#bot-guide` channel with a language menu (requires Manage Server). Servers that added the bot before this feature shipped stay in Chinese.
- `/language` switches the server language in servers the bot is in (requires Manage Server), or your personal language in DMs and personal-app use.

> [!NOTE]
> - Not translated yet: web dashboard API responses (kept in Chinese for compatibility with the website), local command-line tools, and logs.
> - These commands are flagged in code for personal-app use: `/help`, `/language`, `/osu`, `/user_info_osu`, `/mhy`, `/convert`, `/compress`, `/usage`, `/ir`, `Translate message`. They only show up once User Install is enabled in the Discord Developer Portal.

### Web dashboard

At [botweb.shizune.life](https://botweb.shizune.life), sign in with Discord and pick a server you manage. From there you can configure the welcome message, anti-spam, age guard, temporary voice, tickets, GitHub notifications and audit log, run setup checks, deploy panels, and see the bot's live status with 24-hour / 7-day history. The site talks to the bot's local API over a Cloudflare Tunnel and never connects to the database directly.

### Other

- `/help` for multi-page help, `/user_info` for a user's profile (including their osu! link and achievement progress), `/server_info` for server details.
- Command errors are handled in one place: missing permissions, cooldowns, bad arguments and the like get a reply in the user's language, and unexpected errors are logged to a designated error channel and the terminal.
- Developer only: `/dev-status` (also `!dev-status`), the `>>>info` developer panel, and the file-tool test tier and reset commands (see [file tools](file-tools.md)).

## Quick start

Requires Python 3.10 or later (production runs 3.13).

> [!IMPORTANT]
> **Use JSON compatibility mode (`STORAGE_BACKEND=json`) for a fresh install.** MySQL mode won't start until a data migration has been completed, and the migration tool only works from existing JSON / SQLite data under `data/`; there is no way yet to start from an empty MySQL database. Production uses Oracle MySQL 8.4.

**Developer quick install**: `install.py` pulls the project from GitHub and sets up a basic development environment. It checks your system, fetches the code (as a ZIP if git isn't installed), creates a virtual environment, installs dependencies, creates an empty `.env`, and finally checks that every package imports. It relies only on the Python standard library.

```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/keeiv/bot/main/install.py -OutFile install.py
python install.py
```

```bash
# Linux / macOS
curl -O https://raw.githubusercontent.com/keeiv/bot/main/install.py
python3 install.py
```

Common options: `--dir` sets the install folder, `--test` runs the full test suite afterwards, `--no-dev` skips development tools, `--check` only checks the environment, `--plain` prints plain text, and `--yes` skips the confirmation prompt. Run `python install.py --help` for the full list.

> [!NOTE]
> Running it again on an existing install updates it and leaves `.env` and the virtual environment alone. The installer never asks for or writes secrets, so you'll need to add `DISCORD_TOKEN` to `.env` yourself.

To install manually:

**1. Install**

```bash
python -m venv .venv
```

Activate the virtual environment (Windows PowerShell: `.\.venv\Scripts\Activate.ps1`; Linux / macOS: `source .venv/bin/activate`), then install:

```bash
python -m pip install -r requirements.txt
```

**2. Configure `.env`** (in the project root; not tracked by Git)

```env
DISCORD_TOKEN=
OSU_CLIENT_ID=
OSU_CLIENT_SECRET=
GITHUB_TOKEN=
BLACKLIST_API_KEY=
GENSHIN_ENCRYPTION_KEY=
STORAGE_BACKEND=json
STORAGE_ROOT=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
BOT_API_ENABLED=false
BOT_API_HOST=127.0.0.1
BOT_API_PORT=8080
BOT_API_SECRET=
```

> [!WARNING]
> `.env` holds your Discord token, API keys, encryption key and database password. It's already in `.gitignore`. Never commit it or paste it anywhere public.

> [!CAUTION]
> If encrypted accounts already exist, you must keep the original `GENSHIN_ENCRYPTION_KEY`. If it's missing, the service refuses to start rather than overwrite it with a new key. A fresh install generates and saves this key for you.

<details>
<summary>About these settings</summary>

- `STORAGE_ROOT` can point to the project's absolute path. If it's unset, the working directory is used, so launch from the project root.
- `STORAGE_BACKEND` accepts only `json` or `mysql` (leaving the line out means `json`, but an empty value is not allowed). Switch to `mysql` only after the migration in step 3. Create the MySQL database and a dedicated account beforehand; the account needs permission to create tables and to read and write data. In JSON mode, `MYSQL_*` can stay empty.
- To let the website connect, set `BOT_API_ENABLED=true` and a `BOT_API_SECRET` of at least 32 characters.

</details>

**3. Switch to MySQL by migrating existing data (one-time; skip this in JSON mode)**

> [!WARNING]
> Stop the bot before running the migration.

```bash
python -m src.migrate_storage
```

The tool backs up the JSON / SQLite sources, then verifies them along with every document and table. It writes a verification marker only if every check passes. Original files are kept, and the migration stops if it finds conflicting data at the destination. On Windows, backups go to `%LOCALAPPDATA%\NewBotMySQL\backups`. MySQL mode looks for this marker at startup.

**4. Start**

```bash
python -m src.main
```

## Terminal console (Windows)

```bash
python -X utf8 -m src.control_panel
```

Start, stop and restart the bot, check its status, database connection and logs, run dependency installs, tests and format checks, and configure LAN nodes, all from one screen. For how to use it and how it handles database instances, see the [development guide](DEVELOPMENT.md#終端機控制台) (Chinese).

## Permissions

| Feature | Required permission |
| --- | --- |
| `/clear` | Manage Messages |
| `/kick`, `/ban` | Kick Members, Ban Members |
| `/mute`, `/warn` | Timeout Members |
| `/message_log_settings`, `/bot_appearance`, `>>>ticket setup` | Administrator |
| `/anti_spam`, `/age_guard`, `/giveaway`, `/settings` | Administrators only by default (Discord's default command permission; servers can change it under Integrations) |
| `/report_channel set` / `status`, `/repo_watch set` / `disable` | Manage Server |
| Changing a server's language via `/language` or `#bot-guide` (checking the current language or changing your personal language needs no permission) | Manage Server |
| `/welcome setup` / `disable`, `/temp_voice`, `/repo_track add` / `remove` | Manage Channels |
| `/role`, `/auto_role setup` / `remove` | Manage Roles |
| `/emoji upload` | Manage Emojis |
| `/blacklist`, developer commands | Developer only |
| Everything else, such as games, achievements, osu!, HoYoLAB, translation, file tools, `/repo_watch status`, `/repo_track status`, `/welcome templates` / `preview` | None |

## Data and storage

| Location | Contents |
| --- | --- |
| MySQL `documents` | Complete JSON documents keyed by their original file path, with SHA-256 checksums: settings, achievements, blacklist, osu! links, encrypted accounts and more |
| MySQL `samples`, `sample_health`, `cache_entries`, `metrics`, `audit_logs` | Operational history, caches, metrics and audit data |
| MySQL `tool_*` (`tool_users`, `tool_jobs` and 5 more) | File-tool quotas, tiers and job history |
| MySQL `migration_sources`, `migration_state` | Copies of migration sources and the verification marker |
| `data/logs/runtime.log` | Runtime log, written through a background queue so logging never stalls the Discord heartbeat |
| `.env` | Connection details and the encryption key; not tracked by Git |

> [!NOTE]
> MySQL mode never writes back to the old JSON / SQLite files and never falls back to them if the database fails. The kept originals are just a snapshot from migration time.

The local MySQL instance listens on `127.0.0.1:3307` and stores data in `%LOCALAPPDATA%\NewBotMySQL\data`. With `start-mysql.ps1` set up, starting the bot also starts the local database if it isn't already running (this doesn't apply to remote databases).

> [!NOTE]
> Times: Discord logs and the interface show UTC+8; external data such as GitHub and some diagnostics use UTC; internally, Unix timestamps are used.

## Project layout

```text
src/
  main.py               Entry point
  bot.py                Bot class, global blacklist check, automatic cog loading
  cogs/core/            Error handling, settings, logs, blacklist, appearance, language, dashboard API
  cogs/features/        Anti-spam, tickets, temp voice, giveaways, integrations, file tools and more
  cogs/games/           Mini-games
  services/             Business logic and persistence, plus NovaGrid, LAN workers and image review
  locales/              English and Chinese message catalogs
  utils/                Storage, background jobs, translation and shared helpers
  control_panel/        Windows terminal console
services/               Standalone external integrations (GitHub client, osu! API)
tests/                  Automated tests (CI: Python 3.10–3.13 and MySQL 8.4)
docs/                   Documentation
```

<details>
<summary>Main dependencies</summary>

Versions are pinned in one place, `pyproject.toml`. `requirements.txt` installs what the bot needs to run; `requirements-dev.txt` adds the development tools.

| Package | Used for |
| --- | --- |
| discord.py | Discord gateway, commands, events and interactive components |
| aiohttp | Async HTTP client and the dashboard API |
| PyMySQL | MySQL connections |
| Pillow | Image conversion and NovaGrid compression |
| ossapi | osu! API v2 |
| genshin, cryptography | HoYoLAB / Miyoushe integration and cookie encryption |
| deep-translator | Message translation |
| psutil | System resource monitoring |
| python-dotenv | Loading `.env` |
| rich | Terminal console UI |

</details>

Want to contribute? Start with the [contributing guide](CONTRIBUTING.en.md) and the [development guide](DEVELOPMENT.md) (Chinese). For installation, configuration, deployment and troubleshooting, see the [documentation index](Home.md).

## License

Copyright (c) 2026 Keeiv.

Licensed under the **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**. See [LICENSE](../LICENSE) for the full text and [NOTICE](../NOTICE) for copyright notices. You're free to copy, modify, distribute and use it commercially, but if you run a modified version as a network service, your users must be able to get the complete corresponding source for that version at no cost. The source code contains no deployment secrets or user data.

> [!NOTE]
> The license change does not apply retroactively: releases already published under MIT keep that license, and the old notice is kept in [LICENSES/MIT-legacy.txt](../LICENSES/MIT-legacy.txt). Third-party components keep their own licenses and copyright notices.
