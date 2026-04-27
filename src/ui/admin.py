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

    with ui.row().classes("w-full px-2 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide"):
        ui.label("Title").classes("w-[26%]")
        ui.label("Source URL").classes("w-[30%]")
        ui.label("Category").classes("w-[14%]")
        ui.label("Created").classes("w-[16%]")
        ui.label("Actions").classes("w-[14%] text-center")

    docs_container = ui.column().classes("w-full gap-2 mt-2")

    async def refresh_table():
        from src.db.engine import async_session_factory

        async with async_session_factory() as session:
            docs = await get_all_documents(session)

        docs_container.clear()
        if not docs:
            with docs_container:
                ui.label("No documents yet. Click 'Add Document' to get started.").classes(
                    "text-gray-500 text-lg mt-8"
                )
            return

        with docs_container:
            for doc in docs:
                created_str = doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else ""
                with ui.row().classes(
                    "w-full items-center px-3 py-3 rounded-lg border border-gray-200 dark:border-gray-700"
                ):
                    async def _open_doc_dialog(doc_id: int) -> None:
                        await _show_document_dialog(doc_id)

                    ui.label(doc.title).classes("w-[26%] font-medium truncate")
                    if doc.source_url:
                        ui.link(doc.source_url, doc.source_url).classes("w-[30%] truncate text-blue-600")
                    else:
                        ui.label("-").classes("w-[30%] text-gray-400")
                    ui.label(doc.category).classes("w-[14%]")
                    ui.label(created_str).classes("w-[16%] text-sm")
                    with ui.row().classes("w-[14%] justify-center gap-1"):
                        ui.button(
                            icon="visibility",
                            on_click=lambda doc_id=doc.id: _open_doc_dialog(doc_id),
                        ).props("flat dense color=primary size=sm")
                        ui.button(
                            icon="delete",
                            on_click=lambda doc_id=doc.id: _confirm_delete(doc_id, refresh_table),
                        ).props("flat dense color=negative size=sm")

    with ui.dialog().classes("w-[600px]") as add_dialog:
        with ui.card():
            ui.label("Add Document").classes("text-xl font-bold mb-4")

            title_input = ui.input("Title").classes("w-full")
            title_input.validation = {"Title is required": lambda v: bool(v and v.strip())}

            content_input = ui.textarea("Content").classes("w-full").props("rows=10 autogrow")
            content_input.validation = {"Content is required": lambda v: bool(v and v.strip())}

            url_input = ui.input("Source URL (optional)").classes("w-full")
            category_input = ui.select(
                options=CATEGORIES,
                label="Category",
                value=CATEGORIES[0],
            ).classes("w-full")

            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=add_dialog.close).props("flat")

                async def handle_submit() -> None:
                    await _submit_document(
                        add_dialog,
                        refresh_table,
                        title_input,
                        content_input,
                        url_input,
                        category_input,
                    )

                ui.button(
                    "Submit",
                    on_click=handle_submit,
                ).props("color=primary")

    with ui.row().classes("items-center gap-2 mt-2"):
        ui.button(
            "Add Document",
            icon="add",
            on_click=lambda: add_dialog.open(),
        ).props("color=primary")

    background_tasks.create(refresh_table())


async def _submit_document(
    dialog,
    refresh_callback,
    title_input,
    content_input,
    url_input,
    category_input,
):
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
    await refresh_callback()


async def _show_document_dialog(doc_id: int):
    from src.db.engine import async_session_factory

    async with async_session_factory() as session:
        docs = await get_all_documents(session)
        doc = next((d for d in docs if d.id == int(doc_id)), None)

    if doc is None:
        ui.notify("Document not found", type="negative")
        return

    with ui.dialog().classes("w-[800px]") as dialog, ui.card().classes("w-full"):
        ui.label(doc.title).classes("text-xl font-bold")
        if doc.source_url:
            ui.link(doc.source_url, doc.source_url).classes("text-blue-600")
        ui.separator()
        ui.markdown(doc.content).classes("max-h-[60vh] overflow-auto text-sm")
        with ui.row().classes("w-full justify-end mt-4"):
            ui.button("Close", on_click=dialog.close).props("flat")

    dialog.open()


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
