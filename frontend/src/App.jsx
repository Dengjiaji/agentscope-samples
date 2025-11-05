import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

/**
 * Live Trading Intelligence Platform - Read-Only Dashboard
 * Geek Style - Terminal-inspired, minimal, monochrome
 * 
 * 连接到持续运行的后端服务器，实时显示交易系统状态
 */

// ====== Configuration ======
const ASSET_BASE_URL = "/assets/company_room";
const LOGO_BASE_URL = "/assets/logos";

const ASSETS = {
  roomBg: `${ASSET_BASE_URL}/full_room_with_roles_tech_style.png`,
};

// Stock logos mapping
const STOCK_LOGOS = {
  'AAPL': `${LOGO_BASE_URL}/AAPL.png`,
  'MSFT': `${LOGO_BASE_URL}/MSFT.png`,
  'GOOGL': `${LOGO_BASE_URL}/GOOGL.png`,
  'AMZN': `${LOGO_BASE_URL}/AMZN.png`,
  'NVDA': `${LOGO_BASE_URL}/NVDA.png`,
  'META': `${LOGO_BASE_URL}/META.png`,
  'TSLA': `${LOGO_BASE_URL}/TSLA.png`,
};

const SCENE_NATIVE = { width: 1184, height: 864 };

const AGENT_SEATS = [
  { x: 545, y: 380 },
  { x: 600, y: 470 },
  { x: 460, y: 490 },
  { x: 540, y: 590 },
  { x: 710, y: 560 },
  { x: 780, y: 490 },
];

const AGENTS = [
  { id: "alpha", name: "Bob", role: "Portfolio Manager" },
  { id: "beta", name: "Carl", role: "Risk Manager" },
  { id: "gamma", name: "Alice", role: "Valuation Analyst" },
  { id: "delta", name: "David", role: "Sentiment Analyst" },
  { id: "epsilon", name: "Eve", role: "Fundamentals Analyst" },
  { id: "zeta", name: "Frank", role: "Technical Analyst" },
];

const BUBBLE_LIFETIME_MS = 8000; // 延长至10秒，便于阅读agent发言
const CHART_MARGIN = { left: 60, right: 20, top: 20, bottom: 40 };
const AXIS_TICKS = 5;

// WebSocket服务器地址（生产环境需要修改为实际部署地址）
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8765";

// Initial ticker symbols (MAG7 companies) - prices will be updated from real-time data
const MOCK_TICKERS = [
  { symbol: 'AAPL', price: null, change: null },
  { symbol: 'MSFT', price: null, change: null },
  { symbol: 'GOOGL', price: null, change: null },
  { symbol: 'AMZN', price: null, change: null },
  { symbol: 'NVDA', price: null, change: null },
  { symbol: 'META', price: null, change: null },
  { symbol: 'TSLA', price: null, change: null }
];

// ====== WebSocket Client (Read-Only) ======
class ReadOnlyClient {
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
      
      // 自动重连
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

// ====== Global Styles ======
function GlobalStyles() {
  return (
    <style>{`
      * { box-sizing: border-box; }
      html, body, #root { 
        height: 100%; 
        width: 100%;
        margin: 0; 
        padding: 0;
        max-width: none;
      }
      body {
        font-family: 'Courier New', Courier, monospace;
        background: #f5f5f5;
        color: #000000;
        font-size: 13px;
        line-height: 1.5;
      }
      
      /* Layout */
      .app {
        display: flex;
        flex-direction: column;
        height: 100vh;
        width: 100%;
        overflow: hidden;
        background: #f5f5f5;
        max-width: none;
      }
      
      /* Header */
      .header {
        background: #ffffff;
        border-bottom: 1px solid #e0e0e0;
        padding: 0;
        display: flex;
        align-items: stretch;
        flex-shrink: 0;
        font-family: 'Courier New', Courier, monospace;
        width: 100%;
        max-width: none;
      }
      
      .header-title {
        padding: 14px 20px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 1px;
        color: #000000;
        border-right: 1px solid #e0e0e0;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      
      .header-tabs {
        display: flex;
        align-items: stretch;
        flex: 1;
      }
      
      .header-tab {
        padding: 14px 24px;
        border: none;
        border-right: 1px solid #e0e0e0;
        border-radius: 0;
        background: transparent;
        font-family: inherit;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
        color: #666666;
        cursor: pointer;
        transition: all 0.2s;
        text-transform: uppercase;
        position: relative;
      }
      
      .header-tab:hover {
        background: #f5f5f5;
        color: #000000;
        border-radius: 0;
      }
      
      .header-tab.active {
        background: #000000;
        color: #ffffff;
        border-radius: 0;
      }
      
      .header-tab:focus {
        background: #000000;
        color: #ffffff;
        outline: none;
        border-radius: 0;
      }
      
      .header-tab.divider::after {
        content: '';
        position: absolute;
        right: 0;
        top: 25%;
        height: 50%;
        width: 2px;
        background: #000000;
      }
      
      .header-status {
        margin-left: auto;
        padding: 14px 20px;
        display: flex;
        align-items: center;
        gap: 16px;
        font-size: 11px;
        color: #666666;
        border-left: 1px solid #e0e0e0;
      }
      
      .status-indicator {
        font-weight: 700;
      }
      
      .status-indicator.live { 
        color: #00C853;
      }
      
      .status-indicator.disconnected { 
        color: #FF1744;
      }
      
      /* Ticker Bar */
      .ticker-bar {
        background: #000000;
        border-bottom: 1px solid #333333;
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 24px;
        overflow-x: auto;
        flex-shrink: 0;
        width: 100%;
        max-width: none;
      }
      
      .ticker-item {
        display: flex;
        align-items: center;
        gap: 8px;
        white-space: nowrap;
      }
      
      .ticker-symbol {
        font-size: 11px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: 1px;
      }
      
      .ticker-price {
        font-size: 13px;
        font-weight: 700;
        color: #ffffff;
        position: relative;
        overflow: hidden;
        display: inline-block;
        min-width: 60px;
      }
      
      .ticker-price-value {
        display: inline-block;
        transition: transform 0.3s ease-out;
      }
      
      .ticker-price-value.rolling {
        animation: roll 0.5s ease-out;
      }
      
      @keyframes roll {
        0% {
          transform: translateY(-100%);
          opacity: 0;
        }
        50% {
          opacity: 0.5;
        }
        100% {
          transform: translateY(0);
          opacity: 1;
        }
      }
      
      .ticker-change {
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 0;
      }
      
      .ticker-change.positive {
        color: #00C853;
        background: rgba(0, 200, 83, 0.1);
      }
      
      .ticker-change.negative {
        color: #FF1744;
        background: rgba(255, 23, 68, 0.1);
      }
      
      .ticker-change:not(.positive):not(.negative) {
        color: #666666;
        background: transparent;
      }
      
      .portfolio-value {
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 12px;
        padding-left: 24px;
        border-left: 1px solid #333333;
      }
      
      .portfolio-label {
        font-size: 11px;
        font-weight: 700;
        color: #999999;
        letter-spacing: 1px;
      }
      
      .portfolio-amount {
        font-size: 16px;
        font-weight: 700;
        color: #ffffff;
      }
      
      /* Main Container */
      .main-container {
        flex: 1;
        display: flex;
        overflow: hidden;
        background: #f5f5f5;
        position: relative;
        width: 100%;
        max-width: none;
      }
      
      .left-panel {
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: #ffffff;
        min-width: 400px;
        max-width: none;
      }
      
      .resizer {
        width: 4px;
        background: #e0e0e0;
        cursor: col-resize;
        flex-shrink: 0;
        transition: background 0.2s;
      }
      
      .resizer:hover {
        background: #000000;
      }
      
      .resizer.resizing {
        background: #000000;
      }
      
      .right-panel {
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: #ffffff;
        min-width: 300px;
        max-width: none;
      }
      
      /* Chart Section */
      .chart-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: #ffffff;
        position: relative;
        width: 100%;
        max-width: none;
      }
      
      .chart-container {
        flex: 1;
        padding: 24px;
        overflow: hidden;
        position: relative;
        background: #ffffff;
        width: 100%;
        max-width: none;
      }
      
      .chart-canvas {
        width: 100%;
        height: 100%;
        max-width: none;
      }
      
      /* Room View */
      .room-view {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: #ffffff;
        position: relative;
        width: 100%;
        max-width: none;
      }
      
      .room-agents-indicator {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 16px;
        padding: 12px 20px;
        border-bottom: 1px solid #e0e0e0;
        background: #fafafa;
        flex-wrap: wrap;
      }
      
      .agent-indicator {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #666666;
        transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      
      .agent-indicator.speaking {
        color: #000000;
        transform: scale(1.05);
      }
      
      .agent-indicator-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #e0e0e0;
        transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      
      .agent-indicator.speaking .agent-indicator-dot {
        background: #00C853;
        box-shadow: 0 0 12px rgba(0, 200, 83, 0.8);
        transform: scale(1.3);
        animation: pulse 1.5s ease-in-out infinite;
      }
      
      @keyframes pulse {
        0%, 100% {
          box-shadow: 0 0 12px rgba(0, 200, 83, 0.8);
        }
        50% {
          box-shadow: 0 0 20px rgba(0, 200, 83, 1);
        }
      }
      
      .room-canvas-container {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        padding: 24px;
        position: relative;
      }
      
      .room-scene {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      
      .room-canvas {
        display: block;
        image-rendering: pixelated;
        image-rendering: crisp-edges;
      }
      
      .room-bubble {
        position: absolute;
        max-width: 200px;
        font-size: 11px;
        background: #ffffff;
        color: #000000;
        padding: 8px 10px;
        border: 2px solid #000000;
        box-shadow: 3px 3px 0 0 rgba(0, 0, 0, 0.2);
        font-family: 'Courier New', monospace;
        line-height: 1.4;
        animation: bubbleAppear 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      
      @keyframes bubbleAppear {
        0% {
          opacity: 0;
          transform: scale(0.5) translateY(10px);
        }
        100% {
          opacity: 1;
          transform: scale(1) translateY(0);
        }
      }
      
      .room-bubble::after {
        content: "";
        position: absolute;
        left: 12px;
        bottom: -8px;
        width: 10px;
        height: 10px;
        background: #ffffff;
        border-left: 2px solid #000000;
        border-bottom: 2px solid #000000;
        transform: rotate(-45deg);
      }
      
      .room-bubble-name {
        font-weight: 900;
        margin-bottom: 4px;
        font-size: 10px;
        letter-spacing: 0.5px;
      }
      
      /* View Toggle Button */
      .view-toggle-btn {
        position: absolute;
        top: 50%;
        transform: translateY(-50%);
        z-index: 20;
        width: 32px;
        height: 80px;
        background: #ffffff;
        border: 1px solid #e0e0e0;
        cursor: pointer;
        transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        font-size: 18px;
        color: #666666;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      }
      
      .view-toggle-btn:hover {
        background: #000000;
        border-color: #000000;
        color: #ffffff;
        transform: translateY(-50%) scale(1.1);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
      }
      
      .view-toggle-btn:active {
        transform: translateY(-50%) scale(0.95);
      }
      
      .view-toggle-btn.left {
        left: 0;
        border-left: none;
        border-radius: 0 4px 4px 0;
      }
      
      .view-toggle-btn.right {
        right: 0;
        border-right: none;
        border-radius: 4px 0 0 4px;
      }
      
      .view-toggle-btn:focus {
        outline: none;
      }
      
      /* View Transition */
      .view-container {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
      }
      
      .view-slider {
        position: absolute;
        width: 100%;
        height: 100%;
        display: flex;
        transition: transform 1.6s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      
      .view-slider.normal-speed {
        transition: transform 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      
      .view-slider.show-chart {
        transform: translateX(-100%);
      }
      
      .view-slider.show-room {
        transform: translateX(0);
      }
      
      .view-panel {
        flex: 0 0 100%;
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
      }
      
      /* Chart Tabs - Floating inside chart */
      .chart-tabs-floating {
        position: absolute;
        top: 16px;
        right: 16px;
        display: flex;
        gap: 0;
        border: 1px solid #cccccc;
        background: #ffffff;
        z-index: 10;
      }
      
      .chart-tab {
        padding: 4px 8px;
        border: none;
        border-right: 1px solid #cccccc;
        border-radius: 0;
        background: #ffffff;
        font-family: inherit;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #666666;
        cursor: pointer;
        transition: all 0.15s;
      }
      
      .chart-tab:last-child {
        border-right: none;
      }
      
      .chart-tab:hover {
        background: #f5f5f5;
        color: #000000;
        border-radius: 0;
      }
      
      .chart-tab.active {
        background: #000000;
        color: #ffffff;
        border-color: #000000;
        border-radius: 0;
      }
      
      .chart-tab:focus {
        outline: none;
        border-radius: 0;
      }
      
      /* Intelligence Feed */
      .intelligence-feed {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        width: 100%;
        max-width: none;
      }
      
      .feed-header {
        padding: 16px 20px;
        border-bottom: 1px solid #e0e0e0;
        background: #ffffff;
        width: 100%;
        max-width: none;
      }
      
      .feed-title {
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 2px;
        margin: 0;
        color: #000000;
        text-transform: uppercase;
      }
      
      .feed-content {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        background: #fafafa;
        width: 100%;
        max-width: none;
      }
      
      /* Feed Cards */
      .feed-card {
        border: none;
        border-bottom: 1px solid #e0e0e0;
        background: transparent;
        font-size: 11px;
        transition: all 0.2s;
        padding: 12px 0;
      }
      
      .feed-card:hover {
        background: #fafafa;
      }
      
      .card-header {
        padding: 0 0 6px 0;
        border-bottom: none;
        background: transparent;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      
      .card-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 10px;
        font-weight: 700;
        color: #666666;
        letter-spacing: 1px;
        text-transform: uppercase;
      }
      
      .card-icon {
        font-size: 10px;
      }
      
      .card-time {
        font-size: 9px;
        color: #999999;
      }
      
      .message-content-wrapper {
        padding: 4px 0;
      }
      
      .message-text {
        font-size: 12px;
        line-height: 1.6;
        color: #333333;
        word-wrap: break-word;
      }
      
      .message-expand-btn {
        margin-top: 6px;
        padding: 0;
        border: none;
        background: none;
        font-family: inherit;
        font-size: 10px;
        font-weight: 700;
        color: #666666;
        cursor: pointer;
        text-decoration: underline;
        transition: color 0.2s;
      }
      
      .message-expand-btn:hover {
        color: #000000;
      }
      
      .message-expand-btn:focus {
        outline: none;
      }
      
      .live-badge {
        font-size: 10px;
        font-weight: 700;
        color: #00C853;
      }
      
      .conference-meta {
        padding: 4px 0 8px 0;
        background: transparent;
        border-bottom: none;
        font-size: 9px;
        color: #999999;
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }
      
      .conference-messages {
        padding: 8px 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      
      .conf-message {
        padding: 6px 0;
        border-bottom: 1px dotted #e0e0e0;
      }
      
      .conf-message:last-child {
        border-bottom: none;
      }
      
      .msg-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
      }
      
      .msg-agent {
        font-size: 10px;
        font-weight: 700;
        color: #666666;
      }
      
      .msg-time {
        font-size: 9px;
        color: #999999;
      }
      
      .msg-content {
        font-size: 12px;
        line-height: 1.6;
        color: #333333;
      }
      
      .expand-btn {
        width: 100%;
        padding: 8px 0;
        border: none;
        border-top: 1px solid #e0e0e0;
        border-radius: 0;
        background: transparent;
        font-family: inherit;
        font-size: 10px;
        font-weight: 700;
        color: #666666;
        cursor: pointer;
        text-align: center;
        transition: color 0.2s;
        letter-spacing: 0.5px;
      }
      
      .expand-btn:hover {
        background: transparent;
        color: #000000;
        border-radius: 0;
      }
      
      .expand-btn:focus {
        outline: none;
        border-radius: 0;
      }
      
      /* Statistics/Performance Pages */
      .leaderboard-page, .performance-page {
        flex: 1;
        overflow-y: auto;
        padding: 24px;
        background: #f5f5f5;
        width: 100%;
        max-width: none;
      }
      
      .section {
        margin-bottom: 32px;
        background: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        width: 100%;
        max-width: none;
      }
      
      .section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 2px solid #000000;
      }
      
      .section-title {
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 2px;
        margin: 0;
        color: #000000;
        text-transform: uppercase;
      }
      
      .section-tabs {
        display: flex;
        gap: 0;
        border: 1px solid #000000;
      }
      
      .section-tab {
        padding: 8px 16px;
        border: none;
        border-right: 1px solid #000000;
        border-radius: 0;
        background: #ffffff;
        font-family: inherit;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #000000;
        cursor: pointer;
        transition: all 0.15s;
      }
      
      .section-tab:last-child {
        border-right: none;
      }
      
      .section-tab:hover {
        background: #f5f5f5;
        border-radius: 0;
      }
      
      .section-tab.active {
        background: #000000;
        color: #ffffff;
        border-radius: 0;
      }
      
      .section-tab:focus {
        outline: none;
        border-radius: 0;
      }
      
      /* Tables */
      .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        border: 1px solid #e0e0e0;
        table-layout: auto;
        max-width: none;
      }
      
      .table-wrapper {
        width: 100%;
        overflow-x: auto;
        max-width: none;
      }
      
      .data-table thead th {
        background: #000000;
        color: #ffffff;
        padding: 12px 14px;
        text-align: left;
        font-weight: 700;
        letter-spacing: 1px;
        font-size: 11px;
        border-right: 1px solid #333333;
        text-transform: uppercase;
      }
      
      .data-table thead th:last-child {
        border-right: none;
      }
      
      .data-table tbody tr {
        border-bottom: 1px solid #e0e0e0;
        transition: all 0.15s;
      }
      
      .data-table tbody tr:hover {
        background: #f9f9f9;
      }
      
      .data-table tbody td {
        padding: 12px 14px;
        color: #000000;
      }
      
      .rank-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 36px;
        padding: 6px 10px;
        background: #ffffff;
        border: 2px solid #e0e0e0;
        font-weight: 700;
        font-size: 11px;
        color: #000000;
      }
      
      .rank-badge.first {
        background: #000000;
        border-color: #000000;
        color: #ffffff;
      }
      
      .rank-badge.second {
        background: #ffffff;
        border-color: #000000;
        color: #000000;
      }
      
      .rank-badge.third {
        background: #ffffff;
        border-color: #666666;
        color: #666666;
      }
      
      /* Stats Grid */
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        width: 100%;
        max-width: none;
      }
      
      .stat-card {
        border: 1px solid #e0e0e0;
        padding: 16px;
        background: #fafafa;
        transition: all 0.2s;
      }
      
      .stat-card:hover {
        border-color: #000000;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      }
      
      .stat-card-label {
        font-size: 11px;
        color: #666666;
        font-weight: 700;
        letter-spacing: 1px;
        margin-bottom: 8px;
        text-transform: uppercase;
      }
      
      .stat-card-value {
        font-size: 28px;
        font-weight: 700;
        color: #000000;
      }
      
      .stat-card-value.positive { color: #00C853; }
      .stat-card-value.negative { color: #FF1744; }
      
      /* Empty State */
      .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: #999999;
        font-size: 12px;
        letter-spacing: 0.5px;
      }
      
      /* Pagination Controls */
      .pagination-controls {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 0;
        margin-top: 16px;
        border-top: 1px solid #e0e0e0;
      }
      
      .pagination-btn {
        padding: 8px 16px;
        border: 1px solid #000000;
        border-radius: 0;
        background: #ffffff;
        font-family: inherit;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #000000;
        cursor: pointer;
        transition: all 0.2s;
        text-transform: uppercase;
      }
      
      .pagination-btn:hover:not(:disabled) {
        background: #000000;
        color: #ffffff;
      }
      
      .pagination-btn:disabled {
        border-color: #e0e0e0;
        color: #cccccc;
        cursor: not-allowed;
        opacity: 0.5;
      }
      
      .pagination-btn:focus {
        outline: none;
      }
      
      .pagination-info {
        font-size: 11px;
        font-weight: 700;
        color: #000000;
        letter-spacing: 0.5px;
        font-family: 'Courier New', monospace;
      }
      
      /* Scrollbar */
      ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
      }
      
      ::-webkit-scrollbar-track {
        background: #f0f0f0;
      }
      
      ::-webkit-scrollbar-thumb {
        background: #cccccc;
        border-radius: 0;
      }
      
      ::-webkit-scrollbar-thumb:hover {
        background: #999999;
      }
      
      /* Responsive */
      @media (max-width: 900px) {
        .resizer {
          display: none;
        }
        
        .right-panel {
          display: none;
        }
        
        .left-panel {
          min-width: 100%;
        }
      }
      
      @media (max-width: 600px) {
        .header-tabs {
          overflow-x: auto;
        }
        
        .header-tab {
          padding: 12px 16px;
          font-size: 11px;
        }
        
        .leaderboard-page, .performance-page {
          padding: 16px;
        }
        
        .section {
          padding: 12px;
        }
        
        .data-table {
          font-size: 10px;
          display: block;
          overflow-x: auto;
        }
        
        .data-table thead th,
        .data-table tbody td {
          padding: 8px 6px;
          white-space: nowrap;
        }
        
        .stats-grid {
          grid-template-columns: 1fr;
        }
        
        .ticker-bar {
          padding: 8px 12px;
          gap: 16px;
        }
      }
    `}</style>
  );
}

// ====== Main App Component ======
export default function LiveTradingApp() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // 'connecting' | 'connected' | 'disconnected'
  const [systemStatus, setSystemStatus] = useState('initializing'); // 'initializing' | 'running' | 'completed'
  const [currentDate, setCurrentDate] = useState(null);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [now, setNow] = useState(() => new Date());
  const [mainTab, setMainTab] = useState('live'); // 'live' | 'statistics' | 'performance'
  
  // View toggle: 'room' or 'chart'
  const [currentView, setCurrentView] = useState('chart'); // Start with chart, then animate to room
  const [isInitialAnimating, setIsInitialAnimating] = useState(true);
  
  // Chart data
  const [chartTab, setChartTab] = useState('all');
  const [portfolioData, setPortfolioData] = useState({
    netValue: 10000,
    pnl: 0,
    equity: [],
    baseline: [], // Baseline strategy (Buy & Hold - Equal Weight)
    baseline_vw: [], // Baseline strategy (Buy & Hold - Value Weighted)
    momentum: [], // Momentum strategy
    strategies: [] // Other strategies
  });
  
  // Feed data
  const [feed, setFeed] = useState([]);
  const [conferences, setConferences] = useState({ active: null, history: [] });
  
  // Statistics data
  const [holdings, setHoldings] = useState([]);
  const [trades, setTrades] = useState([]);
  const [stats, setStats] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  
  // Ticker prices (now from real-time data)
  const [tickers, setTickers] = useState(MOCK_TICKERS);
  const [rollingTickers, setRollingTickers] = useState({});
  
  // Room bubbles
  const [bubbles, setBubbles] = useState({});
  
  // Resizable panels
  const [leftWidth, setLeftWidth] = useState(70); // percentage
  const [isResizing, setIsResizing] = useState(false);
  
  const clientRef = useRef(null);
  const containerRef = useRef(null);
  
  // Clock
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  
  // Initial animation: show room drawer sliding in
  useEffect(() => {
    // Wait a bit after mount, then trigger slide to room
    const slideTimer = setTimeout(() => {
      setCurrentView('room');
    }, 1200); // Wait 1200ms before starting animation (2x slower)
    
    // Disable animation flag after animation completes
    const completeTimer = setTimeout(() => {
      setIsInitialAnimating(false);
    }, 5000); // 1200ms delay + 1600ms animation duration + 400ms buffer
    
    return () => {
      clearTimeout(slideTimer);
      clearTimeout(completeTimer);
    };
  }, []);
  
  // Helper to check if bubble should still be visible
  const bubbleFor = (id) => {
    const b = bubbles[id];
    if (!b) return null;
    if (Date.now() - b.ts > BUBBLE_LIFETIME_MS) return null;
    return b;
  };
  
  // Auto-connect to server on mount
  useEffect(() => {
    // Define pushEvent inside useEffect to avoid dependency issues
    const handlePushEvent = (evt) => {
      if (!evt) return;
      
      try {
        handleEventInternal(evt);
      } catch (error) {
        console.error('[Event Handler] Error:', error);
      }
    };
    
    const handleEventInternal = (evt) => {
      // 辅助函数：更新ticker价格
      const updateTickersFromPrices = (realtimePrices) => {
        try {
          setTickers(prevTickers => {
            return prevTickers.map(ticker => {
              const realtimeData = realtimePrices[ticker.symbol];
              if (realtimeData && realtimeData.price !== null && realtimeData.price !== undefined) {
                // Initialize change to 0 if this is the first price update
                const newChange = (ticker.price === null || ticker.price === undefined) 
                  ? 0 
                  : ticker.change;
                
                return {
                  ...ticker,
                  price: realtimeData.price,
                  change: newChange
                };
              }
              return ticker;
            });
          });
        } catch (error) {
          console.error('Error updating tickers from prices:', error);
        }
      };
      
      const handlers = {
        // Connection events
        system: (e) => {
          console.log('[System]', e.content);
          if (e.content.includes('Connected')) {
            setConnectionStatus('connected');
            setIsConnected(true);
          } else if (e.content.includes('Disconnected')) {
            setConnectionStatus('disconnected');
            setIsConnected(false);
          }
          
          // Add all system messages to feed
          const message = {
            id: `sys-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: e.content
          };
          setFeed(prev => [{ type: 'message', data: message, id: message.id }, ...prev].slice(0, 200));
        },
        
        // Pong response from server
        pong: (e) => {
          console.log('[Heartbeat] Pong received');
        },
        
        // Initial state from server
        initial_state: (e) => {
          try {
            const state = e.state;
            if (!state) return;
            
            setSystemStatus(state.status || 'initializing');
            setCurrentDate(state.current_date);
            
            if (state.trading_days_total) {
              setProgress({
                current: state.trading_days_completed || 0,
                total: state.trading_days_total
              });
            }
            
            if (state.portfolio) {
              setPortfolioData(prev => ({
                ...prev,
                netValue: state.portfolio.total_value || prev.netValue,
                pnl: state.portfolio.pnl_percent || 0,
                equity: state.portfolio.equity || prev.equity,
                baseline: state.portfolio.baseline || prev.baseline,
                baseline_vw: state.portfolio.baseline_vw || prev.baseline_vw,
                momentum: state.portfolio.momentum || prev.momentum,
                strategies: state.portfolio.strategies || prev.strategies
              }));
            }
            
            if (state.holdings) setHoldings(state.holdings);
            if (state.trades) setTrades(state.trades);
            if (state.stats) setStats(state.stats);
            if (state.leaderboard) setLeaderboard(state.leaderboard);
            if (state.realtime_prices) updateTickersFromPrices(state.realtime_prices);
            
            // 加载历史feed数据 - 后端已经统一格式化
            if (state.feed_history && Array.isArray(state.feed_history)) {
              console.log(`✅ Loading ${state.feed_history.length} historical feed items`);
              setFeed(state.feed_history);
            }
            
            console.log('Initial state loaded');
          } catch (error) {
            console.error('Error loading initial state:', error);
          }
        },
        
        // Real-time price updates
        price_update: (e) => {
          try {
            const { symbol, price, portfolio } = e;
            
            if (!symbol || !price) {
              console.warn('[Price Update] Missing symbol or price:', e);
              return;
            }
            
            // Update ticker price with animation
            setTickers(prevTickers => {
              return prevTickers.map(ticker => {
                if (ticker.symbol === symbol) {
                  const oldPrice = ticker.price;
                  let newChange = ticker.change;
                  
                  // Calculate change if we have a previous price
                  if (oldPrice !== null && oldPrice !== undefined && isFinite(oldPrice)) {
                    const priceChange = ((price - oldPrice) / oldPrice) * 100;
                    // Initialize change if it was null, otherwise accumulate
                    newChange = (newChange !== null && newChange !== undefined) 
                      ? newChange + priceChange 
                      : priceChange;
                  } else if (newChange === null || newChange === undefined) {
                    // First price received, set change to 0
                    newChange = 0;
                  }
                  
                  // Trigger rolling animation only if price actually changed
                  if (oldPrice !== price) {
                    setRollingTickers(prev => ({ ...prev, [symbol]: true }));
                    setTimeout(() => {
                      setRollingTickers(prev => ({ ...prev, [symbol]: false }));
                    }, 500);
                  }
                  
                  return {
                    ...ticker,
                    price: price,
                    change: newChange
                  };
                }
                return ticker;
              });
            });
            
            // Update portfolio value if provided
            if (portfolio && portfolio.total_value) {
              setPortfolioData(prev => ({
                ...prev,
                netValue: portfolio.total_value,
                pnl: portfolio.pnl_percent || 0
              }));
            }
          } catch (error) {
            console.error('[Price Update] Error:', error);
          }
        },
        
        // Day progress events
        day_start: (e) => {
          setCurrentDate(e.date);
          if (e.progress !== undefined) {
            setProgress(prev => ({
              ...prev,
              current: Math.floor(e.progress * (prev.total || 1))
            }));
          }
          setSystemStatus('running');
          
          // Add to feed
          const message = {
            id: `day-start-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Starting day: ${e.date}`
          };
          setFeed(prev => [{ type: 'message', data: message, id: message.id }, ...prev].slice(0, 200));
        },
        
        day_complete: (e) => {
          // Update from day result
          const result = e.result;
          if (result && typeof result === 'object') {
            // Update portfolio equity if available
            if (result.portfolio_summary) {
              const summary = result.portfolio_summary;
              setPortfolioData(prev => {
                const newEquity = [...prev.equity];
                // Add new data point
                const dateObj = new Date(e.date);
                newEquity.push({
                  t: dateObj.getTime(),
                  v: summary.total_value || summary.cash || prev.netValue
                });
                
                return {
                  ...prev,
                  netValue: summary.total_value || summary.cash || prev.netValue,
                  pnl: summary.pnl_percent || 0,
                  equity: newEquity
                };
              });
            }
            
            // Update signals if available
            if (result.pre_market && result.pre_market.signals) {
              // Could update signal display here
            }
          }
          
          // Add to feed
          const message = {
            id: `day-complete-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Day completed: ${e.date}`
          };
          setFeed(prev => [{ type: 'message', data: message, id: message.id }, ...prev].slice(0, 200));
        },
        
        day_error: (e) => {
          console.error('Day error:', e.date, e.error);
          
          // Add to feed
          const message = {
            id: `day-error-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Day error: ${e.date} - ${e.error || 'Unknown error'}`
          };
          setFeed(prev => [{ type: 'message', data: message, id: message.id }, ...prev].slice(0, 200));
        },
        
        conference_start: (e) => {
          const conference = {
            id: e.conferenceId,
            title: e.title,
            startTime: e.timestamp || Date.now(),
            endTime: null,
            isLive: true,
            participants: e.participants || [],
            messages: []
          };
          setConferences(prev => ({ ...prev, active: conference }));
          setFeed(prev => [{ type: 'conference', data: conference, id: conference.id }, ...prev]);
        },
        
        conference_message: (e) => {
          setConferences(prev => {
            if (prev.active?.id === e.conferenceId) {
              const updated = { ...prev.active, messages: [...prev.active.messages, e] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === e.conferenceId ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            }
            return prev;
          });
        },
        
        conference_end: (e) => {
          setConferences(prev => {
            if (prev.active) {
              const ended = {
                ...prev.active,
                endTime: e.timestamp || Date.now(),
                isLive: false,
                duration: calculateDuration(prev.active.startTime, e.timestamp || Date.now())
              };
              setFeed(f => f.map(item =>
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: ended } : item
              ));
              return { active: null, history: [ended, ...prev.history] };
            }
            return prev;
          });
        },
        
        agent_message: (e) => {
          const agent = AGENTS.find(a => a.id === e.agentId);
          const message = {
            id: `msg-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: agent?.name || e.agentName || e.agentId || 'Agent',
            role: agent?.role || e.role || 'Agent',
            content: e.content
          };
          setFeed(prev => [{ type: 'message', data: message, id: message.id }, ...prev].slice(0, 200));
          
          // Update bubbles for room view
          setBubbles(prev => ({
            ...prev,
            [e.agentId]: {
              text: e.content,
              ts: Date.now(),
              agentName: agent?.name || e.agentName || e.agentId
            }
          }));
        },
        
        team_summary: (e) => {
          setPortfolioData(prev => ({
            ...prev,
            netValue: e.balance || prev.netValue,
            pnl: e.pnlPct || 0,
            equity: e.equity || prev.equity,
            baseline: e.baseline || prev.baseline,  // 等权重 baseline
            baseline_vw: e.baseline_vw || prev.baseline_vw,  // 价值加权 baseline
            momentum: e.momentum || prev.momentum  // 动量策略
          }));
          
          // Add to feed
          const message = {
            id: `team-summary-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Portfolio update: $${formatNumber(e.balance || 0)} (${e.pnlPct >= 0 ? '+' : ''}${(e.pnlPct || 0).toFixed(2)}%)`
          };
          setFeed(prev => [{ type: 'message', data: message, id: message.id }, ...prev].slice(0, 200));
        },
        
        team_portfolio: (e) => {
          if (e.holdings) setHoldings(e.holdings);
        },
        
        team_trades: (e) => {
          if (Array.isArray(e.trades)) setTrades(e.trades);
          else if (e.trade) setTrades(prev => [e.trade, ...prev].slice(0, 100));
        },
        
        team_stats: (e) => {
          if (e.stats) setStats(e.stats);
        },
        
        team_leaderboard: (e) => {
          if (Array.isArray(e.rows)) setLeaderboard(e.rows);
          else if (Array.isArray(e.leaderboard)) setLeaderboard(e.leaderboard);
        }
      };
      
      // Call handler or do nothing
      try {
        const handler = handlers[evt.type];
        if (handler) {
          handler(evt);
        } else {
          console.log('[handleEvent] Unknown event type:', evt.type);
        }
      } catch (error) {
        console.error('[handleEvent] Error handling event:', evt.type, error);
      }
    };
    
    // Create and connect WebSocket client
    const client = new ReadOnlyClient(handlePushEvent);
    clientRef.current = client;
    client.connect();
    setConnectionStatus('connecting');
    
    return () => {
      // Cleanup on unmount
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
    };
  }, []); // Empty dependency array - only run once on mount
  
  // Resizing handlers
  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsResizing(true);
  };
  
  useEffect(() => {
    if (!isResizing) return;
    
    const handleMouseMove = (e) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newLeftWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100;
      
      // Limit between 30% and 85%
      if (newLeftWidth >= 30 && newLeftWidth <= 85) {
        setLeftWidth(newLeftWidth);
      }
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);
  
  const loadMockData = () => {
    // Mock portfolio with multiple strategies
    const equity = Array.from({ length: 90 }).map((_, i) => ({
      t: Date.now() - (90 - i) * 3600e3,
      v: 1000000 + Math.sin(i / 8) * 60000 + i * 3000 + Math.random() * 20000
    }));
    
    // Baseline strategy - equal weight (simple buy-and-hold)
    const baseline = Array.from({ length: 90 }).map((_, i) => ({
      t: Date.now() - (90 - i) * 3600e3,
      v: 1000000 + i * 2000 + Math.random() * 10000
    }));
    
    // Baseline strategy - value weighted
    const baseline_vw = Array.from({ length: 90 }).map((_, i) => ({
      t: Date.now() - (90 - i) * 3600e3,
      v: 1000000 + i * 2200 + Math.random() * 12000
    }));
    
    // Momentum strategy (more volatile)
    const momentum = Array.from({ length: 90 }).map((_, i) => ({
      t: Date.now() - (90 - i) * 3600e3,
      v: 1000000 + Math.sin(i / 5) * 50000 + i * 2800 + Math.random() * 18000
    }));
    
    // Other strategies
    const strategies = Array.from({ length: 90 }).map((_, i) => ({
      t: Date.now() - (90 - i) * 3600e3,
      v: 1000000 + Math.sin(i / 6) * 40000 + i * 2500 + Math.random() * 15000
    }));
    
    setPortfolioData({ 
      netValue: 1347500, 
      pnl: 34.75, 
      equity,
      baseline,
      baseline_vw,
      momentum,
      strategies
    });
    
    // Mock holdings
    setHoldings([
      { ticker: 'AAPL', qty: 120, avg: 192.3, pl: 5401.2, weight: 0.21, currentPrice: 237.5 },
      { ticker: 'NVDA', qty: 40, avg: 980.1, pl: -1204.4, weight: 0.18, currentPrice: 950.0 },
      { ticker: 'MSFT', qty: 20, avg: 420.2, pl: 2100.2, weight: 0.15, currentPrice: 525.3 },
      { ticker: 'GOOGL', qty: 80, avg: 142.5, pl: 1520.0, weight: 0.12, currentPrice: 161.5 }
    ]);
    
    // Mock trades
    setTrades([
      { id: 't1', timestamp: Date.now() - 3600e3, side: 'BUY', ticker: 'AAPL', qty: 20, price: 190.23, pnl: 243.0 },
      { id: 't2', timestamp: Date.now() - 7200e3, side: 'SELL', ticker: 'TSLA', qty: 10, price: 201.90, pnl: -101.0 },
      { id: 't3', timestamp: Date.now() - 10800e3, side: 'BUY', ticker: 'MSFT', qty: 5, price: 420.50, pnl: 525.0 }
    ]);
    
    // Mock stats
    setStats({
      winRate: 0.62,
      hitRate: 0.58,
      totalTrades: 44,
      bullBear: { bull: { n: 26, win: 17 }, bear: { n: 18, win: 10 } }
    });
    
    // Mock leaderboard
    setLeaderboard([
      { agentId: 'alpha', name: 'Bob', role: 'Portfolio Manager', rank: 1, accountValue: 18744, returnPct: 87.44, totalPL: 8744, fees: 441.98, winRate: 0.318, biggestWin: 7378, biggestLoss: -1072, sharpe: 0.448, trades: 22 },
      { agentId: 'beta', name: 'Carl', role: 'Risk Manager', rank: 2, accountValue: 15423, returnPct: 54.23, totalPL: 5423, fees: 1218, winRate: 0.333, biggestWin: 8176, biggestLoss: -1728, sharpe: 0.339, trades: 30 },
      { agentId: 'gamma', name: 'Alice', role: 'Valuation Analyst', rank: 3, accountValue: 9847, returnPct: -1.53, totalPL: -153, fees: 431.49, winRate: 0.333, biggestWin: 2112, biggestLoss: -1579, sharpe: 0.035, trades: 24 },
      { agentId: 'delta', name: 'David', role: 'Sentiment Analyst', rank: 4, accountValue: 8915, returnPct: -10.85, totalPL: -1085, fees: 215.17, winRate: 0.19, biggestWin: 1356, biggestLoss: -657, sharpe: 0.040, trades: 21 },
      { agentId: 'epsilon', name: 'Eve', role: 'Fundamentals Analyst', rank: 5, accountValue: 3519, returnPct: -64.81, totalPL: -6481, fees: 1171, winRate: 0.254, biggestWin: 347, biggestLoss: -750, sharpe: -0.709, trades: 189 },
      { agentId: 'zeta', name: 'Frank', role: 'Technical Analyst', rank: 6, accountValue: 3239, returnPct: -67.61, totalPL: -6761, fees: 390.93, winRate: 0.189, biggestWin: 265, biggestLoss: -621, sharpe: -0.639, trades: 74 }
    ]);
    
    // Mock messages
    setFeed([
      { type: 'message', id: 'm1', data: { id: 'm1', timestamp: Date.now() - 300000, agent: 'Bob', role: 'Portfolio Manager', content: 'Markets showing strong momentum. Increasing allocation to tech sector based on positive earnings outlook.' }},
      { type: 'message', id: 'm2', data: { id: 'm2', timestamp: Date.now() - 600000, agent: 'Carl', role: 'Risk Manager', content: 'Volatility spike detected. Recommend hedging with index puts to protect downside.' }}
    ]);
  };

  return (
    <div className="app">
      <GlobalStyles />
      
      {/* Header */}
      <div className="header">
        <div className="header-title">
          <span>TRADING INTELLIGENCE</span>
        </div>
        
        <div className="header-tabs">
          <button
            className={`header-tab ${mainTab === 'live' ? 'active' : ''}`}
            onClick={() => setMainTab('live')}
          >
            Live
          </button>
          <button
            className={`header-tab ${mainTab === 'statistics' ? 'active' : ''}`}
            onClick={() => setMainTab('statistics')}
          >
            Statistics
          </button>
          <button
            className={`header-tab ${mainTab === 'performance' ? 'active' : ''}`}
            onClick={() => setMainTab('performance')}
          >
            Agent Performance
          </button>
        </div>

        <div className="header-status">
          <span className={`status-indicator ${isConnected ? 'live' : 'disconnected'}`}>
            {isConnected ? '● LIVE' : '○ OFFLINE'}
          </span>
          {currentDate && (
            <span style={{ fontSize: '11px', color: '#666' }}>
              Trading: {currentDate}
            </span>
          )}
          {progress.total > 0 && (
            <span style={{ fontSize: '11px', color: '#666' }}>
              {progress.current}/{progress.total}
            </span>
          )}
          <span>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>
      </div>
      
      {/* Main Content */}
      {mainTab === 'live' ? (
        <>
          {/* Ticker Bar */}
          <div className="ticker-bar">
            {tickers.map(ticker => (
              <div key={ticker.symbol} className="ticker-item">
                <StockLogo ticker={ticker.symbol} size={16} />
                <span className="ticker-symbol">{ticker.symbol}</span>
                <span className="ticker-price">
                  <span className={`ticker-price-value ${rollingTickers[ticker.symbol] ? 'rolling' : ''}`}>
                    {ticker.price !== null && ticker.price !== undefined 
                      ? `$${formatTickerPrice(ticker.price)}` 
                      : '-'}
                  </span>
                </span>
                <span className={`ticker-change ${
                  ticker.change === null || ticker.change === undefined 
                    ? '' 
                    : ticker.change >= 0 ? 'positive' : 'negative'
                }`}>
                  {ticker.change !== null && ticker.change !== undefined
                    ? `${ticker.change >= 0 ? '+' : ''}${ticker.change.toFixed(2)}%`
                    : '-'}
                </span>
              </div>
            ))}
            <div className="portfolio-value">
              <span className="portfolio-label">PORTFOLIO</span>
              <span className="portfolio-amount">${formatNumber(portfolioData.netValue)}</span>
            </div>
          </div>
          
          <div className="main-container" ref={containerRef}>
            {/* Left Panel: Chart/Room Toggle View */}
            <div className="left-panel" style={{ width: `${leftWidth}%` }}>
              <div className="chart-section">
                <div className="view-container">
                  {/* Left toggle button - show when chart is visible */}
                  {currentView === 'chart' && (
                    <button
                      className="view-toggle-btn left"
                      onClick={() => setCurrentView('room')}
                      title="Show Room View"
                    >
                      ▶
                    </button>
                  )}
                  
                  {/* Right toggle button - show when room is visible */}
                  {currentView === 'room' && (
                    <button
                      className="view-toggle-btn right"
                      onClick={() => setCurrentView('chart')}
                      title="Show Chart View"
                    >
                      ◀
                    </button>
                  )}
                  
                  {/* Slider container with both views */}
                  <div className={`view-slider ${currentView === 'room' ? 'show-room' : 'show-chart'} ${!isInitialAnimating ? 'normal-speed' : ''}`}>
                    {/* Room View Panel */}
                    <div className="view-panel">
                      <RoomView bubbles={bubbles} bubbleFor={bubbleFor} />
                    </div>
                    
                    {/* Chart View Panel */}
                    <div className="view-panel">
                      <div className="chart-container">
                        {/* Floating Timeframe Tabs */}
                        <div className="chart-tabs-floating">
                          <button
                            className={`chart-tab ${chartTab === 'all' ? 'active' : ''}`}
                            onClick={() => setChartTab('all')}
                          >
                            ALL
                          </button>
                          <button
                            className={`chart-tab ${chartTab === '30d' ? 'active' : ''}`}
                            onClick={() => setChartTab('30d')}
                          >
                            30D
                          </button>
                        </div>

                        <NetValueChart 
                          equity={portfolioData.equity}
                          baseline={portfolioData.baseline}
                          baseline_vw={portfolioData.baseline_vw}
                          momentum={portfolioData.momentum}
                          strategies={portfolioData.strategies}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Resizer */}
            <div 
              className={`resizer ${isResizing ? 'resizing' : ''}`}
              onMouseDown={handleMouseDown}
            />

            {/* Right Panel: Intelligence Feed */}
            <div className="right-panel" style={{ width: `${100 - leftWidth}%` }}>
              <IntelligenceFeed feed={feed} conferences={conferences} />
            </div>
          </div>
        </>
      ) : mainTab === 'statistics' ? (
        <div className="leaderboard-page">
          <StatisticsView
            trades={trades}
            holdings={holdings}
            stats={stats}
          />
        </div>
      ) : (
        <div className="performance-page">
          <PerformanceView leaderboard={leaderboard} />
        </div>
      )}
    </div>
  );
}

// ====== Subcomponents ======

function RoomView({ bubbles, bubbleFor }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const bgImg = useImage(ASSETS.roomBg);
  
  // Calculate scale to fit canvas in container (80% of available space)
  const [scale, setScale] = useState(0.8);
  
  useEffect(() => {
    const updateScale = () => {
      const container = containerRef.current;
      if (!container) return;
      
      const { clientWidth, clientHeight } = container;
      if (clientWidth <= 0 || clientHeight <= 0) return;
      
      const scaleX = clientWidth / SCENE_NATIVE.width;
      const scaleY = clientHeight / SCENE_NATIVE.height;
      const newScale = Math.min(scaleX, scaleY, 1.0) * 0.8; // Scale to 80% of original size
      setScale(Math.max(0.3, newScale));
    };
    
    updateScale();
    const resizeObserver = new ResizeObserver(updateScale);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }
    window.addEventListener('resize', updateScale);
    
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateScale);
    };
  }, []);
  
  // Set canvas size
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    canvas.width = SCENE_NATIVE.width;
    canvas.height = SCENE_NATIVE.height;
    
    const displayWidth = Math.round(SCENE_NATIVE.width * scale);
    const displayHeight = Math.round(SCENE_NATIVE.height * scale);
    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;
  }, [scale]);
  
  // Draw room background
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !bgImg) return;
    
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(bgImg, 0, 0, SCENE_NATIVE.width, SCENE_NATIVE.height);
    };
    
    draw();
  }, [bgImg, scale]); // Re-draw when scale changes
  
  // Determine which agents are speaking
  const speakingAgents = useMemo(() => {
    const speaking = {};
    AGENTS.forEach(agent => {
      const bubble = bubbleFor(agent.id);
      speaking[agent.id] = !!bubble;
    });
    return speaking;
  }, [bubbles, bubbleFor]);
  
  return (
    <div className="room-view">
      {/* Agents Indicator Bar */}
      <div className="room-agents-indicator">
        {AGENTS.map(agent => (
          <div 
            key={agent.id} 
            className={`agent-indicator ${speakingAgents[agent.id] ? 'speaking' : ''}`}
          >
            <span className="agent-indicator-dot"></span>
            <span>{agent.name}</span>
          </div>
        ))}
      </div>
      
      {/* Room Canvas */}
      <div className="room-canvas-container" ref={containerRef}>
        <div className="room-scene">
          <div style={{ position: 'relative', width: Math.round(SCENE_NATIVE.width * scale), height: Math.round(SCENE_NATIVE.height * scale) }}>
            <canvas ref={canvasRef} className="room-canvas" />
            
            {/* Speech Bubbles */}
            {AGENTS.map((agent, idx) => {
              const bubble = bubbleFor(agent.id);
              if (!bubble) return null;
              
              const pos = AGENT_SEATS[idx];
              const left = Math.round((pos.x - 20) * scale);
              const top = Math.round((pos.y - 150) * scale);
              
              // Truncate long text
              const maxLength = 80;
              const displayText = bubble.text.length > maxLength 
                ? bubble.text.substring(0, maxLength) + '...' 
                : bubble.text;
              
              return (
                <div 
                  key={agent.id} 
                  className="room-bubble"
                  style={{ left, top }}
                >
                  <div className="room-bubble-name">{bubble.agentName || agent.name}</div>
                  {displayText}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Hook to load image
function useImage(src) {
  const [img, setImg] = useState(null);
  useEffect(() => {
    if (!src) return;
    const image = new Image();
    image.src = src;
    image.onload = () => setImg(image);
  }, [src]);
  return img;
}

function NetValueChart({ equity, baseline, baseline_vw, momentum, strategies }) {
  const [activePoint, setActivePoint] = useState(null);
  // Store stable Y-axis range to avoid frequent updates
  const [stableYRange, setStableYRange] = useState(null);
  
  const chartData = useMemo(() => {
    if (!equity || equity.length === 0) return [];
    
    return equity.map((d, idx) => {
      const date = new Date(d.t);
      return {
        index: idx,
        time: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + 
              ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
        timestamp: d.t,
        portfolio: d.v,
        baseline: baseline?.[idx]?.v || null,
        baseline_vw: baseline_vw?.[idx]?.v || null,
        momentum: momentum?.[idx]?.v || null,
        strategy: strategies?.[idx]?.v || null
      };
    });
  }, [equity, baseline, baseline_vw, momentum, strategies]);
  
  const { yMin, yMax, xTickIndices } = useMemo(() => {
    if (chartData.length === 0) return { yMin: 0, yMax: 1, xTickIndices: [] };
    
    // Calculate min and max from all series
    const allValues = chartData.flatMap(d => 
      [d.portfolio, d.baseline, d.baseline_vw, d.momentum, d.strategy].filter(v => v !== null && isFinite(v))
    );
    
    if (allValues.length === 0) {
      return { yMin: 0, yMax: 1000000, xTickIndices: [] };
    }
    
    const dataMin = Math.min(...allValues);
    const dataMax = Math.max(...allValues);
    const range = dataMax - dataMin || 1; // Prevent division by zero
    
    // Calculate standard deviation for variance-based padding
    const mean = allValues.reduce((sum, v) => sum + v, 0) / allValues.length;
    const variance = allValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / allValues.length;
    const stdDev = Math.sqrt(variance);
    
    // Use standard deviation to determine padding
    // If stdDev is small relative to mean (low variance), use smaller padding
    const relativeStdDev = stdDev / mean;
    let paddingFactor;
    if (relativeStdDev < 0.01) {
      // Very low variance - use 2x stdDev as padding
      paddingFactor = stdDev * 0.5;
    } else if (relativeStdDev < 0.05) {
      // Low variance - use 1.5x stdDev
      paddingFactor = stdDev * 0.2;
    } else {
      // Normal/high variance - use 10% of range
      paddingFactor = range * 0.1;
    }
    
    let yMinCalc = dataMin - paddingFactor;
    let yMaxCalc = dataMax + paddingFactor;
    
    // Smart rounding based on the magnitude of values
    const magnitude = Math.max(Math.abs(yMinCalc), Math.abs(yMaxCalc));
    let roundTo;
    if (magnitude >= 1e6) {
      roundTo = 10000; // Round to nearest 10k for millions
    } else if (magnitude >= 1e5) {
      roundTo = 5000; // Round to nearest 5k for 100k+
    } else if (magnitude >= 1e4) {
      roundTo = 1000; // Round to nearest 1k for 10k+
    } else {
      roundTo = 100; // Round to nearest 100 for smaller values
    }
    
    yMinCalc = Math.floor(yMinCalc / roundTo) * roundTo;
    yMaxCalc = Math.ceil(yMaxCalc / roundTo) * roundTo;
    
    // Only update range if data touches the boundary (within 5% of edge)
    // This prevents frequent axis changes
    if (stableYRange) {
      const { min: stableMin, max: stableMax } = stableYRange;
      const stableRange = stableMax - stableMin;
      const threshold = stableRange * 0.05; // 5% threshold
      
      // Check if current data exceeds stable boundaries
      const needsUpdate = 
        dataMin < (stableMin + threshold) || 
        dataMax > (stableMax - threshold);
      
      if (!needsUpdate) {
        // Keep using stable range
        yMinCalc = stableMin;
        yMaxCalc = stableMax;
      } else {
        // Update stable range
        setStableYRange({ min: yMinCalc, max: yMaxCalc });
      }
    } else {
      // First time - set initial range
      setStableYRange({ min: yMinCalc, max: yMaxCalc });
    }
    
    // Calculate x-axis tick indices (show 5-8 ticks)
    // Limit chartData to reasonable size to prevent crash
    const safeLength = Math.min(chartData.length, 10000); // Max 10k points
    const targetTicks = Math.min(8, Math.max(5, Math.floor(safeLength / 10)));
    const step = Math.max(1, Math.floor(safeLength / (targetTicks - 1))); // Ensure step >= 1
    
    const indices = [];
    for (let i = 0; i < safeLength && indices.length < 100; i += step) {
      indices.push(i);
    }
    
    // Always include the last point
    if (safeLength > 0 && indices[indices.length - 1] !== safeLength - 1) {
      indices.push(safeLength - 1);
    }
    
    return { yMin: yMinCalc, yMax: yMaxCalc, xTickIndices: indices };
  }, [chartData]);

  if (!equity || equity.length === 0) {
    return (
      <div style={{ 
        width: '100%', 
        height: '100%', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        color: '#cccccc',
        fontFamily: '"Courier New", monospace',
        fontSize: '12px'
      }}>
        NO DATA AVAILABLE
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: '#000000',
          border: '1px solid #333333',
          padding: '10px 14px',
          fontFamily: '"Courier New", monospace',
          fontSize: '10px',
          color: '#ffffff'
        }}>
          <div style={{ fontWeight: 700, marginBottom: '6px', fontSize: '11px' }}>
            {payload[0].payload.time}
          </div>
          {payload.map((entry, index) => (
            <div key={index} style={{ color: entry.color, marginTop: '2px' }}>
              <span style={{ fontWeight: 700 }}>{entry.name}:</span> ${formatNumber(entry.value)}
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  const CustomDot = ({ dataKey, ...props }) => {
    const { cx, cy, payload, index } = props;
    const isActive = activePoint === index;
    
    const colors = {
      portfolio: '#00C853',
      baseline: '#FF6B00',
      baseline_vw: '#9C27B0',
      momentum: '#2196F3',
      strategy: '#795548'
    };
    
    return (
      <circle
        cx={cx}
        cy={cy}
        r={isActive ? 5 : 3}
        fill={colors[dataKey]}
        stroke="#ffffff"
        strokeWidth={2}
        style={{ cursor: 'pointer' }}
        onMouseEnter={() => setActivePoint(index)}
        onMouseLeave={() => setActivePoint(null)}
        onClick={() => console.log('Clicked point:', { dataKey, ...payload })}
      />
    );
  };
  
  const CustomXAxisTick = ({ x, y, payload }) => {
    const shouldShow = xTickIndices.includes(payload.index);
    if (!shouldShow) return null;
    
    return (
      <g transform={`translate(${x},${y})`}>
        <text
          x={0}
          y={0}
          dy={16}
          textAnchor="middle"
          fill="#666666"
          fontSize="10px"
          fontFamily='"Courier New", monospace'
          fontWeight="700"
        >
          {payload.value}
        </text>
      </g>
    );
  };

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart 
        data={chartData} 
        margin={{ top: 20, right: 30, bottom: 50, left: 60 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis 
          dataKey="time" 
          stroke="#666666"
          tick={<CustomXAxisTick />}
          interval={0}
        />
        <YAxis 
          domain={[yMin, yMax]}
          stroke="#000000"
          style={{ fontFamily: '"Courier New", monospace', fontSize: '11px', fontWeight: 700 }}
          tick={{ fill: '#000000' }}
          tickFormatter={(value) => formatFullNumber(value)}
          width={75}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend 
          wrapperStyle={{
            fontFamily: '"Courier New", monospace',
            fontSize: '11px',
            fontWeight: 700
          }}
        />
        
        {/* Portfolio line - Bright Green */}
        <Line 
          type="monotone" 
          dataKey="portfolio" 
          name="Portfolio"
          stroke="#00C853" 
          strokeWidth={2.5}
          dot={(props) => <CustomDot {...props} dataKey="portfolio" />}
          activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
          isAnimationActive={false}
        />
        
        {/* Baseline line - Orange (Equal Weight) */}
        {baseline && baseline.length > 0 && (
          <Line 
            type="monotone" 
            dataKey="baseline" 
            name="Buy & Hold (EW)"
            stroke="#FF6B00" 
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={(props) => <CustomDot {...props} dataKey="baseline" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
        
        {/* Baseline Value Weighted line - Purple */}
        {baseline_vw && baseline_vw.length > 0 && (
          <Line 
            type="monotone" 
            dataKey="baseline_vw" 
            name="Buy & Hold (VW)"
            stroke="#9C27B0" 
            strokeWidth={2}
            strokeDasharray="8 4"
            dot={(props) => <CustomDot {...props} dataKey="baseline_vw" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
        
        {/* Momentum line - Blue */}
        {momentum && momentum.length > 0 && (
          <Line 
            type="monotone" 
            dataKey="momentum" 
            name="Momentum"
            stroke="#2196F3" 
            strokeWidth={2}
            strokeDasharray="3 3"
            dot={(props) => <CustomDot {...props} dataKey="momentum" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
        
        {/* Strategy line - Brown */}
        {strategies && strategies.length > 0 && (
          <Line 
            type="monotone" 
            dataKey="strategy" 
            name="Strategy"
            stroke="#795548" 
            strokeWidth={2}
            dot={(props) => <CustomDot {...props} dataKey="strategy" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

function IntelligenceFeed({ feed, conferences }) {
  return (
    <div className="intelligence-feed">
      <div className="feed-header">
        <h3 className="feed-title">Agent Feed</h3>
      </div>
      
      <div className="feed-content">
        {feed.length === 0 && (
          <div className="empty-state">Waiting for system updates...</div>
        )}
        
        {feed.map(item => {
          if (item.type === 'conference') {
            return <ConferenceCard key={item.id} conference={item.data} />;
          } else {
            return <MessageCard key={item.id} message={item.data} />;
          }
        })}
      </div>
    </div>
  );
}

function ConferenceCard({ conference }) {
  const [expanded, setExpanded] = useState(false);
  const displayMessages = expanded ? conference.messages : conference.messages.slice(0, 3);
  
  return (
    <div className="feed-card conference-card">
      <div className="card-header">
        <div className="card-title">
          <span className="card-icon">▶</span>
          <span>CONF: {conference.title}</span>
        </div>
        {conference.isLive && <span className="live-badge">● LIVE</span>}
      </div>
      
      <div className="conference-meta">
        <span>{formatTime(conference.startTime)} - {conference.endTime ? formatTime(conference.endTime) : 'now'}</span>
        {conference.duration && <span>({conference.duration})</span>}
        <span>👥 {conference.participants.length}</span>
      </div>
      
      <div className="conference-messages">
        {displayMessages.map((msg, idx) => (
          <div className="conf-message" key={idx}>
            <div className="msg-header">
              <span className="msg-agent">{msg.agent} ({msg.role})</span>
              <span className="msg-time">{formatTime(msg.timestamp)}</span>
            </div>
            <div className="msg-content">{msg.content}</div>
          </div>
        ))}
      </div>
      
      {conference.messages.length > 3 && (
        <button className="expand-btn" onClick={() => setExpanded(!expanded)}>
          {expanded ? '▲ COLLAPSE' : `▼ VIEW ${conference.messages.length - 3} MORE`}
        </button>
      )}
    </div>
  );
}

function MessageCard({ message }) {
  const [expanded, setExpanded] = useState(false);
  
  // Use agent name as title, or 'SYSTEM' for system messages
  const messageTitle = message.agent === 'System' ? 'SYSTEM' : (message.agent || 'MESSAGE');
  
  const content = message.content || '';
  const needsTruncation = content.length > 200;
  const MAX_EXPANDED_LENGTH = 1000;
  
  let displayContent = content;
  if (!expanded && needsTruncation) {
    displayContent = content.substring(0, 200) + '...';
  } else if (expanded && content.length > MAX_EXPANDED_LENGTH) {
    displayContent = content.substring(0, MAX_EXPANDED_LENGTH) + '...';
  }
  
  return (
    <div className="feed-card message-card">
      <div className="card-header">
        <div className="card-title">
          <span>{messageTitle}</span>
        </div>
        <span className="card-time">{formatTime(message.timestamp)}</span>
      </div>
      
      <div className="message-content-wrapper">
        <div className="message-text">{displayContent}</div>
        {needsTruncation && (
          <button 
            className="message-expand-btn"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
    </div>
  );
}

// Stock Logo Component
function StockLogo({ ticker, size = 20 }) {
  const logoUrl = STOCK_LOGOS[ticker];
  if (!logoUrl) return null;
  
  return (
    <img 
      src={logoUrl} 
      alt={ticker}
      style={{
        width: size,
        height: size,
        borderRadius: '4px',
        objectFit: 'contain',
        marginRight: '8px',
        verticalAlign: 'middle'
      }}
      onError={(e) => { e.target.style.display = 'none'; }}
    />
  );
}

// Statistics View (Overview, Portfolio Holdings, Trade History)
function StatisticsView({ trades, holdings, stats }) {
  // Pagination state for Transaction History
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  
  // Calculate pagination
  const totalPages = Math.ceil(trades.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentTrades = trades.slice(startIndex, endIndex);
  
  // Reset to page 1 when trades change
  useEffect(() => {
    setCurrentPage(1);
  }, [trades.length]);
  
  return (
    <div>
      
      {/* Overview Section with Charts */}
      {stats && (
        <div className="section">
          <div className="section-header">
            <h2 className="section-title">Performance Overview</h2>
          </div>
          
          {/* Stats Cards */}
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-label">Total Asset Value</div>
              <div className="stat-card-value">
                ${formatNumber(stats.totalAssetValue || 0)}
              </div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Total Return</div>
              <div className={`stat-card-value ${(stats.totalReturn || 0) >= 0 ? 'positive' : 'negative'}`}>
                {(stats.totalReturn || 0) >= 0 ? '+' : ''}{(stats.totalReturn || 0).toFixed(2)}%
              </div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Cash Position</div>
              <div className="stat-card-value">
                ${formatNumber(stats.cashPosition || 0)}
              </div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Total Trades</div>
              <div className="stat-card-value">{stats.totalTrades || 0}</div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Win Rate</div>
              <div className={`stat-card-value ${stats.winRate >= 0.5 ? 'positive' : 'negative'}`}>
                {Math.round(stats.winRate * 100)}%
              </div>
            </div>
          </div>
          
          {/* Ticker Weights */}
          {stats.tickerWeights && Object.keys(stats.tickerWeights).length > 0 && (
            <div style={{ marginTop: 24 }}>
              <h3 style={{ 
                fontSize: 14, 
                fontWeight: 700, 
                marginBottom: 12,
                letterSpacing: 1,
                textTransform: 'uppercase'
              }}>
                Ticker Weights
              </h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {Object.entries(stats.tickerWeights).map(([ticker, weight]) => (
                  <div key={ticker} style={{
                    padding: '8px 12px',
                    border: '1px solid #e0e0e0',
                    background: '#fafafa',
                    fontSize: 11,
                    fontWeight: 700
                  }}>
                    {ticker}: {(weight * 100).toFixed(2)}%
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Portfolio Holdings Section */}
      <div className="section">
        <div className="section-header">
          <h2 className="section-title">Portfolio Holdings</h2>
        </div>
        
        {holdings.length === 0 ? (
          <div className="empty-state">No positions currently held</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Quantity</th>
                <th>Current Price</th>
                <th>Market Value</th>
                <th>Weight</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map(h => (
                <tr key={h.ticker}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      {h.ticker !== 'CASH' && <StockLogo ticker={h.ticker} size={20} />}
                      <span style={{ fontWeight: 700, color: '#000000' }}>{h.ticker}</span>
                    </div>
                  </td>
                  <td>{h.ticker === 'CASH' ? '-' : h.quantity}</td>
                  <td>{h.ticker === 'CASH' ? '-' : `$${Number(h.currentPrice).toFixed(2)}`}</td>
                  <td style={{ fontWeight: 700 }}>${formatNumber(h.marketValue)}</td>
                  <td>{(Number(h.weight) * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
      
      {/* Trade History Section */}
      <div className="section">
        <div className="section-header">
          <h2 className="section-title">Transaction History</h2>
          {trades.length > 0 && (
            <div style={{ 
              fontSize: '11px', 
              color: '#666666',
              fontFamily: '"Courier New", monospace'
            }}>
              Total: {trades.length} trades
            </div>
          )}
        </div>
        
        {trades.length === 0 ? (
          <div className="empty-state">No trades recorded</div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Stock</th>
                  <th>Side</th>
                  <th>Quantity</th>
                  <th>Price</th>
                </tr>
              </thead>
              <tbody>
                {currentTrades.map(t => (
                  <tr key={t.id}>
                    <td style={{ fontSize: 11, color: '#666666', fontFamily: '"Courier New", monospace' }}>
                      {formatDateTime(t.timestamp)}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <StockLogo ticker={t.ticker} size={18} />
                        <span style={{ fontWeight: 700, color: '#000000' }}>{t.ticker}</span>
                      </div>
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        fontSize: 10,
                        fontWeight: 700,
                        border: `1px solid ${t.side === 'LONG' ? '#00C853' : t.side === 'SHORT' ? '#FF1744' : '#666666'}`,
                        color: t.side === 'LONG' ? '#00C853' : t.side === 'SHORT' ? '#FF1744' : '#666666'
                      }}>
                        {t.side}
                      </span>
                    </td>
                    <td>{t.qty}</td>
                    <td>${Number(t.price).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="pagination-controls">
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  ◀ Prev
                </button>
                
                <div className="pagination-info">
                  Page {currentPage} of {totalPages}
                  <span style={{ margin: '0 8px', color: '#e0e0e0' }}>|</span>
                  Showing {startIndex + 1}-{Math.min(endIndex, trades.length)} of {trades.length}
                </div>
                
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next ▶
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Agent Performance View
function PerformanceView({ leaderboard }) {
  return (
    <div>
      {/* Agent Performance Section */}
      <div className="section">
        <div className="section-header">
          <h2 className="section-title">Agent Performance - Signal Accuracy</h2>
        </div>
        
        {leaderboard.length === 0 ? (
          <div className="empty-state">No leaderboard data available</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Agent</th>
                <th>Win Rate</th>
                <th>Bull Signals</th>
                <th>Bull Win Rate</th>
                <th>Bear Signals</th>
                <th>Bear Win Rate</th>
                <th>Total Signals</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map(agent => {
                const bullTotal = agent.bull?.n || 0;
                const bullWins = agent.bull?.win || 0;
                const bearTotal = agent.bear?.n || 0;
                const bearWins = agent.bear?.win || 0;
                const totalSignals = bullTotal + bearTotal;
                const bullWinRate = bullTotal > 0 ? (bullWins / bullTotal) : 0;
                const bearWinRate = bearTotal > 0 ? (bearWins / bearTotal) : 0;
                
                return (
                  <tr key={agent.agentId}>
                    <td>
                      <span className={`rank-badge ${agent.rank === 1 ? 'first' : agent.rank === 2 ? 'second' : agent.rank === 3 ? 'third' : ''}`}>
                        {agent.rank === 1 ? '★ 1' : agent.rank}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: '#000000' }}>{agent.name}</div>
                      <div style={{ fontSize: 10, color: '#666666' }}>{agent.role}</div>
                    </td>
                    <td style={{ fontWeight: 700, color: agent.winRate >= 0.5 ? '#00C853' : '#FF1744' }}>
                      {(agent.winRate * 100).toFixed(1)}%
                    </td>
                    <td>
                      <div style={{ fontSize: 12 }}>{bullTotal} signals</div>
                      <div style={{ fontSize: 10, color: '#666666' }}>{bullWins} wins</div>
                    </td>
                    <td style={{ color: bullWinRate >= 0.5 ? '#00C853' : '#999999' }}>
                      {bullTotal > 0 ? `${(bullWinRate * 100).toFixed(1)}%` : 'N/A'}
                    </td>
                    <td>
                      <div style={{ fontSize: 12 }}>{bearTotal} signals</div>
                      <div style={{ fontSize: 10, color: '#666666' }}>{bearWins} wins</div>
                    </td>
                    <td style={{ color: bearWinRate >= 0.5 ? '#00C853' : '#999999' }}>
                      {bearTotal > 0 ? `${(bearWinRate * 100).toFixed(1)}%` : 'N/A'}
                    </td>
                    <td style={{ fontWeight: 700 }}>{totalSignals}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>
      
      {/* Signal History with Dates */}
      {leaderboard.length > 0 && leaderboard.some(agent => agent.signals && agent.signals.length > 0) && (
        <div className="section" style={{ marginTop: 32 }}>
          <div className="section-header">
            <h2 className="section-title">Signal History</h2>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 20 }}>
            {leaderboard.map(agent => {
              if (!agent.signals || agent.signals.length === 0) return null;
              
              // 按日期倒序排列（最新的在前）
              const sortedSignals = [...agent.signals].sort((a, b) => 
                new Date(b.date).getTime() - new Date(a.date).getTime()
              );
              
              return (
                <div key={agent.agentId} style={{ 
                  border: '1px solid #e0e0e0', 
                  padding: 16,
                  background: '#fafafa'
                }}>
                  <div style={{ 
                    fontWeight: 700, 
                    fontSize: 12, 
                    marginBottom: 12,
                    paddingBottom: 8,
                    borderBottom: '2px solid #000000',
                    letterSpacing: 1,
                    textTransform: 'uppercase'
                  }}>
                    {agent.name}
                  </div>
                  <div style={{ 
                    maxHeight: 500, 
                    overflowY: 'auto',
                    display: 'flex', 
                    flexDirection: 'column', 
                    gap: 8 
                  }}>
                    {sortedSignals.map((signal, idx) => {
                      const signalType = signal.signal.toLowerCase();
                      const isBull = signalType.includes('bull') || signalType === 'long';
                      const isBear = signalType.includes('bear') || signalType === 'short';
                      const isNeutral = signalType.includes('neutral') || signalType === 'hold';
                      const isCorrect = signal.is_correct;
                      
                      return (
                        <div key={idx} style={{ 
                          fontSize: 11, 
                          fontFamily: '"Courier New", monospace',
                          lineHeight: 1.4,
                          padding: '8px 10px',
                          background: '#ffffff',
                          border: '1px solid #e0e0e0',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}>
                          <div style={{ flex: 1 }}>
                            <span style={{ 
                              color: '#666666',
                              fontSize: 10,
                              marginRight: 10,
                              fontWeight: 600
                            }}>
                              {signal.date}
                            </span>
                            <span style={{ 
                              fontWeight: 700,
                              color: isBull ? '#00C853' : isBear ? '#FF1744' : '#999999'
                            }}>
                              {signal.ticker}
                            </span>
                            <span style={{ 
                              marginLeft: 6, 
                              color: isBull ? '#00C853' : isBear ? '#FF1744' : '#999999',
                              fontSize: 12
                            }}>
                              {isBull ? 'Bull' : isBear ? 'Bear' : 'Neutral'}
                            </span>
                            {!isNeutral && (
                              <span style={{ 
                                marginLeft: 8,
                                fontSize: 10,
                                color: signal.real_return >= 0 ? '#00C853' : '#FF1744'
                              }}>
                                {signal.real_return >= 0 ? '+' : ''}{(signal.real_return * 100).toFixed(2)}%
                              </span>
                            )}
                          </div>
                          {!isNeutral && (
                            <span style={{ 
                              fontSize: 14,
                              marginLeft: 10,
                              color: isCorrect ? '#00C853' : '#FF1744'
                            }}>
                              {isCorrect ? '✓' : '✗'}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <div style={{
                    marginTop: 10,
                    paddingTop: 8,
                    borderTop: '1px solid #e0e0e0',
                    fontSize: 10,
                    color: '#666666',
                    textAlign: 'center'
                  }}>
                    Total: {sortedSignals.length} signals
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ====== Helper Functions ======
function formatTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function formatDateTime(ts) {
  try {
    const d = new Date(ts);
    const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    return `${date} ${time}`;
  } catch {
    return '';
  }
}

function formatNumber(num) {
  if (!isFinite(num)) return '-';
  return Math.abs(num).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatFullNumber(num) {
  if (!isFinite(num)) return '-';
  // Format with commas and no decimals for Y-axis
  return num.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatTickerPrice(price) {
  if (!isFinite(price)) return '-';
  if (price >= 1000) {
    return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  } else if (price >= 1) {
    return price.toFixed(2);
  } else {
    return price.toFixed(4);
  }
}

function formatMoney(v) {
  if (!isFinite(v)) return '-';
  const abs = Math.abs(v);
  const sign = v < 0 ? '-' : '';
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

function formatDateLabel(t) {
  if (!t) return '';
  const d = new Date(t);
  if (isNaN(d)) return '';
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
}

function calculateDuration(start, end) {
  const diff = end - start;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}
