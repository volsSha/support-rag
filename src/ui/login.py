from nicegui import ui

from src.config import get_settings
from src.ui.styles import inject_global_styles


def create_login_page():
    @ui.page("/login")
    async def login_page():
        inject_global_styles()
        settings = get_settings()
        request = getattr(ui.context.client, "request", None)
        redirect_to = "/"
        if request is not None:
            redirect_to = request.query_params.get("redirect_to", "/")

        with ui.column().classes(
            "w-full min-h-screen flex items-center justify-center bg-gray-50"
        ):
            with ui.card().classes("w-full max-w-sm p-8 shadow-lg"):
                ui.label(settings.app_name).classes("text-2xl font-bold text-center text-gray-800 mb-2")
                ui.label("Sign in to your account").classes("text-sm text-center text-gray-500 mb-6")

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
        import httpx
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.app_url}/api/auth/login",
                json={"username": username, "password": password},
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token", "")
                if token:
                    ui.run_javascript(f"document.cookie = 'token={token}; path=/; max-age=86400';")
                    ui.navigate.to(redirect_to)
                    return
            ui.notify(resp.json().get("detail", "Login failed"), color="negative")
    except Exception:
        ui.notify("Connection error. Is the server running?", color="negative")


