![1000097848](https://github.com/user-attachments/assets/f84fb9b6-e00d-4f3f-8945-815d7fd6ef43)
<div align="center">

# Nova Store

**A production-ready Telegram shop with a web admin panel and 24/7 VPS deployment.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-powered-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![GitHub](https://img.shields.io/badge/GitHub-samkaren12%2FTelegramshopbot-181717?logo=github&logoColor=white)](https://github.com/samkaren12/Telegramshopbot)

[فارسی](README.fa.md) · [English](README.EN.MD)

</div>

> نسخه کامل مستندات فارسی در [README.fa.md](README.fa.md) و نسخه انگلیسی در [README.EN.MD](README.EN.MD) قرار دارد.

## فهرست مطالب

- [درباره پروژه](#درباره-پروژه)
- [قابلیت‌ها](#قابلیت‌ها)
- [پیش‌نیازها](#پیشنیازها)
- [اجرای محلی](#اجرای-محلی)
- [نصب روی VPS](#نصب-روی-vps)
- [اجرای دائمی](#اجرای-دائمی)
- [امنیت](#امنیت)
- [مستندات زبان‌ها](#مستندات-زبانها)

## درباره پروژه

ربات فروشگاهی حرفه‌ای تلگرام با `aiogram 3`، SQLite، پنل وب و مدیریت دائمی روی VPS.

> یک فروشگاه آماده برای فروش محصولات دیجیتال و فیزیکی، با داشبورد مدیریتی و اجرای 24/7.

**GitHub:** https://github.com/samkaren12/Telegramshopbot

## قابلیت‌ها

| حوزه | قابلیت | وضعیت |
| --- | --- | --- |
| فروشگاه | محصولات، قیمت، موجودی و تصویر | آماده |
| خرید | سبد خرید و محاسبه مبلغ | آماده |
| پرداخت | کارت‌به‌کارت با نمایش شماره کارت و مبلغ | آماده |
| کاربر | پروفایل و پشتیبانی | آماده |
| مدیریت ربات | افزودن و حذف محصول، کارت بانکی و پیام همگانی | آماده |
| پنل وب | داشبورد، محصولات، کارت‌ها و منوی اصلی | آماده |
| امنیت پنل | ورود موقت ۱۵ دقیقه‌ای | آماده |
| استقرار | systemd، شروع پس از reboot و restart پس از crash | آماده |
| SSL | Nginx و Let’s Encrypt در نصب دامنه‌محور | آماده |
| مدیریت سرور | کنترل‌سنتر عددی `novastore` | آماده |

## پیش‌نیازها

ubuntu 24.04

- Python 3.11یا جدیدتر
- یک Bot Token از [@BotFather](https://t.me/BotFather)
- شناسه عددی مالک ربات (`OWNER_ID`)

## اجرای محلی

در PowerShell یا ترمینال پروژه اجرا کنید:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

فایل `.env.example` را به `.env` کپی کنید و حداقل `BOT_TOKEN` و `OWNER_ID` را مقداردهی کنید. در لینوکس:

```bash
cp .env.example .env
```

در PowerShell:

```powershell
Copy-Item .env.example .env
```

سپس ربات را اجرا کنید:

```bash
python main.py
```

برای اجرای پنل وب از دستگاه دیگر، در `.env` مقدار `WEB_HOST=0.0.0.0` و آدرس قابل دسترس را در `WEB_PUBLIC_URL` تنظیم کنید. پنل را مستقیماً روی اینترنت بدون HTTPS یا VPN منتشر نکنید.

## پنل وب مالک

در `.env` مقدارهای `WEB_HOST`، `WEB_PORT` و `WEB_PUBLIC_URL` را تنظیم کنید. سپس از پنل مدیریت ربات روی `🌐 پنل وب` بزنید. لینک، شناسه و رمز موقت ۱۵ دقیقه‌ای برای مالک ارسال می‌شود.

برای دسترسی از دستگاه دیگر، `WEB_HOST=0.0.0.0` و `WEB_PUBLIC_URL` را با آدرس امن سرور تنظیم کنید. در نصب VPS، اگر دامنه و ایمیل را وارد کنید، اسکریپت Nginx و گواهی رایگان Let’s Encrypt را خودکار تنظیم می‌کند.

## نصب روی VPS با deploy.py

از کامپیوتر خود، در پوشه پروژه و روی سیستمی که OpenSSH Client دارد، اجرا کنید:

```bash
python deploy.py
```

اسکریپت IP سرور، کاربر SSH، نام ربات، `OWNER_ID`، Bot Token و نام فروشگاه را می‌گیرد، فایل‌ها را منتقل می‌کند و سرویس systemd را فعال می‌کند. روی سرور بعد از نصب:

```bash
novastore list
novastore menu
novastore status main
novastore restart main
novastore logs main
novastore add
novastore stop main
novastore remove main
novastore uninstall
```

برای اجرای `deploy.py` اتصال SSH با کلید یا ورود تعاملی OpenSSH لازم است. آدرس پنل پیش‌فرض پس از نصب `http://SERVER_IP:8080/control` است. برای HTTPS خودکار، نصب مستقیم GitHub را با دامنه و ایمیل SSL انجام دهید.

### اجرای دائمی

نصب‌کننده برای هر ربات یک سرویس systemd می‌سازد و آن را با `enable --now` فعال می‌کند. در نتیجه ربات بعد از خروج از SSH، reboot سرور یا crash برنامه دوباره اجرا می‌شود. نام داخلی سرویس `telegramshop-main.service` است، اما مدیریت آن از طریق فرمان برندشده `novastore` انجام می‌شود.

```bash
sudo systemctl status telegramshop-main.service --no-pager
sudo journalctl -u telegramshop-main.service -n 100 -f
```

برای کنترل ساده‌تر از کنترل‌سنتر Nova Store استفاده کن:

```bash
sudo novastore
```

با اجرای `novastore` بدون آرگومان، کنترل‌سنتر عددی مستقیماً باز می‌شود. برای دیدن فهرست ربات‌ها می‌توانی `novastore list` را اجرا کنی.

## نصب مستقیم از GitHub روی Ubuntu

این پروژه از repository عمومی `samkaren12/Telegramshopbot` استفاده می‌کند و اسکریپت نصب URL آن را از قبل می‌داند؛ بنابراین هنگام نصب دیگر URL repository را نمی‌پرسد.

```bash
curl -fsSL https://raw.githubusercontent.com/samkaren12/Telegramshopbot/main/install.sh -o /tmp/telegramshop-install.sh
sudo bash /tmp/telegramshop-install.sh
```

در نصب‌کننده Nova Store به‌ترتیب این اطلاعات را وارد کن:

- نام ربات، مثلاً `main`
- نام فروشگاه
- `OWNER_ID` عددی تلگرام
- Bot Token
- آدرس عمومی پنل
- دامنه HTTPS، یا خالی برای رد کردن SSL
- ایمیل Let’s Encrypt، اگر دامنه وارد شده است

اسکریپت همین repository را clone، وابستگی‌ها را نصب، `.env` و سرویس systemd را ایجاد و ربات را اجرا می‌کند. دامنه باید قبل از نصب به IP سرور اشاره کند. اگر بخواهی از repository دیگری نصب کنی، قبل از اجرای اسکریپت مقدار `TELEGRAMSHOP_REPO` را تنظیم کن.

اگر دامنه وارد شود، نصب‌کننده Nginx، Certbot و redirect خودکار HTTP به HTTPS را تنظیم می‌کند. اگر دامنه را خالی بگذاری، پنل با HTTP و پورت `WEB_PORT` اجرا می‌شود.

```bash
sudo TELEGRAMSHOP_REPO=https://github.com/USER/REPOSITORY.git bash /tmp/telegramshop-install.sh
```

برای نصب چند ربات پس از نصب اول:

```bash
novastore status main
novastore logs main
novastore restart main
novastore update main
novastore add
novastore remove main
novastore uninstall
```

برای repository خصوصی، دسترسی Git (مانند SSH key) را از قبل روی سرور تنظیم کنید؛ token را داخل URL عمومی GitHub قرار ندهید.

با اجرای `novastore menu` یک کنترل‌سنتر رنگی و عددی باز می‌شود. در این پنل می‌توان وضعیت، restart، لاگ‌ها، update، افزودن و حذف ربات را با شماره انتخاب کرد. گزینه `7` یا فرمان `novastore uninstall` همه ربات‌ها، دیتابیس‌ها، سرویس‌های systemd و ابزار مدیریتی را حذف می‌کند و برای ادامه نیاز به وارد کردن عدد `1` دارد.

## نکات امنیتی

- فایل `.env` و Bot Token را commit یا در GitHub منتشر نکنید.
- برای پنل وب از HTTPS یا VPN استفاده کنید.
- پورت پنل را فقط در فایروال و شبکه مورد نیاز باز کنید.

## مستندات زبان‌ها

- فارسی: [README.fa.md](README.fa.md)
- English: [README.EN.MD](README.EN.MD)
