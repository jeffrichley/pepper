#!/usr/bin/env bun
/**
 * Pepper Channel Server — production message router
 *
 * MCP channel server that routes messages between external integrations
 * and Pepper's Claude Code session. Single port, routing by source metadata.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'

// --- Configuration ---
const PORT = parseInt(process.env.PEPPER_CHANNEL_PORT ?? '8788')
const ROUTE_TTL_MS = parseInt(process.env.PEPPER_ROUTE_TTL_HOURS ?? '24') * 60 * 60 * 1000
const startTime = Date.now()

// --- Routing table: chat_id -> { source, timestamp } ---
const routes = new Map<string, { source: string; ts: number }>()

function cleanExpiredRoutes() {
  const now = Date.now()
  for (const [id, entry] of routes) {
    if (now - entry.ts > ROUTE_TTL_MS) routes.delete(id)
  }
}

// Run cleanup every hour
setInterval(cleanExpiredRoutes, 60 * 60 * 1000)

// --- Registered integrations ---
const registrations = new Map<string, { description: string; ts: number }>()

// --- SSE listeners: source -> Set<emit function> ---
type Emitter = (chunk: string) => void
const sseListeners = new Map<string, Set<Emitter>>()
const globalListeners = new Set<Emitter>()

function emitToSource(source: string, data: object) {
  const json = JSON.stringify(data)
  const chunk = `data: ${json}\n\n`

  // Send to source-specific listeners
  const sourceListeners = sseListeners.get(source)
  if (sourceListeners) {
    for (const emit of sourceListeners) emit(chunk)
  }

  // Send to global listeners (no filter)
  for (const emit of globalListeners) emit(chunk)
}

// --- MCP Server ---
const mcp = new Server(
  { name: 'pepper-channel', version: '1.0.0' },
  {
    capabilities: {
      experimental: { 'claude/channel': {} },
      tools: {},
    },
    instructions:
      'Messages arrive as <channel source="pepper-channel" chat_id="..." sender="..." integration="...">. ' +
      'These are from external systems (Discord, email, heartbeat) talking to you. ' +
      'Reply with the reply tool, passing the chat_id from the tag. ' +
      'You can include metadata in your reply: reactions (array of emoji names), ' +
      'type ("message" or "reaction" for reaction-only), and embed (object with title, description, color, fields). ' +
      'Treat each message as a task or conversation to handle.',
  },
)

// --- Reply tool ---
mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: 'reply',
    description: 'Send a reply back through the channel to the integration that sent the message',
    inputSchema: {
      type: 'object',
      properties: {
        chat_id: { type: 'string', description: 'The conversation to reply in (from the channel tag)' },
        text: { type: 'string', description: 'The message to send' },
        metadata: {
          type: 'object',
          description: 'Optional: reactions (emoji array), type ("message"|"reaction"), embed (object with title/description/color/fields)',
          properties: {
            reactions: { type: 'array', items: { type: 'string' }, description: 'Emoji names to react with' },
            type: { type: 'string', enum: ['message', 'reaction'], description: 'Reply type: message (default) or reaction-only' },
            embed: {
              type: 'object',
              description: 'Rich embed with title, description, color (int), fields (array of {name, value, inline})',
            },
          },
        },
      },
      required: ['chat_id'],
    },
  }],
}))

mcp.setRequestHandler(CallToolRequestSchema, async req => {
  if (req.params.name === 'reply') {
    const { chat_id, text, metadata } = req.params.arguments as {
      chat_id: string
      text?: string
      metadata?: { reactions?: string[]; type?: string; embed?: object }
    }

    const route = routes.get(chat_id)
    const source = route?.source ?? 'unknown'

    const reply = {
      chat_id,
      text: text ?? '',
      metadata: metadata ?? {},
      source,
      ts: new Date().toISOString(),
    }

    emitToSource(source, reply)

    return { content: [{ type: 'text', text: 'sent' }] }
  }
  throw new Error(`unknown tool: ${req.params.name}`)
})

await mcp.connect(new StdioServerTransport())

// --- HTTP Server ---
Bun.serve({
  port: PORT,
  hostname: '127.0.0.1',
  idleTimeout: 0,
  async fetch(req) {
    const url = new URL(req.url)

    // GET /health
    if (req.method === 'GET' && url.pathname === '/health') {
      cleanExpiredRoutes()
      return new Response(JSON.stringify({
        status: 'ok',
        port: PORT,
        registered_sources: Array.from(registrations.keys()),
        routing_table_size: routes.size,
        uptime_seconds: Math.floor((Date.now() - startTime) / 1000),
      }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // GET /events?source=discord — filtered SSE stream
    if (req.method === 'GET' && url.pathname === '/events') {
      const source = url.searchParams.get('source')
      const stream = new ReadableStream({
        start(ctrl) {
          ctrl.enqueue(': connected\n\n')
          const emit = (chunk: string) => ctrl.enqueue(chunk)

          if (source) {
            if (!sseListeners.has(source)) sseListeners.set(source, new Set())
            sseListeners.get(source)!.add(emit)
            req.signal.addEventListener('abort', () => {
              sseListeners.get(source)?.delete(emit)
            })
          } else {
            globalListeners.add(emit)
            req.signal.addEventListener('abort', () => globalListeners.delete(emit))
          }
        },
      })
      return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      })
    }

    // POST /register
    if (req.method === 'POST' && url.pathname === '/register') {
      const body = await req.json() as { source: string; description?: string }
      if (!body.source) {
        return new Response(JSON.stringify({ error: 'source is required' }), { status: 400 })
      }
      registrations.set(body.source, {
        description: body.description ?? '',
        ts: Date.now(),
      })
      return new Response(JSON.stringify({ status: 'registered', source: body.source }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // POST /message — main inbound endpoint
    if (req.method === 'POST' && url.pathname === '/message') {
      const body = await req.json() as {
        source: string
        chat_id: string
        sender?: string
        content: string
        metadata?: Record<string, string>
      }

      if (!body.source || !body.content || !body.chat_id) {
        return new Response(JSON.stringify({ error: 'source, chat_id, and content are required' }), { status: 400 })
      }

      // Store route for reply routing
      routes.set(body.chat_id, { source: body.source, ts: Date.now() })

      // Build meta attributes for the channel tag
      const meta: Record<string, string> = {
        chat_id: body.chat_id,
        sender: body.sender ?? 'unknown',
        integration: body.source,
      }
      if (body.metadata) {
        for (const [k, v] of Object.entries(body.metadata)) {
          meta[k] = String(v)
        }
      }

      await mcp.notification({
        method: 'notifications/claude/channel',
        params: {
          content: body.content,
          meta,
        },
      })

      return new Response(JSON.stringify({ status: 'queued', chat_id: body.chat_id }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response(JSON.stringify({ error: 'not found' }), { status: 404 })
  },
})

console.error(`Pepper channel server v1.0.0 listening on http://127.0.0.1:${PORT}`)
