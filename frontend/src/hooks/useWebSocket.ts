import { useEffect, useRef, useState, useCallback } from 'react'
import type { WsMessage } from '../types'

interface Options {
  onMessage: (msg: WsMessage) => void
  reconnectDelay?: number
}

export function useWebSocket(url: string, { onMessage, reconnectDelay = 3000 }: Options) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const onMessageRef = useRef(onMessage)
  const shouldReconnect = useRef(true)

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  const connect = useCallback(() => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data) as WsMessage
        onMessageRef.current(msg)
      } catch {
        console.error('WS parse error', event.data)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (shouldReconnect.current) {
        setTimeout(connect, reconnectDelay)
      }
    }

    ws.onerror = () => ws.close()
  }, [url, reconnectDelay])

  useEffect(() => {
    shouldReconnect.current = true
    connect()
    return () => {
      shouldReconnect.current = false
      wsRef.current?.close()
    }
  }, [connect])

  return { connected }
}
