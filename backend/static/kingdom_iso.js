/**
 * Kingdom ISO — Isometric pixel-art game map for the Kingdom AI dashboard.
 * Renders 6 venture buildings in isometric 3-D with animated agent sprites,
 * speech bubbles, CRT scanlines, and a live revenue/agent HUD.
 */
var KingdomISO = (function () {
  'use strict';

  // ── Isometric constants ────────────────────────────────────────────────────
  const TW = 64;           // tile width  (diamond)
  const TH = 32;           // tile height (diamond)
  const BH = 48;           // building wall height in pixels
  const GRID_COLS = 11;
  const GRID_ROWS = 8;

  // ── Project grid → screen ─────────────────────────────────────────────────
  function iso(col, row) {
    return {
      x: (col - row) * (TW / 2),
      y: (col + row) * (TH / 2),
    };
  }

  // ── Building definitions ───────────────────────────────────────────────────
  const BUILDINGS = [
    { id: 'pitwall',    label: 'PITWALL',      col: 1, row: 1, cols: 2, rows: 2, color: '#ffb300', glow: 'rgba(255,179,0,0.4)',   tab: 'pitwall',    icon: '🏎' },
    { id: 'pulsebreak', label: 'PULSEBREAK',   col: 5, row: 0, cols: 2, rows: 2, color: '#c084fc', glow: 'rgba(192,132,252,0.4)', tab: 'pulsebreak', icon: '🎵' },
    { id: 'command',    label: 'COMMAND',       col: 8, row: 2, cols: 2, rows: 2, color: '#00e5ff', glow: 'rgba(0,229,255,0.4)',   tab: 'command',    icon: '⚔️' },
    { id: 'printforge', label: 'PRINT FORGE',  col: 0, row: 4, cols: 2, rows: 2, color: '#fb923c', glow: 'rgba(251,146,60,0.4)', tab: 'pitwall',    icon: '🖨' },
    { id: 'treasury',   label: 'TREASURY',     col: 4, row: 5, cols: 2, rows: 2, color: '#00ff88', glow: 'rgba(0,255,136,0.4)',  tab: 'overview',   icon: '💰' },
    { id: 'livery',     label: 'LIVERY FORGE', col: 8, row: 5, cols: 2, rows: 2, color: '#ff3366', glow: 'rgba(255,51,102,0.4)', tab: 'livery',     icon: '🏁' },
  ];

  // ── Agent types ────────────────────────────────────────────────────────────
  const AGENT_TYPES = [
    { color: '#00e5ff', name: 'Scout' },
    { color: '#ffb300', name: 'Forge' },
    { color: '#c084fc', name: 'Vibes' },
    { color: '#00ff88', name: 'Trade' },
  ];

  // ── Speech-bubble messages ─────────────────────────────────────────────────
  const MESSAGES = [
    'Opportunity found!', 'Revenue +£12', 'Concept ready!',
    'Listing drafted',   'Track analysed', 'Score: 8.5/10',
    'Running scan…',     'Pattern match!', 'Art generated',
    'Queue updated',     'Brief complete', 'Insight logged',
    'Brief drafted',     'API call ✓',     'Task complete',
  ];

  // ── State ──────────────────────────────────────────────────────────────────
  let canvas, ctx;
  let animFrame = null;
  let tick = 0;
  let agents = [];
  let bubbles = [];
  let stars = null;
  let activeAgentData = [];
  let revenueToday = '—';

  // ── Helpers ────────────────────────────────────────────────────────────────
  function shadeColor(hex, amount) {
    const parse = (s, i) => Math.max(0, Math.min(255, parseInt(s.slice(i, i + 2), 16) + amount));
    return `rgb(${parse(hex, 1)},${parse(hex, 3)},${parse(hex, 5)})`;
  }

  function lerpPt(a, b, t) {
    return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
  }

  function roundRect(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y);
    c.lineTo(x + w - r, y);
    c.quadraticCurveTo(x + w, y, x + w, y + r);
    c.lineTo(x + w, y + h - r);
    c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    c.lineTo(x + r, y + h);
    c.quadraticCurveTo(x, y + h, x, y + h - r);
    c.lineTo(x, y + r);
    c.quadraticCurveTo(x, y, x + r, y);
    c.closePath();
  }

  // ── Canvas sizing ──────────────────────────────────────────────────────────
  function getSize() {
    return {
      w: parseInt(canvas.style.width)  || canvas.parentElement.clientWidth,
      h: parseInt(canvas.style.height) || 420,
    };
  }

  function getOffset() {
    const { w } = getSize();
    return { x: w / 2, y: 65 };
  }

  function resize() {
    const parent = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const w = parent.clientWidth;
    const h = w < 480 ? 280 : 420;
    canvas.width  = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width  = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(dpr, dpr);
    stars = null; // regenerate stars for new size
  }

  // ── Building geometry helpers ──────────────────────────────────────────────
  function buildingCorners(b) {
    return {
      tl: iso(b.col,          b.row),
      tr: iso(b.col + b.cols, b.row),
      br: iso(b.col + b.cols, b.row + b.rows),
      bl: iso(b.col,          b.row + b.rows),
    };
  }

  function getBuildingCenter(b) {
    const off = getOffset();
    const c = buildingCorners(b);
    // Average the four base corners for x; use top-left y minus half wall
    const cx = off.x + (c.tl.x + c.tr.x + c.bl.x + c.br.x) / 4;
    const cy = off.y + (c.tl.y + c.tr.y) / 2 - BH;
    return { x: cx, y: cy };
  }

  // ── Stars ──────────────────────────────────────────────────────────────────
  function ensureStars() {
    const { w } = getSize();
    if (!stars) {
      stars = Array.from({ length: 70 }, () => ({
        x: Math.random(),   // 0-1 fractional, scaled to w
        y: Math.random() * 90,
        r: 0.4 + Math.random() * 1.2,
        phase: Math.random() * Math.PI * 2,
      }));
    }
  }

  function drawStars() {
    ensureStars();
    const { w } = getSize();
    stars.forEach(s => {
      const alpha = 0.25 + 0.45 * Math.sin(tick * 0.03 + s.phase);
      ctx.fillStyle = `rgba(255,255,255,${alpha.toFixed(3)})`;
      ctx.beginPath();
      ctx.arc(s.x * w, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // ── Ground grid ────────────────────────────────────────────────────────────
  function drawGround() {
    const off = getOffset();
    for (let c = 0; c <= GRID_COLS; c++) {
      for (let r = 0; r <= GRID_ROWS; r++) {
        const p = iso(c, r);
        const x = off.x + p.x;
        const y = off.y + p.y;
        ctx.beginPath();
        ctx.moveTo(x,          y - TH / 2);
        ctx.lineTo(x + TW / 2, y);
        ctx.lineTo(x,          y + TH / 2);
        ctx.lineTo(x - TW / 2, y);
        ctx.closePath();
        const even = (c + r) % 2 === 0;
        ctx.fillStyle = even ? 'rgba(255,255,255,0.018)' : 'rgba(0,229,255,0.012)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(0,229,255,0.055)';
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }
  }

  // ── Buildings ──────────────────────────────────────────────────────────────
  function drawBuilding(b) {
    const off = getOffset();
    const { tl, tr, br, bl } = buildingCorners(b);
    const ox = off.x, oy = off.y;

    const isActive = b.active;

    // Glow shadow
    if (isActive) {
      ctx.save();
      ctx.shadowColor = b.color;
      ctx.shadowBlur = 22 + 8 * Math.sin(tick * 0.06);
    }

    // LEFT face  (darkest)
    ctx.beginPath();
    ctx.moveTo(ox + bl.x, oy + bl.y);
    ctx.lineTo(ox + br.x, oy + br.y);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.fillStyle = shadeColor(b.color, -70);
    ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.4)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // RIGHT face (medium)
    ctx.beginPath();
    ctx.moveTo(ox + br.x, oy + br.y);
    ctx.lineTo(ox + tr.x, oy + tr.y);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.closePath();
    ctx.fillStyle = shadeColor(b.color, -35);
    ctx.fill();
    ctx.stroke();

    // TOP face (brightest, gradient)
    ctx.beginPath();
    ctx.moveTo(ox + tl.x, oy + tl.y - BH);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    const grd = ctx.createLinearGradient(
      ox + tl.x, oy + tl.y - BH,
      ox + br.x, oy + br.y - BH,
    );
    grd.addColorStop(0, shadeColor(b.color, 25));
    grd.addColorStop(1, shadeColor(b.color, -5));
    ctx.fillStyle = grd;
    ctx.fill();
    ctx.stroke();

    if (isActive) ctx.restore();

    // Windows on RIGHT face
    drawWindows(b, ox, oy, tr, br);

    // Label above building
    const center = getBuildingCenter(b);
    ctx.save();
    ctx.textAlign = 'center';
    // icon
    ctx.font = '15px serif';
    ctx.shadowColor = b.color;
    ctx.shadowBlur = 10;
    ctx.fillText(b.icon, center.x, center.y - 18);
    // text
    ctx.font = 'bold 7px "Press Start 2P", monospace';
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = b.color;
    ctx.shadowBlur = 12;
    ctx.fillText(b.label, center.x, center.y - 4);
    ctx.restore();
  }

  function drawWindows(b, ox, oy, tr, br) {
    const numW = b.cols;
    for (let i = 0; i < numW; i++) {
      const t = (i + 1) / (numW + 1);
      const wx = ox + tr.x + (br.x - tr.x) * t;
      const wy = oy + tr.y + (br.y - tr.y) * t - BH * 0.55;
      const blink = (tick + i * 37 + b.col * 13) % 120 < 85;
      ctx.fillStyle = blink ? 'rgba(0,229,255,0.85)' : 'rgba(0,229,255,0.18)';
      ctx.shadowColor = '#00e5ff';
      ctx.shadowBlur = blink ? 7 : 2;
      ctx.fillRect(wx - 4, wy - 7, 8, 11);
      ctx.shadowBlur = 0;
    }
  }

  // ── Agent sprites ──────────────────────────────────────────────────────────
  function drawAgent(agent) {
    const { x, y, type } = agent;
    const S = 5; // sprite size unit

    ctx.save();
    ctx.shadowColor = type.color;
    ctx.shadowBlur = 10;

    // Legs (animated walk cycle)
    const walk = Math.sin(tick * 0.22 + agent.id * 1.3) * 2.5;
    ctx.fillStyle = shadeColor(type.color, -25);
    ctx.fillRect(x - S / 2,       y - S,     S / 2, S + walk);
    ctx.fillRect(x,                y - S,     S / 2, S - walk);

    // Body
    ctx.fillStyle = type.color;
    ctx.fillRect(x - S / 2, y - S * 2.8, S, S * 1.6);

    // Head
    ctx.fillStyle = shadeColor(type.color, 40);
    ctx.fillRect(x - S / 2, y - S * 3.9, S, S * 1.1);

    ctx.restore();

    // Name tag
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.65)';
    ctx.fillRect(x - 18, y - S * 4 - 13, 36, 11);
    ctx.fillStyle = type.color;
    ctx.font = '6px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(type.name, x, y - S * 4 - 4);
    ctx.restore();
  }

  // ── Speech bubbles ─────────────────────────────────────────────────────────
  function drawBubble(bubble) {
    const { x, y, text, life, maxLife } = bubble;
    const fadeIn  = Math.min(1, life / 15);
    const fadeOut = Math.min(1, (maxLife - life) / 15);  // fade out at end... wait, life counts DOWN
    // life goes from maxLife → 0
    const progress = 1 - life / maxLife;  // 0 → 1 as bubble ages
    const fadeAlpha = Math.min(progress * 5, 1) * Math.min((1 - progress) * 5, 1);
    const dy = -progress * 18; // float upward

    ctx.save();
    ctx.globalAlpha = Math.max(0, fadeAlpha);
    ctx.font = '7px "JetBrains Mono", monospace';
    const tw = ctx.measureText(text).width;
    const bw = tw + 18;
    const bh = 18;
    const bx = x - bw / 2;
    const by = y - 52 + dy;

    roundRect(ctx, bx, by, bw, bh, 4);
    ctx.fillStyle = 'rgba(3,4,16,0.92)';
    ctx.fill();
    ctx.strokeStyle = '#00e5ff';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Tail
    ctx.beginPath();
    ctx.moveTo(x - 4, by + bh);
    ctx.lineTo(x + 4, by + bh);
    ctx.lineTo(x, by + bh + 5);
    ctx.closePath();
    ctx.fillStyle = 'rgba(3,4,16,0.92)';
    ctx.fill();
    ctx.strokeStyle = '#00e5ff';
    ctx.stroke();

    ctx.fillStyle = '#00e5ff';
    ctx.textAlign = 'center';
    ctx.fillText(text, x, by + 12);

    ctx.restore();
  }

  // ── Scanlines + vignette ───────────────────────────────────────────────────
  function drawCRT() {
    const { w, h } = getSize();
    // Scanlines
    ctx.save();
    for (let yy = 0; yy < h; yy += 3) {
      ctx.fillStyle = 'rgba(0,0,0,0.07)';
      ctx.fillRect(0, yy, w, 1);
    }
    // Vignette
    const vg = ctx.createRadialGradient(w / 2, h / 2, h * 0.25, w / 2, h / 2, h * 0.85);
    vg.addColorStop(0, 'rgba(0,0,0,0)');
    vg.addColorStop(1, 'rgba(0,0,0,0.45)');
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  // ── HUD overlay ────────────────────────────────────────────────────────────
  function drawHUD() {
    const { w } = getSize();
    const activeCount = agents.filter(a => a.active).length;

    ctx.save();
    ctx.font = '7px "Press Start 2P", monospace';

    // Left: title
    ctx.fillStyle = 'rgba(0,229,255,0.7)';
    ctx.textAlign = 'left';
    ctx.fillText('KINGDOM OS v2.0', 12, 18);

    // Right: agent count
    ctx.fillStyle = '#00ff88';
    ctx.textAlign = 'right';
    ctx.fillText(`AGENTS: ${activeCount}/${agents.length}`, w - 12, 18);

    // Revenue ticker bottom-left
    ctx.font = '7px "Press Start 2P", monospace';
    ctx.fillStyle = '#ffb300';
    ctx.textAlign = 'left';
    ctx.fillText(`REV TODAY: ${revenueToday}`, 12, parseInt(canvas.style.height) - 12);

    ctx.restore();
  }

  // ── Agent logic ────────────────────────────────────────────────────────────
  function spawnAgents() {
    agents = [];
    for (let i = 0; i < 8; i++) {
      const type = AGENT_TYPES[i % AGENT_TYPES.length];
      const from = BUILDINGS[i % BUILDINGS.length];
      const to   = BUILDINGS[(i + 2) % BUILDINGS.length];
      agents.push({
        id: i,
        type,
        x: 0, y: 0,
        fromBuilding: from,
        toBuilding: to,
        progress: Math.random(),
        speed: 0.0018 + Math.random() * 0.0022,
        active: true,
        bubbleTimer: Math.floor(Math.random() * 200),
        nextBubble: 180 + Math.floor(Math.random() * 350),
      });
    }
  }

  function updateAgents() {
    agents.forEach(agent => {
      agent.progress += agent.speed;

      if (agent.progress >= 1) {
        agent.progress = 0;
        agent.fromBuilding = agent.toBuilding;
        const others = BUILDINGS.filter(b => b.id !== agent.fromBuilding.id);
        agent.toBuilding = others[Math.floor(Math.random() * others.length)];
        // Immediately pop a bubble on arrival
        agent.bubbleTimer = agent.nextBubble;
      }

      const from = getBuildingCenter(agent.fromBuilding);
      const to   = getBuildingCenter(agent.toBuilding);
      const pos  = lerpPt(from, to, agent.progress);
      agent.x = pos.x;
      agent.y = pos.y;

      // Speech bubble
      agent.bubbleTimer++;
      if (agent.bubbleTimer >= agent.nextBubble &&
          !bubbles.some(b => b.agentId === agent.id)) {
        const msg = MESSAGES[Math.floor(Math.random() * MESSAGES.length)];
        bubbles.push({
          agentId: agent.id,
          x: agent.x, y: agent.y,
          text: msg,
          life: 90,
          maxLife: 90,
        });
        agent.bubbleTimer = 0;
        agent.nextBubble = 160 + Math.floor(Math.random() * 320);
      }
    });

    bubbles = bubbles.filter(b => {
      b.life--;
      const a = agents.find(a => a.id === b.agentId);
      if (a) { b.x = a.x; b.y = a.y; }
      return b.life > 0;
    });
  }

  // ── Data fetch ─────────────────────────────────────────────────────────────
  async function fetchData() {
    try {
      const r = await fetch('/scheduler/status');
      const d = await r.json();
      activeAgentData = d.jobs || [];
    } catch (_) {}

    try {
      const r = await fetch('/api/overview');
      const d = await r.json();
      revenueToday = d.revenue_today != null ? `£${d.revenue_today.toFixed(0)}` : '—';
    } catch (_) {}
  }

  // ── Main render loop ───────────────────────────────────────────────────────
  function loop() {
    tick++;
    const { w, h } = getSize();

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = '#030410';
    ctx.fillRect(0, 0, w, h);

    // Stars
    drawStars();

    // Ground
    drawGround();

    // Mark active buildings
    BUILDINGS.forEach(b => {
      b.active = activeAgentData.some(j => j.status === 'running');
    });

    // Draw buildings back→front (lower col+row = further back in iso view)
    const sorted = [...BUILDINGS].sort((a, b) => (a.col + a.row) - (b.col + b.row));
    sorted.forEach(b => drawBuilding(b));

    // Agents sorted by y (painter's algorithm)
    [...agents].sort((a, b) => a.y - b.y).forEach(a => drawAgent(a));

    // Bubbles
    bubbles.forEach(b => drawBubble(b));

    // CRT effects
    drawCRT();

    // HUD
    drawHUD();

    // Update state
    updateAgents();

    animFrame = requestAnimationFrame(loop);
  }

  // ── Click handler ──────────────────────────────────────────────────────────
  function handleClick(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    for (const b of BUILDINGS) {
      const center = getBuildingCenter(b);
      const dx = mx - center.x;
      const dy = my - center.y;
      if (Math.abs(dx) < 55 && Math.abs(dy) < 45) {
        if (b.tab && typeof showTab === 'function') {
          showTab(b.tab);
        }
        return;
      }
    }
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  function init(canvasEl) {
    canvas = canvasEl;
    ctx = canvas.getContext('2d');

    resize();
    spawnAgents();
    loop();

    fetchData();
    setInterval(fetchData, 30000);

    canvas.addEventListener('click', handleClick);
    window.addEventListener('resize', () => {
      resize();
      stars = null;
    });
  }

  function destroy() {
    if (animFrame) cancelAnimationFrame(animFrame);
    window.removeEventListener('resize', resize);
  }

  return { init, destroy };
})();
