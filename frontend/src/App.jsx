import React, { useEffect, useRef, useState } from "react";

/**
 * LiveTradingCompanyApp — controls + client simplification
 * -------------------------------------------------------
 * Changes per request:
 * 1) 底部右侧加入可编辑的日期选择器（input[type=date]）。
 * 2) 前端移除 SandboxClient，统一通过 WebSocket 访问后端（默认 ws://localhost:8765/ws），
 *    连接时通过参数区分是 "replay"（沙盒回放）还是 "run"（实时）。
 * 3) 移除速度控制（1x/2x/4x），按正常速率展示。
 */

// ====== Configuration ======
const ASSET_BASE_URL = "/assets/company_room"; // Place all PNGs under public/assets

const ASSETS = {
  roomBg: `${ASSET_BASE_URL}/full_room_color.png`,
  worker1: `${ASSET_BASE_URL}/worker1.png`,
  worker2: `${ASSET_BASE_URL}/worker2.png`,
  worker4: `${ASSET_BASE_URL}/worker4.png`,
  boss: `${ASSET_BASE_URL}/boss.png`,
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

const todayISO = () => new Date().toISOString().slice(0, 10);

// ====== Client abstraction（仅保留统一 PythonClient） ======
class IClient {
  /** @param {(evt: any) => void} onEvent */
  constructor(onEvent) { this.onEvent = onEvent; }
  start(_config) {}
  stop() {}
}

/**
 * PythonClient — 统一与后端通讯。
 * 后端应支持：WebSocket ws://<host>/ws ，发送 {type:'run', config} 启动；
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
        // 服务端直接下发 {type:'agent_message'|'price'|'system', ...}
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

// ====== Pixel styles ======
function PixelStyles() {
  return (
    <style>{`
      @font-face {font-family: 'Pixeloid'; src: local('Pixeloid'), url('/fonts/PixeloidSans.ttf') format('truetype'); font-display: swap;}
      html, body, #root { height: 100%; }
      body { margin:0; font-family: Pixeloid, monospace; background:#d7d0c8; color:#ededed; }
      canvas, img { image-rendering: pixelated; image-rendering: crisp-edges; }
      .scene canvas { background: #bfb7ad; }

      .wrap { display:flex; flex-direction:column; min-height:100vh; }
      .topbar { background:#cfc7be; color:#1c1c1c; padding:10px 0; border-bottom:2px solid #a9a197; text-align:center; }
      .title { font-size:18px; font-weight:900; letter-spacing:2px; }

      .agents { padding:10px 8px; display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:8px; max-width:2000px; margin:0 auto; }
      .agent-card { display:flex; flex-direction:column; align-items:center; gap:6px; background: transparent; border: 0; box-shadow: none; padding:6px 4px; color:#1a1a1a; }
      .avatar-square { width:96px; height:96px; position:relative; display:flex; align-items:center; justify-content:center; overflow:hidden; }
      .avatar-img { width:96px; height:96px; object-fit:contain; }
      .talk-dot { position:absolute; top:11px; right:7px; width:9px; height:9px; border:2px solid #ffffff; }
      .agent-name { font-size:10px; color:#1a1a1a; }
      .agent-role { font-size:12px; font-weight:700; color:#1a1a1a; margin-top:2px; }

      .main { flex:1; max-width:2000px; margin:12px auto; display:grid; grid-template-columns:300px 1fr 300px; gap:12px; align-items:start; }
      .panel { background:#26364B; border:2px solid #1C2A3D; box-shadow: inset 0 0 0 1px #3b4f6a; padding:8px; }
      .panel h3 { margin:0 0 6px 0; font-size:12px; color:#B8C0CC; }
      .panel-logs { margin-left: 30px; }
      .panel-market { margin-right: 30px; }
      .scene { position:relative; height:540px; background:#bfb7ad; display:flex; align-items:center; justify-content:center; }
      .scene-inner { position:relative; }
      .bubble { position:absolute; max-width:220px; font-size:12px; background:#26364B; border:2px solid #1C2A3D; padding:4px 6px; color:#EDEDED; }
      .bubble::after{ content:""; position:absolute; left:16px; bottom:-6px; width:8px; height:8px; background:#26364B; border-left:2px solid #1C2A3D; border-bottom:2px solid #1C2A3D; transform:rotate(45deg); }

      .logs { height:320px; overflow:auto; font-size:11px; line-height:1.25;color:#EDEDED; }
      .chart { height:320px; image-rendering: pixelated; image-rendering: crisp-edges; }

      .btn { border:2px solid #1e1e1e; background:#F4A63B; color:#1a1a1a; padding:8px 10px; width:100%; font-weight:700; }
      .btn:hover { background:#D98522; }
      .btn-gray { background:#3A3A3A; color:#EDEDED; }

      .footer { background:#e5ddd4; border-top:2px solid #bdb5aa; }
      .footer-inner { max-width:2000px; margin:0 auto; display:flex; gap:10px; align-items:center; justify-content:space-between; padding:8px; color:#1a1a1a; }
      .btn-small { border:2px solid #1e1e1e; background:#2c2c2c; color:#fff; padding:6px 10px; }

      .toolbar { display:none; }
      select, input[type="date"], input[type="text"] { padding:6px 8px; border:1px solid #bbb; border-radius:6px; }
    `}</style>
  );
}

// ====== Main Component ======
export default function LiveTradingCompanyApp() {
  const [isRunning, setIsRunning] = useState(false);
  const [balance, setBalance] = useState(1250000);
  const [logs, setLogs] = useState([]);
  const [bubbles, setBubbles] = useState({});
  const [prices, setPrices] = useState(() => seedPrices());

  // Date for replay (user-selectable)
  const [selectedDate, setSelectedDate] = useState(todayISO());

  // Live clock for display
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

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

  // draw loop sizing
  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    canvas.width = SCENE_NATIVE.width; canvas.height = SCENE_NATIVE.height;
    canvas.style.width = `${SCENE_NATIVE.width * scale}px`;
    canvas.style.height = `${SCENE_NATIVE.height * scale}px`;
  }, [scale]);

  // draw loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf;
    const draw = () => {
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (bgImg) ctx.drawImage(bgImg, 0, 0, SCENE_NATIVE.width, SCENE_NATIVE.height);
      // Agents – fixed size 128x128
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

  // unified client
  const clientRef = useRef(null);

  const pushEvent = (evt) => {
    if (!evt) return;
    if (evt.type === 'price') {
      setPrices((prev) => [...prev.slice(-299), evt.price]);
      return;
    }
    if (evt.type === 'agent_message') {
      const a = AGENTS.find((x) => x.id === evt.agentId);
      const entry = { id: `${Date.now()}-${Math.random()}`, ts: new Date(), who: a?.name || evt.agentId, text: evt.content };
      setLogs((prev) => [entry, ...prev].slice(0, 300));
      setBubbles((prev) => ({ ...prev, [evt.agentId]: { text: evt.content, ts: Date.now() } }));
      return;
    }
    if (evt.type === 'system') {
      const entry = { id: `${Date.now()}-${Math.random()}`, ts: new Date(), who: 'System', text: evt.content };
      setLogs((prev) => [entry, ...prev].slice(0, 300));
      return;
    }
  };

  // Footer button handlers (直接控制 PythonClient）
  const handleRun = () => {
    // 实时模式
    clientRef.current?.stop?.();
    clientRef.current = new PythonClient(pushEvent, { wsUrl: "ws://localhost:8765/ws" });
    clientRef.current.start({ mode: 'run' });
    setIsRunning(true);
  };
  const handleReplay = () => {
    // 回放模式，携带日期
    clientRef.current?.stop?.();
    clientRef.current = new PythonClient(pushEvent, { wsUrl: "ws://localhost:8765/ws" });
    clientRef.current.start({ mode: 'replay', date: selectedDate });
    setIsRunning(true);
  };
  const handleStop = () => {
    clientRef.current?.stop?.();
    setIsRunning(false);
  };

  const bubbleFor = (id) => {
    const b = bubbles[id];
    if (!b) return null;
    const age = (Date.now() - b.ts) / 1000;
    if (age > 4) return null;
    return b.text;
  };

  const doDecision = (type) => {
    const price = prices[prices.length - 1] || 100;
    setLogs((prev) => [{ id: `${Date.now()}-d`, ts: new Date(), who: 'System', text: `Decision: ${type} at $${price.toFixed(2)}` }, ...prev]);
    if (type === 'Buy Stock A') setBalance((b) => b - 10000);
  };

  return (
    <div className="wrap">
      <PixelStyles />
      <div className="topbar">
        <div className="title">LIVE TRADING COMPANY</div>
      </div>

      {/* Agent Cards */}
      <div className="agents">
        {AGENTS.map((a) => {
          const speaking = !!bubbleFor(a.id);
          return (
            <div key={a.id} className="agent-card">
              <div className="avatar-square">
                <img src={ASSETS[a.avatar]} alt={a.name} className="avatar-img" />
                <span className="talk-dot" style={{ background: speaking ? '#3adc64' : '#7a7a7a' }} />
              </div>
              <div className="agent-labels">
                <div className="agent-name">{a.name}</div>
                <div className="agent-role">{a.role}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main content */}
      <div className="main">
        {/* Logs */}
        <div className="panel panel-logs">
          <h3>Agent Logs</h3>
          <div className="logs">
            {logs.length === 0 && (<div style={{ color: '#B8C0CC' }}>No logs yet. Use Replay or Run.</div>)}
            {logs.map((l) => (
              <div key={l.id} style={{ marginBottom: 6 }}>
                <span style={{ fontWeight: 800 }}>{l.who}:</span> {l.text}
              </div>
            ))}
          </div>
        </div>

        {/* Scene */}
        <div className="panel-plain">
          <div className="panel panel-scene">
            <div ref={containerRef} className="scene">
              <div className="scene-inner" style={{ width: SCENE_NATIVE.width * scale, height: SCENE_NATIVE.height * scale }}>
                <canvas ref={canvasRef} />
                {AGENTS.map((a, i) => {
                  const pos = AGENT_SEATS[i];
                  let text = bubbleFor(a.id);
                  if (!text) return null;
                  const MAX_LEN = 50;
                  if (text.length > MAX_LEN) text = text.slice(0, MAX_LEN) + '...';
                  const left = Math.round(pos.x * scale);
                  const top = Math.round((pos.y - 150) * scale);
                  return (
                    <div key={a.id} className="bubble" style={{ left, top }}>
                      {text}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Market + actions */}
        <div className="panel panel-market">
          <h3>Market Data & Trade Actions</h3>
          <PixelChart data={prices} />
          <div style={{ marginTop: 8 }}>
            <button onClick={() => doDecision('Buy Stock A')} className="btn">Buy Stock A</button>
          </div>
          <div style={{ marginTop: 8 }}>
            <button onClick={() => doDecision('Hold Assets')} className="btn btn-gray">Hold Assets</button>
          </div>
          <div style={{ fontSize: 11, color: '#B8C0CC', marginTop: 8 }}>Current Balance: <span style={{ fontWeight: 800, color: '#EDEDED' }}>${balance.toLocaleString()}</span></div>
        </div>
      </div>

      {/* Footer — controls + date/time */}
      <div className="footer">
        <div className="footer-inner">
          {/* Left: controls */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button onClick={handleRun} className="btn-small" title="Run (live)">Run</button>
            <button onClick={handleReplay} className="btn-small" title="Replay (by date)">Replay</button>
            <button onClick={handleStop} className="btn-small" style={{ background: '#c9c1b7', color: '#1a1a1a' }}>Stop</button>
          </div>

          {/* Right: date selector + realtime clock */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <label htmlFor="replay-date">Date:</label>
            <input
              id="replay-date"
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
            />
            <div>|</div>
            <div>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ====== Helpers ======
function useImage(src) {
  const [img, setImg] = useState(null);
  useEffect(() => {
    if (!src) return;
    const i = new Image();
    i.src = src;
    i.onload = () => setImg(i);
  }, [src]);
  return img;
}

function useResizeScale(containerRef, native) {
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const onResize = () => {
      const el = containerRef.current;
      if (!el) return;
      const w = el.clientWidth;
      const h = el.clientHeight;
      const sx = w / native.width;
      const sy = h / native.height;
      setScale(Math.min(sx, sy));
    };
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [containerRef, native.width, native.height]);
  return scale;
}

// ====== Pixel Chart (Canvas) ======
function PixelChart({ data }) {
  const ref = useRef(null);
  useEffect(() => {
    const cnv = ref.current; if (!cnv) return; const ctx = cnv.getContext('2d');
    const parent = cnv.parentElement;
    const W = parent.clientWidth - 16, H = 140; cnv.width = W; cnv.height = H; cnv.style.width = W + 'px'; cnv.style.height = H + 'px';
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#e6eef9'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#c9d6ea'; ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 8) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 8) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    const min = Math.min(...data), max = Math.max(...data);
    ctx.strokeStyle = '#23d160'; ctx.lineWidth = 1; ctx.beginPath();
    data.forEach((p, i) => {
      const x = Math.round((i / (data.length - 1)) * (W - 2) + 1);
      const y = Math.round((1 - (p - min) / ((max - min) || 1)) * (H - 2) + 1);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
  }, [data]);
  return <canvas ref={ref} className="chart" />;
}

function seedPrices() {
  const arr = []; let p = 100;
  for (let i = 0; i < 60; i++) { p += (Math.random() - 0.45) * 2; arr.push(Math.max(50, p)); }
  return arr;
}