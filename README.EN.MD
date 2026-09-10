<div align="center">

# Nova Store

**A production-ready Telegram commerce bot with a web admin panel and always-on VPS deployment.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-powered-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![GitHub](https://img.shields.io/badge/GitHub-samkaren12%2FTelegramshopbot-181717?logo=github&logoColor=white)](https://github.com/samkaren12/Telegramshopbot)

[فارسی](README.fa.md) · [Main README](README.md)

</div>

Nova Store is a complete foundation for selling digital and physical products through Telegram. It combines an `aiogram 3` bot, SQLite persistence, a FastAPI web panel, an Ubuntu installer, optional HTTPS, and systemd-based 24/7 operation.

## Table of Contents

- [Highlights](#highlights)
- [Feature Matrix](#feature-matrix)
- [Requirements](#requirements)
- [Run Locally](#run-locally)
- [Deploy to Ubuntu VPS](#deploy-to-ubuntu-vps)
- [HTTPS and SSL](#https-and-ssl)
- [Operations](#operations)
- [Security](#security)
- [Project Layout](#project-layout)

## Highlights

- Telegram storefront powered by `aiogram 3` and SQLite
- Product, inventory, price, image, and bank-card management
- Cart, amount calculation, support, and broadcast messaging
- Web admin panel with a temporary 15-minute login
- One-command Ubuntu installation and multi-bot management
- Persistent systemd services with boot-time startup and crash recovery
- Numeric, colored server control center available through `novastore`
- Optional Nginx reverse proxy and Let’s Encrypt certificates

## Feature Matrix

| Area | Capability | Status |
| --- | --- | --- |
| Storefront | Digital and physical products | Ready |
| Commerce | Cart and total calculation | Ready |
| Payments | Card-to-card payment instructions | Ready |
| Administration | Products, inventory, cards, and broadcasts | Ready |
| Web panel | Dashboard, products, cards, and menu settings | Ready |
| Authentication | Temporary 15-minute owner login | Ready |
| Deployment | Ubuntu installer and SSH deployment helper | Ready |
| Reliability | systemd, boot startup, and crash restart | Ready |
| HTTPS | Nginx and Let’s Encrypt integration | Optional |
| Server operations | Numeric `novastore` control center | Ready |

## Requirements

- Ubuntu 22.04 or 24.04 for VPS deployment
- Python 3.11+ for local development
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- The numeric Telegram owner ID (`OWNER_ID`)
- A domain pointing to the server IP if HTTPS is required

## Run Locally

Create and activate a virtual environment:

```bash
python -m venv .venv
```

PowerShell:

```powershell
.venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set at least `BOT_TOKEN` and `OWNER_ID` in `.env`, then start the bot:

```bash
python main.py
```

For remote panel access, use `WEB_HOST=0.0.0.0` and set `WEB_PUBLIC_URL` to the address users will reach. Do not expose the panel publicly without HTTPS or a VPN.

## Deploy to Ubuntu VPS

The public repository is already configured in the installer, so no repository URL prompt is required:

```bash
curl -fsSL https://raw.githubusercontent.com/samkaren12/Telegramshopbot/main/install.sh -o /tmp/novastore-install.sh
sudo bash /tmp/novastore-install.sh
```

The installer asks for:

1. Bot name
2. Shop name
3. Numeric `OWNER_ID`
4. Telegram Bot API token
5. Public panel URL
6. HTTPS domain, or an empty value to skip SSL
7. Let’s Encrypt email when a domain is provided

It installs dependencies, clones the project, creates a protected `.env`, registers a systemd service, and starts the bot immediately.

## HTTPS and SSL

Before installation, point your DNS record to the server:

```text
panel.example.com -> SERVER_IP
```

When a domain is provided, the installer automatically installs Nginx and Certbot, configures a reverse proxy, obtains a Let’s Encrypt certificate, and redirects HTTP to HTTPS. The panel is then available at:

```text
https://panel.example.com/control
```

Leave the domain empty to run the panel over HTTP on `WEB_PORT`.

## Operations

Run the numeric Nova Store control center:

```bash
sudo novastore
```

The menu provides:

```text
1) Status     2) Restart    3) Logs
4) Update     5) Add bot    6) Remove bot
7) Uninstall  0) Exit
```

Direct commands:

```bash
novastore list
novastore status main
novastore logs main
novastore restart main
novastore update main
novastore add
novastore remove main
novastore uninstall
```

Every bot runs as a systemd service with `Restart=always` and `enable --now`, so it continues running after SSH disconnects, server reboots, and application crashes. The internal service name is `telegramshop-main.service`; `novastore` is the public management command.

For lower-level diagnostics:

```bash
sudo systemctl status telegramshop-main.service --no-pager
sudo journalctl -u telegramshop-main.service -n 100 -f
```

## Security

- Never commit `.env`, bot tokens, SSH private keys, passwords, or databases.
- Put the web panel behind HTTPS or a VPN.
- Prefer SSH keys over password authentication.
- Rotate a bot token immediately if it is exposed through BotFather.
- The `uninstall` action is destructive and requires numeric confirmation.

## Project Layout

| File | Purpose |
| --- | --- |
| `main.py` | Bot entry point and service startup |
| `handlers.py` | Telegram message and callback handlers |
| `db.py` | SQLite data layer |
| `web_panel.py` | Web admin API and routes |
| `web_ui.py` | Web panel interface |
| `install.sh` | Ubuntu installer, SSL, and systemd setup |
| `deploy.py` | SSH-based VPS deployment helper |
| `.env.example` | Safe configuration template |

## License and Contributions

This repository does not currently include a license file. Add a license before accepting external contributions or redistributing the project.

Issues and improvements are welcome through the repository:

https://github.com/samkaren12/Telegramshopbot
