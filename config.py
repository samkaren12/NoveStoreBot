from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_id: int
    db_path: str
    shop_name: str
    support_username: str
    web_host: str
    web_port: int
    web_public_url: str


settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", ""),
    owner_id=int(os.getenv("OWNER_ID", "0")),
    db_path=os.getenv("DB_PATH", "shop.sqlite3"),
    shop_name=os.getenv("SHOP_NAME", "Nova Store"),
    support_username=os.getenv("SUPPORT_USERNAME", "@support"),
    web_host=os.getenv("WEB_HOST", "127.0.0.1"),
    web_port=int(os.getenv("WEB_PORT", "8080")),
    web_public_url=os.getenv("WEB_PUBLIC_URL", "http://127.0.0.1:8080"),
)
