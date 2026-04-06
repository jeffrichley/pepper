#!/usr/bin/env bun
/**
 * Pepper Channel — proof of concept
 *
 * A two-way channel that accepts HTTP POSTs on localhost:8788
 * and forwards them into Pepper's Claude Code session.
 * Pepper can reply back via the reply tool.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'

// --- Outbound: SSE stream for watching replies ---
const listeners = new Set<(chunk: string) => void>()
function send(text: string) {
  const chunk = text.split('\n').map(l => `data: ${l}\n`).join('') + '\n'
  for (const emit of listeners) emit(chunk)
}

const mcp = new Server(
  { name: 'pepper-channel', version: '0.0.1' },
  {
    capabilities: {
      experimental: { 'claude/channel': {} },
      tools: {},
    },
    instructions:
      'Messages arrive as <channel source="pepper-channel" chat_id="..." sender="...">. ' +
      'These are from external systems (Discord, heartbeat, integrations) talking to you. ' +
      'Reply with the reply tool, passing the chat_id from the tag. ' +
      'Treat each message as a task or conversation to handle.',
  },
)

// --- Reply tool ---
mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: 'reply',
    description: 'Send a reply back through the channel',
    inputSchema: {
      type: 'object',
      properties: {
        chat_id: { type: 'string', description: 'The conversation to reply in' },
        text: { type: 'string', description: 'The message to send' },
      },
      required: ['chat_id', 'text'],
    },
  }],
}))

mcp.setRequestHandler(CallToolRequestSchema, async req => {
  if (req.params.name === 'reply') {
    const { chat_id, text } = req.params.arguments as { chat_id: string; text: string }
    send(JSON.stringify({ chat_id, text, ts: new Date().toISOString() }))
    return { content: [{ type: 'text', text: 'sent' }] }
  }
  throw new Error(`unknown tool: ${req.params.name}`)
})

await mcp.connect(new StdioServerTransport())

// --- HTTP server ---
let nextId = 1
const PORT = parseInt(process.env.PEPPER_CHANNEL_PORT ?? '8788')

Bun.serve({
  port: PORT,
  hostname: '127.0.0.1',
  idleTimeout: 0,
  async fetch(req) {
    const url = new URL(req.url)

    // GET /events: SSE stream for watching replies
    if (req.method === 'GET' && url.pathname === '/events') {
      const stream = new ReadableStream({
        start(ctrl) {
          ctrl.enqueue(': connected\n\n')
          const emit = (chunk: string) => ctrl.enqueue(chunk)
          listeners.add(emit)
          req.signal.addEventListener('abort', () => listeners.delete(emit))
        },
      })
      return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      })
    }

    // GET /health: simple health check
    if (req.method === 'GET' && url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'ok', port: PORT }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // POST: forward to Claude as a channel event
    if (req.method === 'POST') {
      const body = await req.text()
      const sender = req.headers.get('X-Sender') ?? 'unknown'
      const chat_id = req.headers.get('X-Chat-Id') ?? String(nextId++)

      await mcp.notification({
        method: 'notifications/claude/channel',
        params: {
          content: body,
          meta: { chat_id, sender, path: url.pathname },
        },
      })
      return new Response(JSON.stringify({ status: 'queued', chat_id }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response('not found', { status: 404 })
  },
})

console.error(`Pepper channel listening on http://127.0.0.1:${PORT}`)
