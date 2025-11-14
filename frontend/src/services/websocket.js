/**
 * WebSocket Client for Read-Only Connection
 * Handles connection, reconnection, and heartbeat
 */

import { WS_URL } from '../config/constants';

export class ReadOnlyClient {
  constructor(onEvent, { wsUrl = WS_URL, reconnectDelay = 3000, heartbeatInterval = 5000 } = {}) {
    this.onEvent = onEvent;
    this.wsUrl = wsUrl;
    this.reconnectDelay = reconnectDelay;
    this.heartbeatInterval = heartbeatInterval;
    this.ws = null;
    this.shouldReconnect = false;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
  }
  
  connect() {
    this.shouldReconnect = true;
    this._connect();
  }
  
  _connect() {
    if (!this.shouldReconnect) return;
    
    this.ws = new WebSocket(this.wsUrl);
    
    this.ws.onopen = () => {
      this.onEvent({ type: 'system', content: '✅ Connected to live server' });
      console.log('WebSocket connected');
      this._startHeartbeat();
    };
    
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        console.log('[WebSocket] Message received:', msg.type || 'unknown');
        
        // Safely call onEvent with error protection
        try {
          this.onEvent(msg);
        } catch (eventError) {
          console.error('[WebSocket] Error in event handler:', eventError);
        }
      } catch (e) {
        console.error('[WebSocket] Parse error:', e, 'Raw data:', ev.data);
        this.onEvent({ type: 'system', content: `⚠️ Parse error: ${e.message}` });
      }
    };
    
    this.ws.onerror = (error) => {
      this.onEvent({ type: 'system', content: '❌ Connection error' });
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = (event) => {
      const reason = event.reason || 'Unknown reason';
      const code = event.code || 'Unknown code';
      console.log(`[WebSocket] Connection closed: Code=${code}, Reason=${reason}, WasClean=${event.wasClean}`);
      
      this.onEvent({ 
        type: 'system', 
        content: `🔌 Disconnected (${code}) - reconnecting...` 
      });
      this._stopHeartbeat();
      
      // Auto-reconnect
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => {
          console.log('[WebSocket] Attempting to reconnect...');
          this._connect();
        }, this.reconnectDelay);
      }
    };
  }
  
  _startHeartbeat() {
    this._stopHeartbeat();
    
    // Send first ping immediately
    this._sendPing();
    
    // Then send periodically
    this.heartbeatTimer = setInterval(() => {
      this._sendPing();
    }, this.heartbeatInterval);
  }
  
  _sendPing() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      } catch (e) {
        console.error('Heartbeat send error:', e);
      }
    }
  }
  
  _stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
  
  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
        this.ws.send(messageStr);
        return true;
      } catch (e) {
        console.error('Send error:', e);
        return false;
      }
    } else {
      console.warn('WebSocket is not connected, cannot send message');
      return false;
    }
  }
  
  disconnect() {
    this.shouldReconnect = false;
    this._stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try { this.ws.close(); } catch (e) { console.error('Close error:', e); }
    }
    this.ws = null;
  }
}

