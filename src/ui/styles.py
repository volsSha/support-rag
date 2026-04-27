from nicegui import app, ui


def inject_global_styles():
    ui.add_css('''
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            transition: background-color 0.3s, color 0.3s;
        }
        .nicegui-markdown a {
            color: #3b82f6;
            text-decoration: none;
            font-weight: 500;
        }
        .nicegui-markdown a:hover {
            text-decoration: underline;
            color: #2563eb;
        }
        .chat-bubble {
            max-width: 80%;
            padding: 12px 16px;
            border-radius: 12px;
            line-height: 1.6;
        }
        .chat-bubble-user {
            background-color: #3b82f6;
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }
        .chat-bubble-assistant {
            background-color: #f3f4f6;
            color: #1f2937;
            margin-right: auto;
            border-bottom-left-radius: 4px;
        }
        .escalation-banner {
            background-color: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 12px 16px;
            color: #92400e;
        }
        .source-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 8px;
            background-color: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 6px;
            color: #1d4ed8;
            text-decoration: none;
            font-size: 0.875rem;
            transition: background-color 0.2s;
        }
        .source-link:hover {
            background-color: #dbeafe;
            text-decoration: none;
        }
        .think-container {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin: 2px 0;
        }
        .think-step {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 0.75rem;
            color: #4b5563;
            background-color: #f9fafb;
            border: 1px dashed #d1d5db;
            border-radius: 8px;
            padding: 4px 8px;
            width: fit-content;
            max-width: 100%;
        }
        .think-stage {
            font-weight: 600;
            color: #1d4ed8;
        }
        .think-message {
            word-break: break-word;
        }
        /* Dark mode styles */
        .dark body {
            background-color: #111827;
            color: #f9fafb;
        }
        .dark .q-card {
            background-color: #1f2937 !important;
            color: #f9fafb !important;
        }
        .dark .q-input {
            color: #f9fafb !important;
        }
        .dark .q-field__label {
            color: #9ca3af !important;
        }
        .dark .chat-bubble-assistant {
            background-color: #374151;
            color: #f9fafb;
        }
        .dark .chat-bubble-user {
            background-color: #2563eb;
            color: white;
        }
        .dark .q-btn {
            color: #f9fafb !important;
        }
        .dark .source-link {
            background-color: #1e3a8a;
            border-color: #3b82f6;
            color: #93c5fd;
        }
        .dark .source-link:hover {
            background-color: #1e40af;
        }
        .dark .q-header, .dark .q-footer {
            background-color: #1f2937 !important;
            color: #f9fafb !important;
        }
        .dark .think-step {
            color: #e5e7eb;
            background-color: #1f2937;
            border-color: #4b5563;
        }
        .dark .think-stage {
            color: #93c5fd;
        }
        .dark .q-splitter__separator {
            background-color: #374151 !important;
        }
    ''')


async def apply_dark_mode() -> None:
    is_dark = app.storage.user.get("dark_mode", False)
    if is_dark:
        await ui.run_javascript('document.documentElement.classList.add("dark")')
    else:
        await ui.run_javascript('document.documentElement.classList.remove("dark")')


async def toggle_dark_mode() -> None:
    current = app.storage.user.get("dark_mode", False)
    app.storage.user["dark_mode"] = not current
    await apply_dark_mode()
