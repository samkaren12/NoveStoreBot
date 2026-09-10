from __future__ import annotations

import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: str):
        self.path = path

    @asynccontextmanager
    async def connect(self):
        connection = await aiosqlite.connect(self.path)
        await connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = aiosqlite.Row
        try:
            yield connection
        finally:
            await connection.close()

    async def init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with self.connect() as db:
            await db.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, username TEXT, full_name TEXT NOT NULL,
                    is_blocked INTEGER NOT NULL DEFAULT 0, joined_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '', price INTEGER NOT NULL,
                    stock INTEGER NOT NULL DEFAULT 0, photo_id TEXT, is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS cart (
                    user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL,
                    PRIMARY KEY (user_id, product_id), FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                    number TEXT NOT NULL, holder TEXT NOT NULL DEFAULT '', is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT 'ادمین', permissions TEXT NOT NULL DEFAULT 'products,orders,support,broadcast,settings'
                );
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
                    invite_link TEXT NOT NULL DEFAULT '', is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL, content TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        async with self.connect() as db:
            await db.execute(query, params)
            await db.commit()

    async def fetchone(self, query: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        async with self.connect() as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        async with self.connect() as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    async def upsert_user(self, user_id: int, username: str | None, full_name: str) -> None:
        await self.execute(
            "INSERT INTO users(id, username, full_name, joined_at) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
            (user_id, username, full_name, datetime.now(timezone.utc).isoformat()),
        )

    async def is_blocked(self, user_id: int) -> bool:
        row = await self.fetchone("SELECT is_blocked FROM users WHERE id=?", (user_id,))
        return bool(row and row[0])

    async def get_cart(self, user_id: int) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT p.*, c.quantity FROM cart c JOIN products p ON p.id=c.product_id WHERE c.user_id=?", (user_id,)
        )

    async def cart_total(self, user_id: int) -> int:
        row = await self.fetchone(
            "SELECT COALESCE(SUM(p.price*c.quantity),0) total FROM cart c JOIN products p ON p.id=c.product_id WHERE c.user_id=?",
            (user_id,),
        )
        return int(row[0])

    async def add_to_cart(self, user_id: int, product_id: int) -> bool:
        async with self.connect() as db:
            cursor = await db.execute(
                "UPDATE products SET stock=stock-1 WHERE id=? AND is_active=1 AND stock>0",
                (product_id,),
            )
            if cursor.rowcount != 1:
                return False
            await db.execute(
                "INSERT INTO cart(user_id, product_id, quantity) VALUES(?,?,1) "
                "ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=quantity+1",
                (user_id, product_id),
            )
            await db.commit()
            return True

    async def clear_cart(self, user_id: int) -> None:
        async with self.connect() as db:
            await db.execute(
                "UPDATE products SET stock=stock+(SELECT quantity FROM cart WHERE user_id=? AND product_id=products.id) "
                "WHERE id IN (SELECT product_id FROM cart WHERE user_id=?)",
                (user_id, user_id),
            )
            await db.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
            await db.commit()

    async def delete_product(self, product_id: int) -> None:
        async with self.connect() as db:
            await db.execute(
                "UPDATE products SET stock=stock+COALESCE((SELECT SUM(quantity) FROM cart WHERE product_id=?),0) WHERE id=?",
                (product_id, product_id),
            )
            await db.execute("DELETE FROM products WHERE id=?", (product_id,))
            await db.commit()

    async def backup(self, target: str) -> None:
        async with self.connect() as source, aiosqlite.connect(target) as destination:
            await source.backup(destination)

    async def is_valid_backup(self, path: str) -> bool:
        try:
            async with aiosqlite.connect(path) as db:
                cursor = await db.execute("PRAGMA integrity_check")
                row = await cursor.fetchone()
                if not row or row[0] != "ok":
                    return False
                cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {item[0] for item in await cursor.fetchall()}
                required = {"users", "products", "cart", "cards", "admins", "channels", "settings"}
                return required.issubset(tables)
        except Exception:
            return False

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return str(row[0]) if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
