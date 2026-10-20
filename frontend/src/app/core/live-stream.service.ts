import { Injectable, signal } from '@angular/core';
import { Observable, Subject } from 'rxjs';

import { LiveStreamEvent } from './api.models';

function resolveWebSocketUrl(): string {
  if (typeof window === 'undefined') {
    return 'ws://127.0.0.1:8000/ws/live';
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const hostname = window.location.hostname || '127.0.0.1';
  const apiHost = hostname === 'localhost' ? '127.0.0.1' : hostname;

  return `${protocol}//${apiHost}:8000/ws/live`;
}

@Injectable({ providedIn: 'root' })
export class LiveStreamService {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private consumerCount = 0;
  private readonly eventBus = new Subject<LiveStreamEvent>();

  readonly connectionState = signal<'connecting' | 'connected' | 'disconnected'>('disconnected');
  readonly lastEventAt = signal<string | null>(null);

  connect(): Observable<LiveStreamEvent> {
    return new Observable<LiveStreamEvent>((observer) => {
      this.consumerCount += 1;
      this.ensureConnection();

      const subscription = this.eventBus.subscribe(observer);

      return () => {
        subscription.unsubscribe();
        this.consumerCount = Math.max(0, this.consumerCount - 1);
        if (this.consumerCount === 0) {
          this.dispose();
        }
      };
    });
  }

  private ensureConnection(): void {
    if (typeof WebSocket === 'undefined') {
      this.connectionState.set('disconnected');
      return;
    }

    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.connectionState.set('connecting');
    this.socket = new WebSocket(resolveWebSocketUrl());

    this.socket.onopen = () => {
      this.connectionState.set('connected');
    };

    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as LiveStreamEvent;
        this.lastEventAt.set(payload.timestamp);
        this.eventBus.next(payload);
      } catch {
        // Ignore malformed frames and keep the connection alive.
      }
    };

    this.socket.onclose = () => {
      this.socket = null;
      this.connectionState.set('disconnected');
      if (this.consumerCount > 0) {
        this.reconnectTimer = setTimeout(() => this.ensureConnection(), 2500);
      }
    };

    this.socket.onerror = () => {
      this.connectionState.set('disconnected');
    };
  }

  private dispose(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.connectionState.set('disconnected');
  }
}
