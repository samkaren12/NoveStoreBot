from __future__ import annotations

import getpass
import ipaddress
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXCLUDED = {".git", ".venv", "__pycache__", "*.sqlite3", "*.db", ".env"}


def ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def run(command: list[str], input_text: str | None = None) -> None:
    print("$", " ".join(command))
    subprocess.run(command, input=input_text, text=True, check=True)


def archive_project(target: Path, bot_token: str, owner_id: str, server_ip: str, shop_name: str) -> None:
    with tempfile.TemporaryDirectory() as temp:
        staging = Path(temp) / "telegramshop"
        shutil.copytree(ROOT, staging, ignore=shutil.ignore_patterns(*EXCLUDED))
        (staging / ".env").write_text(
            f"BOT_TOKEN={bot_token}\nOWNER_ID={owner_id}\nDB_PATH=shop.sqlite3\n"
            f"SHOP_NAME={shop_name}\nWEB_HOST=0.0.0.0\nWEB_PORT=8080\n"
            f"WEB_PUBLIC_URL=http://{server_ip}:8080\n",
            encoding="utf-8",
        )
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in staging.rglob("*"):
                if file.is_file():
                    archive.write(file, Path("telegramshop") / file.relative_to(staging))


def remote_script(install_dir: str, bot_name: str, owner_id: str, server_ip: str) -> str:
    return textwrap.dedent(
        f"""
        set -e
        APP_ROOT={install_dir}
        BOT_NAME={bot_name}
        sudo apt-get update -y
        sudo apt-get install -y python3 python3-venv unzip
        sudo mkdir -p "$APP_ROOT/bots/$BOT_NAME"
        sudo unzip -oq /tmp/telegramshop.zip -d "$APP_ROOT/bots/$BOT_NAME"
        sudo python3 -m venv "$APP_ROOT/bots/$BOT_NAME/.venv"
        sudo "$APP_ROOT/bots/$BOT_NAME/.venv/bin/pip" install --upgrade pip
        sudo "$APP_ROOT/bots/$BOT_NAME/.venv/bin/pip" install -r "$APP_ROOT/bots/$BOT_NAME/telegramshop/requirements.txt"
        sudo cp "$APP_ROOT/bots/$BOT_NAME/telegramshop/.env" "$APP_ROOT/bots/$BOT_NAME/.env"
        sudo tee /etc/systemd/system/telegramshop-$BOT_NAME.service >/dev/null <<SERVICE
        [Unit]
        Description=Telegram Shop $BOT_NAME
        After=network-online.target
        Wants=network-online.target

        [Service]
        Type=simple
        WorkingDirectory=$APP_ROOT/bots/$BOT_NAME/telegramshop
        EnvironmentFile=$APP_ROOT/bots/$BOT_NAME/.env
        ExecStart=$APP_ROOT/bots/$BOT_NAME/.venv/bin/python main.py
        Restart=always
        RestartSec=5
        User=root

        [Install]
        WantedBy=multi-user.target
        SERVICE
        sudo systemctl daemon-reload
        sudo systemctl enable --now telegramshop-$BOT_NAME.service
        sudo tee /usr/local/bin/novastore >/dev/null <<'CLI'
        #!/usr/bin/env bash
        set -e
        ROOT={install_dir}/bots
        usage() {{ echo "novastore: list | add | remove NAME | start NAME | stop NAME | restart NAME | enable NAME | disable NAME | status NAME | logs NAME"; }}
        default_name={bot_name}
        name="${{2:-$default_name}}"
        service="telegramshop-$name.service"
        case "${{1:-list}}" in
          list) systemctl list-units 'telegramshop-*.service' --all --no-legend || true ;;
          start|stop|restart|enable|disable) sudo systemctl "$1" "$service" ;;
          status) sudo systemctl status "$service" --no-pager ;;
          logs) sudo journalctl -u "$service" -n 100 -f ;;
          add)
            read -rp "Bot name: " new_name
            read -rsp "Telegram Bot API token: " new_token; echo
            sudo mkdir -p "$ROOT/$new_name"
            sudo cp -a "$ROOT/$name/telegramshop" "$ROOT/$new_name/"
            sudo cp -a "$ROOT/$name/.venv" "$ROOT/$new_name/"
            sudo sed -i "s/^BOT_TOKEN=.*/BOT_TOKEN=$new_token/" "$ROOT/$new_name/telegramshop/.env"
            sudo sed -i "s/^WEB_PORT=.*/WEB_PORT=$((8080 + RANDOM % 1000))/" "$ROOT/$new_name/telegramshop/.env"
            sudo sed -i "s/^OWNER_ID=.*/OWNER_ID={owner_id}/" "$ROOT/$new_name/telegramshop/.env"
            sudo sed -i "s#^WEB_PUBLIC_URL=.*#WEB_PUBLIC_URL=http://{server_ip}:8080#" "$ROOT/$new_name/telegramshop/.env"
            sudo cp "$ROOT/$new_name/telegramshop/.env" "$ROOT/$new_name/.env"
            sudo sed "s/telegramshop-$name/telegramshop-$new_name/g; s#/$name/#/$new_name/#g" /etc/systemd/system/telegramshop-$name.service | sudo tee /etc/systemd/system/telegramshop-$new_name.service >/dev/null
            sudo systemctl daemon-reload; sudo systemctl enable --now telegramshop-$new_name.service
            echo "Bot $new_name added."
            ;;
          remove)
            sudo systemctl disable --now "$service" || true
            sudo rm -f "/etc/systemd/system/$service"
            sudo rm -rf "$ROOT/$name"
            sudo systemctl daemon-reload
            echo "Bot $name removed."
            ;;
          *) usage; exit 1 ;;
        esac
        CLI
        sudo chmod +x /usr/local/bin/novastore
        sudo ufw allow 8080/tcp || true
        rm -f /tmp/telegramshop.zip
        echo "Deployment complete. Use: novastore status $BOT_NAME"
        """
    )


def main() -> None:
    if os.name == "nt" and not shutil.which("ssh"):
        raise SystemExit("OpenSSH Client is required. Install it from Windows Optional Features.")
    print("\nNova Store VPS deployment\n")
    server_ip = ask("Server IP")
    ssh_user = ask("SSH username", "root")
    ssh_port = ask("SSH port", "22")
    bot_name = ask("Bot name", "main")
    shop_name = ask("Shop name", "Telegram Shop")
    owner_id = ask("Telegram owner numeric ID")
    bot_token = getpass.getpass("Telegram Bot API token: ").strip()
    install_dir = ask("Remote install directory", "/opt/telegramshop")
    if not all((server_ip, ssh_user, owner_id, bot_token)) or not owner_id.isdigit():
        raise SystemExit("Server IP, SSH username, numeric owner ID and bot token are required.")
    try:
        ipaddress.ip_address(server_ip)
    except ValueError as error:
        raise SystemExit("Server IP is not a valid IPv4 or IPv6 address.") from error
    if not re.fullmatch(r"[A-Za-z0-9_-]+", bot_name):
        raise SystemExit("Bot name may contain only letters, numbers, underscore and hyphen.")
    if "\n" in shop_name or "\r" in shop_name:
        raise SystemExit("Shop name cannot contain a line break.")
    host = f"{ssh_user}@{server_ip}"
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "telegramshop.zip"
        archive_project(archive, bot_token, owner_id, server_ip, shop_name)
        run(["scp", "-P", ssh_port, str(archive), f"{host}:/tmp/telegramshop.zip"])
        command = remote_script(install_dir, bot_name, owner_id, server_ip)
        run(["ssh", "-p", ssh_port, host, "bash -s"], command)
    print("\nDone. SSH to the server and run:")
    print(f"  novastore status {bot_name}")
    print(f"  http://{server_ip}:8080/control")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Deployment command failed with exit code {error.returncode}") from error
