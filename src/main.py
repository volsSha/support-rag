import asyncio
import os
import sqlite3
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from nicegui import app, ui

from src.auth.middleware import AuthMiddleware, router as auth_router
from src.config import get_settings
from src.db.engine import async_engine, async_session_factory
from src.db.vec import create_vec_table, load_vec_extension
from src.rag.embeddings import load_embedding_model
from src.rag.reranker import load_reranker
from src.services.rate_limit import create_limiter
from src.ui.admin import create_admin_page
from src.ui.chat import create_chat_page
from src.ui.login import create_login_page


async def on_startup() -> None:
    settings = get_settings()

    os.makedirs("data", exist_ok=True)

    alembic_cfg = AlembicConfig("alembic.ini")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, lambda: alembic_command.upgrade(alembic_cfg, "head"),
    )

    db_path = Path("data/app.db")
    db_connection = sqlite3.connect(str(db_path))
    load_vec_extension(db_connection)
    create_vec_table(db_connection)
    db_connection.close()

    print("Loading embedding model...")
    load_embedding_model()

    print("Loading reranker model...")
    load_reranker()

    create_limiter()

    app.add_router(auth_router)

    print(f"\n{settings.app_name} is ready at {settings.app_url}\n")

 

async def on_shutdown() -> None:
    await async_engine.dispose()


create_login_page()

app.add_middleware(AuthMiddleware)
app.on_startup(on_startup)
app.on_shutdown(on_shutdown)

settings = get_settings()
ui.run(
    title=settings.app_name,
    storage_secret=settings.auth.jwt_secret.get_secret_value(),
    port=8080,
    reload=settings.debug,
    host="0.0.0.0",
    show=False,
)
