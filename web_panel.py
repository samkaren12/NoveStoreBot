from __future__ import annotations

import hashlib
import html
import json
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from starlette.background import BackgroundTask

from config import Settings
from db import Database
from keyboards import MENU_DEFAULTS
from web_ui import CONTROL_CSS, control_body

app = FastAPI(title="Nova Store Control Center", docs_url=None, redoc_url=None)
_access: dict[str, dict[str, Any]] = {}


class ProductPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    price: int = Field(ge=0)
    stock: int = Field(ge=0)
    is_active: bool = True


class CardPayload(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    number: str = Field(min_length=16, max_length=16)
    holder: str = Field(default="", max_length=100)
    is_active: bool = True

    @field_validator("number")
    @classmethod
    def validate_number(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 16:
            raise ValueError("شماره کارت باید دقیقاً ۱۶ رقم باشد")
        return value


class MenuPayload(BaseModel):
    config: dict[str, dict[str, Any]]


class AdminPayload(BaseModel):
    user_id: int
    title: str = "ادمین"
    permissions: str = "products,orders,support,broadcast,settings"


class ChannelPayload(BaseModel):
    chat_id: str
    title: str = Field(min_length=1, max_length=100)
    invite_link: str = ""
    is_active: bool = True


class BroadcastPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SupportReplyPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def create_access(owner_id: int, settings: Settings) -> dict[str, str]:
    username = f"owner_{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(12)
    token = secrets.token_urlsafe(32)
    _access[token] = {"owner_id": owner_id, "username": username, "password_hash": _hash(password), "expires": time.time() + 900}
    base = settings.web_public_url.rstrip("/")
    return {"username": username, "password": password, "url": f"{base}/control?token={token}"}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _session(request: Request) -> dict[str, Any] | None:
    session = _access.get(request.cookies.get("nova_panel_session", ""))
    return session if session and session["expires"] > time.time() else None


def _require(request: Request) -> dict[str, Any]:
    session = _session(request)
    if not session:
        raise HTTPException(status_code=401, detail="ورود پنل منقضی شده است")
    return session


def _valid_menu(config: dict[str, dict[str, Any]]) -> bool:
    if set(config) != set(MENU_DEFAULTS):
        return False
    orders = []
    for key, item in config.items():
        if not isinstance(item, dict) or not isinstance(item.get("label"), str) or not 1 <= len(item["label"]) <= 40:
            return False
        if item.get("color") not in {"danger", "success", "primary"}:
            return False
        if not isinstance(item.get("order"), int) or not 1 <= item["order"] <= len(MENU_DEFAULTS):
            return False
        orders.append(item["order"])
    return len(set(orders)) == len(MENU_DEFAULTS)


def _page(title: str, body: str) -> str:
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>
:root{{--bg:#101522;--panel:#171f32;--line:#2b3854;--text:#eef3ff;--muted:#9caac4;--red:#ef6262;--green:#39c98b;--blue:#5e8dff;--gold:#f2c66d}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 85% 0,#23335a 0,transparent 35%),var(--bg);color:var(--text);font-family:Tahoma,Arial,sans-serif}}.wrap{{max-width:1180px;margin:auto;padding:28px}}header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}}h1{{font-size:25px;margin:0}}.sub{{color:var(--muted);font-size:13px;margin-top:8px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:15px;margin-bottom:24px}}.card{{background:rgba(23,31,50,.88);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 12px 35px #070b1430}}.metric{{font-size:30px;font-weight:bold;margin-top:10px}}.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}}button,.btn{{border:0;border-radius:9px;padding:11px 15px;color:white;cursor:pointer;background:var(--blue);text-decoration:none;font-size:13px}}button.green,.green{{background:var(--green);color:#071a13}}button.red,.red{{background:var(--red)}}button.dark,.dark{{background:#283650}}input,textarea,select{{width:100%;background:#101828;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:11px;margin:6px 0 12px}}table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid var(--line);padding:12px 8px;text-align:right;font-size:13px}}th{{color:var(--muted)}}.status{{color:var(--green)}}.off{{color:var(--red)}}.notice{{background:#21304c;border:1px solid #3b5481;padding:13px;border-radius:10px;margin-bottom:18px}}.hide{{display:none}}@media(max-width:600px){{.wrap{{padding:16px}}header{{align-items:flex-start;gap:12px;flex-direction:column}}table{{font-size:11px}}}}
</style></head><body><main class="wrap">{body}</main></body></html>'''


@app.get("/panel", response_class=HTMLResponse)
async def panel(request: Request, token: str | None = None):
    if not _session(request):
        if not token or token not in _access or _access[token]["expires"] <= time.time():
            return HTMLResponse(_page("ورود پنل", '<div class="card" style="max-width:430px;margin:10vh auto"><h1>Nova Store</h1><p class="sub">لینک ورود نامعتبر یا منقضی شده است. از ربات لینک تازه بگیرید.</p></div>'), status_code=401)
        login_form = f'''<div class="card" style="max-width:430px;margin:10vh auto"><h1>ورود به Nova Store</h1><p class="sub">شناسه و رمز دریافت‌شده از ربات را وارد کنید.</p><form method="post" action="/login"><input type="hidden" name="token" value="{html.escape(token)}"><input name="username" placeholder="شناسه مالک" required><input name="password" type="password" placeholder="رمز یک‌بارمصرف" required><button class="green" type="submit">ورود امن</button></form></div>'''
        return HTMLResponse(_page("ورود پنل", login_form))
    return HTMLResponse(_page("مرکز کنترل", '''<header><div><h1>مرکز کنترل Nova Store</h1><div class="sub">مدیریت سریع فروشگاه و ربات</div></div><button class="dark" onclick="logout()">خروج</button></header><div class="tabs"><button onclick="show('dashboard')">داشبورد</button><button onclick="show('products')">محصولات</button><button onclick="show('cards')">کارت‌ها</button><button onclick="show('menu')">منوی اصلی</button></div><section id="dashboard"></section><section id="products" class="hide"></section><section id="cards" class="hide"></section><section id="menu" class="hide"></section><script>
const api=(u,o={})=>fetch(u,{headers:{'Content-Type':'application/json'},...o}).then(async r=>{if(!r.ok)throw Error((await r.json()).detail||'خطا');return r.json()});const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));function show(id){document.querySelectorAll('section').forEach(x=>x.classList.add('hide'));document.getElementById(id).classList.remove('hide');if(id==='dashboard')dash();if(id==='products')products();if(id==='cards')cards();if(id==='menu')menu()}async function dash(){let d=await api('/api/stats');dashboard.innerHTML=`<div class="grid"><div class="card">کاربران<div class="metric">${d.users}</div></div><div class="card">محصولات فعال<div class="metric">${d.products}</div></div><div class="card">کارت‌های فعال<div class="metric">${d.cards}</div></div><div class="card">ارزش موجودی<div class="metric">${d.inventory.toLocaleString()} تومان</div></div></div><div class="card"><h3>وضعیت سیستم</h3><p class="status">● آنلاین و آماده‌ی مدیریت</p></div>`}async function products(){let a=await api('/api/products');products.innerHTML=`<div class="card"><h2>محصولات</h2><button class="green" onclick="newProduct()">+ محصول جدید</button><table><tr><th>نام</th><th>قیمت</th><th>موجودی</th><th>وضعیت</th><th>عملیات</th></tr>${a.map(x=>`<tr><td>${esc(x.name)}</td><td>${x.price.toLocaleString()}</td><td>${x.stock}</td><td class="${x.is_active?'status':'off'}">${x.is_active?'فعال':'غیرفعال'}</td><td><button class="dark" onclick='editProduct(${JSON.stringify(x)})'>ویرایش</button> <button class="${x.is_active?'red':'green'}" onclick="toggleProduct(${x.id})">${x.is_active?'غیرفعال':'فعال'}</button> <button class="red" onclick="deleteProduct(${x.id})">حذف</button></td></tr>`).join('')}</table></div>`}function productForm(x={}){return `<div class="card"><h2>${x.id?'ویرایش':'محصول جدید'}</h2><input id="pn" placeholder="نام" value="${esc(x.name)}"><textarea id="pd" placeholder="توضیحات">${esc(x.description)}</textarea><input id="pp" type="number" placeholder="قیمت" value="${x.price||0}"><input id="ps" type="number" placeholder="موجودی" value="${x.stock||0}"><button class="green" onclick="saveProduct(${x.id||0})">ذخیره</button></div>`}function newProduct(){products.innerHTML=productForm()}function editProduct(x){products.innerHTML=productForm(x)}async function saveProduct(id){let x={name:pn.value,description:pd.value,price:+pp.value,stock:+ps.value,is_active:true};await api(id?'/api/products/'+id:'/api/products',{method:id?'PUT':'POST',body:JSON.stringify(x)});products()}async function toggleProduct(id){await api('/api/products/'+id+'/toggle',{method:'POST'});products()}async function deleteProduct(id){if(confirm('حذف کامل شود؟')){await api('/api/products/'+id,{method:'DELETE'});products()}}async function cards(){let a=await api('/api/cards');cards.innerHTML=`<div class="card"><h2>کارت‌های بانکی</h2><button class="green" onclick="newCard()">+ کارت جدید</button><table><tr><th>عنوان</th><th>شماره</th><th>صاحب کارت</th><th>وضعیت</th><th>عملیات</th></tr>${a.map(x=>`<tr><td>${esc(x.title)}</td><td>${esc(x.number)}</td><td>${esc(x.holder)}</td><td class="${x.is_active?'status':'off'}">${x.is_active?'فعال':'غیرفعال'}</td><td><button class="dark" onclick='editCard(${JSON.stringify(x)})'>ویرایش</button> <button class="${x.is_active?'red':'green'}" onclick="toggleCard(${x.id})">${x.is_active?'غیرفعال':'فعال'}</button> <button class="red" onclick="deleteCard(${x.id})">حذف</button></td></tr>`).join('')}</table></div>`}function cardForm(x={}){return `<div class="card"><h2>${x.id?'ویرایش':'کارت جدید'}</h2><input id="ct" placeholder="عنوان" value="${esc(x.title)}"><input id="cn" maxlength="16" placeholder="شماره ۱۶ رقمی" value="${esc(x.number)}"><input id="ch" placeholder="صاحب کارت" value="${esc(x.holder)}"><button class="green" onclick="saveCard(${x.id||0})">ذخیره</button></div>`}function newCard(){cards.innerHTML=cardForm()}function editCard(x){cards.innerHTML=cardForm(x)}async function saveCard(id){let x={title:ct.value,number:cn.value.replaceAll(' ',''),holder:ch.value,is_active:true};await api(id?'/api/cards/'+id:'/api/cards',{method:id?'PUT':'POST',body:JSON.stringify(x)});cards()}async function toggleCard(id){await api('/api/cards/'+id+'/toggle',{method:'POST'});cards()}async function deleteCard(id){if(confirm('حذف کامل شود؟')){await api('/api/cards/'+id,{method:'DELETE'});cards()}}async function menu(){let x=await api('/api/menu');menu.innerHTML=`<div class="card"><h2>تنظیمات منوی اصلی</h2><p class="sub">نام، رنگ و ترتیب دکمه‌ها را تنظیم کنید.</p>${Object.entries(x).sort((a,b)=>a[1].order-b[1].order).map(([k,v])=>`<div class="card"><b>${esc(k)}</b><input id="l_${k}" value="${esc(v.label)}"><select id="c_${k}"><option ${v.color==='danger'?'selected':''} value="danger">قرمز</option><option ${v.color==='success'?'selected':''} value="success">سبز</option><option ${v.color==='primary'?'selected':''} value="primary">آبی</option></select><input id="o_${k}" type="number" min="1" max="6" value="${v.order}"></div>`).join('')}<button class="green" onclick="saveMenu()">ذخیره منو</button></div>`}async function saveMenu(){let x=await api('/api/menu');Object.keys(x).forEach(k=>{x[k]={label:document.getElementById('l_'+k).value,color:document.getElementById('c_'+k).value,order:+document.getElementById('o_'+k).value}});await api('/api/menu',{method:'PUT',body:JSON.stringify(x)});alert('ذخیره شد');menu()}async function logout(){await fetch('/api/logout',{method:'POST'});location.href='/panel'}show('dashboard');</script>'''))


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    token = str(form.get("token", ""))
    session = _access.get(token)
    valid = session and session["expires"] > time.time() and session["username"] == form.get("username") and session["password_hash"] == _hash(str(form.get("password", "")))
    if not valid:
        return HTMLResponse(_page("خطای ورود", '<div class="card" style="max-width:430px;margin:10vh auto"><h1>ورود ناموفق</h1><p class="sub">شناسه یا رمز اشتباه است.</p></div>'), status_code=401)
    response = RedirectResponse("/control", status_code=303)
    response.set_cookie("nova_panel_session", token, httponly=True, samesite="strict", max_age=900)
    return response


@app.get("/control", response_class=HTMLResponse)
async def control(request: Request, token: str | None = None):
    current_name = await request.app.state.db.get_setting("shop_name", getattr(request.app.state, "default_shop_name", "Nova Store"))
    if not _session(request):
        if not token or token not in _access or _access[token]["expires"] <= time.time():
            return HTMLResponse(_page("ورود پنل", f'<div class="card" style="max-width:430px;margin:10vh auto"><h1>{html.escape(current_name)}</h1><p class="sub">لینک ورود نامعتبر یا منقضی شده است.</p></div>'), status_code=401)
        form = f'''<div class="card" style="max-width:430px;margin:10vh auto"><h1>ورود به {html.escape(current_name)}</h1><p class="sub">شناسه و رمز دریافت‌شده از ربات را وارد کنید.</p><form method="post" action="/login"><input type="hidden" name="token" value="{html.escape(token)}"><input name="username" placeholder="شناسه مالک" required><input name="password" type="password" placeholder="رمز یک‌بارمصرف" required><button class="green" type="submit">ورود امن</button></form></div>'''
        return HTMLResponse(_page("ورود پنل", form))
    safe_reply_script = '''<script>window.sendReply=async function(id){await api('/api/support/'+id+'/reply',{method:'POST',body:JSON.stringify({text:document.querySelector('#replyText').value})});closeModal();toast('پاسخ برای کاربر ارسال شد')};const shopBtn=document.createElement('button');shopBtn.className='icon-btn';shopBtn.textContent='🏷 نام فروشگاه';shopBtn.onclick=async()=>{const old=(await api('/api/shop-name')).name;const name=prompt('نام جدید فروشگاه',old);if(name&&name.trim()!==old){await api('/api/shop-name',{method:'PUT',body:JSON.stringify({name:name.trim()}));applyShopName(name.trim());toast('نام فروشگاه تغییر کرد')}};document.querySelector('.top-actions')?.prepend(shopBtn);async function applyShopName(name){document.title=name+' | Control Center';const brand=document.querySelector('.brand b');if(brand)brand.textContent=name;const heading=document.querySelector('#viewTitle');if(heading&&heading.textContent.includes('داشبورد'))heading.textContent='داشبورد '+name}api('/api/shop-name').then(x=>applyShopName(x.name));</script>'''
    rendered_body = (CONTROL_CSS + control_body() + safe_reply_script).replace("Nova Store", html.escape(current_name))
    return HTMLResponse(_page(f"مرکز کنترل {html.escape(current_name)}", rendered_body))


async def db(request: Request) -> Database:
    return request.app.state.db


@app.get("/api/stats")
async def stats(request: Request):
    _require(request); database = await db(request)
    users = await database.fetchone("SELECT COUNT(*) n FROM users")
    products = await database.fetchone("SELECT COUNT(*) n FROM products WHERE is_active=1")
    cards = await database.fetchone("SELECT COUNT(*) n FROM cards WHERE is_active=1")
    inventory = await database.fetchone("SELECT COALESCE(SUM(price*stock),0) n FROM products WHERE is_active=1")
    return {"users": users["n"], "products": products["n"], "cards": cards["n"], "inventory": inventory["n"]}


@app.get("/api/products")
async def list_products(request: Request):
    _require(request); rows = await (await db(request)).fetchall("SELECT * FROM products ORDER BY id DESC")
    return [dict(row) for row in rows]


@app.post("/api/products")
async def create_product(payload: ProductPayload, request: Request):
    _require(request); database = await db(request); await database.execute("INSERT INTO products(name,description,price,stock,is_active) VALUES(?,?,?,?,?)", (payload.name, payload.description, payload.price, payload.stock, int(payload.is_active))); return {"ok": True}


@app.put("/api/products/{product_id}")
async def update_product(product_id: int, payload: ProductPayload, request: Request):
    _require(request); await (await db(request)).execute("UPDATE products SET name=?,description=?,price=?,stock=?,is_active=? WHERE id=?", (payload.name, payload.description, payload.price, payload.stock, int(payload.is_active), product_id)); return {"ok": True}


@app.post("/api/products/{product_id}/toggle")
async def toggle_product(product_id: int, request: Request):
    _require(request); await (await db(request)).execute("UPDATE products SET is_active=CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (product_id,)); return {"ok": True}


@app.delete("/api/products/{product_id}")
async def remove_product(product_id: int, request: Request):
    _require(request); await (await db(request)).delete_product(product_id); return {"ok": True}


@app.get("/api/cards")
async def list_cards(request: Request):
    _require(request); rows = await (await db(request)).fetchall("SELECT * FROM cards ORDER BY id DESC"); return [dict(row) for row in rows]


@app.post("/api/cards")
async def create_card(payload: CardPayload, request: Request):
    _require(request); await (await db(request)).execute("INSERT INTO cards(title,number,holder,is_active) VALUES(?,?,?,?)", (payload.title, payload.number, payload.holder, int(payload.is_active))); return {"ok": True}


@app.put("/api/cards/{card_id}")
async def update_card(card_id: int, payload: CardPayload, request: Request):
    _require(request); await (await db(request)).execute("UPDATE cards SET title=?,number=?,holder=?,is_active=? WHERE id=?", (payload.title, payload.number, payload.holder, int(payload.is_active), card_id)); return {"ok": True}


@app.post("/api/cards/{card_id}/toggle")
async def toggle_card(card_id: int, request: Request):
    _require(request); await (await db(request)).execute("UPDATE cards SET is_active=CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (card_id,)); return {"ok": True}


@app.delete("/api/cards/{card_id}")
async def remove_card(card_id: int, request: Request):
    _require(request); await (await db(request)).execute("DELETE FROM cards WHERE id=?", (card_id,)); return {"ok": True}


@app.get("/api/menu")
async def get_menu(request: Request):
    _require(request); database = await db(request); raw = await database.get_setting("menu_config", "")
    try:
        config = json.loads(raw) if raw else {key: value.copy() for key, value in MENU_DEFAULTS.items()}
    except json.JSONDecodeError:
        config = {key: value.copy() for key, value in MENU_DEFAULTS.items()}
    return config if _valid_menu(config) else {key: value.copy() for key, value in MENU_DEFAULTS.items()}


@app.put("/api/menu")
async def update_menu(payload: MenuPayload, request: Request):
    _require(request)
    if not _valid_menu(payload.config):
        raise HTTPException(status_code=422, detail="تنظیمات منو معتبر نیست؛ ترتیب باید یکتا و رنگ‌ها معتبر باشند")
    await (await db(request)).set_setting("menu_config", json.dumps(payload.config, ensure_ascii=False)); return {"ok": True}


@app.get("/api/shop-name")
async def get_shop_name(request: Request):
    _require(request)
    database = await db(request)
    return {"name": await database.get_setting("shop_name", getattr(request.app.state, "default_shop_name", "Nova Store"))}


@app.put("/api/shop-name")
async def update_shop_name(request: Request):
    _require(request)
    payload = await request.json()
    name = str(payload.get("name", "")).strip()
    if not 2 <= len(name) <= 60:
        raise HTTPException(status_code=422, detail="نام فروشگاه باید بین ۲ تا ۶۰ کاراکتر باشد")
    await (await db(request)).set_setting("shop_name", name)
    return {"ok": True, "name": name}


@app.get("/api/users")
async def list_users(request: Request):
    _require(request)
    rows = await (await db(request)).fetchall("SELECT id,username,full_name,is_blocked,joined_at FROM users ORDER BY joined_at DESC")
    return [dict(row) for row in rows]


@app.post("/api/users/{user_id}/toggle")
async def toggle_user(user_id: int, request: Request):
    _require(request); await (await db(request)).execute("UPDATE users SET is_blocked=CASE is_blocked WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (user_id,)); return {"ok": True}


@app.get("/api/admins")
async def list_admins(request: Request):
    _require(request); rows = await (await db(request)).fetchall("SELECT * FROM admins ORDER BY user_id"); return [dict(row) for row in rows]


@app.post("/api/admins")
async def create_admin(payload: AdminPayload, request: Request):
    _require(request); await (await db(request)).execute("INSERT INTO admins(user_id,title,permissions) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET title=excluded.title,permissions=excluded.permissions", (payload.user_id, payload.title, payload.permissions)); return {"ok": True}


@app.delete("/api/admins/{user_id}")
async def remove_admin(user_id: int, request: Request):
    _require(request); await (await db(request)).execute("DELETE FROM admins WHERE user_id=?", (user_id,)); return {"ok": True}


@app.get("/api/channels")
async def list_channels(request: Request):
    _require(request); rows = await (await db(request)).fetchall("SELECT * FROM channels ORDER BY id DESC"); return [dict(row) for row in rows]


@app.post("/api/channels")
async def create_channel(payload: ChannelPayload, request: Request):
    _require(request); await (await db(request)).execute("INSERT INTO channels(chat_id,title,invite_link,is_active) VALUES(?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,invite_link=excluded.invite_link,is_active=excluded.is_active", (payload.chat_id, payload.title, payload.invite_link, int(payload.is_active))); return {"ok": True}


@app.delete("/api/channels/{channel_id}")
async def remove_channel(channel_id: int, request: Request):
    _require(request); await (await db(request)).execute("DELETE FROM channels WHERE id=?", (channel_id,)); return {"ok": True}


@app.get("/api/support")
async def list_support(request: Request):
    _require(request)
    rows = await (await db(request)).fetchall("SELECT s.*,u.full_name,u.username FROM support_messages s LEFT JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 100")
    return [dict(row) for row in rows]


@app.post("/api/support/{ticket_id}/close")
async def close_support(ticket_id: int, request: Request):
    _require(request); await (await db(request)).execute("UPDATE support_messages SET status='closed' WHERE id=?", (ticket_id,)); return {"ok": True}


@app.post("/api/support/{user_id}/reply")
async def reply_support(user_id: int, payload: SupportReplyPayload, request: Request):
    _require(request); bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="ربات هنوز آماده نیست")
    try:
        await bot.send_message(user_id, f"💬 پاسخ پشتیبانی:\n\n{payload.text}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="ارسال پاسخ به کاربر انجام نشد") from exc
    return {"ok": True}


@app.post("/api/broadcast")
async def broadcast(payload: BroadcastPayload, request: Request):
    _require(request); bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="ربات هنوز آماده نیست")
    users = await (await db(request)).fetchall("SELECT id FROM users WHERE is_blocked=0")
    sent = 0
    for user in users:
        try:
            await bot.send_message(user["id"], payload.text)
            sent += 1
        except Exception:
            continue
    return {"sent": sent, "total": len(users)}


@app.get("/api/backup")
async def download_database_backup(request: Request):
    _require(request)
    temporary = tempfile.NamedTemporaryFile(prefix="nova_backup_", suffix=".sqlite3", delete=False)
    temporary.close()
    target = Path(temporary.name)
    await (await db(request)).backup(str(target))
    return FileResponse(
        target,
        filename="nova_store_backup.sqlite3",
        media_type="application/octet-stream",
        background=BackgroundTask(target.unlink, missing_ok=True),
    )


@app.post("/api/restore")
async def restore_database(request: Request, file: UploadFile = File(...)):
    _require(request)
    if not file.filename or not file.filename.lower().endswith((".sqlite3", ".sqlite", ".db")):
        raise HTTPException(status_code=400, detail="فایل SQLite معتبر ارسال کنید")
    target = Path("web_restore.sqlite3")
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="حجم بکاپ نباید بیشتر از ۲۰ مگابایت باشد")
    target.write_bytes(content)
    database = await db(request)
    if not await database.is_valid_backup(str(target)):
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="فایل بکاپ معتبر نیست")
    previous = Path(f"{database.path}.before_web_restore")
    previous.unlink(missing_ok=True)
    Path(database.path).replace(previous)
    target.replace(Path(database.path))
    return {"ok": True}


@app.post("/api/logout")
async def logout(request: Request):
    response = RedirectResponse("/panel"); response.delete_cookie("nova_panel_session"); return response


def configure(app_db: Database, bot: Any = None, settings: Any = None) -> None:
    app.state.db = app_db
    app.state.bot = bot
    app.state.default_shop_name = getattr(settings, "shop_name", "Nova Store")
