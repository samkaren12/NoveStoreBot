<div dir="rtl" align="right">

# Nova Store

</div>

<div align="center">

**ربات فروشگاهی حرفه‌ای تلگرام با پنل مدیریت وب و استقرار دائمی روی VPS**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-powered-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![GitHub](https://img.shields.io/badge/GitHub-samkaren12%2FTelegramshopbot-181717?logo=github&logoColor=white)](https://github.com/samkaren12/Telegramshopbot)

[صفحه اصلی](README.md) · [English](README.EN.MD)

</div>

Nova Store یک چارچوب آماده برای فروش محصولات دیجیتال و فیزیکی در تلگرام است. پروژه شامل ربات، دیتابیس SQLite، پنل وب مالک، نصب‌کننده Ubuntu، SSL اختیاری و اجرای دائمی با systemd است.

## فهرست مطالب

- [قابلیت‌ها](#قابلیت‌ها)
- [جدول امکانات](#جدول-امکانات)
- [پیش‌نیازها](#پیشنیازها)
- [اجرای محلی](#اجرای-محلی)
- [نصب سریع روی VPS](#نصب-سریع-روی-vps)
- [SSL و دامنه](#ssl-و-دامنه)
- [مدیریت پس از نصب](#مدیریت-پس-از-نصب)
- [امنیت](#امنیت)
- [ساختار پروژه](#ساختار-پروژه)

## قابلیت‌ها

- رابط فروشگاهی تلگرام با `aiogram 3` و SQLite
- مدیریت محصولات، قیمت، موجودی، تصویر و کارت‌های بانکی
- سبد خرید، محاسبه مبلغ، پشتیبانی و پیام همگانی
- پنل وب مدیریت با ورود موقت ۱۵ دقیقه‌ای
- نصب خودکار روی Ubuntu و مدیریت چند ربات
- اجرای دائمی، شروع خودکار پس از reboot و restart بعد از crash
- کنترل‌سنتر عددی و رنگی با فرمان `novastore`

## جدول امکانات

| بخش | امکان | وضعیت |
| --- | --- | --- |
| فروشگاه | محصولات دیجیتال و فیزیکی | آماده |
| خرید | سبد خرید و محاسبه مبلغ | آماده |
| پرداخت | کارت‌به‌کارت و نمایش مبلغ | آماده |
| مدیریت | محصولات، کارت‌ها و پیام همگانی | آماده |
| پنل وب | داشبورد، محصولات و تنظیمات منو | آماده |
| استقرار | systemd و مدیریت چند ربات | آماده |
| امنیت | SSL با Nginx و Let’s Encrypt | اختیاری |

## پیش‌نیازها

- Ubuntu 22.04 یا 24.04 برای VPS
- Python 3.11 یا جدیدتر برای اجرای محلی
- Bot Token از [@BotFather](https://t.me/BotFather)
- شناسه عددی مالک تلگرام (`OWNER_ID`)
- برای SSL: یک دامنه که از قبل به IP سرور اشاره کند

## اجرای محلی

```bash
python -m venv .venv
```

فعال‌سازی محیط مجازی در PowerShell:

```powershell
.venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

در فایل `.env` مقدارهای `BOT_TOKEN` و `OWNER_ID` را تنظیم کن، سپس اجرا کن:

```bash
python main.py
```

## نصب سریع روی VPS

پروژه عمومی است و installer آدرس Repository را از قبل می‌داند:

```bash
curl -fsSL https://raw.githubusercontent.com/samkaren12/Telegramshopbot/main/install.sh -o /tmp/novastore-install.sh
sudo bash /tmp/novastore-install.sh
```

Installer این موارد را می‌گیرد:

1. نام ربات
2. نام فروشگاه
3. `OWNER_ID`
4. Bot Token
5. آدرس عمومی پنل
6. دامنه HTTPS، یا خالی برای رد کردن SSL
7. ایمیل Let’s Encrypt، در صورت وارد کردن دامنه

## SSL و دامنه

قبل از نصب، رکورد DNS دامنه را به IP سرور متصل کن. برای مثال:

```text
panel.example.com -> SERVER_IP
```

اگر دامنه وارد شود، installer به‌صورت خودکار Nginx و Certbot را نصب می‌کند، ربات را پشت reverse proxy قرار می‌دهد و HTTP را به HTTPS redirect می‌کند. آدرس نهایی پنل:

```text
https://panel.example.com/control
```

## مدیریت پس از نصب

با اجرای دستور زیر کنترل‌سنتر عددی باز می‌شود:

```bash
sudo novastore
```

گزینه‌های پنل:

```text
1) Status     2) Restart    3) Logs
4) Update     5) Add bot    6) Remove bot
7) Uninstall  0) Exit
```

فرمان‌های مستقیم:

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

ربات به‌صورت سرویس systemd اجرا می‌شود و بعد از reboot یا crash دوباره بالا می‌آید. حذف کامل با `novastore uninstall` نیاز به تأیید عددی `1` دارد.

## امنیت

- هرگز `.env`، Bot Token، کلید SSH یا دیتابیس را در GitHub قرار نده.
- پنل وب را با HTTPS یا VPN منتشر کن.
- برای SSH از SSH Key استفاده کن.
- اگر Token در جایی منتشر شد، فوراً از BotFather آن را تعویض کن.

## ساختار پروژه

| فایل | کاربرد |
| --- | --- |
| `main.py` | اجرای ربات و راه‌اندازی سرویس‌ها |
| `handlers.py` | منطق پیام‌ها و callbackها |
| `db.py` | لایه دیتابیس SQLite |
| `web_panel.py` | API و پنل مدیریت وب |
| `web_ui.py` | رابط پنل وب |
| `install.sh` | نصب خودکار Ubuntu، SSL و systemd |
| `deploy.py` | انتقال و نصب از راه SSH |
| `.env.example` | نمونه تنظیمات بدون اطلاعات محرمانه |

## لینک پروژه

https://github.com/samkaren12/Telegramshopbot
