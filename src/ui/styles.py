from nicegui import ui


def inject_global_styles():
    ui.add_css('''
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
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
    ''')
