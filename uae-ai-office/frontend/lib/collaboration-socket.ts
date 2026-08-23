"use client";

// Thin client for the realtime layer (see
// backend/app/modules/collaboration/ws.py): one multiplexed WebSocket
// carrying typing indicators, presence, and WebRTC signaling. Kept as a
// small hand-rolled pub/sub rather than a library -- the wire protocol is
// a handful of small JSON event shapes, not worth a dependency.
//
// Ephemeral by design, matching the backend: nothing here is persisted
// to component state beyond what's needed to render the current typing/
// presence indicators, and a page reload starts clean.

export type CollaborationSocketEvent =
  | { type: "typing"; conversation_id: string; user_id: string }
  | { type: "stop_typing"; conversation_id: string; user_id: string }
  | { type: "presence_status"; online_user_ids: string[] }
  | { type: "webrtc_offer"; call_session_id: string; from_user_id: string; payload: unknown }
  | { type: "webrtc_answer"; call_session_id: string; from_user_id: string; payload: unknown }
  | { type: "webrtc_ice_candidate"; call_session_id: string; from_user_id: string; payload: unknown }
  | { type: "error"; message: string };

type Listener = (event: CollaborationSocketEvent) => void;

const RECONNECT_DELAY_MS = 2000;

class CollaborationSocketClient {
  private socket: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private token: string | null = null;
  private urlBuilder: ((token: string) => string) | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closedByClient = false;

  configure(urlBuilder: (token: string) => string) {
    this.urlBuilder = urlBuilder;
  }

  connect(token: string) {
    if (this.socket && this.token === token && this.socket.readyState <= WebSocket.OPEN) return;
    this.token = token;
    this.closedByClient = false;
    this.open();
  }

  private open() {
    if (!this.urlBuilder || !this.token) return;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    const socket = new WebSocket(this.urlBuilder(this.token));
    this.socket = socket;

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as CollaborationSocketEvent;
        this.listeners.forEach((listener) => listener(data));
      } catch {
        // Malformed frame -- ignore rather than crash the connection.
      }
    };

    socket.onclose = () => {
      if (this.closedByClient) return;
      this.reconnectTimer = setTimeout(() => this.open(), RECONNECT_DELAY_MS);
    };

    socket.onerror = () => {
      socket.close();
    };
  }

  disconnect() {
    this.closedByClient = true;
    this.token = null;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
  }

  send(payload: Record<string, unknown>) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

// One connection per browser tab, shared across every component that
// needs realtime events -- mirrors the "one WebSocket per client"
// design on the backend rather than opening a socket per open
// conversation.
export const collaborationSocket = new CollaborationSocketClient();

