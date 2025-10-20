import React, { useEffect, useRef, useState } from "react";

/**
 * LiveTradingCompanyApp
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
  { x: 470, y: 500 },
  { x: 600, y: 470 },
  { x: 730, y: 530 },
  { x: 545, y: 590 },
  { x: 655, y: 615 },
  { x: 800, y: 600 },
];

const AGENTS = [
  { id: "alpha", name: "Bob", role: "Portfolio Manager", avatar: "agent1" },
  { id: "beta", name: "Carl", role: "Risk Manager", avatar: "agent2" },
  { id: "gamma", name: "Alice", role: "Valuation Analyst", avatar: "agent3" },
  { id: "delta", name: "David", role: "Sentiment Analyst", avatar: "agent4" },
  { id: "epsilon", name: "Eve", role: "Fundamental Analyst", avatar: "agent5" },
  { id: "zeta", name: "Frank", role: "Technical Analyst", avatar: "agent6" },
];

// Neon, cold, hacker-ish accents (no warm oranges)
const ROLE_COLORS = {
  "Portfolio Manager": "#00B3CC", // deep cyan (readable)
  "Risk Manager": "#CC2E70", // deep magenta (readable)
  "Valuation Analyst": "#5C49CC", // deep indigo
  "Sentiment Analyst": "#6EB300", // deep lime
  "Fundamental Analyst": "#00B87A", // deep mint
  "Technical Analyst": "#BFA300", // deep yellow
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
    if (this.ws) { try { this.ws.close(); } catch {} }
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
      .topbar { background:#ffffff; padding:14px 0; border-bottom:1px solid #000; position: sticky; top: 0; z-index: 5; }
      .title { font-size:18px; font-weight:900; letter-spacing:2px; text-align:center; text-transform:uppercase; }

      .agents { padding:14px 12px; display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; max-width:1400px; margin:0 auto; }
      .agent-card { display:flex; flex-direction:column; align-items:center; gap:6px; background:#fff; border:1px dotted #000; border-radius:4px; padding:8px 6px; }
      .avatar-square { width:92px; height:92px; position:relative; display:flex; align-items:center; justify-content:center; overflow:hidden; border-radius:0; background:#ffffff; border:none; }
      .avatar-img { width:92px; height:92px; object-fit:contain; }
      .talk-dot { position:absolute; top:6px; right:6px; width:10px; height:10px; border-radius:0; border:1px solid #000; }
      .agent-name { font-size:12px; font-weight:900; }
      .agent-role { font-size:11px; margin-top:2px; opacity:.95; }

      .main { flex:1; max-width:1400px; margin:12px auto 18px; display:grid; grid-template-columns:1fr 380px; gap:16px; align-items:start; }

      /* Scene panel — NO bg, NO border */
      .panel-scene { background:transparent; border:none; border-radius:0; }
      .scene { position:relative; height:520px; background:transparent; display:flex; align-items:center; justify-content:center; }
      .scene-inner { position:relative; }

      /* Square bubble (1px) */
      .bubble { position:absolute; max-width:300px; font-size:12px; background:#ffffff; color:#0b1220; padding:8px 10px; border-radius:0; border:1px solid #000; }
      .bubble::after{ content:""; position:absolute; left:14px; bottom:-7px; width:10px; height:10px; background:#ffffff; border-left:1px solid #000; border-bottom:1px solid #000; transform:rotate(45deg); }

      /* Right dock: single bordered box with tabs header */
      .dock { display:flex; flex-direction:column; height:520px; }
      .dock-box { display:flex; flex-direction:column; border:1px solid #000; border-radius:0; height:100%; overflow:hidden;}
      .tabs { display:flex; gap:0; border-bottom:1px solid #000; border-radius:0; }
      .tab { flex:1; font-size:12px; font-weight:900; padding:8px 10px; background:#ffffff; cursor:pointer; border-right:1px solid #000; border-radius:0;}
      .tab:last-child{ border-right:none;border-radius:0; }
      .tab.active { background:#000; color:#fff; border-radius:0;}

      .dock-body { flex:1; display:flex; flex-direction:column; padding:8px; overflow:auto; }
      .section-title { font-size:12px; font-weight:900; margin:0 0 8px; color:#0b1220; text-transform:uppercase; }

      /* Chart */
      .chart { height:200px; border:1px solid #000; border-radius:0; background:#fff; width:100%; box-sizing:border-box; /* updated: no overflow */ }
      .portfolio-table { width:100%; border-collapse:separate; border-spacing:0; font-size:12px; }
      .portfolio-table th, .portfolio-table td { text-align:left; padding:6px 8px; }
      .portfolio-table thead th { position:sticky; top:0; background:#ffffff; border-bottom:1px solid #000; font-weight:900; }
      .portfolio-table tbody tr + tr td { border-top:1px dotted #000; }

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
  const [candles, setCandles] = useState(() => seedOHLC()); // K线数据
  const [holdings, setHoldings] = useState([]);

  const [tab, setTab] = useState('market');
  const [selectedDate, setSelectedDate] = useState(todayISO());

  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);

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
    if (evt.type === 'price') { setCandles((prev) => applyTick(prev, evt.price)); return; }
    if (evt.type === 'candle') { setCandles((prev) => [...prev.slice(-199), evt.candle]); return; }
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
    }
  };

  const handleRun = () => {
    clientRef.current?.stop?.();
    clientRef.current = new PythonClient(pushEvent, { wsUrl: "ws://localhost:8765/ws" });
    clientRef.current.start({ mode: 'run' });
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

  // ===== UI =====
  return (
    <div className="wrap">
      <RevampStyles />
      <div className="topbar"><div className="title">LIVE TRADING COMPANY</div></div>

      {/* Agent Cards */}
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
                if (text.length > 50) text = text.slice(0, 50) + '…'; // 7) bubble text limit
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

        {/* Right dock (fixed same height as scene) */}
        <div className="dock">
          <div className="dock-box">
            <div className="tabs">
              <button className={`tab ${tab === 'market' ? 'active' : ''}`} onClick={() => setTab('market')}>MARKET & PORTFOLIO</button>
              <button className={`tab ${tab === 'logs' ? 'active' : ''}`} onClick={() => setTab('logs')}>AGENT LOGS</button>
            </div>
            <div className="dock-body">
              {tab === 'market' ? (
                <>
                  <h3 className="section-title">Market</h3>
                  <KChart data={candles} />
                  <h3 className="section-title" style={{ marginTop:8 }}>Portfolio</h3>
                  <PortfolioTable holdings={holdings} />
                  <div style={{ fontSize:12, marginTop:8 }}>Balance: <span style={{ fontWeight: 900 }}>${balance.toLocaleString()}</span></div>
                </>
              ) : (
                <>
                  <h3 className="section-title">Agent Logs</h3>
                  <AgentLogs logs={logs} />
                </>
              )}
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
              <span style={{ color }}>&nbsp;::&nbsp;</span>
              <span style={{ color }}>{l.role}</span>
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
      <table className="portfolio-table">
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
          {holdings.length === 0 ? (
            <tr><td colSpan={5} style={{ padding: 10, opacity:.6 }}>No positions</td></tr>
          ) : holdings.map((h) => (
            <tr key={h.ticker}>
              <td style={{ fontWeight: 900 }}>{h.ticker}</td>
              <td>{h.qty}</td>
              <td>${h.avg.toFixed(2)}</td>
              <td style={{ color: h.pl >= 0 ? '#9EFF00' : '#FF3B8D', fontWeight: 900 }}>{h.pl >= 0 ? '+' : ''}{h.pl.toFixed(2)}</td>
              <td>{(h.weight * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// K-line chart
function KChart({ data }) {
  const ref = useRef(null);
  useEffect(() => {
    const cnv = ref.current; if (!cnv) return; const ctx = cnv.getContext('2d');
    const parent = cnv.parentElement;
    const W = parent.clientWidth - 0; const H = 200; // body has padding already
    cnv.width = W; cnv.height = H; cnv.style.width = W + 'px'; cnv.style.height = H + 'px';
    ctx.imageSmoothingEnabled = false;

    // grid (1px)
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#000'; ctx.lineWidth = 1;
    for (let y = 0; y <= H; y += 16) { ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(W, y + 0.5); ctx.stroke(); }

    const highs = data.map(d => d.h), lows = data.map(d => d.l);
    const hi = Math.max(...highs), lo = Math.min(...lows);
    const pxY = (v) => Math.round((1 - (v - lo) / ((hi - lo) || 1)) * (H - 6)) + 3;

    const n = data.length; const gap = Math.max(1, Math.floor(W / (n * 2.2)));
    const bw = Math.max(3, Math.floor((W - n * gap) / n));

    data.forEach((d, i) => {
      const x = Math.round(i * (bw + gap) + 4);
      const yO = pxY(d.o), yC = pxY(d.c), yH = pxY(d.h), yL = pxY(d.l);
      const up = d.c >= d.o;
      const bodyTop = Math.min(yO, yC), bodyBot = Math.max(yO, yC);
      // wick
      ctx.strokeStyle = '#000';
      ctx.beginPath(); ctx.moveTo(x + Math.floor(bw/2), yH); ctx.lineTo(x + Math.floor(bw/2), yL); ctx.stroke();
      // body
      ctx.fillStyle = up ? '#00F5A0' : '#FF3B8D';
      ctx.strokeStyle = '#000';
      const hBody = Math.max(1, bodyBot - bodyTop);
      ctx.fillRect(x, bodyTop, bw, hBody);
      ctx.strokeRect(x, bodyTop, bw, hBody);
    });
  }, [data]);
  return <canvas ref={ref} className="chart" style={{ border:'1px solid #000' }} />;
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

function seedOHLC(n = 80, start = 100) {
  const arr = []; let p = start;
  for (let i = 0; i < n; i++) {
    const o = p; const ch = (Math.random() - 0.5) * 2.4;
    let h = o + Math.abs(ch) * (0.8 + Math.random());
    let l = o - Math.abs(ch) * (0.8 + Math.random());
    const c = o + ch; p = c; h = Math.max(h, Math.max(o, c)); l = Math.min(l, Math.min(o, c)); arr.push({ o, h, l, c });
  }
  return arr;
}

function applyTick(prev, price) {
  const out = prev.slice(); if (out.length === 0) return [{ o: price, h: price, l: price, c: price }];
  const last = { ...out[out.length - 1] }; last.c = price; last.h = Math.max(last.h, price); last.l = Math.min(last.l, price); out[out.length - 1] = last; return out;
}

function formatTime(ts) { try { const d = new Date(ts); return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch { return '' } }

function hexToRgba(hex, a = 1) { if (!hex) return `rgba(0,0,0,${a})`; const c = hex.replace('#', ''); const bigint = parseInt(c.length === 3 ? c.split('').map(x=>x+x).join('') : c, 16); const r = (bigint >> 16) & 255; const g = (bigint >> 8) & 255; const b = bigint & 255; return `rgba(${r}, ${g}, ${b}, ${a})`; }