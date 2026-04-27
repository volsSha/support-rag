from datetime import timedelta

from nicegui import app, ui
from sqlalchemy import select

from src.auth.jwt import create_access_token
from src.auth.passwords import verify_password
from src.config import get_settings
from src.db.engine import async_session_factory
from src.db.models import User
from src.ui.styles import apply_dark_mode, inject_global_styles, toggle_dark_mode


def create_login_page():
    @ui.page("/login")
    async def login_page():
        inject_global_styles()
        await apply_dark_mode()
        settings = get_settings()
        request = getattr(ui.context.client, "request", None)
        redirect_to = "/"
        if request is not None:
            redirect_to = request.query_params.get("redirect_to", "/")

        with ui.column().classes(
            "w-full min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900"
        ):
            with ui.card().classes("w-full max-w-sm p-8 shadow-lg bg-white dark:bg-gray-800"):
                with ui.row().classes("w-full justify-end"):
                    dark_icon = "light_mode" if app.storage.user.get("dark_mode", False) else "dark_mode"
                    ui.button(icon=dark_icon, on_click=toggle_dark_mode).props("flat")
                ui.label(settings.app_name).classes(
                    "text-2xl font-bold text-center text-gray-800 dark:text-gray-100 mb-2"
                )
                ui.label("Sign in to your account").classes(
                    "text-sm text-center text-gray-500 dark:text-gray-300 mb-6"
                )

                username_input = ui.input(
                    "Username", placeholder="Enter your username"
                ).classes("w-full mb-4")

                password_input = ui.input(
                    "Password", placeholder="Enter your password", password=True,
                    password_toggle_button=True,
                ).classes("w-full mb-6")

                ui.button(
                    "Login",
                    on_click=lambda: _do_login(username_input, password_input, redirect_to),
                ).props("unelevated color=primary").classes("w-full mb-3")

    return login_page


async def _do_login(username_input, password_input, redirect_to: str):
    username = username_input.value
    password = password_input.value

    if not username or not password:
        ui.notify("Username and password are required", color="negative")
        return

    try:
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.hashed_password):
            ui.notify("Invalid credentials", color="negative")
            return

        settings = get_settings()
        token = create_access_token(
            user_id=user.id,
            secret=settings.auth.jwt_secret.get_secret_value(),
            algorithm=settings.auth.jwt_algorithm,
            expires_delta=timedelta(minutes=settings.auth.jwt_expire_minutes),
        )

        await ui.run_javascript(
            f"document.cookie = 'access_token={token}; path=/; max-age={settings.auth.jwt_expire_minutes * 60}; SameSite=Lax';"
        )
        ui.navigate.to(redirect_to)
    except Exception:
        ui.notify("Login error. Please try again.", color="negative")


