import React from 'react';

/**
 * Global CSS Styles for the Trading Intelligence Platform
 * Terminal-inspired, minimal, monochrome design
 */
export default function GlobalStyles() {
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
      
      /* Import Inter font for agent names */
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
      
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
      }
      
      .header-tab.active {
        background: #000000;
        color: #ffffff;
      }
      
      .header-tab:focus {
        background: #000000;
        color: #ffffff;
        outline: none;
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
      }
      
      .chart-tab.active {
        background: #000000;
        color: #ffffff;
        border-color: #000000;
      }
      
      .chart-tab:focus {
        outline: none;
      }
      
      /* Agent Feed - Minimalist Design */
      .agent-feed {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        width: 100%;
        max-width: none;
        background: transparent;
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
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0;
        background: transparent;
        width: 100%;
        max-width: none;
      }
      
      /* Feed Item - Ultra Minimal with Subtle Background */
      .feed-item {
        border-bottom: 1px solid #f5f5f5;
        padding: 16px 20px;
        transition: all 0.15s ease;
      }
      
      .feed-item:hover {
        filter: brightness(0.98);
      }
      
      .feed-item-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
      }
      
      .feed-item-title {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
      }
      
      .feed-item-time {
        margin-left: auto;
        font-size: 10px;
        color: #999999;
        font-family: 'Courier New', monospace;
      }
      
      .feed-live-badge {
        font-size: 9px;
        font-weight: 700;
        color: #00C853;
        letter-spacing: 0.5px;
      }
      
      .feed-item-subtitle {
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 10px;
        line-height: 1.4;
      }
      
      .feed-item-content {
        font-size: 13px;
        line-height: 1.6;
        color: #333333;
        word-wrap: break-word;
        font-family: 'Courier New', monospace;
      }
      
      /* Conference Messages */
      .conference-messages {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-top: 10px;
      }
      
      .conf-message-item {
        font-size: 12px;
        line-height: 1.5;
        color: #333333;
      }
      
      .conf-agent-name {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-weight: 700;
        font-size: 11px;
        margin-right: 8px;
        letter-spacing: 0.3px;
      }
      
      .conf-message-content {
        font-family: 'Courier New', monospace;
        font-size: 12px;
        color: #333333;
      }
      
      /* Expand Button */
      .feed-expand-btn {
        margin-top: 8px;
        padding: 0;
        border: none;
        background: none;
        font-family: 'Courier New', monospace;
        font-size: 10px;
        font-weight: 600;
        color: #666666;
        cursor: pointer;
        transition: color 0.15s;
        text-align: left;
      }
      
      .feed-expand-btn:hover {
        color: #000000;
      }
      
      .feed-expand-btn:focus {
        outline: none;
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
      }
      
      .section-tab.active {
        background: #000000;
        color: #ffffff;
      }
      
      .section-tab:focus {
        outline: none;
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

