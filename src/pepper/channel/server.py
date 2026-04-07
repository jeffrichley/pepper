"""Pepper Channel Server — Python MCP + HTTP message router.

MCP server over stdio for Claude Code integration.
HTTP server for external integrations (Discord, email, etc.).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from pepper.channel.router import Router

log = logging.getLogger("pepper-channel")

# --- SSE listener management ---

_source_listeners: dict[str, set] = {}
_global_listeners: set = set()


def emit_to_source(source: str, data: dict) -> None:
    """Emit an event to source-specific and global SSE listeners."""
    encoded = json.dumps(data)
    chunk = f"data: {encoded}\n\n"

    for emit in _source_listeners.get(source, set()):
        emit(chunk)
    for emit in _global_listeners:
        emit(chunk)


# --- HTTP app (ASGI) ---

_start_time = time.monotonic()


def create_http_app(router: Router, mcp_server: FastMCP | None = None):
    """Create an ASGI app with channel HTTP endpoints."""

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return

        method = scope["method"]
        path = scope["path"]

        if method == "GET" and path == "/health":
            router.clean_expired()
            body = json.dumps({
                "status": "ok",
                "registered_sources": router.registered_sources,
                "routing_table_size": router.size,
                "uptime_seconds": int(time.monotonic() - _start_time),
            }).encode()
            await send({"type": "http.response.start", "status": 200, "headers": [
                [b"content-type", b"application/json"],
            ]})
            await send({"type": "http.response.body", "body": body})
            return

        if method == "POST" and path == "/register":
            body = await _read_body(receive)
            data = json.loads(body)
            if not data.get("source"):
                await _json_response(send, 400, {"error": "source is required"})
                return
            router.register_source(data["source"], data.get("description", ""))
            await _json_response(send, 200, {"status": "registered", "source": data["source"]})
            return

        if method == "POST" and path == "/message":
            body = await _read_body(receive)
            data = json.loads(body)
            source = data.get("source")
            chat_id = data.get("chat_id")
            content = data.get("content")
            if not source or not chat_id or not content:
                await _json_response(send, 400, {"error": "source, chat_id, and content are required"})
                return

            router.add(chat_id, source)

            meta = {
                "chat_id": chat_id,
                "sender": data.get("sender", "unknown"),
                "integration": source,
            }
            for k, v in data.get("metadata", {}).items():
                meta[k] = str(v)

            emit_to_source(source, {"chat_id": chat_id, "content": content, "meta": meta})
            await _json_response(send, 200, {"status": "queued", "chat_id": chat_id})
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
    await send({"type": "http.response.start", "status": status, "headers": [
        [b"content-type", b"application/json"],
    ]})
    await send({"type": "http.response.body", "body": body})


# --- MCP Server ---

def create_mcp_server(router: Router) -> FastMCP:
    """Create the MCP server with the reply tool."""

    mcp = FastMCP(
        "pepper-channel",
        instructions=(
            'Messages arrive as <channel source="pepper-channel" chat_id="..." sender="..." integration="...">. '
            "These are from external systems (Discord, email, heartbeat) talking to you. "
            "Reply with the reply tool, passing the chat_id from the tag. "
            "You can include metadata in your reply: reactions (array of emoji names), "
            'type ("message" or "reaction" for reaction-only), and embed (object with title, description, color, fields). '
            "Treat each message as a task or conversation to handle."
        ),
    )

    @mcp.tool()
    def reply(
        chat_id: str,
        text: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Send a reply back through the channel to the integration that sent the message.

        Args:
            chat_id: The conversation to reply in (from the channel tag).
            text: The message to send.
            metadata: Optional dict with reactions (emoji array), type ("message"|"reaction"), embed.
        """
        source = router.lookup(chat_id) or "unknown"
        reply_data = {
            "chat_id": chat_id,
            "text": text,
            "metadata": metadata or {},
            "source": source,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        emit_to_source(source, reply_data)
        return "sent"

    return mcp


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
    mcp = create_mcp_server(router)
    http_app = create_http_app(router, mcp)

    # Start HTTP server in a background thread
    import threading
    import uvicorn

    config = uvicorn.Config(http_app, host="127.0.0.1", port=port, log_level="warning")
    http_server = uvicorn.Server(config)
    http_thread = threading.Thread(target=http_server.run, daemon=True)
    http_thread.start()

    log.info(f"Pepper channel server v2.0.0 (Python) listening on http://127.0.0.1:{port}")

    # Run MCP server on stdio (blocks)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
