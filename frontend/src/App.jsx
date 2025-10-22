import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * LiveTradingCompanyApp — "仪表条 + 抽屉" 版本（可直接运行）
 * 说明：
 * - 用全宽仪表条（Bar）替换原来的小三角折叠按钮。
 * - 仪表条点击后，展开/收起 Team 抽屉（Drawer）。
 * - 订阅/退订 WebSocket 仍然基于 showTeam 状态。
 * - 移除了缩放 Agents 行的 transform/测高逻辑，避免文字被缩放导致的可读性问题。
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
    if (this.ws) { try { this.ws.close(); } catch {}
    }
    this.ws = null;
  }
}

// ====== Global style ======
function RevampStyles() {
  return (
    <style>{`
      @font-face {font-family: 'Pixeloid'; src: local('Pixeloid'), url('/fonts/PixeloidSans.ttf') format('truetype'); font-display: swap;}
      html, body, #root { height: 100%; }
      body { margin:0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Pixeloid', 'Courier New', monospace; background:#ffffff; color:#0b1220; letter-spacing:0.2px; }
      canvas, img { image-rendering: pixelated; image-rendering: crisp-edges; }

      .wrap { display:flex; flex-direction:column; min-height:100vh; }
      .topbar { background:#ffffff; padding:14px 0; border-bottom:1px solid #000; position: sticky; top: 0; z-index: 10; }
      .title { font-size:18px; font-weight:900; letter-spacing:2px; text-align:center; text-transform:uppercase; }

      /* ===== Agents row ===== */
      .agentsShell { position:relative; }
      .agents { padding:14px 12px; display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; max-width:1400px; margin:0 auto; }
      .agent-card { display:flex; flex-direction:column; align-items:center; gap:6px; background:#fff; border:1px dotted #000; border-radius:4px; padding:8px 6px; }
      .avatar-square { width:92px; height:92px; position:relative; display:flex; align-items:center; justify-content:center; overflow:hidden; border-radius:0; background:#ffffff; border:none; }
      .avatar-img { width:92px; height:92px; object-fit:contain; }
      .talk-dot { position:absolute; top:6px; right:6px; width:10px; height:10px; border-radius:0; border:1px solid #000; }
      .agent-name { font-size:12px; font-weight:900; }
      .agent-role { font-size:11px; margin-top:2px; opacity:.95; }

      /* ===== Meter Bar + Drawer ===== */
      .bar { width:100%; border-top:1px solid #000; background:#fff; display:flex; align-items:center; justify-content:center; gap:12px; padding:10px 12px; border-radius:0;}
      .bar:focus { border-top:1px solid #000; outline-offset:-2px; }
      .bar-title { font-weight:900; letter-spacing:1px; }
      .bar-metrics { font-size:12px; opacity:.9; }
      .bar b { font-weight:900; }
      .chev { width:10px; height:10px; border-right:2px solid #000; border-bottom:2px solid #000; transform:rotate(45deg); transition: transform .25s ease; }
      .chev.up { transform: rotate(-135deg); }

      .drawer { overflow:hidden; max-height:0; transition:max-height .45s ease; background:#fff; }
      .drawer.open { max-height: 680px; }

      .teamWrap { max-width:1400px; margin:0 auto; padding:0 12px 10px; display:flex; flex-direction:column; gap:12px; max-height: 60vh; overflow:auto; }

      .panel { border:1px solid #000; background:#fff; border-radius:0; padding:10px; }
      .teamPanel { border:none !important; padding:0 !important; background:#fff; }
      .panel-title { font-size:16px; font-weight:900; letter-spacing:1px; display:flex; align-items:center; justify-content:space-between; }

      .tabs { display:flex; border-bottom:1px solid #000; }
      .tab { font-size:12px; font-weight:900; padding:8px 10px; border-right:1px solid #000; background:#fff; cursor:pointer; }
      .tab.active { background:#000; color:#fff; }

      /* Chart: no border; axes drawn in canvas */
      .chart { height:220px; width:100%; }

      /* Leaderboard */
      .leaderboard { border:1px solid #000; }
      .lb-header { font-size:16px; font-weight:900; letter-spacing:1px; padding:10px; border-bottom:1px solid #000; display:flex; align-items:center; justify-content:space-between; }
      .lb-table { width:100%; border-collapse:separate; border-spacing:0; font-size:12px; }
      .lb-table thead th { position:sticky; top:0; background:#fff; border-bottom:1px solid #000; padding:8px; text-align:left; font-weight:900; }
      .lb-row { transition: transform .35s ease; }
      .lb-row.movedUp { animation: bumpUp .35s ease; }
      @keyframes bumpUp { 0%{transform:translateY(4px);} 100%{transform:translateY(0);} }
      .lb-cell { padding:8px; border-top:1px dotted #000; }
      .lb-avatar { width:28px; height:28px; image-rendering:pixelated; }
      .lb-expand { cursor:pointer; text-decoration:underline; font-size:11px; }
      .lb-log { padding:8px 10px; background:rgba(0,0,0,.03); border-top:1px dotted #000; white-space:pre-wrap; }

      .main { flex:1; max-width:1400px; margin:12px auto 18px; display:grid; grid-template-columns:1fr 380px; gap:16px; align-items:start; transition: transform .35s ease; }

      /* Scene panel — NO bg, NO border */
      .panel-scene { background:transparent; border:none; border-radius:0; }
      .scene { position:relative; height:520px; background:transparent; display:flex; align-items:center; justify-content:center; }
      .scene-inner { position:relative; }

      /* Square bubble (1px) */
      .bubble { position:absolute; max-width:300px; font-size:12px; background:#ffffff; color:#0b1220; padding:8px 10px; border-radius:0; border:1px solid #000; }
      .bubble::after{ content:""; position:absolute; left:14px; bottom:-7px; width:10px; height:10px; background:#ffffff; border-left:1px solid #000; border-bottom:1px solid #000; transform:rotate(45deg); }

      /* Right dock: Agent Logs only */
      .dock { display:flex; flex-direction:column; height:520px; }
      .dock-box { display:flex; flex-direction:column; border:1px solid #000; border-radius:0; height:100%; overflow:hidden;}
      .dock-body { flex:1; display:flex; flex-direction:column; padding:8px; overflow:auto; }
      .section-title { font-size:12px; font-weight:900; margin:0 0 8px; color:#0b1220; text-transform:uppercase; }

      /* Log list */
      .logs { overflow:auto; display:flex; flex-direction:column; gap:8px; }
      .log-card { border:1px dotted #000; border-radius:0; padding:8px; position:relative; box-sizing:border-box; }
      .log-header { display:flex; align-items:center; gap:8px; font-size:12px; }
      .log-badge { height:10px; width:10px; border-radius:0; border:1px solid #000; }
      .log-agent { font-weight:900; }
      .log-time { margin-left:auto; color:#0b1220; font-size:11px; opacity:.7; }
      .log-text { font-size:12px; line-height:1.45; margin-top:6px; white-space:pre-wrap; }
      .log-expand { position:absolute; right:8px; bottom:6px; font-size:11px; color:#000; cursor:pointer; user-select:none; text-decoration:underline; }

      /* Footer buttons */
      .footer { background:#ffffff; border-top:1px solid #000; }
      .footer-inner { max-width:1400px; margin:0 auto; display:flex; gap:10px; align-items:center; justify-content:space-between; padding:10px; }
      .btn { border:1px solid #000; background:#ffffff; color:#000; padding:8px 12px; font-weight:900; border-radius:0; }
      .btn:hover { background:#000; color:#fff; }
      .btn-primary { background:#000; color:#fff; }
      .btn-primary:hover { filter:contrast(1.1); }
      .btn-danger { border-color:#FF3B8D; color:#FF3B8D; }
      .btn-danger:hover { background:#FF3B8D; color:#fff; }

      .toolbar { display:none; }
      select, input[type="date"], input[type="text"] { padding:6px 8px; border:1px solid #000; border-radius:0; }
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

  // Drawer state（替代小三角折叠）
  const [showTeam, setShowTeam] = useState(false);

  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const scale = useResizeScale(containerRef, SCENE_NATIVE);

  const bgImg = useImage(ASSETS.roomBg);
  const avatars = {
    agent1: useImage(ASSETS.boss),
    agent2: useImage(ASSETS.worker2),
    agent3: useImage(ASSETS.worker4),
    agent4: useImage(ASSETS.worker1),
    agent5: useImage(ASSETS.worker1),
    agent6: useImage(ASSETS.worker4),
  };

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    canvas.width = SCENE_NATIVE.width; canvas.height = SCENE_NATIVE.height;
    canvas.style.width = `${SCENE_NATIVE.width * scale}px`;
    canvas.style.height = `${SCENE_NATIVE.height * scale}px`;
  }, [scale]);

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return; const ctx = canvas.getContext("2d"); let raf;
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
  }, [bgImg, avatars.worker1, avatars.worker2, avatars.worker4, avatars.boss]);

  const clientRef = useRef(null);

  const pushEvent = (evt) => {
    if (!evt) return;
    if (evt.type === 'agent_message') {
      const a = AGENTS.find((x) => x.id === evt.agentId);
      const entry = { id: `${Date.now()}-${Math.random()}`, ts: new Date(), who: a?.name || evt.agentId, role: a?.role, text: evt.content };
      setLogs((prev) => [entry, ...prev].slice(0, 400));
      setBubbles((prev) => ({ ...prev, [evt.agentId]: { text: evt.content, ts: Date.now(), role: a?.role } }));
      return;
    }
    if (evt.type === 'system') {
      const entry = { id: `${Date.now()}-${Math.random()}`, ts: new Date(), who: 'System', role: 'System', text: evt.content };
      setLogs((prev) => [entry, ...prev].slice(0, 400));
      return;
    }
    // ===== Team Dashboard channels over WebSocket =====
    if (evt.type === 'team_summary') {
      // { pnlPct, equity:[{t,v}], balance }
      setTeamSummary({ pnlPct: evt.pnlPct ?? 0, equity: evt.equity || [], balance: evt.balance });
      if (typeof evt.balance === 'number') setBalance(evt.balance);
      return;
    }
    if (evt.type === 'team_portfolio') {
      // { holdings:[...] }
      setHoldings(evt.holdings || []);
      return;
    }
    if (evt.type === 'team_stats') {
      // { winRate, hitRate, bullBear:{ bull:{n,win}, bear:{n,win} } }
      setStats(evt);
      return;
    }
    if (evt.type === 'team_trades') {
      if (Array.isArray(evt.trades)) setTradeLogs(evt.trades);
      else if (evt.trade) setTradeLogs((prev)=>[evt.trade, ...prev].slice(0,400));
      return;
    }
    if (evt.type === 'team_leaderboard') {
      if (Array.isArray(evt.rows)) setLeaderboard(evt.rows);
      return;
    }
  };

  const handleRun = () => {
    clientRef.current?.stop?.();
    clientRef.current = new PythonClient(pushEvent, { wsUrl: "ws://localhost:8765/ws" });
    clientRef.current.start({ mode: 'realtime' });
    setIsRunning(true);
  };
  const handleReplay = () => {
    clientRef.current?.stop?.();
    clientRef.current = new PythonClient(pushEvent, { wsUrl: "ws://localhost:8765/ws" });
    clientRef.current.start({ mode: 'replay', date: selectedDate });
    setIsRunning(true);
  };
  const handleStop = () => { clientRef.current?.stop?.(); setIsRunning(false); };

  const bubbleFor = (id) => {
    const b = bubbles[id]; if (!b) return null; const age = (Date.now() - b.ts) / 1000; if (age > 4) return null; return b; };

  // ===== Team Results state =====
  const [teamTab, setTeamTab] = useState('net'); // 'net' | 'portfolio' | 'stats' | 'trades'
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

  // Subscribe/unsubscribe based on visibility (改为基于 Drawer)
  useEffect(() => {
    const ws = clientRef.current?.ws;
    const channels = ['team_summary','team_portfolio','team_stats','team_trades','team_leaderboard'];
    if (!ws) return;
    if (showTeam) {
      ws.send(JSON.stringify({ type: 'subscribe', channels }));
      ws.send(JSON.stringify({ type: 'request_snapshot', channels }));
    } else {
      ws.send(JSON.stringify({ type: 'unsubscribe', channels }));
    }
  }, [showTeam]);

  return (
    <div className="wrap">
      <RevampStyles />
      <div className="topbar"><div className="title">LIVE TRADING COMPANY</div></div>

      {/* Agent Cards */}
      <div className="agentsShell">
        <div className="agents">
          {AGENTS.map((a) => {
            const talk = bubbleFor(a.id);
            const speaking = !!talk;
            const color = ROLE_COLORS[a.role] || '#000';
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

        {/* 仪表条（Bar） */}
        <button
          className="bar"
          aria-expanded={showTeam}
          aria-controls="team-drawer"
          onClick={() => setShowTeam(v => !v)}
          style={{
        background: teamSummary.pnlPct >= 0 ? '#E8F8E0' : '#FFE8EE',   // 胜利=浅绿，亏损=浅红
        borderBottom: '1px solid #000'
        }}
        >
          <span className="bar-title">TEAM DASHBOARD</span>
          <span className="bar-metrics">P&L <b>{teamSummary.pnlPct >= 0 ? '+' : ''}{(teamSummary.pnlPct||0).toFixed(1)}%</b> · Holdings <b>{holdings?.length || 0}</b></span>
          <span className={`chev ${showTeam ? 'up' : ''}`} aria-hidden />
        </button>

        {/* Drawer（抽屉） */}
        <div id="team-drawer" className={`drawer ${showTeam ? 'open' : ''}`}>
          {showTeam && (
            <div className="teamWrap">
              {/* TEAM RESULTS (full width) */}
              <section className="panel teamPanel">
                <div className="panel-title">
                  <span>TEAM RESULTS</span>
                  <strong style={{ color: teamSummary.pnlPct >= 0 ? '#6EB300' : '#FF3B8D' }}>{teamSummary.pnlPct >= 0 ? '+' : ''}{(teamSummary.pnlPct||0).toFixed(1)}%</strong>
                </div>
                {/* Tabs */}
                <div className="tabs" style={{ marginTop:8 }}>
                  <div className={`tab ${teamTab==='net'?'active':''}`} onClick={()=>setTeamTab('net')}>NET VALUE</div>
                  <div className={`tab ${teamTab==='portfolio'?'active':''}`} onClick={()=>setTeamTab('portfolio')}>PORTFOLIO</div>
                  <div className={`tab ${teamTab==='stats'?'active':''}`} onClick={()=>setTeamTab('stats')}>STATISTICS</div>
                  <div className={`tab ${teamTab==='trades'?'active':''}`} onClick={()=>setTeamTab('trades')}>TRADES</div>
                </div>
                <div style={{ paddingTop:10 }}>
                  {teamTab==='net' && <NetValueChart data={teamSummary.equity || []} />}
                  {teamTab==='portfolio' && <PortfolioTable holdings={holdings} />}
                  {teamTab==='stats' && <StatisticsPanel stats={stats} />}
                  {teamTab==='trades' && <TradesTable trades={tradeLogs} />}
                  <div style={{ fontSize:12, marginTop:8 }}>Balance: <span style={{ fontWeight: 900 }}>${balance.toLocaleString()}</span></div>
                </div>
              </section>

              {/* LEADERBOARD */}
              <section className="panel teamPanel" style={{ padding:0 }}>
                <div className="lb-header" style={{ borderBottom:'1px solid #000' }}>LEADERBOARD
                  <small style={{ fontSize:11, opacity:.7 }}>&nbsp;•&nbsp;Click row to expand</small>
                </div>
                <div style={{ maxHeight: '38vh', minHeight: 180, overflowY:'auto' }}>
                  <LeaderboardTable rows={leaderboard} />
                </div>
              </section>

              <div style={{ borderTop:'1px solid #000', margin:'8px 0 0' }} />
            </div>
          )}
        </div>
      </div>

      {/* Main content: scene + right dock */}
      <div className="main">
        {/* Full room scene (no bg/border) */}
        <div className="panel-scene">
          <div ref={containerRef} className="scene">
            <div className="scene-inner" style={{ width: SCENE_NATIVE.width * scale, height: SCENE_NATIVE.height * scale }}>
              <canvas ref={canvasRef} />
              {AGENTS.map((a, i) => {
                const pos = AGENT_SEATS[i];
                const b = bubbleFor(a.id);
                if (!b) return null;
                const color = ROLE_COLORS[a.role] || '#000';
                let text = b.text || '';
                if (text.length > 50) text = text.slice(0, 50) + '…';
                const left = Math.round((pos.x - 20) * scale);
                const top = Math.round((pos.y - 150) * scale);
                return (
                  <div key={a.id} className="bubble" style={{ left, top }}>
                    <div style={{ fontWeight: 900, marginBottom: 4, color }}>{a.name}</div>
                    {text}
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

      {/* Footer */}
      <div className="footer">
        <div className="footer-inner">
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button onClick={handleRun} className="btn btn-primary" title="Run (live)">RUN</button>
            <button onClick={handleReplay} className="btn" title="Replay (by date)">REPLAY</button>
            <button onClick={handleStop} className="btn btn-danger">STOP</button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <label htmlFor="replay-date" style={{ fontSize:12 }}>DATE</label>
            <input id="replay-date" type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} />
            <div>|</div>
            <div style={{ fontVariantNumeric:'tabular-nums' }}>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</div>
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
    <div style={{ border: '1px solid #000', borderRadius: 0, padding: 6 }}>
      <table className="portfolio-table" style={{ width:'100%' }}>
        <thead>
          <tr>
            <th style={{ width: '28%' }}>Ticker</th>
            <th>Qty</th>
            <th>Avg Cost</th>
            <th>P/L</th>
            <th>Weight</th>
          </tr>
        </thead>
        <tbody>
          {(!holdings || holdings.length === 0) ? (
            <tr><td colSpan={5} style={{ padding: 10, opacity:.6 }}>No positions</td></tr>
          ) : holdings.map((h) => (
            <tr key={h.ticker}>
              <td style={{ fontWeight: 900 }}>{h.ticker}</td>
              <td>{h.qty}</td>
              <td>${Number(h.avg).toFixed(2)}</td>
              <td style={{ color: h.pl >= 0 ? '#6EB300' : '#FF3B8D', fontWeight: 900 }}>{h.pl >= 0 ? '+' : ''}{Number(h.pl).toFixed(2)}</td>
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
    const cnv = ref.current; if (!cnv) return; const ctx = cnv.getContext('2d');
    const parent = cnv.parentElement; const W = Math.max(280, parent.clientWidth - 15); const H = 220;
    cnv.width = W; cnv.height = H; cnv.style.width = W + 'px'; cnv.style.height = H + 'px';

    // Clear background
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle = '#fff'; ctx.fillRect(0,0,W,H);

    // Early exit
    if (!data || data.length === 0) {
      drawAxes(ctx, W, H, { lo: 0, hi: 1 }, []);
      return;
    }

    const vals = data.map(d => d.v);
    const hi = Math.max(...vals), lo = Math.min(...vals);

    // Axes (left + bottom) with ticks & labels
    drawAxes(ctx, W, H, { lo, hi }, data);

    // Line
    const m = { left: 42, right: 10, top: 8, bottom: 28 };
    const chartW = W - m.left - m.right;
    const chartH = H - m.top - m.bottom;
    const y = (v) => m.top + Math.round((1 - (v - lo) / ((hi - lo) || 1)) * chartH);
    const x = (i) => m.left + Math.round((i / Math.max(1, data.length - 1)) * chartW);

    ctx.beginPath();
    data.forEach((d, i) => {
      const px = x(i), py = y(d.v);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#00B3CC';
    ctx.stroke();
  }, [data]);
  return <canvas ref={ref} className="chart" />;
}

function drawAxes(ctx, W, H, range, data) {
  const m = { left: 42, right: 10, top: 8, bottom: 28 };
  const chartW = W - m.left - m.right;
  const chartH = H - m.top - m.bottom;

  // Axes lines
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 1;
  ctx.beginPath();
  // Y axis
  ctx.moveTo(m.left + 0.5, m.top); ctx.lineTo(m.left + 0.5, m.top + chartH);
  // X axis
  ctx.moveTo(m.left, m.top + chartH + 0.5); ctx.lineTo(m.left + chartW, m.top + chartH + 0.5);
  ctx.stroke();

  // Y ticks & labels (5 ticks)
  const ticks = 5;
  ctx.font = '10px ui-monospace, Menlo, monospace';
  ctx.fillStyle = '#000';
  for (let i = 0; i <= ticks; i++) {
    const t = i / ticks;
    const val = range.lo + (range.hi - range.lo) * (1 - t);
    const py = m.top + Math.round(t * chartH) + 0.5;
    // tick
    ctx.beginPath();
    ctx.moveTo(m.left - 4, py); ctx.lineTo(m.left, py);
    ctx.stroke();
    // label
    const label = formatMoney(val);
    ctx.fillText(label, 4, py + 3);
  }

  // X ticks & labels (start / mid / end dates)
  const n = data?.length || 0;
  const xIdx = (i) => m.left + Math.round((i / Math.max(1, n - 1)) * chartW);
  const picks = n >= 3 ? [0, Math.floor((n - 1) / 2), n - 1] : [0, n - 1].filter((v, i, a) => a.indexOf(v) === i);
  picks.forEach((idx) => {
    if (idx < 0 || idx >= n) return;
    const px = xIdx(idx) + 0.5;
    ctx.beginPath(); ctx.moveTo(px, m.top + chartH); ctx.lineTo(px, m.top + chartH + 4); ctx.stroke();
    const label = formatDateLabel(data[idx]?.t);
    const textW = ctx.measureText(label).width;
    ctx.fillText(label, px - textW / 2, H - 4);
  });
}

function formatMoney(v) {
  if (!isFinite(v)) return '-';
  const abs = Math.abs(v);
  const sign = v < 0 ? '-' : '';
  if (abs >= 1e9) return `${sign}${(abs/1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(abs/1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs/1e3).toFixed(2)}K`;
  return `${sign}${abs.toFixed(2)}`;
}

function formatDateLabel(t) {
  if (!t) return '';
  const d = new Date(t);
  if (isNaN(d)) return '';
  return `${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')}`;
}

function StatisticsPanel({ stats }) {
  if (!stats) return <div style={{ opacity:.6, fontSize:12 }}>No statistics.</div>;
  const rows = [
    ["WIN %", `${Math.round((stats.winRate||0)*100)}%`],
    ["HIT RATE", `${Math.round((stats.hitRate||0)*100)}%`],
    ["BULL", `${stats.bullBear?.bull?.n||0} × / WIN ${stats.bullBear?.bull?.win||0}`],
    ["BEAR", `${stats.bullBear?.bear?.n||0} × / WIN ${stats.bullBear?.bear?.win||0}`],
  ];
  return (
    <div className="panel" style={{ padding:6 }}>
      <table className="portfolio-table" style={{ width:'100%' }}>
        <tbody>
          {rows.map(([k,v]) => (
            <tr key={k}>
              <td style={{ width:'40%', fontWeight:900 }}>{k}</td>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradesTable({ trades }) {
  return (
    <div className="panel" style={{ padding:6 }}>
      <table className="portfolio-table" style={{ width:'100%' }}>
        <thead>
          <tr>
            <th>Time</th><th>Ticker</th><th>Side</th><th>Qty</th><th>Price</th><th>P/L</th>
          </tr>
        </thead>
        <tbody>
          {(!trades || trades.length===0) ? (
            <tr><td colSpan={6} style={{ padding: 10, opacity:.6 }}>No trades</td></tr>
          ) : trades.map(t => (
            <tr key={t.id}>
              <td>{formatTime(t.ts)}</td>
              <td style={{ fontWeight:900 }}>{t.ticker}</td>
              <td>{t.side}</td>
              <td>{t.qty}</td>
              <td>${Number(t.price).toFixed(2)}</td>
              <td style={{ color: t.pnl >= 0 ? '#6EB300' : '#FF3B8D', fontWeight:900 }}>{t.pnl>=0?'+':''}{Number(t.pnl).toFixed(2)}</td>
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

  return (
    <div>
      <table className="lb-table">
        <thead>
          <tr>
            <th style={{ width:60 }}>RANK</th>
            <th colSpan={2}>AGENT</th>
            <th style={{ width:90 }}>WIN %</th>
            <th style={{ width:160 }}>BULL</th>
            <th style={{ width:160 }}>BEAR</th>
            <th style={{ width:80 }}>LOGS</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const color = ROLE_COLORS[r.role] || '#000';
            const movedUp = prevRanksRef.current[r.agentId] && prevRanksRef.current[r.agentId] > r.rank;
            prevRanksRef.current[r.agentId] = r.rank;
            const open = openRow === r.agentId;
            return (
              <React.Fragment key={r.agentId}>
                <tr className={`lb-row ${movedUp ? 'movedUp' : ''}`} onClick={()=> setOpenRow(open ? null : r.agentId)}>
                  <td className="lb-cell" style={{ fontWeight:900 }}>{r.rank}</td>
                  <td className="lb-cell" style={{ width:34 }}>
                    <img className="lb-avatar" src={ASSETS[r.avatar]} alt={r.name} />
                  </td>
                  <td className="lb-cell" style={{ fontWeight:900, color }}>{r.name}<div style={{ fontSize:10, opacity:.8 }}>{r.role}</div></td>
                  <td className="lb-cell" style={{ fontWeight:900 }}>{r.winRate==null?'-':Math.round((r.winRate||0)*100)+'%'}</td>
                  <td className="lb-cell">{fmt(r.bull?.n)} × / WIN {fmt(r.bull?.win)}</td>
                  <td className="lb-cell">{fmt(r.bear?.n)} × / WIN {fmt(r.bear?.win)}</td>
                  <td className="lb-cell"><span className="lb-expand">{open ? 'collapse' : 'expand'}</span></td>
                </tr>
                {open && (
                  <tr>
                    <td className="lb-log" colSpan={7}>{(r.logs || []).length ? (r.logs||[]).map((l,i)=>`${i+1}. ${l}`).join("") : 'No logs.'}</td>
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
  useEffect(() => {
    const onResize = () => {
      const el = containerRef.current; if (!el) return;
      const w = el.clientWidth; const h = el.clientHeight; const sx = w / native.width; const sy = h / native.height; setScale(Math.min(sx, sy));
    };
    onResize(); window.addEventListener("resize", onResize); return () => window.removeEventListener("resize", onResize);
  }, [containerRef, native.width, native.height]);
  return scale;
}

function formatTime(ts) { try { const d = new Date(ts); return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch { return '' } }

function hexToRgba(hex, a = 1) { if (!hex) return `rgba(0,0,0,${a})`; const c = hex.replace('#', ''); const bigint = parseInt(c.length === 3 ? c.split('').map(x=>x+x).join('') : c, 16); const r = (bigint >> 16) & 255; const g = (bigint >> 8) & 255; const b = bigint & 255; return `rgba(${r}, ${g}, ${b}, ${a})`; }

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
    // 标记通过，供组件内判断是否注入 mock 数据
    window.__LB_SELFTEST_OK = true;
  } catch (e) {
    window.__LB_SELFTEST_OK = false;
  }
})();
