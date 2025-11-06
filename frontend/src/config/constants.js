/**
 * Application Configuration Constants
 */

// Asset paths
export const ASSET_BASE_URL = "/assets/company_room";
export const LOGO_BASE_URL = "/assets/logos";

export const ASSETS = {
  roomBg: `${ASSET_BASE_URL}/full_room_with_roles_tech_style.png`,
};

// Stock logos mapping
export const STOCK_LOGOS = {
  'AAPL': `${LOGO_BASE_URL}/AAPL.png`,
  'MSFT': `${LOGO_BASE_URL}/MSFT.png`,
  'GOOGL': `${LOGO_BASE_URL}/GOOGL.png`,
  'AMZN': `${LOGO_BASE_URL}/AMZN.png`,
  'NVDA': `${LOGO_BASE_URL}/NVDA.png`,
  'META': `${LOGO_BASE_URL}/META.png`,
  'TSLA': `${LOGO_BASE_URL}/TSLA.png`,
};

// Scene dimensions
export const SCENE_NATIVE = { width: 1184, height: 864 };

// Agent seat positions (pixel coordinates on the room image)
export const AGENT_SEATS = [
  { x: 545, y: 380 },
  { x: 600, y: 470 },
  { x: 460, y: 490 },
  { x: 540, y: 590 },
  { x: 710, y: 560 },
  { x: 780, y: 490 },
];

// Agent definitions
export const AGENTS = [
  { id: "alpha", name: "Bob", role: "Portfolio Manager" },
  { id: "beta", name: "Carl", role: "Risk Manager" },
  { id: "gamma", name: "Alice", role: "Valuation Analyst" },
  { id: "delta", name: "David", role: "Sentiment Analyst" },
  { id: "epsilon", name: "Eve", role: "Fundamentals Analyst" },
  { id: "zeta", name: "Frank", role: "Technical Analyst" },
];

// UI timing constants
export const BUBBLE_LIFETIME_MS = 8000;
export const CHART_MARGIN = { left: 60, right: 20, top: 20, bottom: 40 };
export const AXIS_TICKS = 5;

// WebSocket configuration
export const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8001";

// Initial ticker symbols (MAG7 companies)
export const INITIAL_TICKERS = [
  { symbol: 'AAPL', price: null, change: null },
  { symbol: 'MSFT', price: null, change: null },
  { symbol: 'GOOGL', price: null, change: null },
  { symbol: 'AMZN', price: null, change: null },
  { symbol: 'NVDA', price: null, change: null },
  { symbol: 'META', price: null, change: null },
  { symbol: 'TSLA', price: null, change: null }
];

