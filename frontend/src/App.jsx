import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * LiveTradingCompanyApp
 * 1) 抽出常量（CHANNELS、颜色、图表边距等），去重魔法字符串。
 * 2) 将 run/replay 的启动逻辑合并为 startClient()，减少重复。
 * 3) WebSocket 事件通过 handlers 映射集中处理，pushEvent 更简洁。
 * 4) Drawer 订阅/退订使用统一的 TEAM_CHANNELS 常量。
 * 5) 提炼小工具函数（truncate、getRoleColor），减少内联逻辑噪音。
 * 6) NetValueChart 抽出边距 & 刻度常量，复用 drawAxes。
 */

// ====== Configuration ======
const ASSET_BASE_URL = "/assets/company_room"; // Place all PNGs under public/assets

const ASSETS = {
  roomBg: `${ASSET_BASE_URL}/full_room_with_roles_tech_style.png`,
  worker1: `${ASSET_BASE_URL}/null.png`,
  worker2: `${ASSET_BASE_URL}/null.png`,
  worker4: `${ASSET_BASE_URL}/null.png`,
  boss: `${ASSET_BASE_URL}/null.png`,
  agent1: `${ASSET_BASE_URL}/agent_1.png`,
  agent2: `${ASSET_BASE_URL}/agent_2.png`,
  agent3: `${ASSET_BASE_URL}/agent_3.png`,
  agent4: `${ASSET_BASE_URL}/agent_4.png`,
  agent5: `${ASSET_BASE_URL}/agent_5.png`,
  agent6: `${ASSET_BASE_URL}/agent_6.png`,
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
  { id: "alpha", name: "Bob", role: "Portfolio Manager", avatar: "agent1" },
  { id: "beta", name: "Carl", role: "Risk Manager", avatar: "agent2" },
  { id: "gamma", name: "Alice", role: "Valuation Analyst", avatar: "agent3" },
  { id: "delta", name: "David", role: "Sentiment Analyst", avatar: "agent4" },
  { id: "epsilon", name: "Eve", role: "Fundamentals Analyst", avatar: "agent5" },
  { id: "zeta", name: "Frank", role: "Technical Analyst", avatar: "agent6" },
];

// Neon, cold, hacker-ish accents (no warm oranges)
const ROLE_COLORS = {
  "Portfolio Manager": "#00B3CC",
  "Risk Manager": "#CC2E70",
  "Valuation Analyst": "#5C49CC",
  "Sentiment Analyst": "#6EB300",
  "Fundamentals Analyst": "#00B87A",
  "Technical Analyst": "#BFA300",
  System: "#000000",
};

const TEAM_CHANNELS = [
  "team_summary",
  "team_portfolio",
  "team_stats",
  "team_trades",
  "team_leaderboard",
];

const BUBBLE_LIFETIME_MS = 4000;
const CHART_MARGIN = { left: 48, right: 12, top: 12, bottom: 32 };
const AXIS_TICKS = 5;

const todayISO = () => new Date().toISOString().slice(0, 10);

// ====== Client abstraction（仅保留统一 PythonClient） ======
class IClient {
  /** @param {(evt: any) => void} onEvent */
  constructor(onEvent) { this.onEvent = onEvent; }
  start(_config) {}
  stop() {}
}

/**
 * PythonClient
 * 后端支持：WebSocket ws://<host>/ws ，发送 {type:'run', config} 启动；
 * config: { mode: 'run' | 'replay', date?: 'YYYY-MM-DD' }
 */
class PythonClient extends IClient {
  constructor(onEvent, { wsUrl = "ws://localhost:8765/ws" } = {}) {
    super(onEvent);
    this.wsUrl = wsUrl;
    this.ws = null;
  }
  start(config) {
    this.stop();
    this.ws = new WebSocket(this.wsUrl);
    this.ws.onopen = () => {
      this.onEvent({ type: 'system', content: 'Python client connected.' });
      this.ws?.send(JSON.stringify({ type: 'run', config }));
    };
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        this.onEvent(msg);
      } catch (e) {
        this.onEvent({ type: 'system', content: `Bad message from server: ${e.message}` });
      }
    };
    this.ws.onerror = () => this.onEvent({ type: 'system', content: 'Python client error.' });
    this.ws.onclose = () => this.onEvent({ type: 'system', content: 'Python client disconnected.' });
  }
  stop() {
    if (this.ws) {
      try { this.ws.close(); } catch {}
    }
    this.ws = null;
  }
}

// ====== Global style ======
function RevampStyles() {
  return (
    <style>{`
      @font-face {font-family: 'Pixeloid'; src: local('Pixeloid'), url('/fonts/PixeloidSans.ttf') format('truetype'); font-display: swap;}
      html, body, #root { height: 100%; width: 100%; }
      body { margin:0; padding:0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Pixeloid', 'Courier New', monospace; background:#ffffff; color:#0b1220; letter-spacing:0.2px; }
      canvas, img { image-rendering: pixelated; image-rendering: crisp-edges; }

      .wrap { display:flex; flex-direction:column; min-height:100vh; width:100%; position:relative; overflow-x:hidden; }
      .topbar { background:#ffffff; padding:14px 0; border-bottom:2px solid #000; z-index: 100; width:100%; }
      .title { font-size:clamp(14px, 3vw, 18px); font-weight:900; letter-spacing:clamp(1px, 0.3vw, 3px); text-align:center; text-transform:uppercase; }
      
      .content-wrap { flex:1; display:flex; flex-direction:column; width:100%; max-width:1600px; margin:0 auto; padding:0 clamp(12px, 1.5vw, 24px); box-sizing:border-box; }
      @media (max-width: 1280px) { .content-wrap { padding:0 16px; } }

      /* ===== Dashboard Shell (Top) ===== */
      .dashboardShell { width:100%; z-index: 90; background:#fff; border-bottom:2px solid #000; }
      
      /* ===== Meter Bar + Drawer - Responsive ===== */
      .bar { width:100%; background:#fff; display:flex; align-items:center; justify-content:center; gap:clamp(8px, 2vw, 12px); padding:clamp(10px, 2vw, 12px) clamp(12px, 2vw, 16px); border:none; cursor:pointer; transition: all .3s ease; position:relative; flex-wrap:wrap; }
      .bar::before { content:''; position:absolute; left:0; right:0; bottom:0; height:2px; background: linear-gradient(90deg, #00B3CC 0%, #CC2E70 25%, #5C49CC 50%, #6EB300 75%, #00B87A 100%); opacity:0; transition: opacity .3s ease; }
      .bar:hover::before { opacity:1; }
      .bar:focus { outline: none; outline-offset:-2px; }
      .bar-title { font-weight:900; letter-spacing:clamp(1px, 0.3vw, 2px); font-size:clamp(12px, 2.5vw, 14px); }
      .bar-metrics { font-size:clamp(11px, 2vw, 13px); opacity:.85; display:flex; gap:clamp(12px, 2vw, 16px); align-items:center; flex-wrap:wrap; }
      .bar b { font-weight:900; font-size:clamp(13px, 2.5vw, 15px); }
      .chev { width:clamp(10px, 2vw, 12px); height:clamp(10px, 2vw, 12px); border-right:2px solid #000; border-bottom:2px solid #000; transform:rotate(45deg); transition: transform .35s ease; }
      .chev.up { transform: rotate(-135deg); }

      /* Drawer */
      .drawer { width:100%; background:#fff; border-bottom:2px solid #000; overflow:hidden; max-height:0; transition: max-height .5s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 4px 12px rgba(0,0,0,0.1); box-sizing:border-box; }
      .drawer.open { max-height: 85vh; overflow-y:auto; }

      .teamWrap { width:100%; margin:0; padding:clamp(12px, 2vw, 20px) clamp(12px, 2vw, 16px); display:flex; flex-direction:column; gap:clamp(12px, 2vw, 20px); box-sizing:border-box; }

      .panel { border:2px solid #000; background:#fff; border-radius:0; padding:clamp(8px, 1.5vw, 12px); box-shadow: 4px 4px 0 0 rgba(0,0,0,0.1); }
      .teamPanel { border:2px solid #000 !important; padding:clamp(12px, 2vw, 16px) !important; background:#fff; }
      .panel-title { font-size:clamp(14px, 2.5vw, 18px); font-weight:900; letter-spacing:clamp(1px, 0.3vw, 2px); display:flex; align-items:center; justify-content:space-between; text-transform:uppercase; flex-wrap:wrap; gap:8px; }

      /* Team Record Layout - Responsive */
      .recordLayout { display:grid; grid-template-columns: 1.2fr 1fr; gap:clamp(12px, 2vw, 20px); align-items:start; }
      @media (max-width: 1024px) { .recordLayout { grid-template-columns: 1fr; } }
      .recordChart { border:2px solid #000; padding:clamp(12px, 2vw, 16px); background:#fff; box-shadow: 4px 4px 0 0 rgba(0,0,0,0.1); overflow:hidden; }
      .recordRight { border:2px solid #000; padding:0; background:#fff; box-shadow: 4px 4px 0 0 rgba(0,0,0,0.1); overflow:hidden; }

      .tabs { display:flex; border-bottom:2px solid #000; background:#f8f8f8; flex-wrap:wrap; }
      .tab { font-size:clamp(11px, 2vw, 13px); font-weight:900; padding:clamp(8px, 1.5vw, 10px) clamp(10px, 2vw, 14px); border-right:2px solid #000; background:#fff; cursor:pointer; transition: all .2s ease; letter-spacing:0.5px; white-space:nowrap; }
      .tab:hover { background:#f0f0f0; }
      .tab.active { background:#000; color:#fff; position:relative; }
      .tab.active::after { content:''; position:absolute; bottom:-2px; left:0; right:0; height:2px; background:#00B3CC; }

      /* Chart - Responsive */
      .chart { height:clamp(200px, 35vh, 280px); width:100%; max-width:100%; display:block; }

      /* ===== Agents row - Auto-fit Responsive with max-width ===== */
      .agentsShell { position:relative; width:100%; display:flex; justify-content:center; padding:clamp(12px, 2vw, 16px) 0; box-sizing:border-box; }
      .agents { 
        display:grid; 
        grid-template-columns:repeat(6, minmax(100px, 150px)); 
        gap:clamp(12px, 2vw, 20px); 
        justify-content:center;
        width:100%;
        max-width:1200px;
        margin:0 auto;
      }
      @media (max-width: 1024px) { .agents { grid-template-columns:repeat(3, minmax(100px, 150px)); } }
      @media (max-width: 600px) { .agents { grid-template-columns:repeat(2, minmax(100px, 150px)); } }
      .agent-card { display:flex; flex-direction:column; align-items:center; gap:clamp(4px, 1vw, 6px); background:#fff; border:2px solid #000; border-radius:0; padding:clamp(6px, 1.5vw, 10px) clamp(4px, 1vw, 8px); box-shadow: 3px 3px 0 0 rgba(0,0,0,0.1); transition: transform .2s ease; min-width:0; }
      .agent-card:hover { transform: translateY(-2px); box-shadow: 4px 4px 0 0 rgba(0,0,0,0.15); }
      .avatar-square { width:100%; max-width:110px; aspect-ratio:1; position:relative; display:flex; align-items:center; justify-content:center; overflow:hidden; border-radius:0; background:#ffffff; border:none; }
      .avatar-img { width:100%; height:100%; object-fit:contain; }
      .talk-dot { position:absolute; top:clamp(4px, 1vw, 6px); right:clamp(4px, 1vw, 6px); width:clamp(8px, 1.5vw, 10px); height:clamp(8px, 1.5vw, 10px); border-radius:0; border:2px solid #000; }
      .agent-name { font-size:clamp(10px, 1.6vw, 13px); font-weight:900; letter-spacing:0.5px; text-align:center; }
      .agent-role { font-size:clamp(9px, 1.4vw, 11px); margin-top:2px; opacity:.95; text-align:center; }

      /* Leaderboard - MVP Style - Fully Responsive */
      .leaderboard { border:2px solid #000; box-shadow: 4px 4px 0 0 rgba(0,0,0,0.1); overflow-x:auto; }
      .lb-header { font-size:clamp(14px, 2.5vw, 18px); font-weight:900; letter-spacing:clamp(1px, 0.3vw, 2px); padding:clamp(12px, 2vw, 14px) clamp(12px, 2vw, 16px); border-bottom:2px solid #000; display:flex; align-items:center; justify-content:space-between; text-transform:uppercase; background: linear-gradient(180deg, #fff 0%, #f8f8f8 100%); flex-wrap:wrap; gap:8px; }
      .lb-table { width:100%; border-collapse:separate; border-spacing:0; font-size:clamp(10px, 1.8vw, 12px); }
      .lb-table thead th { position:sticky; top:0; background:#000; color:#fff; border-bottom:2px solid #000; padding:clamp(8px, 1.5vw, 10px) clamp(10px, 1.5vw, 12px); text-align:left; font-weight:900; letter-spacing:1px; text-transform:uppercase; font-size:clamp(9px, 1.5vw, 11px); white-space:nowrap; }
      .lb-row { transition: all .3s ease; cursor:pointer; }
      .lb-row:hover { background:rgba(0,179,204,0.05); }
      .lb-row.movedUp { animation: bumpUp .5s ease; }
      @keyframes bumpUp { 0%{transform:translateY(8px); background:rgba(110,179,0,0.2);} 100%{transform:translateY(0); background:transparent;} }
      .lb-cell { padding:clamp(8px, 1.5vw, 10px) clamp(10px, 1.5vw, 12px); border-top:1px dotted #ccc; }
      .lb-avatar { width:clamp(24px, 4vw, 32px); height:clamp(24px, 4vw, 32px); image-rendering:pixelated; border:2px solid #000; }
      .lb-expand { cursor:pointer; text-decoration:underline; font-size:clamp(10px, 1.5vw, 11px); font-weight:900; }
      .lb-log { padding:clamp(10px, 2vw, 12px) clamp(12px, 2vw, 16px); background:#f8f8f8; border-top:2px dotted #000; white-space:pre-wrap; font-size:clamp(10px, 1.5vw, 11px); line-height:1.6; }

      /* Main content - Centered with max-width */
      .main { 
        width:100%; 
        max-width:1420px;
        margin:0 auto;
        display:flex;
        gap:clamp(20px, 3vw, 60px); 
        align-items:start; 
        justify-content:center;
        box-sizing:border-box;
        padding:clamp(12px, 2vw, 20px) 0;
      }
      @media (max-width: 1280px) { .main { gap:20px; } }
      @media (max-width: 1024px) { .main { flex-direction:column; gap:16px; max-width:100%; } }

      /* Scene panel — NO bg, NO border, limited max size */
      .panel-scene { 
        background:transparent; 
        border:none; 
        border-radius:0; 
        flex:1 1 auto;
        max-width:900px;
        min-width:0; 
        overflow:hidden; 
        display:flex; 
        align-items:center; 
        justify-content:center;
      }
      .scene { 
        position:relative; 
        width:100%; 
        height:clamp(500px, 60vh, 650px); 
        background:transparent; 
        display:flex; 
        align-items:center; 
        justify-content:center; 
        overflow:visible; 
      }
      .scene-inner { position:relative; display:flex; align-items:center; justify-content:center; opacity:1; transition: opacity .2s ease; }
      .scene-inner.loading { opacity:0; }

      /* Square bubble (retro) - responsive */
      .bubble { position:absolute; max-width:clamp(180px, 35vw, 300px); font-size:clamp(10px, 1.8vw, 12px); background:#ffffff; color:#0b1220; padding:clamp(8px, 1.5vw, 10px) clamp(10px, 2vw, 12px); border-radius:0; border:2px solid #000; box-shadow: 3px 3px 0 0 rgba(0,0,0,0.2); }
      .bubble::after{ content:""; position:absolute; left:14px; bottom:-9px; width:12px; height:12px; background:#ffffff; border-left:2px solid #000; border-bottom:2px solid #000; transform:rotate(45deg); }

      /* Right dock: Agent Logs - height matches scene */
      .dock { 
        display:flex; 
        flex-direction:column; 
        height:clamp(500px, 60vh, 650px); 
        flex:0 0 auto;
        width:420px;
        min-width:320px;
        max-width:420px;
      }
      @media (max-width: 1280px) { .dock { width:380px; } }
      @media (max-width: 1024px) { .dock { height:auto; min-height:400px; flex:1; width:100%; max-width:100%; } }
      .dock-box { display:flex; flex-direction:column; border:2px solid #000; border-radius:0; height:100%; overflow:hidden; box-shadow: 4px 4px 0 0 rgba(0,0,0,0.1); }
      .dock-body { flex:1; display:flex; flex-direction:column; padding:clamp(8px, 1.5vw, 10px); overflow:auto; }
      .section-title { font-size:clamp(11px, 2vw, 13px); font-weight:900; margin:0 0 clamp(8px, 1.5vw, 10px); color:#0b1220; text-transform:uppercase; letter-spacing:1px; border-bottom:2px solid #000; padding-bottom:6px; }

      /* Log list */
      .logs { overflow:auto; display:flex; flex-direction:column; gap:10px; }
      .log-card { border:2px dotted #ccc; border-radius:0; padding:10px; position:relative; box-sizing:border-box; transition: all .2s ease; }
      .log-card:hover { border-color:#000; box-shadow: 2px 2px 0 0 rgba(0,0,0,0.1); }
      .log-header { display:flex; align-items:center; gap:8px; font-size:12px; }
      .log-badge { height:10px; width:10px; border-radius:0; border:2px solid #000; }
      .log-agent { font-weight:900; letter-spacing:0.3px; }
      .log-time { margin-left:auto; color:#0b1220; font-size:11px; opacity:.7; }
      .log-text { font-size:12px; line-height:1.5; margin-top:6px; white-space:pre-wrap; }
      .log-expand { position:absolute; right:10px; bottom:8px; font-size:11px; color:#000; cursor:pointer; user-select:none; text-decoration:underline; font-weight:900; }

      /* Tables - MVP/Poker Style - Fully Responsive */
      .portfolio-table { width:100%; border-collapse:collapse; font-size:clamp(10px, 1.8vw, 12px); }
      .portfolio-table thead th { background:#000; color:#fff; padding:clamp(8px, 1.5vw, 10px) clamp(10px, 1.5vw, 12px); text-align:left; font-weight:900; letter-spacing:1px; text-transform:uppercase; font-size:clamp(9px, 1.5vw, 11px); border-right:1px solid #333; white-space:nowrap; }
      .portfolio-table thead th:last-child { border-right:none; }
      .portfolio-table tbody tr { transition: all .2s ease; border-bottom:1px solid #e0e0e0; }
      .portfolio-table tbody tr:hover { background:rgba(0,179,204,0.05); }
      .portfolio-table tbody td { padding:clamp(8px, 1.5vw, 10px) clamp(10px, 1.5vw, 12px); white-space:nowrap; }
      .portfolio-table tbody tr:last-child { border-bottom:none; }

      /* Footer buttons - Sticky at bottom */
      .footer { 
        width:100%;
        background:#ffffff; 
        border-top:2px solid #000; 
        box-shadow: 0 -2px 0 0 rgba(0,0,0,0.05); 
        position:sticky; 
        bottom:0; 
        z-index:80;
        margin-top:auto;
      }
      .footer-inner { width:100%; margin:0; display:flex; gap:clamp(8px, 1.5vw, 12px); align-items:center; justify-content:space-between; padding:clamp(10px, 1.5vw, 12px) clamp(12px, 2vw, 16px); box-sizing:border-box; }
      .footer-left { display:flex; gap:clamp(6px, 1vw, 8px); align-items:center; }
      .footer-right { display:flex; gap:clamp(8px, 1.5vw, 10px); align-items:center; white-space:nowrap; }
      @media (max-width: 768px) { .footer-inner { flex-wrap:wrap; gap:10px; } .footer-left, .footer-right { flex:1; min-width:max-content; } }
      .btn { border:2px solid #000; background:#ffffff; color:#000; padding:clamp(7px, 1.5vw, 9px) clamp(12px, 2vw, 16px); font-weight:900; border-radius:0; cursor:pointer; transition: all .2s ease; letter-spacing:0.5px; box-shadow: 2px 2px 0 0 rgba(0,0,0,0.1); font-size:clamp(11px, 2vw, 13px); white-space:nowrap; }
      .btn:hover { background:#000; color:#fff; transform: translateY(-1px); box-shadow: 3px 3px 0 0 rgba(0,0,0,0.2); }
      .btn-primary { background:#000; color:#fff; }
      .btn-primary:hover { background:#00B3CC; border-color:#00B3CC; }
      .btn-danger { border-color:#FF3B8D; color:#FF3B8D; }
      .btn-danger:hover { background:#FF3B8D; color:#fff; border-color:#FF3B8D; }

      .toolbar { display:none; }
      select, input[type="date"], input[type="text"] { padding:clamp(6px, 1.5vw, 8px) clamp(8px, 1.5vw, 10px); border:2px solid #000; border-radius:0; font-weight:700; box-shadow: 2px 2px 0 0 rgba(0,0,0,0.1); font-size:clamp(11px, 2vw, 13px); }
      select:focus, input:focus { outline:none; border-color:#00B3CC; }
    `}</style>
  );
}

export default function LiveTradingCompanyApp() {
  const [isRunning, setIsRunning] = useState(false);
  const [balance, setBalance] = useState(1250000);
  const [logs, setLogs] = useState([]);
  const [bubbles, setBubbles] = useState({});
  const [holdings, setHoldings] = useState([]); // Team panel portfolio

  const [selectedDate, setSelectedDate] = useState(todayISO());
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);

  // Drawer state
  const [showTeam, setShowTeam] = useState(false);

  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const { scale, isReady: scaleReady } = useResizeScale(containerRef, SCENE_NATIVE);

  const bgImg = useImage(ASSETS.roomBg);
  const avatars = {
    agent1: useImage(ASSETS.boss),
    agent2: useImage(ASSETS.worker2),
    agent3: useImage(ASSETS.worker4),
    agent4: useImage(ASSETS.worker1),
    agent5: useImage(ASSETS.worker1),
    agent6: useImage(ASSETS.worker4),
  };

  // Keep canvas internal size fixed, scale CSS size only
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

  // Draw scene on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf;
    const draw = () => {
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (bgImg) ctx.drawImage(bgImg, 0, 0, SCENE_NATIVE.width, SCENE_NATIVE.height);
      const w = 128, h = 128;
      AGENTS.forEach((a, i) => {
        const pos = AGENT_SEATS[i];
        const img = avatars[a.avatar] || avatars.worker1;
        if (img) ctx.drawImage(img, Math.round(pos.x - w / 2), Math.round(pos.y - h), w, h);
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [bgImg, avatars.worker1, avatars.worker2, avatars.worker4, avatars.boss, avatars.agent1]);

  const clientRef = useRef(null);

  // Unified start logic for run/replay
  const startClient = (config) => {
    clientRef.current?.stop?.();
    clientRef.current = new PythonClient(pushEvent, { wsUrl: "ws://localhost:8765/ws" });
    clientRef.current.start(config);
    setIsRunning(true);
  };

  const handleRun = () => startClient({ mode: 'realtime' });
  const handleReplay = () => startClient({ mode: 'replay', date: selectedDate });
  const handleStop = () => { clientRef.current?.stop?.(); setIsRunning(false); };

  // Helpers
  const bubbleFor = (id) => {
    const b = bubbles[id];
    if (!b) return null;
    if (Date.now() - b.ts > BUBBLE_LIFETIME_MS) return null;
    return b;
  };
  const getRoleColor = (role) => ROLE_COLORS[role] || '#000';

  // ===== Team Record state =====
  const [teamTab, setTeamTab] = useState('stats'); // 'stats' | 'portfolio' | 'trades'
  const [teamSummary, setTeamSummary] = useState({ pnlPct: 0, equity: [] });
  const [leaderboard, setLeaderboard] = useState([]);
  const [tradeLogs, setTradeLogs] = useState([]);
  const [stats, setStats] = useState(null);

  // 使用 selfTest() 的结果来注入 mock（开发时方便预览）
  useEffect(() => {
    if (!isRunning && window.__LB_SELFTEST_OK) {
      const ms = mockSummary();
      const hs = mockHoldings();
      const st = mockStats();
      const tr = mockTrades();
      const lb = mockLeaderboard();
      setTeamSummary(ms);
      setHoldings(hs);
      setStats(st);
      setTradeLogs(tr);
      setLeaderboard(lb);
    }
  }, [isRunning]);

  // Subscribe/unsubscribe based on Drawer visibility
  useEffect(() => {
    const ws = clientRef.current?.ws;
    if (!ws) return;
    const payload = { channels: TEAM_CHANNELS };
    ws.send(JSON.stringify({ type: showTeam ? 'subscribe' : 'unsubscribe', ...payload }));
    if (showTeam) ws.send(JSON.stringify({ type: 'request_snapshot', ...payload }));
  }, [showTeam]);

  // Centralized event dispatcher
  const pushEvent = (evt) => {
    if (!evt) return;
    const handlers = {
      agent_message: (e) => {
        const a = AGENTS.find((x) => x.id === e.agentId);
        const entry = { id: `${Date.now()}-${Math.random()}`, ts: new Date(), who: a?.name || e.agentId, role: a?.role, text: e.content };
        setLogs((prev) => [entry, ...prev].slice(0, 400));
        setBubbles((prev) => ({ ...prev, [e.agentId]: { text: e.content, ts: Date.now(), role: a?.role } }));
      },
      system: (e) => {
        const entry = { id: `${Date.now()}-${Math.random()}`, ts: new Date(), who: 'System', role: 'System', text: e.content };
        setLogs((prev) => [entry, ...prev].slice(0, 400));
      },
      team_summary: (e) => {
        setTeamSummary({ pnlPct: e.pnlPct ?? 0, equity: e.equity || [], balance: e.balance });
        if (typeof e.balance === 'number') setBalance(e.balance);
      },
      team_portfolio: (e) => setHoldings(e.holdings || []),
      team_stats: (e) => setStats(e),
      team_trades: (e) => {
        if (Array.isArray(e.trades)) setTradeLogs(e.trades);
        else if (e.trade) setTradeLogs((prev)=>[e.trade, ...prev].slice(0,400));
      },
      team_leaderboard: (e) => { if (Array.isArray(e.rows)) setLeaderboard(e.rows); },
    };
    (handlers[evt.type] || (()=>{}))(evt);
  };

  return (
    <div className="wrap">
      <RevampStyles />
      <div className="topbar"><div className="title">LIVE TRADING COMPANY</div></div>

      {/* Dashboard Shell */}
      <div className="dashboardShell">
        {/* Meter Bar */}
        <button
          className="bar"
          aria-expanded={showTeam}
          aria-controls="team-drawer"
          onClick={() => setShowTeam(v => !v)}
          style={{ background: (teamSummary.pnlPct ?? 0) >= 0 ? '#E8F8E0' : '#FFE8EE' }}
        >
          <span className="bar-title">TEAM DASHBOARD</span>
          <span className="bar-metrics">
            <span>P&L <b>{(teamSummary.pnlPct ?? 0) >= 0 ? '+' : ''}{(teamSummary.pnlPct||0).toFixed(1)}%</b></span>
            <span>Holdings <b>{holdings?.length || 0}</b></span>
          </span>
          <span className={`chev ${showTeam ? 'up' : ''}`} aria-hidden />
        </button>

        {/* Drawer */}
        <div id="team-drawer" className={`drawer ${showTeam ? 'open' : ''}`}>
          <div className="teamWrap">
            {/* TEAM RECORD - New Layout */}
            <section className="teamPanel">
              <div className="panel-title" style={{ marginBottom: 16 }}>
                <span>TEAM RECORD</span>
                <strong style={{ color: (teamSummary.pnlPct ?? 0) >= 0 ? '#6EB300' : '#FF3B8D', fontSize: 20 }}>
                  {(teamSummary.pnlPct ?? 0) >= 0 ? '+' : ''}{(teamSummary.pnlPct||0).toFixed(1)}%
                </strong>
              </div>
              <div className="recordLayout">
                {/* Left: Chart */}
                <div className="recordChart">
                  <div style={{ fontSize: 14, fontWeight: 900, letterSpacing: 1, marginBottom: 12, textTransform: 'uppercase' }}>NET VALUE CURVE</div>
                  <NetValueChart data={teamSummary.equity || []} />
                  <div style={{ fontSize: 12, marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Balance: <span style={{ fontWeight: 900 }}>${balance.toLocaleString()}</span></span>
                    <span style={{ opacity: 0.7, fontSize: 11 }}>Data Points: {teamSummary.equity?.length || 0}</span>
                  </div>
                </div>

                {/* Right: Tabs */}
                <div className="recordRight">
                  <div className="tabs">
                    <div className={`tab ${teamTab==='stats'?'active':''}`} onClick={()=>setTeamTab('stats')}>STATISTICS</div>
                    <div className={`tab ${teamTab==='portfolio'?'active':''}`} onClick={()=>setTeamTab('portfolio')}>PORTFOLIO</div>
                    <div className={`tab ${teamTab==='trades'?'active':''}`} onClick={()=>setTeamTab('trades')}>TRADING LOGS</div>
                  </div>
                  <div style={{ padding: 12 }}>
                    {teamTab==='stats' && <StatisticsPanel stats={stats} />}
                    {teamTab==='portfolio' && <PortfolioTable holdings={holdings} />}
                    {teamTab==='trades' && <TradesTable trades={tradeLogs} />}
                  </div>
                </div>
              </div>
            </section>

            {/* INDIVIDUAL LEADERBOARD */}
            <section className="leaderboard">
              <div className="lb-header">
                <span>INDIVIDUAL LEADERBOARD</span>
                <small style={{ fontSize:11, opacity:.7, fontWeight: 400 }}>Click row to expand</small>
              </div>
              <div style={{ maxHeight: '42vh', minHeight: 200, overflowY:'auto' }}>
                <LeaderboardTable rows={leaderboard} />
              </div>
            </section>
          </div>
        </div>
      </div>

      {/* Content wrapper for centered layout */}
      <div className="content-wrap">
        {/* Agent Cards */}
        <div className="agentsShell">
          <div className="agents">
            {AGENTS.map((a) => {
              const talk = bubbleFor(a.id);
              const speaking = !!talk;
              const color = getRoleColor(a.role);
              return (
                <div key={a.id} className="agent-card">
                  <div className="avatar-square">
                    <img src={ASSETS[a.avatar]} alt={a.name} className="avatar-img" />
                    <span className="talk-dot" style={{ background: speaking ? color : '#fff' }} />
                  </div>
                  <div className="agent-labels" style={{ textAlign: 'center' }}>
                    <div className="agent-name" style={{ color }}>{a.name}</div>
                    <div className="agent-role" style={{ color }}>{a.role}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Main content: scene + right dock */}
        <div className="main">
          {/* Full room scene (no bg/border) */}
          <div className="panel-scene">
            <div ref={containerRef} className="scene">
              <div
                className={`scene-inner ${!scaleReady ? 'loading' : ''}`}
                style={{
                  width: Math.round(SCENE_NATIVE.width * scale),
                  height: Math.round(SCENE_NATIVE.height * scale),
                  position: 'relative'
                }}
              >
                <canvas ref={canvasRef} style={{ display: 'block' }} />
                {AGENTS.map((a, i) => {
                  const pos = AGENT_SEATS[i];
                  const b = bubbleFor(a.id);
                  if (!b) return null;
                  const color = getRoleColor(a.role);
                  const left = Math.round((pos.x - 20) * scale);
                  const top = Math.round((pos.y - 150) * scale);
                  return (
                    <div key={a.id} className="bubble" style={{ left, top }}>
                      <div style={{ fontWeight: 900, marginBottom: 4, color }}>{a.name}</div>
                      {truncate(b.text || '', 50)}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right dock (Agent Logs only) */}
          <div className="dock">
            <div className="dock-box">
              <div className="dock-body">
                <h3 className="section-title">Agent Logs</h3>
                <AgentLogs logs={logs} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="footer">
        <div className="footer-inner">
          <div className="footer-left">
            <button onClick={handleRun} className="btn btn-primary" title="Run (live)">RUN</button>
            <button onClick={handleReplay} className="btn" title="Replay (by date)">REPLAY</button>
            <button onClick={handleStop} className="btn btn-danger">STOP</button>
          </div>
          <div className="footer-right">
            <label htmlFor="replay-date" style={{ fontSize:'12px', fontWeight:900 }}>DATE</label>
            <input id="replay-date" type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} />
            <span style={{ fontSize:'12px' }}>|</span>
            <div style={{ fontVariantNumeric:'tabular-nums', fontSize:'13px', fontWeight:700 }}>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ====== Subcomponents ======
function AgentLogs({ logs }) {
  const [expanded, setExpanded] = useState({});
  const MAX = 200;
  return (
    <div className="logs">
      {logs.length === 0 && (<div style={{ opacity:.6, fontSize:12 }}>No logs yet. Use Replay or Run.</div>)}
      {logs.map((l) => {
        const color = ROLE_COLORS[l.role] || '#000';
        const light = hexToRgba(color, 0.08);
        const isLong = l.text && l.text.length > MAX;
        const open = !!expanded[l.id];
        const shown = !isLong || open ? l.text : `${l.text.slice(0, MAX)}…`;
        return (
          <div key={l.id} className="log-card" style={{ background: light }}>
            <div className="log-header">
              <span className="log-badge" style={{ background: color }} />
              <span className="log-agent" style={{ color }}>{l.who}</span>
              {l.who !== l.role && (
                <>
                  <span style={{ color }}>:</span>
                  <span style={{ color }}>{l.role}</span>
                </>
              )}
              <span className="log-time">{formatTime(l.ts)}</span>
            </div>
            <div className="log-text">{shown}</div>
            {isLong && (
              <div className="log-expand" onClick={() => setExpanded((s) => ({ ...s, [l.id]: !open }))}>{open ? 'collapse' : 'click to expand'}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PortfolioTable({ holdings }) {
  return (
    <div style={{ maxHeight: 320, overflowY: 'auto' }}>
      <table className="portfolio-table">
        <thead>
          <tr>
            <th>TICKER</th>
            <th>QTY</th>
            <th>AVG COST</th>
            <th>P/L</th>
            <th>WEIGHT</th>
          </tr>
        </thead>
        <tbody>
          {(!holdings || holdings.length === 0) ? (
            <tr><td colSpan={5} style={{ padding: 16, opacity:.6, textAlign: 'center' }}>No positions</td></tr>
          ) : holdings.map((h) => (
            <tr key={h.ticker}>
              <td style={{ fontWeight: 900, fontSize: 13 }}>{h.ticker}</td>
              <td>{h.qty}</td>
              <td>${Number(h.avg).toFixed(2)}</td>
              <td style={{ color: h.pl >= 0 ? '#6EB300' : '#FF3B8D', fontWeight: 900 }}>
                {h.pl >= 0 ? '▲ +' : '▼ '}{Number(h.pl).toFixed(2)}
              </td>
              <td>{(Number(h.weight) * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NetValueChart({ data }) {
  const ref = useRef(null);

  useEffect(() => {
    const drawChart = () => {
      const cnv = ref.current;
      if (!cnv) return;
      const ctx = cnv.getContext('2d');
      const parent = cnv.parentElement;
      if (!parent) return;
      const W = Math.max(280, parent.clientWidth);
      const H = Math.min(280, Math.max(200, parent.clientHeight || 280));
      cnv.width = W;
      cnv.height = H;
      cnv.style.width = '100%';
      cnv.style.height = '100%';

      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0,0,W,H);
      ctx.fillStyle = '#fff'; ctx.fillRect(0,0,W,H);

      if (!data || data.length === 0) {
        drawAxes(ctx, W, H, { lo: 0, hi: 1 }, [], CHART_MARGIN, AXIS_TICKS);
        ctx.fillStyle = '#ccc';
        ctx.font = '12px ui-monospace, monospace';
        ctx.textAlign = 'center';
        ctx.fillText('NO DATA AVAILABLE', W/2, H/2);
        return;
      }

      const vals = data.map(d => d.v);
      const hi = Math.max(...vals), lo = Math.min(...vals);
      drawAxes(ctx, W, H, { lo, hi }, data, CHART_MARGIN, AXIS_TICKS);

      const m = CHART_MARGIN;
      const chartW = W - m.left - m.right;
      const chartH = H - m.top - m.bottom;
      const y = (v) => m.top + Math.round((1 - (v - lo) / ((hi - lo) || 1)) * chartH);
      const x = (i) => m.left + Math.round((i / Math.max(1, data.length - 1)) * chartW);

      const gradient = ctx.createLinearGradient(0, m.top, 0, m.top + chartH);
      gradient.addColorStop(0, 'rgba(0, 179, 204, 0.15)');
      gradient.addColorStop(1, 'rgba(0, 179, 204, 0.01)');
      ctx.beginPath();
      ctx.moveTo(x(0), m.top + chartH);
      data.forEach((d, i) => ctx.lineTo(x(i), y(d.v)));
      ctx.lineTo(x(data.length - 1), m.top + chartH);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      ctx.beginPath();
      data.forEach((d, i) => {
        const px = x(i), py = y(d.v);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      });
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#00B3CC';
      ctx.stroke();

      data.forEach((d, i) => {
        if (i % Math.max(1, Math.floor(data.length / 20)) === 0 || i === data.length - 1) {
          ctx.beginPath();
          ctx.arc(x(i), y(d.v), 3, 0, Math.PI * 2);
          ctx.fillStyle = '#00B3CC';
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      });
    };

    drawChart();
    window.addEventListener('resize', drawChart);
    return () => window.removeEventListener('resize', drawChart);
  }, [data]);

  return <canvas ref={ref} className="chart" />;
}

function drawAxes(ctx, W, H, range, data, m = CHART_MARGIN, ticks = AXIS_TICKS) {
  const chartW = W - m.left - m.right;
  const chartH = H - m.top - m.bottom;

  // Grid lines (subtle)
  ctx.strokeStyle = '#e8e8e8';
  ctx.lineWidth = 1;
  for (let i = 0; i <= ticks; i++) {
    const t = i / ticks;
    const py = m.top + Math.round(t * chartH) + 0.5;
    ctx.beginPath();
    ctx.moveTo(m.left, py);
    ctx.lineTo(m.left + chartW, py);
    ctx.stroke();
  }

  // Axes lines (bold)
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(m.left, m.top); ctx.lineTo(m.left, m.top + chartH);
  ctx.moveTo(m.left, m.top + chartH); ctx.lineTo(m.left + chartW, m.top + chartH);
  ctx.stroke();

  // Y ticks & labels
  ctx.font = 'bold 10px ui-monospace, Menlo, monospace';
  ctx.fillStyle = '#000';
  ctx.textAlign = 'right';
  for (let i = 0; i <= ticks; i++) {
    const t = i / ticks;
    const val = range.lo + (range.hi - range.lo) * (1 - t);
    const py = m.top + Math.round(t * chartH) + 0.5;
    ctx.beginPath();
    ctx.moveTo(m.left - 6, py); ctx.lineTo(m.left, py);
    ctx.lineWidth = 2; ctx.stroke();
    ctx.fillText(formatMoney(val), m.left - 10, py + 3);
  }

  // X ticks & labels (start / mid / end dates)
  const n = data?.length || 0;
  const xIdx = (i) => m.left + Math.round((i / Math.max(1, n - 1)) * chartW);
  const picks = n >= 3 ? [0, Math.floor((n - 1) / 2), n - 1] : [0, n - 1].filter((v, i, a) => a.indexOf(v) === i);
  ctx.textAlign = 'center';
  picks.forEach((idx) => {
    if (idx < 0 || idx >= n) return;
    const px = xIdx(idx);
    ctx.beginPath();
    ctx.moveTo(px, m.top + chartH);
    ctx.lineTo(px, m.top + chartH + 6);
    ctx.lineWidth = 2;
    ctx.stroke();
    const label = formatDateLabel(data[idx]?.t);
    ctx.fillText(label, px, H - 8);
  });
}

function StatisticsPanel({ stats }) {
  if (!stats) return <div style={{ opacity:.6, fontSize:12, padding: 20, textAlign: 'center' }}>No statistics available</div>;
  const winRate = Math.round((stats.winRate||0)*100);
  const hitRate = Math.round((stats.hitRate||0)*100);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ border: '2px solid #000', padding: 12, background: '#fff', boxShadow: '3px 3px 0 0 rgba(0,0,0,0.1)' }}>
        <div style={{ fontSize: 11, fontWeight: 900, letterSpacing: 1, opacity: 0.7, marginBottom: 6 }}>WIN RATE</div>
        <div style={{ fontSize: 28, fontWeight: 900, color: winRate >= 50 ? '#6EB300' : '#FF3B8D' }}>{winRate}%</div>
      </div>
      <div style={{ border: '2px solid #000', padding: 12, background: '#fff', boxShadow: '3px 3px 0 0 rgba(0,0,0,0.1)' }}>
        <div style={{ fontSize: 11, fontWeight: 900, letterSpacing: 1, opacity: 0.7, marginBottom: 6 }}>HIT RATE</div>
        <div style={{ fontSize: 28, fontWeight: 900, color: hitRate >= 50 ? '#6EB300' : '#FF3B8D' }}>{hitRate}%</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ border: '2px solid #6EB300', padding: 10, background: 'rgba(110,179,0,0.05)' }}>
          <div style={{ fontSize: 11, fontWeight: 900, letterSpacing: 1, color: '#6EB300', marginBottom: 6 }}>▲ BULL</div>
          <div style={{ fontSize: 13, fontWeight: 900 }}>{stats.bullBear?.bull?.n||0} trades</div>
          <div style={{ fontSize: 11, marginTop: 4 }}>Win: {stats.bullBear?.bull?.win||0}</div>
        </div>
        <div style={{ border: '2px solid #FF3B8D', padding: 10, background: 'rgba(255,59,141,0.05)' }}>
          <div style={{ fontSize: 11, fontWeight: 900, letterSpacing: 1, color: '#FF3B8D', marginBottom: 6 }}>▼ BEAR</div>
          <div style={{ fontSize: 13, fontWeight: 900 }}>{stats.bullBear?.bear?.n||0} trades</div>
          <div style={{ fontSize: 11, marginTop: 4 }}>Win: {stats.bullBear?.bear?.win||0}</div>
        </div>
      </div>
    </div>
  );
}

function TradesTable({ trades }) {
  return (
    <div style={{ maxHeight: 320, overflowY: 'auto' }}>
      <table className="portfolio-table">
        <thead>
          <tr>
            <th>TIME</th>
            <th>TICKER</th>
            <th>SIDE</th>
            <th>QTY</th>
            <th>PRICE</th>
            <th>P/L</th>
          </tr>
        </thead>
        <tbody>
          {(!trades || trades.length===0) ? (
            <tr><td colSpan={6} style={{ padding: 16, opacity:.6, textAlign: 'center' }}>No trades recorded</td></tr>
          ) : trades.map(t => (
            <tr key={t.id}>
              <td style={{ fontSize: 11, opacity: 0.8 }}>{formatTime(t.ts)}</td>
              <td style={{ fontWeight: 900, fontSize: 13 }}>{t.ticker}</td>
              <td>
                <span style={{
                  display: 'inline-block',
                  padding: '2px 6px',
                  fontSize: 10,
                  fontWeight: 900,
                  border: `2px solid ${t.side === 'BUY' ? '#6EB300' : '#FF3B8D'}`,
                  color: t.side === 'BUY' ? '#6EB300' : '#FF3B8D',
                  background: t.side === 'BUY' ? 'rgba(110,179,0,0.05)' : 'rgba(255,59,141,0.05)'
                }}>
                  {t.side}
                </span>
              </td>
              <td>{t.qty}</td>
              <td>${Number(t.price).toFixed(2)}</td>
              <td style={{ color: t.pnl >= 0 ? '#6EB300' : '#FF3B8D', fontWeight: 900 }}>
                {t.pnl >= 0 ? '▲ +' : '▼ '}{Number(t.pnl).toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LeaderboardTable({ rows }) {
  const prevRanksRef = useRef({});
  const [openRow, setOpenRow] = useState(null);

  const baseRows = useMemo(() => {
    if (rows && rows.length) return rows;
    return AGENTS.map((a, i) => ({
      agentId: a.id,
      name: a.name,
      role: a.role,
      avatar: a.avatar,
      rank: i + 1,
      winRate: null,
      bull: { n: null, win: null },
      bear: { n: null, win: null },
      logs: []
    }));
  }, [rows]);

  const sorted = useMemo(() => baseRows.slice().sort((a,b)=>a.rank - b.rank), [baseRows]);
  const fmt = (v) => (v === null || v === undefined ? '-' : v);

  const getRankBadge = (rank) => {
    if (rank === 1) return { bg: '#FFD700', icon: '👑', label: '1ST' };
    if (rank === 2) return { bg: '#C0C0C0', icon: '🥈', label: '2ND' };
    if (rank === 3) return { bg: '#CD7F32', icon: '🥉', label: '3RD' };
    return { bg: '#e0e0e0', icon: '•', label: `${rank}TH` };
  };

  return (
    <div>
      <table className="lb-table">
        <thead>
          <tr>
            <th style={{ width:70 }}>RANK</th>
            <th colSpan={2}>AGENT</th>
            <th style={{ width:90 }}>WIN %</th>
            <th style={{ width:140 }}>BULL</th>
            <th style={{ width:140 }}>BEAR</th>
            <th style={{ width:80 }}></th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const color = ROLE_COLORS[r.role] || '#000';
            const movedUp = prevRanksRef.current[r.agentId] && prevRanksRef.current[r.agentId] > r.rank;
            prevRanksRef.current[r.agentId] = r.rank;
            const open = openRow === r.agentId;
            const badge = getRankBadge(r.rank);
            const winPct = r.winRate==null ? null : Math.round((r.winRate||0)*100);

            return (
              <React.Fragment key={r.agentId}>
                <tr className={`lb-row ${movedUp ? 'movedUp' : ''}`} onClick={()=> setOpenRow(open ? null : r.agentId)}>
                  <td className="lb-cell">
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '4px 8px',
                      background: badge.bg,
                      border: '2px solid #000',
                      fontWeight: 900,
                      fontSize: 11,
                      letterSpacing: 0.5
                    }}>
                      <span>{badge.icon}</span>
                      <span>{badge.label}</span>
                    </div>
                  </td>
                  <td className="lb-cell" style={{ width:40 }}>
                    <img className="lb-avatar" src={ASSETS[r.avatar]} alt={r.name} />
                  </td>
                  <td className="lb-cell" style={{ fontWeight:900, color }}>
                    <div style={{ fontSize: 13 }}>{r.name}</div>
                    <div style={{ fontSize: 10, opacity: 0.7, fontWeight: 400, marginTop: 2 }}>{r.role}</div>
                  </td>
                  <td className="lb-cell">
                    <div style={{
                      fontWeight: 900,
                      fontSize: 15,
                      color: winPct === null ? '#999' : (winPct >= 50 ? '#6EB300' : '#FF3B8D')
                    }}>
                      {winPct === null ? '-' : `${winPct}%`}
                    </div>
                  </td>
                  <td className="lb-cell" style={{ fontSize: 11 }}>
                    <div style={{ color: '#6EB300', fontWeight: 900 }}>▲ {fmt(r.bull?.n)} trades</div>
                    <div style={{ fontSize: 10, opacity: 0.7, marginTop: 2 }}>Win: {fmt(r.bull?.win)}</div>
                  </td>
                  <td className="lb-cell" style={{ fontSize: 11 }}>
                    <div style={{ color: '#FF3B8D', fontWeight: 900 }}>▼ {fmt(r.bear?.n)} trades</div>
                    <div style={{ fontSize: 10, opacity: 0.7, marginTop: 2 }}>Win: {fmt(r.bear?.win)}</div>
                  </td>
                  <td className="lb-cell">
                    <span className="lb-expand">{open ? '▲' : '▼'}</span>
                  </td>
                </tr>
                {open && (
                  <tr>
                    <td className="lb-log" colSpan={7}>
                      {(r.logs || []).length ? (
                        <div>
                          <div style={{ fontWeight: 900, marginBottom: 8, fontSize: 11, letterSpacing: 1 }}>ACTIVITY LOG</div>
                          {(r.logs||[]).map((l,i)=> (
                            <div key={i} style={{ marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #ccc' }}>
                              {i+1}. {l}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ opacity: 0.6 }}>No activity logs available</div>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ====== Helpers ======
function useImage(src) {
  const [img, setImg] = useState(null);
  useEffect(() => { if (!src) return; const i = new Image(); i.src = src; i.onload = () => setImg(i); }, [src]);
  return img;
}

function useResizeScale(containerRef, native) {
  const [scale, setScale] = useState(1);
  const [isReady, setIsReady] = useState(false);
  const readyRef = useRef(false);

  useEffect(() => {
    const onResize = () => {
      const el = containerRef.current;
      if (!el) return;
      const { clientWidth: containerWidth, clientHeight: containerHeight } = el;
      if (containerWidth <= 0 || containerHeight <= 0) return;
      const scaleX = containerWidth / native.width;
      const scaleY = containerHeight / native.height;
      const newScale = Math.min(scaleX, scaleY, 1.0);
      setScale(Math.max(0.3, newScale));
      if (!readyRef.current) { readyRef.current = true; setIsReady(true); }
    };
    onResize();
    const resizeObserver = new ResizeObserver(onResize);
    if (containerRef.current) resizeObserver.observe(containerRef.current);
    window.addEventListener("resize", onResize);
    return () => { resizeObserver.disconnect(); window.removeEventListener("resize", onResize); };
  }, [native.width, native.height]);

  return { scale, isReady };
}

function formatTime(ts) { try { const d = new Date(ts); return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch { return '' } }
function hexToRgba(hex, a = 1) { if (!hex) return `rgba(0,0,0,${a})`; const c = hex.replace('#', ''); const bigint = parseInt(c.length === 3 ? c.split('').map(x=>x+x).join('') : c, 16); const r = (bigint >> 16) & 255; const g = (bigint >> 8) & 255; const b = bigint & 255; return `rgba(${r}, ${g}, ${b}, ${a})`; }
function formatMoney(v) { if (!isFinite(v)) return '-'; const abs = Math.abs(v); const sign = v < 0 ? '-' : ''; if (abs >= 1e9) return `${sign}${(abs/1e9).toFixed(2)}B`; if (abs >= 1e6) return `${sign}${(abs/1e6).toFixed(2)}M`; if (abs >= 1e3) return `${sign}${(abs/1e3).toFixed(2)}K`; return `${sign}${abs.toFixed(2)}`; }
function formatDateLabel(t) { if (!t) return ''; const d = new Date(t); if (isNaN(d)) return ''; return `${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')}`; }
const truncate = (s = '', n = 50) => (s.length > n ? `${s.slice(0, n)}…` : s);

// ===== Mock fallbacks =====
function mockSummary(){
  const equity = Array.from({length: 90}).map((_,i)=>({ t: Date.now() - (90-i)*3600e3, v: 100 + Math.sin(i/8)*6 + i*0.3 + Math.random()*2 }));
  return { pnlPct: 34.7, equity, balance: 1250000 };
}
function mockHoldings(){
  return [
    { ticker:'AAPL', qty: 120, avg: 192.3, pl: 540.12, weight: .21 },
    { ticker:'NVDA', qty: 40, avg: 980.1, pl: -120.44, weight: .18 },
    { ticker:'MSFT', qty: 20, avg: 420.2, pl: 210.02, weight: .15 }
  ];
}
function mockStats(){
  return { winRate:.62, hitRate:.58, bullBear:{ bull:{ n: 26, win: 17 }, bear:{ n: 18, win: 10 } } };
}
function mockTrades(){
  return [
    { id:'t1', ts: Date.now()-3600e3, side:'BUY', ticker:'AAPL', qty:20, price:190.23, pnl: 24.3 },
    { id:'t2', ts: Date.now()-3200e3, side:'SELL', ticker:'TSLA', qty:10, price:201.90, pnl: -10.1 }
  ];
}
function mockLeaderboard(){
  return [
    { agentId:'alpha', name:'Bob', role:'Portfolio Manager', avatar:'agent1', rank:1, winRate:.70, bull:{n:15, win:12}, bear:{n:6, win:4}, logs:["Bull on AAPL ✓","Bear on SNAP ✗"] },
    { agentId:'beta', name:'Carl', role:'Risk Manager', avatar:'agent2', rank:2, winRate:.62, bull:{n:11, win:7}, bear:{n:8, win:6}, logs:["Bear hedge on QQQ ✓"] },
    { agentId:'gamma', name:'Alice', role:'Valuation Analyst', avatar:'agent3', rank:3, winRate:.58, bull:{n:9, win:6}, bear:{n:12, win:7} },
    { agentId:'delta', name:'David', role:'Sentiment Analyst', avatar:'agent4', rank:4, winRate:.39, bull:{n:14, win:7}, bear:{n:18, win:7} },
    { agentId:'epsilon', name:'Eve', role:'Fundamentals Analyst', avatar:'agent5', rank:5, winRate:.39, bull:{n:14, win:7}, bear:{n:18, win:7} },
    { agentId:'zeta', name:'Frank', role:'Technical Analyst', avatar:'agent6', rank:5, winRate:.39, bull:{n:14, win:7}, bear:{n:18, win:7} }
  ];
}

// ======= Dev self-test (now actually used) =======
(function selfTest(){
  try {
    const lb = mockLeaderboard();
    console.assert(Array.isArray(lb) && lb.length >= 1, 'mockLeaderboard should return non-empty array');
    console.assert(lb[0].agentId && lb[0].name && lb[0].role, 'leaderboard row shape');
    const hs = mockHoldings();
    console.assert(Array.isArray(hs), 'mockHoldings array');
    const ms = mockSummary();
    console.assert(ms && Array.isArray(ms.equity), 'mockSummary equity array');
    window.__LB_SELFTEST_OK = true;
  } catch (e) {
    window.__LB_SELFTEST_OK = false;
  }
})();
