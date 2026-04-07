"""Pepper Channel Server — Python MCP + HTTP message router.

Low-level MCP server over stdio for Claude Code integration.
HTTP server for external integrations (Discord, email, etc.).

Uses the low-level MCP Server API (not FastMCP) to support custom
notifications via the experimental 'claude/channel' capability.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
import threading
import time
from datetime import UTC, datetime
from typing import Any

from mcp import types
from mcp.server.lowlevel.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from pepper.channel.router import Router

log = logging.getLogger("pepper-channel")

# --- SSE listener management ---
# Each listener is an asyncio.Queue that receives SSE chunks.

_source_listeners: dict[str, set[asyncio.Queue]] = {}
_global_listeners: set[asyncio.Queue] = set()
_sse_lock = threading.Lock()


def emit_to_source(source: str, data: dict) -> None:
    """Emit an event to source-specific and global SSE listeners (thread-safe)."""
    encoded = json.dumps(data)
    chunk = f"data: {encoded}\n\n"

    with _sse_lock:
        for q in _source_listeners.get(source, set()):
            with contextlib.suppress(Exception):
                q.put_nowait(chunk)
        for q in _global_listeners:
            with contextlib.suppress(Exception):
                q.put_nowait(chunk)


def _add_sse_listener(source: str | None) -> asyncio.Queue:
    """Register an SSE listener queue. If source is None, listens to all."""
    q: asyncio.Queue = asyncio.Queue()
    with _sse_lock:
        if source:
            if source not in _source_listeners:
                _source_listeners[source] = set()
            _source_listeners[source].add(q)
        else:
            _global_listeners.add(q)
    return q


def _remove_sse_listener(source: str | None, q: asyncio.Queue) -> None:
    """Unregister an SSE listener queue."""
    with _sse_lock:
        if source:
            listeners = _source_listeners.get(source)
            if listeners:
                listeners.discard(q)
        else:
            _global_listeners.discard(q)


# --- Notification bridge (HTTP thread -> MCP event loop) ---

_notification_queue: asyncio.Queue | None = None
_mcp_loop: asyncio.AbstractEventLoop | None = None


def _enqueue_notification(content: str, meta: dict[str, str]) -> None:
    """Thread-safe: enqueue a notification for the MCP event loop to send."""
    if _notification_queue is not None and _mcp_loop is not None:
        _mcp_loop.call_soon_threadsafe(
            _notification_queue.put_nowait,
            {"content": content, "meta": meta},
        )


# --- HTTP app (ASGI) ---

_start_time = time.monotonic()


def create_http_app(router: Router):  # noqa: PLR0915
    """Create an ASGI app with channel HTTP endpoints."""

    async def app(scope, receive, send):  # noqa: PLR0911, PLR0912, PLR0915
        if scope["type"] != "http":
            return

        method = scope["method"]
        path = scope["path"]

        if method == "GET" and path == "/events":
            # SSE endpoint — long-lived connection that streams replies
            query = scope.get("query_string", b"").decode()
            source = None
            for param in query.split("&"):
                if param.startswith("source="):
                    source = param[7:]

            q = _add_sse_listener(source)
            try:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [
                            [b"content-type", b"text/event-stream"],
                            [b"cache-control", b"no-cache"],
                            [b"connection", b"keep-alive"],
                        ],
                    }
                )
                # Send initial connected comment
                await send(
                    {
                        "type": "http.response.body",
                        "body": b": connected\n\n",
                        "more_body": True,
                    }
                )

                # Stream events from the queue
                while True:
                    try:
                        chunk = await asyncio.wait_for(q.get(), timeout=30.0)
                        await send(
                            {
                                "type": "http.response.body",
                                "body": chunk.encode(),
                                "more_body": True,
                            }
                        )
                    except TimeoutError:
                        # Send keepalive comment
                        await send(
                            {
                                "type": "http.response.body",
                                "body": b": keepalive\n\n",
                                "more_body": True,
                            }
                        )
                    except Exception:
                        break
            finally:
                _remove_sse_listener(source, q)
            return

        if method == "GET" and path == "/health":
            router.clean_expired()
            body = json.dumps(
                {
                    "status": "ok",
                    "registered_sources": router.registered_sources,
                    "routing_table_size": router.size,
                    "uptime_seconds": int(time.monotonic() - _start_time),
                }
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        [b"content-type", b"application/json"],
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        if method == "POST" and path == "/register":
            body = await _read_body(receive)
            data = json.loads(body)
            if not data.get("source"):
                await _json_response(send, 400, {"error": "source is required"})
                return
            router.register_source(
                data["source"],
                data.get("description", ""),
            )
            await _json_response(
                send,
                200,
                {"status": "registered", "source": data["source"]},
            )
            return

        if method == "POST" and path == "/message":
            body = await _read_body(receive)
            data = json.loads(body)
            source = data.get("source")
            chat_id = data.get("chat_id")
            content = data.get("content")
            if not source or not chat_id or not content:
                await _json_response(
                    send,
                    400,
                    {"error": "source, chat_id, and content are required"},
                )
                return

            router.add(chat_id, source)

            meta = {
                "chat_id": chat_id,
                "sender": data.get("sender", "unknown"),
                "integration": source,
            }
            for k, v in data.get("metadata", {}).items():
                meta[k] = str(v)

            # Notify Claude Code via MCP notification bridge
            _enqueue_notification(content, meta)

            emit_to_source(
                source,
                {"chat_id": chat_id, "content": content, "meta": meta},
            )
            await _json_response(
                send,
                200,
                {"status": "queued", "chat_id": chat_id},
            )
            return

        await _json_response(send, 404, {"error": "not found"})

    return app


async def _read_body(receive) -> bytes:
    body = b""
    while True:
        msg = await receive()
        body += msg.get("body", b"")
        if not msg.get("more_body"):
            break
    return body


async def _json_response(send, status: int, data: dict) -> None:
    body = json.dumps(data).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


# --- MCP Server (low-level API) ---


def create_mcp_server(router: Router) -> Server:
    """Create the low-level MCP server with reply tool and notifications."""
    server = Server(
        name="pepper-channel",
        version="2.0.0",
        instructions=(
            "Messages arrive as notifications with method "
            '"notifications/claude/channel". '
            'The notification params contain "content" (the message text) and "meta" '
            "(with chat_id, sender, integration, and other metadata). "
            "Reply with the reply tool, passing the chat_id"
            " from the notification meta. "
            "You can include metadata in your reply: reactions (array of emoji names), "
            'type ("message" or "reaction" for reaction-only), '
            "and embed (object with title, description, color, fields). "
            "Treat each message as a task or conversation to handle."
        ),
    )

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="reply",
                description=(
                    "Send a reply back through the channel"
                    " to the integration that sent the message"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chat_id": {
                            "type": "string",
                            "description": (
                                "The conversation to reply in"
                                " (from the channel notification meta)"
                            ),
                        },
                        "text": {
                            "type": "string",
                            "description": "The message to send",
                        },
                        "metadata": {
                            "type": "object",
                            "description": (
                                "Optional: reactions (emoji array),"
                                ' type ("message"|"reaction"),'
                                " embed (object with"
                                " title/description/color/fields)"
                            ),
                            "properties": {
                                "reactions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Emoji names to react with",
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["message", "reaction"],
                                    "description": (
                                        "Reply type: message (default) or reaction-only"
                                    ),
                                },
                                "embed": {
                                    "type": "object",
                                    "description": (
                                        "Rich embed with title,"
                                        " description, color (int),"
                                        " fields (array of"
                                        " {name, value, inline})"
                                    ),
                                },
                            },
                        },
                    },
                    "required": ["chat_id"],
                },
            )
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> list[types.TextContent]:
        if name != "reply":
            raise ValueError(f"unknown tool: {name}")

        arguments = arguments or {}
        chat_id = arguments.get("chat_id", "")
        text = arguments.get("text", "")
        metadata = arguments.get("metadata", {})

        source = router.lookup(chat_id) or "unknown"
        reply_data = {
            "chat_id": chat_id,
            "text": text,
            "metadata": metadata,
            "source": source,
            "ts": datetime.now(UTC).isoformat(),
        }
        emit_to_source(source, reply_data)

        return [types.TextContent(type="text", text="sent")]

    return server


async def _notification_pump(server: Server, read_stream, write_stream) -> None:  # noqa: ARG001
    """Drain the notification queue and send MCP notifications to Claude Code.

    This runs on the MCP event loop and sends custom notifications
    that were enqueued by the HTTP thread.
    """
    global _notification_queue  # noqa: PLW0603
    _notification_queue = asyncio.Queue()

    # We need the session to send notifications, but the session is created
    # inside server.run(). Instead, we'll send raw JSON-RPC notifications
    # directly to the write stream.
    from mcp.shared.session import SessionMessage  # noqa: PLC0415
    from mcp.types import JSONRPCNotification  # noqa: PLC0415

    while True:
        item = await _notification_queue.get()
        try:
            # Build a raw JSON-RPC notification (custom method)
            notification = JSONRPCNotification(
                jsonrpc="2.0",
                method="notifications/claude/channel",
                params=item,  # {"content": "...", "meta": {...}}
            )
            message = SessionMessage(message=notification)
            await write_stream.send(message)
            chat_id = item.get("meta", {}).get("chat_id", "unknown")
            log.debug(f"Sent channel notification: {chat_id}")
        except Exception as e:
            log.error(f"Failed to send notification: {e}")


def main() -> None:
    """Entry point for pepper-channel. Runs MCP over stdio + HTTP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    port = int(os.environ.get("PEPPER_CHANNEL_PORT", "8788"))
    ttl_hours = int(os.environ.get("PEPPER_ROUTE_TTL_HOURS", "24"))

    router = Router(ttl_seconds=ttl_hours * 3600)
    server = create_mcp_server(router)
    http_app = create_http_app(router)

    async def run():
        global _mcp_loop  # noqa: PLW0603
        _mcp_loop = asyncio.get_running_loop()

        # Start HTTP server in a background thread
        import uvicorn  # noqa: PLC0415

        config = uvicorn.Config(
            http_app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
        http_server = uvicorn.Server(config)
        http_thread = threading.Thread(target=http_server.run, daemon=True)
        http_thread.start()

        log.info(
            "Pepper channel server v2.0.0 (Python)"
            f" listening on http://127.0.0.1:{port}",
        )

        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options(
                notification_options=NotificationOptions(),
                experimental_capabilities={"claude/channel": {}},
            )

            # Start notification pump alongside the MCP server
            pump_task = asyncio.create_task(
                _notification_pump(server, read_stream, write_stream)
            )

            try:
                await server.run(
                    read_stream,
                    write_stream,
                    init_options,
                    raise_exceptions=False,
                )
            finally:
                pump_task.cancel()

    asyncio.run(run())


if __name__ == "__main__":
    main()
