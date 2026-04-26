import logging

from nicegui import background_tasks, ui

from src.config import get_settings
from src.db.engine import async_session_factory
from src.db.models import Conversation, Message
from src.rag.pipeline import get_pipeline
from src.rag.safety import RAGResult, Source
from src.ui.styles import inject_global_styles

logger = logging.getLogger(__name__)


class ChatState:
    def __init__(self):
        self.messages: list[dict] = []
        self.is_streaming: bool = False
        self.conversation_id: int | None = None


def _build_sources_html(sources: list[Source]) -> str:
    if not sources:
        return ""
    links: list[str] = []
    for s in sources:
        if s.url:
            links.append(
                f'<a href="{s.url}" target="_blank" class="source-link">{s.title}</a>'
            )
        else:
            links.append(f'<span class="source-link">{s.title}</span>')
    return '<div class="sources-container">' + " &middot; ".join(links) + "</div>"


@ui.refreshable
async def message_list(state: ChatState):
    with ui.column().classes("w-full gap-2"):
        for msg in state.messages:
            if msg["role"] == "user":
                with ui.row().classes("w-full justify-end"):
                    ui.label(msg["content"]).classes(
                        "chat-bubble-user rounded-xl px-4 py-2 max-w-[75%] "
                        "text-white text-sm break-words"
                    )
            elif msg["role"] == "assistant":
                with ui.row().classes("w-full justify-start"):
                    with ui.column().classes("max-w-[75%] gap-1"):
                        if msg.get("escalated"):
                            with ui.row().classes(
                                "escalation-banner items-center gap-2 rounded-xl "
                                "px-4 py-3 text-sm"
                            ):
                                ui.icon("warning", color="warning").classes(
                                    "text-lg shrink-0"
                                )
                                ui.label(
                                    "I couldn't find relevant information for your "
                                    "question. A support agent will follow up."
                                ).classes("text-warning")
                        if msg["content"]:
                            ui.markdown(msg["content"]).classes(
                                "chat-bubble-assistant rounded-xl px-4 py-2 text-sm "
                                "break-words"
                            )
                        sources = msg.get("sources")
                        if sources:
                            ui.html(_build_sources_html(sources))
            elif msg["role"] == "error":
                with ui.row().classes("w-full justify-center"):
                    ui.label(msg["content"]).classes(
                        "text-negative text-sm italic"
                    )


async def _scroll_to_bottom():
    await ui.run_javascript(
        "const el = document.getElementById('message-area'); "
        "if (el) el.scrollTop = el.scrollHeight;"
    )


async def _stream_response(state: ChatState, query: str):
    try:
        pipeline = get_pipeline()
        settings = get_settings()
        user_id = app.storage.user.get("user_id", 1)

        assistant_idx = len(state.messages)
        state.messages.append({
            "role": "assistant",
            "content": "",
            "sources": [],
            "escalated": False,
        })
        message_list.refresh()

        accumulated = ""
        final_result: RAGResult | None = None

        async for item in pipeline.process_query(
            query,
            user_id=user_id,
            conversation_id=state.conversation_id,
        ):
            if isinstance(item, str):
                accumulated += item
                state.messages[assistant_idx]["content"] = accumulated
                message_list.refresh()
                await _scroll_to_bottom()
            elif isinstance(item, RAGResult):
                final_result = item

        if final_result:
            if final_result.escalated:
                state.messages[assistant_idx] = {
                    "role": "assistant",
                    "content": final_result.answer,
                    "sources": [],
                    "escalated": True,
                }
            else:
                state.messages[assistant_idx] = {
                    "role": "assistant",
                    "content": final_result.answer or accumulated,
                    "sources": final_result.sources,
                    "escalated": False,
                }
                if final_result.answer and accumulated:
                    state.messages[assistant_idx]["content"] = final_result.answer

            if final_result.confidence > 0 and not final_result.escalated:
                state.conversation_id = await _persist_conversation(
                    state, query, final_result, user_id
                )
        elif accumulated:
            state.messages[assistant_idx]["content"] = accumulated

        message_list.refresh()
        await _scroll_to_bottom()

    except Exception as exc:
        logger.exception("Error streaming response")
        state.messages.append({
            "role": "error",
            "content": "Something went wrong. Please try again.",
        })
        message_list.refresh()
        ui.notify(
            f"Error: {exc}",
            color="negative",
            position="top",
            close_button=True,
        )

    finally:
        state.is_streaming = False


async def _persist_conversation(
    state: ChatState, query: str, result: RAGResult, user_id: int,
) -> int | None:
    try:
        async with async_session_factory() as session:
            conv = Conversation(user_id=user_id, title=query[:100])
            session.add(conv)
            await session.flush()
            conv_id = conv.id

            session.add(Message(
                conversation_id=conv_id,
                role="user",
                content=query,
            ))
            session.add(Message(
                conversation_id=conv_id,
                role="assistant",
                content=result.answer,
                sources_json=result.model_dump_json(include={"sources"}),
            ))
            await session.commit()
            return conv_id
    except Exception:
        logger.exception("Failed to persist conversation")
        return None


async def _create_new_conversation(state: ChatState):
    state.messages.clear()
    state.conversation_id = None
    message_list.refresh()


async def _load_conversation_history() -> list[dict]:
    try:
        async with async_session_factory() as session:
            from sqlalchemy import select
            stmt = (
                select(Conversation)
                .order_by(Conversation.created_at.desc())
                .limit(20)
            )
            result = await session.execute(stmt)
            conversations = result.scalars().all()
            return [
                {"id": c.id, "title": c.title, "created_at": c.created_at}
                for c in conversations
            ]
    except Exception:
        logger.exception("Failed to load conversation history")
        return []


@ui.refreshable
async def conversation_sidebar(state: ChatState):
    async with async_session_factory() as session:
        from sqlalchemy import select
        stmt = (
            select(Conversation)
            .order_by(Conversation.created_at.desc())
            .limit(20)
        )
        result = await session.execute(stmt)
        conversations = result.scalars().all()

    with ui.column().classes("w-full gap-1"):
        ui.button(
            "New Conversation",
            icon="add",
            on_click=lambda: _create_new_conversation(state),
        ).props("flat no-caps color=primary").classes("w-full justify-start")

        if not conversations:
            ui.label("No conversations yet").classes("text-sm text-gray-500 italic")
            return

        for conv in conversations:
            is_active = state.conversation_id == conv.id
            ui.button(
                conv.title,
                icon="chat",
                on_click=lambda c=conv: _switch_conversation(state, c.id),
            ).props(
                "flat no-caps dense"
                + (" color=primary" if is_active else "")
            ).classes(
                "w-full justify-start text-left truncate text-xs"
                + (" font-bold" if is_active else "")
            )


async def _switch_conversation(state: ChatState, conv_id: int):
    try:
        async with async_session_factory() as session:
            from sqlalchemy import select
            stmt = (
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.created_at.asc())
            )
            result = await session.execute(stmt)
            messages = result.scalars().all()

        state.messages.clear()
        state.conversation_id = conv_id
        for msg in messages:
            entry: dict = {
                "role": msg.role,
                "content": msg.content,
                "sources": [],
                "escalated": False,
            }
            if msg.sources_json:
                try:
                    import json
                    data = json.loads(msg.sources_json)
                    entry["sources"] = [
                        Source.model_validate(s) for s in data
                    ]
                except Exception:
                    pass
            if "couldn't find" in msg.content.lower() or "escalating" in msg.content.lower():
                entry["escalated"] = True
            state.messages.append(entry)

        message_list.refresh()
        conversation_sidebar.refresh()
        await _scroll_to_bottom()

    except Exception:
        logger.exception("Failed to load conversation")
        ui.notify("Failed to load conversation", color="negative")


async def create_chat_page():
    inject_global_styles()

    state = ChatState()

    await ui.context.client.connected()

    with ui.splitter(value=20).classes("w-full h-full") as splitter:
        with splitter.before:
            with ui.scroll_area().classes("h-full p-2"):
                with ui.card().classes("w-full h-fit"):
                    ui.label("Conversations").classes(
                        "text-sm font-semibold mb-2 text-gray-700"
                    )
                    await conversation_sidebar(state)

        with splitter.after:
            with ui.column().classes("w-full h-full"):
                with ui.header().classes("w-full").props("elevated"):
                    ui.link("Chat", "/").classes("text-white mr-4").props("color=white")
                    is_admin = app.storage.user.get("is_admin", False)
                    if is_admin:
                        ui.link("Admin", "/admin").classes("text-white mr-4").props("color=white")
                    ui.space()
                    ui.button(
                        "Logout", on_click=lambda: (
                            ui.run_javascript('document.cookie="access_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/"'),
                            ui.navigate.to("/login"),
                        )
                    ).props("flat color=white size=sm")

                with ui.scroll_area().classes("flex-grow w-full").props(
                    'id="message-area"'
                ):
                    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-2"):
                        await message_list(state)

                with ui.footer().classes("w-full").props("elevated"):
                    with ui.row().classes(
                        "w-full max-w-4xl mx-auto items-center gap-2 p-2"
                    ):
                        text_input = ui.input(
                            placeholder="Ask a question...",
                        ).classes("flex-grow").props("outlined dense").on(
                            "keydown.enter",
                            lambda e: _on_submit(state, text_input, send_button),
                        )

                        send_button = ui.button(
                            icon="send",
                            on_click=lambda: _on_submit(state, text_input, send_button),
                        ).props(
                            "round dense color=primary size=sm"
                        ).classes("shrink-0")


def _on_submit(state: ChatState, text_input: ui.input, send_button: ui.button):
    text = text_input.value
    if not text or not text.strip() or state.is_streaming:
        return

    text_input.set_value("")
    state.is_streaming = True
    send_button.disable()
    text_input.disable()

    state.messages.append({"role": "user", "content": text.strip()})
    message_list.refresh()

    async def _after_stream():
        await _scroll_to_bottom()
        send_button.enable()
        text_input.enable()
        await text_input.run_method("focus")
        conversation_sidebar.refresh()

    async def _task():
        await _stream_response(state, text.strip())
        await _after_stream()

    background_tasks.create(_task)
