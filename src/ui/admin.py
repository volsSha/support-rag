from __future__ import annotations

from nicegui import app, background_tasks, ui

from src.services.documents import create_document, delete_document, get_all_documents, ingest_document

CATEGORIES = ["FAQ", "Guide", "API Reference", "Troubleshooting", "Other"]


@ui.page("/admin")
async def create_admin_page():
    from src.ui.styles import apply_dark_mode, inject_global_styles, toggle_dark_mode
    inject_global_styles()
    await apply_dark_mode()

    is_admin = app.storage.user.get("is_admin", False)
    if not is_admin:
        ui.label("Access denied. Admin role required.").classes("text-red-500 text-lg mt-10")
        return

    with ui.row().classes("w-full items-center justify-between mb-4"):
        ui.label("Document Management").classes("text-3xl font-bold")
        dark_icon = "light_mode" if app.storage.user.get("dark_mode", False) else "dark_mode"
        ui.button(icon=dark_icon, on_click=toggle_dark_mode).props("flat")

    ui.button("Add Document", icon="add", on_click=lambda: _open_add_dialog()).props("color=primary")

    columns = [
        {"name": "title", "label": "Title", "field": "title", "align": "left"},
        {"name": "source_url", "label": "Source URL", "field": "source_url", "align": "left"},
        {"name": "category", "label": "Category", "field": "category", "align": "left"},
        {"name": "created", "label": "Created", "field": "created", "align": "left"},
        {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
    ]

    table = ui.table(columns=columns, rows=[]).classes("w-full mt-4")

    async def refresh_table():
        from src.db.engine import async_session_factory

        async with async_session_factory() as session:
            docs = await get_all_documents(session)

        if not docs:
            table.rows = []
            table.update()
            empty_container.clear()
            with empty_container:
                ui.label("No documents yet. Click 'Add Document' to get started.").classes(
                    "text-gray-500 text-lg mt-8"
                )
            return

        empty_container.clear()
        rows = []
        for doc in docs:
            created_str = doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else ""
            rows.append({
                "id": doc.id,
                "title": doc.title,
                "source_url": doc.source_url or "",
                "category": doc.category,
                "created": created_str,
            })
        table.rows = rows
        table.update()

    with table.add_slot("body-cell-actions"):
        async def render_actions(props):
            with ui.row().classes("flex items-center justify-center gap-2"):
                ui.button(
                    icon="delete",
                    on_click=lambda _, doc_id=props.row["id"]: _confirm_delete(doc_id, refresh_table),
                ).props("flat dense color=negative size=sm")

        render_actions

    empty_container = ui.column().classes("w-full")

    background_tasks.create(refresh_table())


def _open_add_dialog():
    with ui.dialog().classes("w-[600px]") as dialog, ui.card():
        ui.label("Add Document").classes("text-xl font-bold mb-4")

        title_input = ui.input("Title").classes("w-full")
        title_input.validation = {"Title is required": lambda v: bool(v.strip())}

        content_input = ui.textarea("Content").classes("w-full").props('rows=10 autogrow')
        content_input.validation = {"Content is required": lambda v: bool(v.strip())}

        url_input = ui.input("Source URL (optional)").classes("w-full")

        category_input = ui.select(
            "Category",
            options=CATEGORIES,
            value=CATEGORIES[0],
        ).classes("w-full")

        with ui.row().classes("justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Submit",
                on_click=lambda: _submit_document(
                    dialog,
                    title_input,
                    content_input,
                    url_input,
                    category_input,
                ),
            ).props("color=primary")

    dialog.open()


async def _submit_document(dialog, title_input, content_input, url_input, category_input):
    title = title_input.value.strip()
    content = content_input.value.strip()
    source_url = url_input.value.strip() or None
    category = category_input.value

    if not title or not content:
        ui.notify("Title and content are required", type="negative")
        return

    from src.db.engine import async_session_factory

    async with async_session_factory() as session:
        document = await create_document(session, title, content, source_url, category)
        await session.commit()
        await session.refresh(document)
        chunk_count = await ingest_document(session, document.id)

    dialog.close()
    ui.notify(f"Document created successfully ({chunk_count} chunks)", type="positive")


def _confirm_delete(doc_id, refresh_callback):
    with ui.dialog() as dialog, ui.card():
        ui.label("Delete Document?").classes("text-lg font-bold")
        ui.label("This will permanently delete the document and all its data.").classes("text-gray-500")

        with ui.row().classes("justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Delete",
                on_click=lambda: _do_delete(dialog, doc_id, refresh_callback),
            ).props("color=negative")

    dialog.open()


async def _do_delete(dialog, doc_id, refresh_callback):
    from src.db.engine import async_session_factory

    async with async_session_factory() as session:
        await delete_document(session, doc_id)

    dialog.close()
    ui.notify("Document deleted", type="positive")
    await refresh_callback()
