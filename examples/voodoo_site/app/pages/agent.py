"""AI Agent chat interface for autonomous system operations."""
import uuid
from voodoo import Div, Heading, Card, Input, ChatBox, Text, register_event, ws_manager, Agent, _
from app.layout import Layout

agent = Agent(system_prompt="You are Voodoo, an AI assistant for this SaaS dashboard.")

async def handle_chat_message(element_id: str, value: str):
    if not value:
        return
        
    user_msg = Div(Text(value), className="bg-[var(--color-primary)] text-white p-3 rounded-2xl rounded-tr-sm self-end w-fit max-w-[80%] shadow-lg")
    await ws_manager.broadcast_append("chat-history", user_msg.render())
    
    # We don't have access to the current request in the websocket handler easily
    # for full i18n, but for simplicity we will just clear the input box
    await ws_manager.broadcast_patch("chat-input", Input(id="chat-input", type="text", placeholder="", on_change="chat_message", className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4 text-[var(--color-text)] focus:outline-none focus:border-[var(--color-secondary)] transition-colors").render())
    
    msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    agent_msg = Div(id=msg_id, className="bg-[var(--color-surface)] text-[var(--color-text)] p-3 rounded-2xl rounded-tl-sm self-start w-fit max-w-[80%] shadow-sm")
    await ws_manager.broadcast_append("chat-history", agent_msg.render())
    
    async for chunk in agent.stream(value):
        await ws_manager.broadcast_append(msg_id, chunk)

register_event("chat_message", handle_chat_message)

async def page(request):
    content = Div(
        Card(
            ChatBox(
                id="chat-history",
                className="h-[60vh] mb-6 p-6 bg-[var(--color-background)]/50 rounded-xl border border-[var(--color-border)] flex flex-col space-y-4"
            ),
            Input(
                id="chat-input",
                type="text",
                placeholder=_("agent.placeholder"),
                on_change="chat_message",
                className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4 text-[var(--color-text)] focus:outline-none focus:border-[var(--color-secondary)] transition-colors"
            ),
            className="bg-[var(--color-surface)] border-[var(--color-border)] backdrop-blur-md h-full flex flex-col"
        )
    )
    
    return Layout(content, title=_("agent.title"))
