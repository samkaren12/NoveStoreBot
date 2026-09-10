#!/usr/bin/env bash
set -Eeuo pipefail

if [[ -t 1 ]]; then
  RESET='\033[0m'; BOLD='\033[1m'; CYAN='\033[36m'; BLUE='\033[34m'
  GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; DIM='\033[2m'
else
  RESET=''; BOLD=''; CYAN=''; BLUE=''; GREEN=''; YELLOW=''; RED=''; DIM=''
fi

banner() {
  printf '\n%b\n' "${CYAN}${BOLD}╭────────────────────────────────────────────╮${RESET}"
  printf '%b\n' "${CYAN}${BOLD}│          NOVA STORE  /  INSTALLER         │${RESET}"
  printf '%b\n\n' "${CYAN}${BOLD}╰────────────────────────────────────────────╯${RESET}"
}

info() { printf '%b\n' "${CYAN}  ·${RESET} $*"; }
ok() { printf '%b\n' "${GREEN}  ✓${RESET} $*"; }
warn() { printf '%b\n' "${YELLOW}  !${RESET} $*"; }
fail() { printf '%b\n' "${RED}  ✕${RESET} $*" >&2; exit 1; }
step() { printf '\n%b\n' "${BLUE}${BOLD}[$1/6]${RESET} $2"; }
pulse() {
  local text="$1" frame
  [[ -t 1 ]] || return 0
  for frame in '◐' '◓' '◑' '◒'; do
    printf '\r%b' "${CYAN}${BOLD}${frame}${RESET} ${text}"
    sleep 0.08
  done
  printf '\r%b\n' "${GREEN}${BOLD}✓${RESET} ${text}"
}

on_error() {
  printf '%b\n' "${RED}  ✕ Installation failed at line $1.${RESET}" >&2
  printf '%b\n' "${DIM}  Check the command above and run the installer again after fixing it.${RESET}" >&2
}
trap 'on_error $LINENO' ERR

APP_ROOT="${TELEGRAMSHOP_ROOT:-/opt/telegramshop}"
REPO_URL="${TELEGRAMSHOP_REPO:-https://github.com/samkaren12/Telegramshopbot.git}"
INSTALLER_URL="${TELEGRAMSHOP_INSTALLER:-https://raw.githubusercontent.com/samkaren12/Telegramshopbot/main/install.sh}"
BOT_NAME="${TELEGRAMSHOP_NAME:-main}"
WEB_PORT="${TELEGRAMSHOP_PORT:-8080}"

if [[ "${EUID}" -ne 0 ]]; then
  fail "Run this installer as root: sudo bash install.sh"
  exit 1
fi

banner
pulse 'Starting Nova Store installer'
info "GitHub: $REPO_URL"

ask() {
  local prompt="$1" default="${2:-}" value=""
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " value
    printf '%s' "${value:-$default}"
  else
    read -r -p "$prompt: " value
    printf '%s' "$value"
  fi
}

BOT_NAME="$(ask 'Bot name' "${BOT_NAME:-main}")"
SHOP_NAME="$(ask 'Shop name' 'Telegram Shop')"
OWNER_ID="$(ask 'Telegram owner numeric ID')"
OWNER_ID="${OWNER_ID:-}"
BOT_TOKEN=""
read -r -s -p 'Telegram Bot API token: ' BOT_TOKEN
printf '\n'
SERVER_IP="$(hostname -I | awk '{print $1}')"
PUBLIC_URL="$(ask 'Public panel URL' "http://${SERVER_IP}:${WEB_PORT}")"
SSL_DOMAIN="$(ask 'HTTPS domain (leave empty to skip SSL)')"
SSL_EMAIL=""
if [[ -n "$SSL_DOMAIN" ]]; then
  SSL_EMAIL="$(ask "Let's Encrypt email")"
  PUBLIC_URL="https://${SSL_DOMAIN}"
fi

if [[ ! "$BOT_NAME" =~ ^[A-Za-z0-9_-]+$ ]]; then
  fail "Invalid bot name. Use only letters, numbers, _ and -."
fi
if [[ ! "$OWNER_ID" =~ ^[0-9]+$ ]]; then
  fail "OWNER_ID must be numeric."
fi
if [[ "$SHOP_NAME" == *$'\n'* || "$SHOP_NAME" == *$'\r'* ]]; then
  fail "Shop name cannot contain a line break."
fi
if [[ -n "$SSL_DOMAIN" && ! "$SSL_DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
  fail "Invalid HTTPS domain."
fi
if [[ -n "$SSL_DOMAIN" && ! "$SSL_EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
  fail "A valid email is required for the HTTPS certificate."
fi
if [[ -z "$BOT_TOKEN" || -z "$REPO_URL" ]]; then
  fail "Repository URL and bot token are required."
fi

export DEBIAN_FRONTEND=noninteractive
step 1 "Preparing Ubuntu packages"
apt-get update -y
apt-get install -y curl git python3 python3-venv python3-pip
ok "System packages are ready"

BOT_ROOT="$APP_ROOT/bots/$BOT_NAME"
mkdir -p "$APP_ROOT/bots"
step 2 "Downloading project"
if [[ -d "$BOT_ROOT/.git" ]]; then
  git -C "$BOT_ROOT" pull --ff-only
  ok "Project updated from GitHub"
else
  rm -rf "$BOT_ROOT"
  git clone --depth 1 "$REPO_URL" "$BOT_ROOT"
  ok "Project cloned from GitHub"
fi

step 3 "Creating Python environment"
python3 -m venv "$BOT_ROOT/.venv"
"$BOT_ROOT/.venv/bin/python" -m pip install --upgrade pip
"$BOT_ROOT/.venv/bin/pip" install -r "$BOT_ROOT/requirements.txt"
ok "Python dependencies installed"

step 4 "Writing secure configuration"
cat > "$BOT_ROOT/.env" <<ENV
BOT_TOKEN=$BOT_TOKEN
OWNER_ID=$OWNER_ID
DB_PATH=$BOT_ROOT/shop.sqlite3
SHOP_NAME=$SHOP_NAME
WEB_HOST=0.0.0.0
WEB_PORT=$WEB_PORT
WEB_PUBLIC_URL=$PUBLIC_URL
ENV
chmod 600 "$BOT_ROOT/.env"
ok "Environment file created"

step 5 "Registering system service"
cat > "/etc/systemd/system/telegramshop-$BOT_NAME.service" <<SERVICE
[Unit]
Description=Telegram Shop $BOT_NAME
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BOT_ROOT
EnvironmentFile=$BOT_ROOT/.env
ExecStart=$BOT_ROOT/.venv/bin/python $BOT_ROOT/main.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
SERVICE

cat > /usr/local/bin/novastore <<'CLI'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ -t 1 ]]; then RESET='\033[0m'; BOLD='\033[1m'; CYAN='\033[36m'; GREEN='\033[32m'; RED='\033[31m'; YELLOW='\033[33m'; else RESET=''; BOLD=''; CYAN=''; GREEN=''; RED=''; YELLOW=''; fi
ROOT="/opt/telegramshop/bots"
DEFAULT_NAME="BOT_NAME_PLACEHOLDER"
REPO_URL="REPO_URL_PLACEHOLDER"
pulse() {
  local text="$1" frame
  [[ -t 1 ]] || return 0
  for frame in '◐' '◓' '◑' '◒'; do
    printf '\r%b' "${CYAN}${BOLD}${frame}${RESET} ${text}"
    sleep 0.08
  done
  printf '\r%b\n' "${GREEN}${BOLD}✓${RESET} ${text}"
}
usage() {
  printf '%b\n' "${CYAN}${BOLD}NOVA STORE CONTROL CENTER${RESET}"
  printf '%s\n' "GitHub: $REPO_URL"
  printf '%s\n' "Usage: novastore [command] [bot-name]"
  printf '%s\n' "  menu                         numeric control panel"
  printf '%s\n' "  list                         list all bots"
  printf '%s\n' "  add                          install another bot"
  printf '%s\n' "  update|remove NAME          update or remove a bot"
  printf '%s\n' "  uninstall                   remove all bots and this manager"
  printf '%s\n' "  start|stop|restart NAME     control service"
  printf '%s\n' "  status|logs NAME            inspect service"
}
choose_bot() {
  local names=() choice index
  mapfile -t names < <(find "$ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort)
  ((${#names[@]} > 0)) || { printf '%b\n' "${RED}  No bots found.${RESET}" >&2; return 1; }
  printf '%s\n' "  Select a bot:" >&2
  for index in "${!names[@]}"; do printf '  %d) %s\n' "$((index + 1))" "${names[$index]}" >&2; done
  read -r -p '  Number: ' choice
  [[ "$choice" =~ ^[0-9]+$ && "$choice" -ge 1 && "$choice" -le "${#names[@]}" ]] || { printf '%b\n' "${RED}  Invalid selection.${RESET}" >&2; return 1; }
  printf '%s' "${names[$((choice - 1))]}"
}
update_bot() { local n="${1:-$DEFAULT_NAME}"; git -C "$ROOT/$n" pull --ff-only; "$ROOT/$n/.venv/bin/pip" install -r "$ROOT/$n/requirements.txt"; systemctl restart "telegramshop-$n.service"; printf '%b\n' "${GREEN}  Updated $n${RESET}"; }
remove_bot() { local n="${1:-}"; [[ -n "$n" && "$n" != "$DEFAULT_NAME" ]] || { printf '%b\n' "${RED}  Main bot cannot be removed here.${RESET}"; return 1; }; systemctl disable --now "telegramshop-$n.service" || true; rm -f "/etc/systemd/system/telegramshop-$n.service"; rm -rf "$ROOT/$n"; systemctl daemon-reload; printf '%b\n' "${YELLOW}  Removed $n${RESET}"; }
uninstall_all() {
  local confirmation service
  printf '%b\n' "${RED}  This removes every bot, its data, services, and this command.${RESET}"
  read -r -p '  Enter 1 to confirm, or 0 to cancel: ' confirmation
  [[ "$confirmation" == "1" ]] || { printf '%s\n' '  Cancelled.'; return 0; }
  for service in /etc/systemd/system/telegramshop-*.service; do
    [[ -e "$service" ]] || continue
    systemctl disable --now "$(basename "$service")" || true
    rm -f "$service"
  done
  systemctl daemon-reload
  rm -rf "${ROOT%/bots}"
  rm -f /usr/local/bin/novastore /usr/local/bin/telegramshop
  printf '%b\n' "${YELLOW}  Nova Store was completely removed.${RESET}"
}
menu() {
  while true; do
    clear
    pulse 'Loading Nova Store control center'
    printf '%b\n' "${CYAN}${BOLD}NOVA STORE MANAGER${RESET}"
    printf '%s\n' '  1) Status  2) Restart  3) Logs  4) Update  5) Add bot  6) Remove bot  7) Uninstall  0) Exit'
    read -r -p '  Number: ' choice
    case "$choice" in
      1) name="$(choose_bot)" && systemctl status "telegramshop-$name.service" --no-pager ;;
      2) name="$(choose_bot)" && systemctl restart "telegramshop-$name.service" ;;
      3) name="$(choose_bot)" && journalctl -u "telegramshop-$name.service" -n 100 --no-pager ;;
      4) name="$(choose_bot)" && update_bot "$name" ;;
      5) bash <(curl -fsSL "INSTALLER_URL_PLACEHOLDER") ;;
      6) name="$(choose_bot)" && remove_bot "$name" ;;
      7) uninstall_all; break ;;
      0) break ;;
      *) printf '%b\n' "${RED}  Invalid selection.${RESET}" ;;
    esac
    read -r -p '  Press Enter to continue...' _
  done
}
name="${2:-$DEFAULT_NAME}"
service="telegramshop-$name.service"
case "${1:-menu}" in
  menu) menu ;;
  list) systemctl list-units 'telegramshop-*.service' --all --no-legend || true ;;
  start|stop|restart|enable|disable|status) systemctl "$1" "$service" ;;
  logs) journalctl -u "$service" -n 100 -f ;;
  update) update_bot "$name" ;;
  add) bash <(curl -fsSL "INSTALLER_URL_PLACEHOLDER") ;;
  remove) remove_bot "$name" ;;
  uninstall) uninstall_all ;;
  *) usage; exit 1 ;;
esac
CLI
sed -i "s#BOT_NAME_PLACEHOLDER#$BOT_NAME#g; s#REPO_URL_PLACEHOLDER#$REPO_URL#g; s#INSTALLER_URL_PLACEHOLDER#$INSTALLER_URL#g" /usr/local/bin/novastore
chmod +x /usr/local/bin/novastore
ln -sfn /usr/local/bin/novastore /usr/local/bin/telegramshop
systemctl daemon-reload
systemctl enable --now "telegramshop-$BOT_NAME.service"
ok "Nova Store bot '$BOT_NAME' is running permanently"

step 6 "Configuring firewall"
if [[ -n "$SSL_DOMAIN" ]]; then
  step 6 "Configuring HTTPS with Nginx and Let's Encrypt"
  apt-get install -y nginx certbot python3-certbot-nginx
  cat > "/etc/nginx/sites-available/telegramshop-$BOT_NAME" <<NGINX
server {
    listen 80;
    server_name $SSL_DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$WEB_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
  ln -sfn "/etc/nginx/sites-available/telegramshop-$BOT_NAME" "/etc/nginx/sites-enabled/telegramshop-$BOT_NAME"
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  certbot --nginx --non-interactive --agree-tos --redirect --email "$SSL_EMAIL" -d "$SSL_DOMAIN"
  if command -v ufw >/dev/null 2>&1; then
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
  fi
  ok "HTTPS is enabled at https://$SSL_DOMAIN/control"
elif command -v ufw >/dev/null 2>&1; then
  ufw allow "$WEB_PORT/tcp" || true
fi
if [[ -z "$SSL_DOMAIN" ]]; then
  ok "Panel port $WEB_PORT is configured"
fi

printf '\n%b\n' "${GREEN}${BOLD}╭────────────────────────────────────────────╮${RESET}"
printf '%b\n' "${GREEN}${BOLD}│             INSTALLATION COMPLETE          │${RESET}"
printf '%b\n' "${GREEN}${BOLD}╰────────────────────────────────────────────╯${RESET}"
printf '%b\n' "  Panel:  ${CYAN}$PUBLIC_URL/control${RESET}"
printf '%b\n' "  Status: ${CYAN}novastore status $BOT_NAME${RESET}"
printf '%b\n' "  Logs:   ${CYAN}novastore logs $BOT_NAME${RESET}"
