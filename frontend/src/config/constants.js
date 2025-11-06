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

// Agent definitions with subtle color schemes (very light backgrounds)
export const AGENTS = [
  { 
    id: "Portfolio Manager",
    name: "Portfolio Manager",
    role: "Portfolio Manager",
    colors: { bg: '#F9FDFF', text: '#1565C0', accent: '#1565C0' }
  },
  { 
    id: "Risk Manager",
    name: "Risk Manager",
    role: "Risk Manager",
    colors: { bg: '#FFF8F8', text: '#C62828', accent: '#C62828' }
  },
  { 
    id: "Valuation Analyst",
    name: "Valuation Analyst",
    role: "Valuation Analyst",
    colors: { bg: '#FAFFFA', text: '#2E7D32', accent: '#2E7D32' }
  },
  { 
    id: "Sentiment Analyst",
    name: "Sentiment Analyst",
    role: "Sentiment Analyst",
    colors: { bg: '#FCFAFF', text: '#6A1B9A', accent: '#6A1B9A' }
  },
  { 
    id: "Fundamentals Analyst",
    name: "Fundamentals Analyst",
    role: "Fundamentals Analyst",
    colors: { bg: '#FFFCF7', text: '#E65100', accent: '#E65100' }
  },
  { 
    id: "Technical Analyst",
    name: "Technical Analyst",
    role: "Technical Analyst",
    colors: { bg: '#F9FEFF', text: '#00838F', accent: '#00838F' }
  },
];

// Message type colors (very subtle backgrounds)
export const MESSAGE_COLORS = {
  system: { bg: '#FAFAFA', text: '#424242', accent: '#424242' },
  memory: { bg: '#FFFEFA', text: '#F57F17', accent: '#F57F17' },
  conference: { bg: '#F1F4FF', text: '#3949AB', accent: '#3949AB' }
};

// Helper function to get agent colors by ID or name
export const getAgentColors = (agentId, agentName) => {
  const agent = AGENTS.find(a => a.id === agentId || a.name === agentName);
  return agent?.colors || MESSAGE_COLORS.system;
};

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

