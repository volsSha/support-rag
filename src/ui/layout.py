from nicegui import ui


def app_header(is_admin: bool = False):
    with ui.header().classes("bg-white border-b border-gray-200 shadow-sm"):
        with ui.row().classes("w-full flex items-center justify-between px-6 py-3"):
            with ui.row().classes("flex items-center gap-6"):
                ui.label("Support RAG").classes("text-xl font-bold text-gray-800")
                with ui.row().classes("flex items-center gap-2"):
                    ui.link("Chat", "/").classes("text-gray-600 hover:text-gray-900 transition-colors")
                    if is_admin:
                        ui.link("Admin", "/admin").classes(
                            "text-gray-600 hover:text-gray-900 transition-colors"
                        )
            ui.button("Logout", on_click=_logout).props("flat color=grey").classes("text-gray-600")


def create_layout(is_admin: bool = False, content_fn=None):
    app_header(is_admin=is_admin)
    with ui.column().classes("w-full flex-1 overflow-y-auto"):
        if content_fn is not None:
            content_fn()


async def _logout():
    ui.run_javascript("document.cookie = 'token=; path=/; max-age=0';")
    ui.navigate.to("/login")
