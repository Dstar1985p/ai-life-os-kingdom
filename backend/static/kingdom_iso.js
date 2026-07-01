/**
 * Kingdom ISO — Isometric cyberpunk neon city map for the Kingdom AI dashboard.
 * Renders 6 venture buildings in isometric 3-D with animated agent orbs,
 * speech bubbles, CRT scanlines, particle bursts, footprints, and energy beams.
 */
var KingdomISO = (function () {
  'use strict';

  // ── Isometric constants ────────────────────────────────────────────────────
  const TW = 56;           // tile width  (diamond)
  const TH = 28;           // tile height (diamond)
  const BH = 72;           // building wall height in pixels
  const GRID_COLS = 8;
  const GRID_ROWS = 6;

  // ── Project grid → screen ─────────────────────────────────────────────────
  function iso(col, row) {
    return {
      x: (col - row) * (TW / 2),
      y: (col + row) * (TH / 2),
    };
  }

  // ── Building definitions — 3×2 compact grid ───────────────────────────────
  const BUILDINGS = [
    { id: 'pitwall',    label: 'PIT GARAGE',   col: 0, row: 0, cols: 2, rows: 2, color: '#ff9500', glow: 'rgba(255,149,0,0.6)',   tab: 'pitwall',    icon: '🏎' },
    { id: 'pulsebreak', label: 'THE CLUB',      col: 3, row: 0, cols: 2, rows: 2, color: '#bf5fff', glow: 'rgba(191,95,255,0.6)',  tab: 'pulsebreak', icon: '🎵' },
    { id: 'command',    label: 'COMMAND HQ',   col: 6, row: 0, cols: 2, rows: 2, color: '#00f0ff', glow: 'rgba(0,240,255,0.6)',   tab: 'command',    icon: '⚔️' },
    { id: 'printforge', label: 'PRINT FORGE',  col: 0, row: 3, cols: 2, rows: 2, color: '#ff7020', glow: 'rgba(255,112,32,0.6)',  tab: 'pitwall',    icon: '🖨' },
    { id: 'treasury',   label: 'THE BANK',     col: 3, row: 3, cols: 2, rows: 2, color: '#00ff66', glow: 'rgba(0,255,102,0.6)',   tab: 'overview',   icon: '💰' },
    { id: 'livery',     label: 'WORKSHOP',     col: 6, row: 3, cols: 2, rows: 2, color: '#ff1a4a', glow: 'rgba(255,26,74,0.6)',   tab: 'livery',     icon: '🏁' },
  ];

  // ── Agent → Building mapping (mirrors backend) ────────────────────────────
  const AGENT_TO_BUILDING = {
    'Vibes AI': 'pulsebreak', 'Music Licensing': 'pulsebreak', 'Content Agent': 'pulsebreak',
    'Print Forge AI': 'printforge', 'Printify Studio': 'printforge',
    'Price Optimizer': 'pitwall', 'SEO Agent': 'pitwall', 'Etsy Scout': 'pitwall',
    'Opportunity Scout': 'command', 'AI Engineer': 'command', 'Market Scout': 'command',
    'Treasury Agent': 'treasury',
  };

  // ── Agent types ────────────────────────────────────────────────────────────
  const AGENT_TYPES = [
    { color: '#ff9500', name: 'Driver'    },  // 0 Pitwall — Racing Driver
    { color: '#bf5fff', name: 'DJ'        },  // 1 PulseBreak — DJ
    { color: '#00f0ff', name: 'Commander' },  // 2 Command — Commander
    { color: '#ff7020', name: 'Forger'    },  // 3 PrintForge — Forge Worker
    { color: '#00ff66', name: 'Merchant'  },  // 4 Treasury — Merchant
    { color: '#ff1a4a', name: 'Engineer'  },  // 5 Livery — Race Engineer
  ];

  // ── Speech-bubble messages ─────────────────────────────────────────────────
  const MESSAGES = [
    'Opportunity found!', 'Revenue +£12', 'Concept ready!',
    'Listing drafted',    'Track analysed', 'Score: 8.5/10',
    'Running scan…',      'Pattern match!', 'Art generated',
    'Queue updated',      'Brief complete', 'Insight logged',
    'Brief drafted',      'API call ✓',     'Task complete',
  ];

  // ── State ──────────────────────────────────────────────────────────────────
  let canvas, ctx;
  let animFrame = null;
  let tick = 0;
  let agents = [];
  let bubbles = [];
  let particles = [];     // burst particles
  let ambientParticles = []; // ambient per-building particles
  let stars = null;
  let activeAgentData = [];
  let revenueToday = '—';
  let _buildingStates = {};  // building_id → {status, running_agent, last_action, pending_count, activity_level}
  let _liveBubbles   = [];   // {buildingId, text, color, life, maxLife}

  // ── Helpers ────────────────────────────────────────────────────────────────
  function shadeColor(hex, amount) {
    const parse = (s, i) => Math.max(0, Math.min(255, parseInt(s.slice(i, i + 2), 16) + amount));
    return `rgb(${parse(hex, 1)},${parse(hex, 3)},${parse(hex, 5)})`;
  }

  function lerpPt(a, b, t) {
    return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
  }

  function hexToRgb(hex) {
    return {
      r: parseInt(hex.slice(1, 3), 16),
      g: parseInt(hex.slice(3, 5), 16),
      b: parseInt(hex.slice(5, 7), 16),
    };
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
      w: canvas.clientWidth  || canvas.offsetWidth  || 800,
      h: canvas.clientHeight || canvas.offsetHeight || 600,
    };
  }

  function getScale() {
    const { w, h } = getSize();
    const mapW = (GRID_COLS + GRID_ROWS) * (TW / 2);
    const mapH = (GRID_COLS + GRID_ROWS) * (TH / 2) + BH * 2;
    const usableH = h - 60; // HUD bar at bottom
    const scaleX = (w * 0.94) / mapW;
    const scaleY = (usableH * 0.82) / mapH;
    return Math.min(scaleX, scaleY, 2.4);
  }

  function getOffset() {
    const { w, h } = getSize();
    const s = getScale();
    const mapH = ((GRID_COLS + GRID_ROWS) * (TH / 2) + BH * 2) * s;
    const topPad  = h * 0.13;
    const botPad  = 56;
    const usableH = h - topPad - botPad;
    const y = topPad + (usableH - mapH) / 2 + BH * s;
    return { x: w / 2, y: Math.max(y, topPad + 10) };
  }

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const parent = canvas.parentElement;
    const w = parent ? parent.clientWidth  : window.innerWidth;
    const h = parent ? parent.clientHeight : window.innerHeight;
    canvas.width  = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width  = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(dpr, dpr);
    stars = null;
    shootingStars = null;
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
    const cx = off.x + (c.tl.x + c.tr.x + c.bl.x + c.br.x) / 4;
    const cy = off.y + (c.tl.y + c.tr.y) / 2 - BH;
    return { x: cx, y: cy };
  }

  // ── Stars / shooting stars ─────────────────────────────────────────────────
  let shootingStars = null;

  // ── Background — deep space nebula ─────────────────────────────────────────
  function drawBackground() {
    const { w, h } = getSize();

    // Deep space gradient
    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0,   '#000008');
    bg.addColorStop(0.4, '#050018');
    bg.addColorStop(0.7, '#080028');
    bg.addColorStop(1,   '#020010');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    // Nebula clouds
    const nebulas = [
      { x: 0.15, y: 0.2,  r: w * 0.35, c1: 'rgba(120,0,255,0.06)'  },
      { x: 0.8,  y: 0.15, r: w * 0.3,  c1: 'rgba(0,80,255,0.07)'   },
      { x: 0.5,  y: 0.35, r: w * 0.4,  c1: 'rgba(0,200,255,0.04)'  },
      { x: 0.3,  y: 0.5,  r: w * 0.25, c1: 'rgba(180,0,180,0.05)'  },
    ];
    nebulas.forEach(n => {
      const g = ctx.createRadialGradient(n.x * w, n.y * h, 0, n.x * w, n.y * h, n.r);
      g.addColorStop(0, n.c1);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    });

    // Aurora band across horizon
    const off = getOffset();
    const horizonY = off.y + 20;
    const aurora = ctx.createLinearGradient(0, horizonY - 30, 0, horizonY + 60);
    aurora.addColorStop(0,   'rgba(0,255,200,0)');
    aurora.addColorStop(0.3, 'rgba(0,200,255,0.06)');
    aurora.addColorStop(0.5, 'rgba(100,0,255,0.04)');
    aurora.addColorStop(1,   'rgba(0,0,0,0)');
    ctx.fillStyle = aurora;
    ctx.fillRect(0, horizonY - 30, w, 90);

    // Stars
    if (!stars) {
      stars = Array.from({ length: 200 }, () => ({
        x: Math.random(),
        y: Math.random() * 0.5,
        r: 0.3 + Math.random() * 1.8,
        phase: Math.random() * Math.PI * 2,
        colorType: Math.floor(Math.random() * 3), // 0=white, 1=blue, 2=purple
      }));
    }
    stars.forEach(s => {
      const a = 0.4 + 0.5 * Math.sin(tick * 0.02 + s.phase);
      ctx.globalAlpha = a;
      if (s.colorType === 1)      ctx.fillStyle = '#aaf';
      else if (s.colorType === 2) ctx.fillStyle = '#faf';
      else                        ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(s.x * w, s.y * h, s.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    });

    // Shooting stars
    if (!shootingStars) {
      shootingStars = Array.from({ length: 5 }, (_, i) => ({
        phase: i * (1800 / 5),
        period: 1800,
        y: 0.05 + Math.random() * 0.3,
        angle: 0.3 + Math.random() * 0.3,
      }));
    }
    shootingStars.forEach(ss => {
      const t = ((tick + ss.phase) % ss.period) / ss.period;
      if (t > 0.12) return;
      const progress = t / 0.12;
      const tailLen = 120;
      const sx = progress * (w + tailLen);
      const sy = ss.y * h + sx * Math.tan(ss.angle);
      const ex = sx - tailLen;
      const ey = sy - tailLen * Math.tan(ss.angle);
      const alpha = Math.min(progress * 5, 1) * (1 - progress);
      const grad = ctx.createLinearGradient(ex, ey, sx, sy);
      grad.addColorStop(0, 'rgba(255,255,255,0)');
      grad.addColorStop(1, `rgba(255,255,255,${alpha.toFixed(3)})`);
      ctx.save();
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(ex, ey);
      ctx.lineTo(sx, sy);
      ctx.stroke();
      ctx.restore();
    });
  }

  // ── Ground grid — neon cyberpunk ───────────────────────────────────────────
  function drawGround() {
    const off = getOffset();

    // Vertical iso lines (constant col)
    for (let c = 0; c <= GRID_COLS; c++) {
      const isMajor = c % 3 === 0;
      ctx.beginPath();
      const s = iso(c, 0), e = iso(c, GRID_ROWS);
      ctx.moveTo(off.x + s.x, off.y + s.y);
      ctx.lineTo(off.x + e.x, off.y + e.y);
      ctx.strokeStyle = isMajor ? 'rgba(0,229,255,0.2)' : 'rgba(0,229,255,0.07)';
      ctx.lineWidth = isMajor ? 0.8 : 0.4;
      ctx.stroke();
    }

    // Horizontal iso lines (constant row)
    for (let r = 0; r <= GRID_ROWS; r++) {
      const isMajor = r % 3 === 0;
      ctx.beginPath();
      const s = iso(0, r), e = iso(GRID_COLS, r);
      ctx.moveTo(off.x + s.x, off.y + s.y);
      ctx.lineTo(off.x + e.x, off.y + e.y);
      ctx.strokeStyle = isMajor ? 'rgba(0,229,255,0.2)' : 'rgba(0,229,255,0.07)';
      ctx.lineWidth = isMajor ? 0.8 : 0.4;
      ctx.stroke();
    }

    // Pulsing intersection dots
    for (let c = 0; c <= GRID_COLS; c += 2) {
      for (let r = 0; r <= GRID_ROWS; r += 2) {
        const p = iso(c, r);
        const alpha = 0.15 + 0.1 * Math.sin(tick * 0.04 + c + r);
        ctx.fillStyle = `rgba(0,229,255,${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(off.x + p.x, off.y + p.y, 1.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Scanning line — sweeps across grid every 5 seconds
    const scanT = (tick % 300) / 300;
    const scanC = Math.floor(scanT * GRID_COLS);
    if (scanC < GRID_COLS) {
      const s = iso(scanC, 0), e = iso(scanC, GRID_ROWS);
      ctx.save();
      ctx.strokeStyle = 'rgba(0,229,255,0.5)';
      ctx.lineWidth = 1.5;
      ctx.shadowColor = '#00e5ff';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(off.x + s.x, off.y + s.y);
      ctx.lineTo(off.x + e.x, off.y + e.y);
      ctx.stroke();
      ctx.restore();
    }
  }

  // ── Energy beams between buildings ────────────────────────────────────────
  function drawEnergyBeams() {
    const CONNECTIONS = [
      ['pitwall', 'printforge'],
      ['pitwall', 'treasury'],
      ['pulsebreak', 'command'],
      ['treasury', 'livery'],
      ['command', 'livery'],
    ];

    CONNECTIONS.forEach(([aId, bId], idx) => {
      const bA = BUILDINGS.find(b => b.id === aId);
      const bB = BUILDINGS.find(b => b.id === bId);
      if (!bA || !bB) return;
      const cA = getBuildingCenter(bA);
      const cB = getBuildingCenter(bB);

      // Place beams at ground level (below buildings)
      const gA = { x: cA.x, y: cA.y + BH };
      const gB = { x: cB.x, y: cB.y + BH };

      const rA = parseInt(bA.color.slice(1, 3), 16);
      const gvA = parseInt(bA.color.slice(3, 5), 16);
      const bvA = parseInt(bA.color.slice(5, 7), 16);
      const rB = parseInt(bB.color.slice(1, 3), 16);
      const gvB = parseInt(bB.color.slice(3, 5), 16);
      const bvB = parseInt(bB.color.slice(5, 7), 16);

      ctx.save();

      // Beam line with gradient
      const beamGrad = ctx.createLinearGradient(gA.x, gA.y, gB.x, gB.y);
      beamGrad.addColorStop(0,   `rgba(${rA},${gvA},${bvA},0.5)`);
      beamGrad.addColorStop(0.5, `rgba(${rA},${gvA},${bvA},0.1)`);
      beamGrad.addColorStop(1,   `rgba(${rB},${gvB},${bvB},0.5)`);
      ctx.strokeStyle = beamGrad;
      ctx.lineWidth = 0.8;
      ctx.shadowColor = bA.color;
      ctx.shadowBlur = 4;
      ctx.setLineDash([4, 8]);
      ctx.lineDashOffset = -(tick * 1.5) % 12;
      ctx.beginPath();
      ctx.moveTo(gA.x, gA.y);
      ctx.lineTo(gB.x, gB.y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Data packet travelling along beam
      const t = ((tick * 0.01) + idx * 0.2) % 1;
      const px = gA.x + (gB.x - gA.x) * t;
      const py = gA.y + (gB.y - gA.y) * t;
      ctx.shadowColor = bA.color;
      ctx.shadowBlur = 10;
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(px, py, 2.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    });
  }

  // ── Holographic data panel above active building ───────────────────────────
  function drawHologram(b, ox, oy) {
    const { tl, tr } = buildingCorners(b);
    const cx = ox + (tl.x + tr.x) / 2;
    const cy = oy + tl.y - BH - 30;
    const pulse = 0.6 + 0.4 * Math.sin(tick * 0.08);
    const { r, g, b: bv } = hexToRgb(b.color);

    ctx.save();
    ctx.globalAlpha = pulse * 0.85;

    // Panel background
    const pw = 64, ph = 28;
    roundRect(ctx, cx - pw / 2, cy - ph / 2, pw, ph, 4);
    ctx.fillStyle = `rgba(${Math.floor(r * 0.1)},${Math.floor(g * 0.1)},${Math.floor(bv * 0.1)},0.9)`;
    ctx.fill();
    ctx.strokeStyle = b.color;
    ctx.lineWidth = 0.8;
    ctx.shadowColor = b.color;
    ctx.shadowBlur = 8;
    ctx.stroke();

    // Panel content
    ctx.shadowBlur = 0;
    ctx.font = '5px "Press Start 2P", monospace';
    ctx.fillStyle = b.color;
    ctx.textAlign = 'center';
    ctx.fillText(b.label, cx, cy - 6);
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.font = '5px monospace';
    ctx.fillText('● ACTIVE', cx, cy + 4);

    // Connector line from panel to building
    ctx.strokeStyle = `rgba(${r},${g},${bv},0.4)`;
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.moveTo(cx, cy + ph / 2);
    ctx.lineTo(cx, oy + tl.y - BH);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.restore();
  }

  // ── Per-building themed roof decorations ──────────────────────────────────
  function drawBuildingSign(b, ox, oy) {
    const { tl, tr, bl, br } = buildingCorners(b);
    const cx = ox + (tl.x + tr.x + bl.x + br.x) / 4;
    const cy = oy + (tl.y + tr.y + bl.y + br.y) / 4 - BH;
    const { r, g, bv: bvx } = { r: parseInt(b.color.slice(1,3),16), g: parseInt(b.color.slice(3,5),16), bv: parseInt(b.color.slice(5,7),16) };

    ctx.save();
    ctx.shadowColor = b.color;

    if (b.id === 'pulsebreak') {
      // Disco ball on roof
      const blink = 0.5 + 0.5 * Math.sin(tick * 0.25);
      ctx.shadowBlur = 18 * blink;
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(cx, cy - 6, 5, 0, Math.PI * 2);
      ctx.fill();
      // rotating coloured light rays
      for (let i = 0; i < 6; i++) {
        const a = (tick * 0.08) + (i * Math.PI / 3);
        const hues = ['#ff00ff','#00ffff','#ffff00','#ff4488','#00ff88','#ff8800'];
        ctx.strokeStyle = hues[i];
        ctx.globalAlpha = 0.7;
        ctx.lineWidth = 1.5;
        ctx.shadowColor = hues[i];
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.moveTo(cx, cy - 6);
        ctx.lineTo(cx + Math.cos(a) * 18, cy - 6 + Math.sin(a) * 9);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      // Neon club sign on face
      ctx.font = 'bold 5px "Press Start 2P", monospace';
      ctx.fillStyle = '#ff00ff';
      ctx.shadowColor = '#ff00ff';
      ctx.shadowBlur = 10 + 6 * blink;
      ctx.textAlign = 'center';
      ctx.fillText('CLUB', cx + 16, cy + 18);

    } else if (b.id === 'treasury') {
      // Bank pillars on left face
      const faceL = ox + (bl.x + br.x) / 2 - 12;
      const faceR = ox + (bl.x + br.x) / 2 + 12;
      const faceBase = oy + (bl.y + br.y) / 2;
      ctx.strokeStyle = '#00ff66';
      ctx.lineWidth = 2;
      ctx.shadowBlur = 6;
      for (let pi = 0; pi < 3; pi++) {
        const px = faceL + pi * 12;
        ctx.beginPath();
        ctx.moveTo(px, faceBase);
        ctx.lineTo(px, faceBase - BH * 0.7);
        ctx.stroke();
      }
      // £ sign on roof
      ctx.font = 'bold 12px monospace';
      ctx.fillStyle = '#00ff66';
      ctx.shadowBlur = 14;
      ctx.textAlign = 'center';
      ctx.fillText('£', cx, cy - 2);
      // vault door glow pulse
      const vaultPulse = 0.6 + 0.4 * Math.sin(tick * 0.04);
      ctx.globalAlpha = vaultPulse;
      ctx.shadowColor = '#00ff66';
      ctx.shadowBlur = 20;
      ctx.strokeStyle = '#00ff66';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx + 14, cy + 14, 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;

    } else if (b.id === 'pitwall') {
      // Pit lane stripe + tyre stack
      ctx.fillStyle = '#ff9500';
      ctx.shadowBlur = 8;
      // Chequered roof edge
      for (let ci = 0; ci < 4; ci++) {
        ctx.fillStyle = (ci % 2 === 0) ? '#ff9500' : '#fff';
        ctx.fillRect(cx - 14 + ci * 7, cy - 14, 7, 5);
      }
      // Tyre stack on left face
      const tyreX = ox + bl.x + 8;
      const tyreY = oy + bl.y - BH * 0.3;
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 3;
      ctx.shadowBlur = 0;
      for (let ti = 0; ti < 2; ti++) {
        ctx.beginPath();
        ctx.arc(tyreX, tyreY + ti * 5, 3, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = '#222';
        ctx.fill();
      }

    } else if (b.id === 'command') {
      // Radar dish on roof
      const a = tick * 0.05;
      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.moveTo(cx, cy - 4);
      ctx.lineTo(cx, cy - 16);
      ctx.stroke();
      // rotating sweep
      ctx.beginPath();
      ctx.moveTo(cx, cy - 10);
      ctx.lineTo(cx + Math.cos(a) * 12, cy - 10 + Math.sin(a) * 6);
      ctx.strokeStyle = `rgba(0,240,255,0.9)`;
      ctx.stroke();
      // dish arc
      ctx.beginPath();
      ctx.arc(cx, cy - 16, 8, Math.PI * 0.8, Math.PI * 2.2);
      ctx.stroke();

    } else if (b.id === 'printforge') {
      // Chimneys on roof with smoke
      for (let chi = 0; chi < 2; chi++) {
        const chX = cx - 8 + chi * 16;
        ctx.fillStyle = '#ff7020';
        ctx.shadowBlur = 4;
        ctx.fillRect(chX - 3, cy - 14, 6, 10);
        // smoke puffs
        const sp = ((tick * 0.3 + chi * 15) % 15);
        ctx.globalAlpha = Math.max(0, 1 - sp / 15);
        ctx.fillStyle = 'rgba(180,180,180,0.5)';
        ctx.shadowBlur = 0;
        ctx.beginPath();
        ctx.arc(chX, cy - 14 - sp, 3 + sp * 0.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
      // Gear on right face
      const gearA = tick * 0.04;
      const gearX = ox + (tr.x + br.x) / 2 + 4;
      const gearY = oy + (tr.y + br.y) / 2 - BH * 0.5;
      ctx.save();
      ctx.translate(gearX, gearY);
      ctx.rotate(gearA);
      ctx.strokeStyle = '#ff7020';
      ctx.lineWidth = 1.5;
      ctx.shadowColor = '#ff7020';
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.arc(0, 0, 5, 0, Math.PI * 2);
      ctx.stroke();
      for (let ti = 0; ti < 6; ti++) {
        const ta = (ti / 6) * Math.PI * 2;
        ctx.beginPath();
        ctx.moveTo(Math.cos(ta) * 4, Math.sin(ta) * 4);
        ctx.lineTo(Math.cos(ta) * 7, Math.sin(ta) * 7);
        ctx.stroke();
      }
      ctx.restore();

    } else if (b.id === 'livery') {
      // Chequered flag on roof
      const flagWave = Math.sin(tick * 0.12) * 3;
      const fStartX = cx - 10;
      const fStartY = cy - 18;
      // pole
      ctx.strokeStyle = '#aaa';
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 0;
      ctx.beginPath();
      ctx.moveTo(fStartX, fStartY);
      ctx.lineTo(fStartX, fStartY + 16);
      ctx.stroke();
      // chequered squares
      for (let fi = 0; fi < 3; fi++) {
        for (let fj = 0; fj < 2; fj++) {
          ctx.fillStyle = ((fi + fj) % 2 === 0) ? '#fff' : '#111';
          const warp = Math.sin(tick * 0.1 + fi * 0.5) * 1.5;
          ctx.fillRect(fStartX + fi * 5, fStartY - 12 + fj * 5 + warp, 5, 5);
        }
      }
      // paint splash on right face
      const splatX = ox + (tr.x + br.x) / 2 + 2;
      const splatY = oy + (tr.y + br.y) / 2 - BH * 0.4;
      ctx.shadowColor = '#ff1a4a';
      ctx.shadowBlur = 8;
      ctx.fillStyle = '#ff1a4a';
      ctx.beginPath();
      ctx.arc(splatX, splatY, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(splatX + 6, splatY - 2, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Label below building (all buildings)
    ctx.shadowColor = b.color;
    ctx.shadowBlur = 8;
    ctx.font = '6px "Press Start 2P", monospace';
    ctx.fillStyle = b.color;
    ctx.textAlign = 'center';
    const lblY = oy + Math.max(bl.y, br.y) + 11;
    ctx.fillText(b.label, ox + (bl.x + br.x) / 2, lblY);
    ctx.restore();
  }

  // ── Building interior animated scenes ─────────────────────────────────────
  function drawBuildingInterior(b, ox, oy) {
    const { tr, br } = buildingCorners(b);

    // Clip to right face parallelogram
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y);
    ctx.lineTo(ox + tr.x, oy + tr.y);
    ctx.closePath();
    ctx.clip();

    // Dark interior fill
    ctx.fillStyle = 'rgba(5,0,15,0.88)';
    ctx.fillRect(ox + tr.x - 2, oy + tr.y - BH - 2, (br.x - tr.x) + 4, BH + 4);

    // Face center
    const cx = ox + (tr.x + br.x) / 2;
    const cy = oy + (tr.y + br.y) / 2 - BH / 2;

    const bst = _buildingStates[b.id] || {};
    const ts = bst.status === 'running' ? 2.4 : bst.status === 'recently_active' ? 1.4 : 1.0;
    const pose = bst.status === 'waiting' ? 'waiting' : bst.status === 'running' ? 'active' : 'idle';

    switch (b.id) {
      case 'pulsebreak': _interiorClub(cx, cy, ts, pose);    break;
      case 'pitwall':    _interiorGarage(cx, cy, ts, pose);  break;
      case 'command':    _interiorCommand(cx, cy, ts, pose); break;
      case 'printforge': _interiorForge(cx, cy, ts, pose);   break;
      case 'treasury':   _interiorBank(cx, cy, ts, pose);    break;
      case 'livery':     _interiorWorkshop(cx, cy, ts, pose); break;
    }

    ctx.restore();
  }

  // Interior: THE CLUB (pulsebreak)
  function _interiorClub(cx, cy, ts=1, pose='idle') {
    // Spotlight cones from ceiling
    const spotColors = ['rgba(160,0,255,0.18)', 'rgba(0,220,255,0.15)', 'rgba(255,0,200,0.15)'];
    const spotOffsets = [-18, 0, 18];
    spotOffsets.forEach((dx, i) => {
      const sway = Math.sin(tick * 0.02 * ts + i * 1.2) * 8;
      const sx = cx + dx + sway;
      const topY = cy - BH * 0.42;
      const botY = cy + BH * 0.3;
      const grad = ctx.createRadialGradient(sx, topY, 0, sx, botY, 22);
      grad.addColorStop(0, spotColors[i]);
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.beginPath();
      ctx.moveTo(sx, topY);
      ctx.lineTo(sx - 14, botY);
      ctx.lineTo(sx + 14, botY);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();
    });

    // Strobe flash
    if (Math.floor(tick * ts) % 180 < 3) {
      ctx.save();
      ctx.globalAlpha = 0.3;
      ctx.fillStyle = '#fff';
      ctx.fillRect(cx - 60, cy - 60, 120, 120);
      ctx.restore();
    }

    // EQ bars at bottom
    const eqY = cy + BH * 0.28;
    const eqColors = ['#bf5fff','#dd44ff','#ff00cc','#aa00ff','#ff44dd','#cc00ff','#e060ff'];
    for (let i = 0; i < 7; i++) {
      const bh2 = 8 + 10 * Math.abs(Math.sin(tick * 0.12 * ts + i * 0.9));
      ctx.fillStyle = eqColors[i % eqColors.length];
      ctx.globalAlpha = 0.85;
      ctx.fillRect(cx - 22 + i * 7, eqY - bh2, 5, bh2);
    }
    ctx.globalAlpha = 1;

    // Turntable decks
    const deckY = cy + 4;
    [-14, 14].forEach((dx, di) => {
      ctx.strokeStyle = '#666';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx + dx, deckY, 10, 0, Math.PI * 2);
      ctx.fillStyle = '#1a0030';
      ctx.fill();
      ctx.stroke();
      // Spinning crosshair
      const angle = tick * 0.06 * ts * (di === 0 ? 1 : -1);
      ctx.save();
      ctx.strokeStyle = '#bf5fff';
      ctx.lineWidth = 1;
      ctx.shadowColor = '#bf5fff';
      ctx.shadowBlur = 4;
      ctx.beginPath();
      ctx.moveTo(cx + dx + Math.cos(angle) * 9, deckY + Math.sin(angle) * 9);
      ctx.lineTo(cx + dx - Math.cos(angle) * 9, deckY - Math.sin(angle) * 9);
      ctx.stroke();
      ctx.restore();
    });

    // Mixer board
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(cx - 6, deckY - 6, 12, 10);
    for (let si = 0; si < 3; si++) {
      ctx.strokeStyle = '#888';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - 3 + si * 3, deckY - 4);
      ctx.lineTo(cx - 3 + si * 3, deckY + 2);
      ctx.stroke();
    }

    // DJ figure
    const djX = cx, djY = cy - 8;
    _drawDJ(djX, djY, Math.sin(tick * 0.18 * ts), pose);
  }

  // Interior: PIT GARAGE (pitwall)
  function _interiorGarage(cx, cy, ts=1, pose='idle') {
    // Dark grey floor
    ctx.fillStyle = 'rgba(30,30,30,0.7)';
    ctx.fillRect(cx - 50, cy + 10, 100, 30);

    // Overhead work light
    const lightGrad = ctx.createRadialGradient(cx, cy - BH * 0.35, 0, cx, cy, 35);
    lightGrad.addColorStop(0, 'rgba(255,200,80,0.18)');
    lightGrad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = lightGrad;
    ctx.fillRect(cx - 50, cy - BH * 0.4, 100, 80);

    // F1 car body
    const carY = cy + 8;
    ctx.fillStyle = '#ff9500';
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(cx - 22, carY - 5, 44, 9, 4) : ctx.fillRect(cx - 22, carY - 5, 44, 9);
    ctx.fill();
    // Nose cone
    ctx.fillStyle = '#cc7000';
    ctx.beginPath();
    ctx.moveTo(cx + 22, carY);
    ctx.lineTo(cx + 30, carY - 2);
    ctx.lineTo(cx + 30, carY + 2);
    ctx.closePath();
    ctx.fill();
    // Rear wing fins
    ctx.fillStyle = '#ff9500';
    ctx.fillRect(cx - 28, carY - 8, 6, 3);
    ctx.fillRect(cx - 28, carY + 5, 6, 3);
    // Wheels
    const wheelSpin = tick * 0.15 * ts;
    [cx - 14, cx + 12].forEach(wx => {
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(wx, carY + 6, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#222';
      ctx.fill();
      ctx.stroke();
      // Spinning spoke
      ctx.save();
      ctx.strokeStyle = '#555';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(wx + Math.cos(wheelSpin) * 4, carY + 6 + Math.sin(wheelSpin) * 4);
      ctx.lineTo(wx - Math.cos(wheelSpin) * 4, carY + 6 - Math.sin(wheelSpin) * 4);
      ctx.stroke();
      ctx.restore();
    });
    // Under-lighting
    ctx.save();
    ctx.globalAlpha = 0.4;
    const underGlow = ctx.createLinearGradient(cx - 22, carY + 4, cx + 22, carY + 4);
    underGlow.addColorStop(0, '#ff9500');
    underGlow.addColorStop(1, '#ffcc00');
    ctx.strokeStyle = underGlow;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - 20, carY + 4);
    ctx.lineTo(cx + 20, carY + 4);
    ctx.stroke();
    ctx.restore();

    // Sparks near wheel (more frequent when running)
    const sparkCount = pose === 'active' ? 12 : 5;
    ctx.save();
    for (let s = 0; s < sparkCount; s++) {
      const sx = cx + 12 + Math.sin(tick * 0.3 * ts + s * 1.5) * 6;
      const sy = carY + 5 + Math.cos(tick * 0.4 * ts + s * 2.1) * 4;
      ctx.fillStyle = '#ffdd00';
      ctx.globalAlpha = 0.7;
      ctx.beginPath();
      ctx.arc(sx, sy, 1, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    // Mechanic figure crouching
    const mX = cx + 14, mY = carY - 6;
    _drawDriver(mX, mY, Math.sin(tick * 0.18 * ts), pose);

    // Tool cabinet
    ctx.fillStyle = '#222';
    ctx.fillRect(cx - 40, cy - 10, 12, 20);
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 0.5;
    for (let di = 0; di < 4; di++) {
      ctx.beginPath();
      ctx.moveTo(cx - 40, cy - 10 + di * 5);
      ctx.lineTo(cx - 28, cy - 10 + di * 5);
      ctx.stroke();
    }
  }

  // Interior: COMMAND HQ
  function _interiorCommand(cx, cy, ts=1, pose='idle') {
    // Status strip at top
    const statusColors = ['#00ff66','#ff3300','#00ff66','#ffaa00'];
    for (let i = 0; i < 4; i++) {
      const on = Math.floor(tick * 0.05 * ts + i) % 2 === 0;
      ctx.fillStyle = on ? statusColors[i] : '#222';
      ctx.beginPath();
      ctx.arc(cx - 12 + i * 8, cy - BH * 0.38, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // 3 monitor screens
    const screenY = cy - 14;
    const screenW = 22, screenH = 18;
    [-24, 0, 24].forEach((dx, si) => {
      const sx = cx + dx;
      // Bezel
      ctx.fillStyle = '#111';
      ctx.fillRect(sx - screenW / 2 - 1, screenY - screenH / 2 - 1, screenW + 2, screenH + 2);
      // Screen
      ctx.fillStyle = '#001520';
      ctx.fillRect(sx - screenW / 2, screenY - screenH / 2, screenW, screenH);
      // Screen glow outline
      ctx.strokeStyle = 'rgba(0,240,255,0.5)';
      ctx.lineWidth = 0.8;
      ctx.strokeRect(sx - screenW / 2, screenY - screenH / 2, screenW, screenH);

      ctx.save();
      ctx.beginPath();
      ctx.rect(sx - screenW / 2, screenY - screenH / 2, screenW, screenH);
      ctx.clip();

      if (si === 0) {
        // Bar chart
        for (let bi = 0; bi < 5; bi++) {
          const bh3 = 3 + 8 * Math.abs(Math.sin(tick * 0.05 * ts + bi * 0.8));
          ctx.fillStyle = '#00f0ff';
          ctx.globalAlpha = 0.8;
          ctx.fillRect(sx - screenW / 2 + 2 + bi * 4, screenY + screenH / 2 - bh3, 3, bh3);
        }
      } else if (si === 1) {
        // Scrolling sine wave
        ctx.strokeStyle = '#00ff88';
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.9;
        ctx.beginPath();
        for (let xi = 0; xi <= screenW; xi++) {
          const wy = screenY + Math.sin((xi + tick * 2 * ts) * 0.25) * 5;
          xi === 0 ? ctx.moveTo(sx - screenW / 2 + xi, wy) : ctx.lineTo(sx - screenW / 2 + xi, wy);
        }
        ctx.stroke();
      } else {
        // Radar sweep
        const radarR = 7;
        ctx.strokeStyle = 'rgba(0,240,255,0.4)';
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.arc(sx, screenY, radarR, 0, Math.PI * 2);
        ctx.stroke();
        // Sweep line
        const sweepA = (tick * 0.06 * ts) % (Math.PI * 2);
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.9;
        ctx.beginPath();
        ctx.moveTo(sx, screenY);
        ctx.lineTo(sx + Math.cos(sweepA) * radarR, screenY + Math.sin(sweepA) * radarR);
        ctx.stroke();
        // Radar fade sector
        ctx.save();
        const radarGrad = ctx.createConicalGradient ? null : null;
        ctx.globalAlpha = 0.15;
        ctx.fillStyle = '#00f0ff';
        ctx.beginPath();
        ctx.moveTo(sx, screenY);
        ctx.arc(sx, screenY, radarR, sweepA - 1.2, sweepA);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }

      ctx.restore();
    });

    // Console desk
    ctx.fillStyle = '#0a1020';
    ctx.fillRect(cx - 28, cy + 4, 56, 10);
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 0.6;
    ctx.strokeRect(cx - 28, cy + 4, 56, 10);
    // Console buttons
    const btnColors = ['#00ff66','#ff3300','#ffff00','#00aaff','#ff44ff'];
    for (let bi = 0; bi < 5; bi++) {
      ctx.fillStyle = btnColors[bi];
      ctx.beginPath();
      ctx.arc(cx - 16 + bi * 8, cy + 10, 2, 0, Math.PI * 2);
      ctx.fill();
    }

    // Commander seated figure
    const cmdX = cx, cmdY = cy + 2;
    _drawCommander(cmdX, cmdY, Math.sin(tick * 0.18 * ts), pose);
  }

  // Interior: PRINT FORGE
  function _interiorForge(cx, cy, ts=1, pose='idle') {
    // Easel
    const easelX = cx + 6, easelY = cy;
    ctx.strokeStyle = '#886644';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(easelX - 10, easelY + 16);
    ctx.lineTo(easelX, easelY - 18);
    ctx.lineTo(easelX + 10, easelY + 16);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(easelX - 5, easelY + 16);
    ctx.lineTo(easelX, easelY);
    ctx.stroke();

    // Canvas on easel
    const canW = 18, canH = 14;
    ctx.fillStyle = '#f0ead6';
    ctx.fillRect(easelX - canW / 2, easelY - 16, canW, canH);
    ctx.strokeStyle = '#886644';
    ctx.lineWidth = 1;
    ctx.strokeRect(easelX - canW / 2, easelY - 16, canW, canH);

    // Progressively drawn car outline (tick % 300 drives progress)
    const progress = (Math.floor(tick * ts) % 300) / 300;
    ctx.save();
    ctx.beginPath();
    ctx.rect(easelX - canW / 2, easelY - 16, canW, canH);
    ctx.clip();
    const carLines = [
      [easelX - 7, easelY - 10, easelX + 8, easelY - 10],
      [easelX + 8, easelY - 10, easelX + 8, easelY - 6],
      [easelX + 8, easelY - 6, easelX - 7, easelY - 6],
      [easelX - 7, easelY - 6, easelX - 7, easelY - 10],
      [easelX - 5, easelY - 6, easelX - 4, easelY - 4],
      [easelX + 4, easelY - 6, easelX + 5, easelY - 4],
    ];
    const totalSegs = carLines.length;
    const segsDone = Math.floor(progress * totalSegs);
    ctx.strokeStyle = '#ff7020';
    ctx.lineWidth = 1;
    for (let li = 0; li < segsDone && li < totalSegs; li++) {
      const [x1, y1, x2, y2] = carLines[li];
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
    ctx.restore();

    // Ink splatter particles
    ctx.save();
    for (let pi = 0; pi < 8; pi++) {
      const angle = (pi / 8) * Math.PI * 2;
      const dist = 3 + ((tick * 0.5 * ts + pi * 37) % 12);
      ctx.fillStyle = '#ff7020';
      ctx.globalAlpha = 0.6;
      ctx.beginPath();
      ctx.arc(easelX + Math.cos(angle) * dist, easelY - 9 + Math.sin(angle) * dist * 0.5, 1, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    // Artist figure
    const artX = cx - 12, artY = cy - 2;
    _drawForger(artX, artY, Math.sin(tick * 0.18 * ts), pose);

    // Printing press roller
    ctx.fillStyle = '#333';
    ctx.fillRect(cx - 40, cy + 4, 18, 14);
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx - 31, cy + 4, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#555';
    ctx.fill();
    ctx.stroke();
    // Paper coming out
    ctx.fillStyle = '#f0ead6';
    ctx.fillRect(cx - 36, cy + 11, 10, 3);
  }

  // Interior: THE BANK (treasury)
  function _interiorBank(cx, cy, ts=1, pose='idle') {
    // Vault door (large circular)
    const vX = cx + 4, vY = cy - 4;
    const vR = 18;
    // Outer ring
    ctx.strokeStyle = '#00ff66';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#00ff66';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(vX, vY, vR, 0, Math.PI * 2);
    ctx.fillStyle = '#001a08';
    ctx.fill();
    ctx.stroke();
    // Middle ring (rotates)
    const vRot = tick * 0.01 * ts;
    ctx.save();
    ctx.translate(vX, vY);
    ctx.rotate(vRot);
    ctx.strokeStyle = '#00cc55';
    ctx.lineWidth = 1.5;
    ctx.shadowBlur = 4;
    ctx.beginPath();
    ctx.arc(0, 0, vR - 4, 0, Math.PI * 2);
    ctx.stroke();
    // Spoke handles
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * (vR - 7), Math.sin(a) * (vR - 7));
      ctx.lineTo(Math.cos(a) * (vR - 3), Math.sin(a) * (vR - 3));
      ctx.stroke();
    }
    ctx.restore();
    // Inner circle
    ctx.strokeStyle = '#00ff66';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(vX, vY, 5, 0, Math.PI * 2);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Counter
    ctx.fillStyle = '#1a1000';
    ctx.fillRect(cx - 28, cy + 16, 56, 8);
    ctx.strokeStyle = '#00ff66';
    ctx.lineWidth = 0.6;
    ctx.strokeRect(cx - 28, cy + 16, 56, 8);

    // Merchant figure behind counter
    const mX = cx - 10, mY = cy + 14;
    _drawMerchant(mX, mY, Math.sin(tick * 0.18 * ts), pose);

    // Gold coin stack on counter
    const coinX = cx + 12, coinY = cy + 15;
    for (let ci = 0; ci < 4; ci++) {
      ctx.fillStyle = '#ffd700';
      ctx.beginPath();
      ctx.ellipse(coinX, coinY - ci * 2, 5, 2, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#cc9900';
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }

    // Raining coins
    const coinRainSpeed = pose === 'active' ? 3.0 : 1.5;
    for (let ri = 0; ri < 5; ri++) {
      const phase = (tick * coinRainSpeed * ts + ri * 60) % 90;
      const rx = cx - 20 + ri * 10 + Math.sin(ri * 2.3) * 5;
      const ry = cy - BH * 0.4 + phase;
      if (ry < cy + 20) {
        ctx.globalAlpha = 0.7;
        ctx.fillStyle = '#ffd700';
        ctx.beginPath();
        ctx.ellipse(rx, ry, 4, 1.5, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    }

    // Digital £ display
    const dispY = cy - BH * 0.3;
    const amount = Math.floor(Math.sin(tick * 0.05 * ts) * 5000 + 15000);
    ctx.fillStyle = '#001a00';
    ctx.fillRect(cx - 20, dispY - 6, 40, 10);
    ctx.font = 'bold 6px monospace';
    ctx.fillStyle = '#00ff66';
    ctx.shadowColor = '#00ff66';
    ctx.shadowBlur = 6;
    ctx.textAlign = 'center';
    ctx.fillText('£' + amount, cx, dispY + 2);
    ctx.shadowBlur = 0;
  }

  // Interior: LIVERY WORKSHOP
  function _interiorWorkshop(cx, cy, ts=1, pose='idle') {
    // Checkered floor
    for (let fi = 0; fi < 6; fi++) {
      for (let fj = 0; fj < 3; fj++) {
        ctx.fillStyle = ((fi + fj) % 2 === 0) ? 'rgba(40,40,40,0.7)' : 'rgba(20,20,20,0.7)';
        ctx.fillRect(cx - 30 + fi * 10, cy + 16 + fj * 6, 10, 6);
      }
    }

    // Car body side-view silhouette
    const carY = cy + 4;
    const paintProgress = (Math.sin(tick * 0.02 * ts) + 1) / 2;
    const saturation = Math.floor(40 + paintProgress * 60);
    ctx.fillStyle = `hsl(350, ${saturation}%, 45%)`;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(cx - 26, carY - 5, 52, 10, 5);
    } else {
      ctx.rect(cx - 26, carY - 5, 52, 10);
    }
    ctx.fill();
    // Wheel arch cutouts
    [-14, 14].forEach(dx => {
      ctx.fillStyle = 'rgba(5,0,15,0.88)';
      ctx.beginPath();
      ctx.arc(cx + dx, carY + 5, 5, 0, Math.PI * 2);
      ctx.fill();
      // Wheel
      ctx.fillStyle = '#333';
      ctx.beginPath();
      ctx.arc(cx + dx, carY + 5, 4, 0, Math.PI * 2);
      ctx.fill();
    });

    // Colour swatches on wall
    const swatchColors = ['#ff1a4a','#00f0ff','#ffff00','#00ff66','#ff9500','#bf5fff'];
    swatchColors.forEach((c, i) => {
      ctx.fillStyle = c;
      ctx.fillRect(cx - 40 + i * 9, cy - BH * 0.35, 7, 5);
    });

    // Paint spray artist
    const artX = cx + 28, artY = cy + 2;
    _drawEngineer(artX, artY, Math.sin(tick * 0.18 * ts), pose);
    // Spray can held in hand (additional detail)
    ctx.fillStyle = '#666';
    ctx.fillRect(artX - 14, artY - 10, 4, 6);
    // Spray cone particles
    const sprayCount = pose === 'active' ? 20 : 12;
    for (let pi = 0; pi < sprayCount; pi++) {
      const angle = Math.PI + (pi - 6) * 0.08;
      const dist = 3 + ((tick * 0.5 * ts + pi * 17) % 18);
      const alpha = Math.max(0, 0.7 - dist / 18);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = '#ff1a4a';
      ctx.beginPath();
      ctx.arc(
        artX - 14 + Math.cos(angle) * dist,
        artY - 7 + Math.sin(angle) * dist,
        1, 0, Math.PI * 2
      );
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  // ── Buildings — cyberpunk glass towers ────────────────────────────────────
  function drawBuilding(b) {
    const off = getOffset();
    const { tl, tr, br, bl } = buildingCorners(b);
    const ox = off.x, oy = off.y;

    const isActive = b.active;
    const pulse = 0.5 + 0.5 * Math.sin(tick * 0.065);
    const st = _buildingStates[b.id] || {};
    const stateGlow = st.status === 'running' ? 1.8 : st.status === 'waiting' ? 1.3 : st.status === 'recently_active' ? 1.15 : 1.0;
    const glowStrength = (isActive ? 30 + 30 * pulse : 8) * stateGlow;

    const { r, g, b: bv } = hexToRgb(b.color);

    // ── GLOW PASS ──
    ctx.save();
    ctx.shadowColor = b.color;
    ctx.shadowBlur = glowStrength * 2;
    ctx.strokeStyle = b.color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.3;
    ctx.beginPath();
    ctx.moveTo(ox + tl.x, oy + tl.y - BH);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();

    // ── GROUND GLOW ──
    const baseCx = ox + (bl.x + br.x) / 2;
    const baseCy = oy + (bl.y + br.y) / 2;
    const gnd = ctx.createRadialGradient(baseCx, baseCy, 0, baseCx, baseCy, 70);
    gnd.addColorStop(0, `rgba(${r},${g},${bv},${isActive ? 0.18 : 0.08})`);
    gnd.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gnd;
    ctx.fillRect(baseCx - 70, baseCy - 40, 140, 80);

    // ── LEFT FACE (dark night side) ──
    const leftGrad = ctx.createLinearGradient(ox + bl.x, oy + bl.y, ox + br.x, oy + br.y);
    leftGrad.addColorStop(0, `rgba(${Math.floor(r * 0.12)},${Math.floor(g * 0.12)},${Math.floor(bv * 0.12)},1)`);
    leftGrad.addColorStop(1, `rgba(${Math.floor(r * 0.22)},${Math.floor(g * 0.22)},${Math.floor(bv * 0.22)},1)`);
    ctx.beginPath();
    ctx.moveTo(ox + bl.x, oy + bl.y);
    ctx.lineTo(ox + br.x, oy + br.y);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.fillStyle = leftGrad;
    ctx.fill();

    // ── RIGHT FACE (lit side) ──
    const rightGrad = ctx.createLinearGradient(ox + tr.x, oy + tr.y - BH, ox + br.x, oy + br.y);
    rightGrad.addColorStop(0,   `rgba(${Math.min(255, r + 60)},${Math.min(255, g + 60)},${Math.min(255, bv + 60)},1)`);
    rightGrad.addColorStop(0.3, `rgba(${r},${g},${bv},1)`);
    rightGrad.addColorStop(0.7, `rgba(${Math.floor(r * 0.55)},${Math.floor(g * 0.55)},${Math.floor(bv * 0.55)},1)`);
    rightGrad.addColorStop(1,   `rgba(${Math.floor(r * 0.3)},${Math.floor(g * 0.3)},${Math.floor(bv * 0.3)},1)`);
    ctx.beginPath();
    ctx.moveTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y);
    ctx.lineTo(ox + tr.x, oy + tr.y);
    ctx.closePath();
    ctx.fillStyle = rightGrad;
    ctx.fill();

    // ── INTERIOR SCENE ──
    drawBuildingInterior(b, ox, oy);

    // Glass panel horizontal lines on right face
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 0.5;
    for (let i = 1; i < 4; i++) {
      const t = i / 4;
      const x1 = ox + tr.x;
      const y1 = oy + tr.y - BH + BH * t;
      const x2 = ox + br.x;
      const y2 = oy + br.y - BH + BH * t;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
    ctx.restore();

    // Lit windows on right face
    ctx.save();
    for (let wi = 0; wi < 3; wi++) {
      for (let wj = 0; wj < 2; wj++) {
        const wt = (wi + 1) / 4;
        const ws = (wj + 1) / 3;
        const wx = ox + tr.x + (br.x - tr.x) * ws;
        const wy = oy + tr.y - BH + BH * wt + (br.y - tr.y) * ws;
        const lit = Math.sin(tick * 0.03 + wi * 1.7 + wj * 2.3 + b.col) > 0.1;
        if (lit) {
          ctx.shadowColor = b.color;
          ctx.shadowBlur = 6;
          ctx.fillStyle = `rgba(${Math.min(255, r + 100)},${Math.min(255, g + 100)},${Math.min(255, bv + 100)},0.9)`;
        } else {
          ctx.shadowBlur = 0;
          ctx.fillStyle = `rgba(${Math.floor(r * 0.3)},${Math.floor(g * 0.3)},${Math.floor(bv * 0.3)},0.5)`;
        }
        ctx.fillRect(wx - 3, wy - 2, 5, 4);
      }
    }
    ctx.restore();

    // ── TOP FACE (roof) ──
    const topGrad = ctx.createLinearGradient(ox + tl.x, oy + tl.y - BH, ox + br.x, oy + br.y - BH);
    topGrad.addColorStop(0,   `rgba(${Math.min(255, r + 120)},${Math.min(255, g + 120)},${Math.min(255, bv + 120)},0.95)`);
    topGrad.addColorStop(0.5, `rgba(${Math.min(255, r + 80)},${Math.min(255, g + 80)},${Math.min(255, bv + 80)},0.9)`);
    topGrad.addColorStop(1,   `rgba(${r},${g},${bv},0.85)`);
    ctx.beginPath();
    ctx.moveTo(ox + tl.x, oy + tl.y - BH);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.fillStyle = topGrad;
    ctx.fill();

    // ── NEON EDGE LINES (rim lighting) ──
    ctx.save();
    ctx.strokeStyle = b.color;
    ctx.lineWidth = isActive ? 1.5 : 0.8;
    ctx.shadowColor = b.color;
    ctx.shadowBlur = isActive ? 12 : 4;
    // Top face edges
    ctx.beginPath();
    ctx.moveTo(ox + tl.x, oy + tl.y - BH);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.stroke();
    // Vertical corner edges
    [tl, tr, br, bl].forEach(pt => {
      ctx.beginPath();
      ctx.moveTo(ox + pt.x, oy + pt.y - BH);
      ctx.lineTo(ox + pt.x, oy + pt.y);
      ctx.stroke();
    });
    ctx.restore();

    // ── AGENT COUNT BADGE ──
    const center = getBuildingCenter(b);
    if (b.agentCount > 0) {
      drawAgentBadge(center.x, center.y - 34, b.agentCount, b.color);
    }
    if (st.status === 'running' || st.status === 'waiting' || st.status === 'recently_active') {
      drawActivityBadge(b, ox, oy, st);
    }

    // ── HOLOGRAPHIC PANEL when active ──
    if (isActive) {
      drawHologram(b, ox, oy);
    }

    // ── ROOF SIGN ──
    drawBuildingSign(b, ox, oy);
    drawLiveActionBubble(b, ox, oy, st);
  }

  function drawActivityBadge(b, ox, oy, state) {
    const { tl, tr } = buildingCorners(b);
    const cx = ox + (tl.x + tr.x) / 2;
    const cy = oy + tl.y - BH - 18;

    ctx.save();
    if (state.status === 'running') {
      // Spinning cyan circle
      const spinA = tick * 0.12;
      ctx.shadowColor = '#00e5ff';
      ctx.shadowBlur = 12;
      ctx.strokeStyle = '#00e5ff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, 8, spinA, spinA + Math.PI * 1.5);
      ctx.stroke();
      // Dot at tip
      ctx.fillStyle = '#00e5ff';
      ctx.beginPath();
      ctx.arc(cx + Math.cos(spinA) * 8, cy + Math.sin(spinA) * 8, 2.5, 0, Math.PI * 2);
      ctx.fill();
      // RUNNING text
      ctx.shadowBlur = 6;
      ctx.font = '5px "Press Start 2P", monospace';
      ctx.fillStyle = '#00e5ff';
      ctx.textAlign = 'center';
      ctx.fillText('▶ RUNNING', cx, cy + 18);
    } else if (state.status === 'waiting') {
      // Pulsing amber circle
      const pulseA = 0.6 + 0.4 * Math.abs(Math.sin(tick * 0.1));
      ctx.globalAlpha = pulseA;
      ctx.shadowColor = '#ffaa00';
      ctx.shadowBlur = 14;
      ctx.strokeStyle = '#ffaa00';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, 8, 0, Math.PI * 2);
      ctx.stroke();
      // ❗ icon
      ctx.fillStyle = '#ffaa00';
      ctx.font = '10px serif';
      ctx.textAlign = 'center';
      ctx.fillText('❗', cx, cy + 4);
      ctx.globalAlpha = 1;
      ctx.font = '5px "Press Start 2P", monospace';
      ctx.fillStyle = '#ffaa00';
      ctx.fillText('WAITING', cx, cy + 18);
    } else if (state.status === 'recently_active') {
      // Soft green check — static, no spin
      const greenA = 0.7 + 0.3 * Math.abs(Math.sin(tick * 0.04));
      ctx.globalAlpha = greenA;
      ctx.shadowColor = '#00e676';
      ctx.shadowBlur = 8;
      ctx.strokeStyle = '#00e676';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, 7, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = '#00e676';
      ctx.font = '9px serif';
      ctx.textAlign = 'center';
      ctx.fillText('✓', cx, cy + 4);
      ctx.globalAlpha = 1;
      ctx.font = '5px "Press Start 2P", monospace';
      ctx.fillStyle = '#00e676';
      ctx.fillText('ACTIVE', cx, cy + 18);
    } else if (state.status === 'error') {
      ctx.shadowColor = '#ff3300';
      ctx.shadowBlur = 10;
      ctx.fillStyle = '#ff3300';
      ctx.font = '12px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('✗', cx, cy + 4);
    }
    ctx.restore();
  }

  function drawLiveActionBubble(b, ox, oy, state) {
    const { tl, tr } = buildingCorners(b);
    const cx = ox + (tl.x + tr.x) / 2;
    const cy = oy + tl.y - BH - 38;

    // Find matching live bubble, or fall back to last_action from state
    const lb = _liveBubbles.find(lb => lb.buildingId === b.id && lb.life > 0);
    if (!lb) {
      // Show a dim subtitle from last_action if available
      if (!state.last_action) return;
      const text = state.last_action.length > 32 ? state.last_action.slice(0, 31) + '…' : state.last_action;
      ctx.save();
      ctx.globalAlpha = 0.45;
      ctx.font = '5px "JetBrains Mono", monospace';
      ctx.fillStyle = '#8899aa';
      ctx.textAlign = 'center';
      ctx.fillText(text, cx, cy);
      ctx.restore();
      return;
    }

    const alpha = Math.min(lb.life / lb.maxLife * 3, 1) * Math.min((1 - lb.life / lb.maxLife) * 6 + 0.1, 1);
    const text = lb.text.length > 28 ? lb.text.slice(0, 27) + '…' : lb.text;

    ctx.save();
    ctx.globalAlpha = Math.max(0, alpha);
    ctx.font = '6px "JetBrains Mono", monospace';
    const tw = ctx.measureText(text).width;
    const bw = tw + 16;
    const bh = 16;
    const bx = cx - bw / 2;
    const by = cy - bh;

    // Background rounded rect
    roundRect(ctx, bx, by, bw, bh, 4);
    ctx.fillStyle = 'rgba(3,4,16,0.92)';
    ctx.fill();
    ctx.strokeStyle = lb.color;
    ctx.lineWidth = 1;
    ctx.shadowColor = lb.color;
    ctx.shadowBlur = 8;
    ctx.stroke();

    // Triangle pointer
    ctx.beginPath();
    ctx.moveTo(cx - 4, by + bh);
    ctx.lineTo(cx + 4, by + bh);
    ctx.lineTo(cx, by + bh + 5);
    ctx.closePath();
    ctx.fillStyle = 'rgba(3,4,16,0.92)';
    ctx.fill();
    ctx.strokeStyle = lb.color;
    ctx.stroke();

    // Text
    ctx.shadowBlur = 0;
    ctx.fillStyle = lb.color;
    ctx.textAlign = 'center';
    ctx.fillText(text, cx, by + bh - 4);

    ctx.restore();
  }

  function drawAgentBadge(x, y, count, color) {
    ctx.save();
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    roundRect(ctx, x - 9, y - 9, 18, 14, 4);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.font = 'bold 7px "Press Start 2P", monospace';
    ctx.fillStyle = '#000';
    ctx.textAlign = 'center';
    ctx.fillText(String(count), x, y + 2);
    ctx.restore();
  }

  // ── Agent characters ──────────────────────────────────────────────────────
  function drawFootprints(agent) {
    const trail = agent.trail || [];
    const color = AGENT_TYPES[agent.typeIdx] ? AGENT_TYPES[agent.typeIdx].color : '#00e5ff';
    trail.forEach((pt, i) => {
      const alpha = (i + 1) / trail.length * 0.4;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 5;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    });
  }

  function drawAgent(agent) {
    const { x, y } = agent;
    const typeIdx = agent.typeIdx !== undefined ? agent.typeIdx : (agent.id % AGENT_TYPES.length);
    const agType = AGENT_TYPES[typeIdx];
    const phase = agent.phase || agent.id || 0;
    const walk = Math.sin(tick * 0.18 + phase);
    const bob  = Math.sin(tick * 0.12 + phase) * 1.5;

    drawFootprints(agent);

    ctx.save();
    ctx.shadowColor = agType.color;
    ctx.shadowBlur = 10;

    // Ground shadow
    ctx.globalAlpha = 0.3;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(x, y + 1, 7, 2.5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    const ay = y + bob;

    // Determine agent's building state for pose
    const agentBuildingId = agent.toBuilding ? agent.toBuilding.id : null;
    const agentBSt = agentBuildingId ? (_buildingStates[agentBuildingId] || {}) : {};
    const agentPose = agentBSt.status === 'waiting' ? 'waiting' : agentBSt.status === 'running' ? 'active' : 'idle';

    switch (typeIdx) {
      case 0: _drawDriver(x, ay, walk, agentPose); break;    // Pitwall — Racing Driver
      case 1: _drawDJ(x, ay, walk, agentPose); break;         // PulseBreak — DJ
      case 2: _drawCommander(x, ay, walk, agentPose); break;  // Command — Commander
      case 3: _drawForger(x, ay, walk, agentPose); break;     // PrintForge — Forge Worker
      case 4: _drawMerchant(x, ay, walk, agentPose); break;   // Treasury — Merchant
      case 5: _drawEngineer(x, ay, walk, agentPose); break;   // Livery — Engineer
      default: _drawDriver(x, ay, walk, agentPose); break;
    }

    // Name label with glow
    ctx.font = '5px "Press Start 2P", monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = agType.color;
    ctx.shadowColor = agType.color;
    ctx.shadowBlur = 8;
    ctx.fillText(agType.name, x, ay - 22);

    ctx.restore();
  }

  function _drawDriver(x, y, walk, pose='idle') {
    // Legs
    ctx.fillStyle = '#111';
    ctx.fillRect(x - 3, y - 4 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 4 - walk * 2, 2.5, 5);
    // Racing suit (white + amber stripe)
    ctx.fillStyle = '#eee';
    ctx.fillRect(x - 4, y - 14, 8, 10);
    ctx.fillStyle = '#ff9500';
    ctx.fillRect(x - 1, y - 14, 2, 10);
    // Arms
    ctx.fillStyle = '#eee';
    if (pose === 'active') {
      // Both arms pumping
      ctx.fillRect(x - 7, y - 13 + walk * 4, 2.5, 5);
      ctx.fillRect(x + 4, y - 13 - walk * 4, 2.5, 5);
    } else if (pose === 'waiting') {
      ctx.fillRect(x - 7, y - 13 + walk * 2.5, 2.5, 5);
      ctx.fillRect(x + 4, y - 18, 2.5, 5); // arm up
      // Amber badge
      ctx.fillStyle = '#ffaa00';
      ctx.shadowColor = '#ffaa00';
      ctx.shadowBlur = 8;
      ctx.font = '7px serif';
      ctx.textAlign = 'center';
      ctx.fillText('❗', x + 5, y - 20);
      ctx.fillStyle = '#eee';
      ctx.shadowBlur = 0;
    } else {
      ctx.fillRect(x - 7, y - 13 + walk * 2.5, 2.5, 5);
      ctx.fillRect(x + 4, y - 13 - walk * 2.5, 2.5, 5);
    }
    // Helmet (orange, neon glow)
    ctx.shadowBlur = pose === 'active' ? 22 : 14;
    ctx.fillStyle = pose === 'waiting' ? '#cc4400' : '#ff6600';
    ctx.beginPath();
    if (pose === 'waiting') {
      // Helmet tilted
      ctx.save();
      ctx.translate(x, y - 19);
      ctx.rotate(0.3);
      ctx.arc(0, 0, 6, 0, Math.PI * 2);
      ctx.restore();
    } else {
      ctx.arc(x, y - 19, 6, 0, Math.PI * 2);
    }
    ctx.fill();
    // Visor
    ctx.fillStyle = '#001a2e';
    ctx.fillRect(x - 5, y - 21, 10, 3);
  }

  function _drawDJ(x, y, walk, pose='idle') {
    const armRaiseBase = Math.sin(tick * 0.22) * 5;
    const armRaise = pose === 'active' ? armRaiseBase * 2 : armRaiseBase;
    // Legs
    ctx.fillStyle = '#111';
    ctx.fillRect(x - 3, y - 4 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 4 - walk * 2, 2.5, 5);
    // Dark body
    ctx.fillStyle = '#1a0033';
    ctx.fillRect(x - 4, y - 14, 8, 10);
    // Lightning bolt chest
    ctx.strokeStyle = '#c084fc';
    ctx.lineWidth = 1.5;
    ctx.shadowColor = '#c084fc';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(x + 1, y - 14); ctx.lineTo(x - 1, y - 9);
    ctx.lineTo(x + 1, y - 9); ctx.lineTo(x - 1, y - 4);
    ctx.stroke();
    // Arms — right arm raised (both raised when active)
    ctx.fillStyle = '#f4a460';
    if (pose === 'active') {
      ctx.fillRect(x - 7, y - 13 - armRaise, 2, 5);
      ctx.fillRect(x + 5, y - 13 - armRaise, 2, 5);
    } else if (pose === 'waiting') {
      ctx.fillRect(x - 7, y - 13 + walk * 2, 2, 5);
      ctx.fillRect(x + 5, y - 20, 2, 5); // arm straight up
      // Amber glow on raised hand
      ctx.shadowColor = '#ffaa00';
      ctx.shadowBlur = 10;
      ctx.fillStyle = '#ffaa00';
      ctx.beginPath();
      ctx.arc(x + 6, y - 20, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#f4a460';
      ctx.shadowBlur = 0;
    } else {
      ctx.fillRect(x - 7, y - 13 + walk * 2, 2, 5);
      ctx.fillRect(x + 5, y - 13 - armRaise, 2, 5);
    }
    // Head
    ctx.shadowBlur = 0;
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 4, y - 24, 8, 9);
    // Headphones arc
    ctx.strokeStyle = '#c084fc';
    ctx.lineWidth = 3;
    ctx.shadowColor = pose === 'active' ? '#ffffff' : '#c084fc';
    ctx.shadowBlur = pose === 'active' ? 18 : 10;
    ctx.beginPath();
    ctx.arc(x, y - 23, 6, Math.PI, 0);
    ctx.stroke();
    // Cups
    ctx.fillStyle = '#c084fc';
    ctx.fillRect(x - 8, y - 25, 3, 4);
    ctx.fillRect(x + 5, y - 25, 3, 4);
    // Music note floating
    const noteY = y - 30 - Math.abs(Math.sin(tick * 0.1)) * 5;
    ctx.font = '8px serif';
    ctx.fillStyle = '#c084fc';
    ctx.shadowBlur = 8;
    ctx.textAlign = 'center';
    ctx.fillText('♪', x + 8, noteY);
    // Waiting pose: amber exclamation above head
    if (pose === 'waiting') {
      ctx.font = '8px serif';
      ctx.fillStyle = '#ffaa00';
      ctx.shadowColor = '#ffaa00';
      ctx.shadowBlur = 10;
      ctx.fillText('❗', x, y - 30);
    }
  }

  function _drawCommander(x, y, walk, pose='idle') {
    const capeSway = Math.sin(tick * 0.06) * (pose === 'active' ? 6 : 3);
    // Cape
    ctx.fillStyle = '#0a1a5a';
    ctx.beginPath();
    ctx.moveTo(x - 3, y - 12);
    ctx.lineTo(x + 3, y - 12);
    ctx.lineTo(x + capeSway, y + 1);
    ctx.closePath();
    ctx.fill();
    // Legs
    ctx.fillStyle = '#003355';
    ctx.fillRect(x - 3, y - 4 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 4 - walk * 2, 2.5, 5);
    // Armour body
    ctx.fillStyle = '#0d2233';
    ctx.fillRect(x - 3, y - 13, 6, 9);
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 1;
    ctx.shadowColor = '#00f0ff';
    ctx.shadowBlur = 8;
    ctx.strokeRect(x - 3, y - 13, 6, 9);
    // Shoulder plates
    ctx.fillStyle = '#004466';
    ctx.fillRect(x - 7, y - 13, 14, 4);
    // Arms
    ctx.fillStyle = '#004466';
    if (pose === 'active') {
      // Pointing at monitors
      ctx.fillRect(x - 7, y - 11 + walk * 2, 2, 5);
      ctx.fillRect(x + 5, y - 14, 2, 5);
    } else if (pose === 'waiting') {
      ctx.fillRect(x - 7, y - 11 + walk * 2, 2, 5);
      ctx.fillRect(x + 5, y - 18, 2, 5); // arm raised
      // Amber badge
      ctx.fillStyle = '#ffaa00';
      ctx.shadowColor = '#ffaa00';
      ctx.shadowBlur = 8;
      ctx.font = '8px serif';
      ctx.textAlign = 'center';
      ctx.fillText('❗', x, y - 28);
      ctx.fillStyle = '#004466';
      ctx.shadowBlur = 0;
    } else {
      ctx.fillRect(x - 7, y - 11 + walk * 2, 2, 5);
      ctx.fillRect(x + 5, y - 11 - walk * 2, 2, 5);
    }
    // Helmet
    ctx.fillStyle = '#00e5ff';
    ctx.shadowColor = '#00e5ff';
    ctx.shadowBlur = pose === 'active' ? 20 : 12;
    ctx.fillRect(x - 5, y - 24, 10, 10);
    // T-visor
    ctx.fillStyle = '#001a22';
    ctx.fillRect(x - 4, y - 21, 8, 3);
    ctx.fillRect(x - 1, y - 24, 2, 8);
  }

  function _drawForger(x, y, walk, pose='idle') {
    // Legs
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 4, y - 4 + walk * 2, 3, 5);
    ctx.fillRect(x + 1, y - 4 - walk * 2, 3, 5);
    // Boilersuit
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 4, y - 14, 8, 10);
    // Hi-vis stripe
    ctx.fillStyle = pose === 'active' ? '#ffcc00' : '#fb923c';
    ctx.fillRect(x - 4, y - 10, 8, 3);
    // Arms
    ctx.fillStyle = '#1a2233';
    if (pose === 'waiting') {
      // Arms crossed
      ctx.fillRect(x - 8, y - 13, 3, 5);
      ctx.fillRect(x + 5, y - 13, 3, 5);
      // Crossed arms overlay
      ctx.strokeStyle = '#1a2233';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(x - 5, y - 11);
      ctx.lineTo(x + 5, y - 11);
      ctx.stroke();
    } else {
      ctx.fillRect(x - 8, y - 13 + walk * 2, 3, 5);
      ctx.fillRect(x + 5, y - 13 - walk * 2, 3, 5);
      // Wrench in right hand (moves faster when active)
      const wrenchY = pose === 'active' ? y - 15 + Math.sin(tick * 0.3) * 3 : y - 15;
      ctx.fillStyle = '#bbb';
      ctx.fillRect(x + 8, wrenchY, 4, 2);
      ctx.fillRect(x + 9, wrenchY - 2, 2, 5);
    }
    // Face
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 4, y - 22, 8, 7);
    // Hard hat (orange)
    ctx.fillStyle = '#fb923c';
    ctx.shadowColor = '#fb923c';
    ctx.shadowBlur = pose === 'active' ? 16 : 10;
    ctx.fillRect(x - 5, y - 26, 10, 5);
    ctx.fillRect(x - 7, y - 22, 14, 2); // brim
    // Waiting: amber exclamation
    if (pose === 'waiting') {
      ctx.font = '8px serif';
      ctx.fillStyle = '#ffaa00';
      ctx.shadowColor = '#ffaa00';
      ctx.shadowBlur = 8;
      ctx.textAlign = 'center';
      ctx.fillText('❗', x, y - 30);
    }
  }

  function _drawMerchant(x, y, walk, pose='idle') {
    const coinBounceSpeed = pose === 'active' ? 0.4 : 0.2;
    const coinBounce = Math.abs(Math.sin(tick * coinBounceSpeed)) * (pose === 'active' ? 8 : 4);
    // Legs
    ctx.fillStyle = '#1a3322';
    ctx.fillRect(x - 3, y - 4 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 4 - walk * 2, 2.5, 5);
    // Coat
    ctx.fillStyle = '#0d2218';
    ctx.fillRect(x - 3, y - 14, 6, 10);
    // Gold buttons
    ctx.fillStyle = '#ffb300';
    [y - 13, y - 9, y - 5].forEach(by => {
      ctx.beginPath();
      ctx.arc(x, by, 1.5, 0, Math.PI * 2);
      ctx.fill();
    });
    // Arms
    ctx.fillStyle = '#0d2218';
    if (pose === 'waiting') {
      ctx.fillRect(x - 6, y - 13 + walk * 2, 2, 5);
      ctx.fillRect(x + 4, y - 19, 2, 5); // arm raised up with coin
    } else {
      ctx.fillRect(x - 6, y - 13 + walk * 2, 2, 5);
      ctx.fillRect(x + 4, y - 13 - walk * 2, 2, 5);
    }
    // Bouncing coin
    ctx.fillStyle = pose === 'waiting' ? '#ffaa00' : '#ffb300';
    ctx.shadowColor = pose === 'waiting' ? '#ffaa00' : '#ffb300';
    ctx.shadowBlur = pose === 'waiting' ? 18 : 12;
    ctx.beginPath();
    ctx.arc(x + 8, y - 12 - coinBounce, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#a07800';
    ctx.font = 'bold 5px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('£', x + 8, y - 10 - coinBounce);
    // Face
    ctx.fillStyle = '#c8a882';
    ctx.shadowBlur = 0;
    ctx.fillRect(x - 4, y - 26, 8, 8);
    // Top hat
    ctx.fillStyle = '#111';
    ctx.fillRect(x - 4, y - 37, 8, 11);
    ctx.fillRect(x - 6, y - 27, 12, 3);
    // Monocle
    ctx.strokeStyle = '#ffb300';
    ctx.lineWidth = 1;
    ctx.shadowColor = '#ffb300';
    ctx.shadowBlur = 6;
    ctx.beginPath();
    ctx.arc(x + 1, y - 20, 2.5, 0, Math.PI * 2);
    ctx.stroke();
  }

  function _drawEngineer(x, y, walk, pose='idle') {
    const flagWaveSpeed = pose === 'active' ? 0.36 : 0.18;
    const flagWave = Math.sin(tick * flagWaveSpeed) * 4;
    // Legs
    ctx.fillStyle = '#8b0000';
    ctx.fillRect(x - 3, y - 4 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 4 - walk * 2, 2.5, 5);
    // Red jumpsuit
    ctx.fillStyle = '#cc0033';
    ctx.fillRect(x - 4, y - 14, 8, 10);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 6px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('1', x, y - 6);
    // Arms
    ctx.fillStyle = '#cc0033';
    ctx.fillRect(x - 7, y - 13 + walk * 2, 2, 5);
    if (pose === 'waiting') {
      // Flag lowered, hand raised amber
      ctx.fillRect(x + 5, y - 17, 2, 5);
      ctx.fillStyle = '#ffaa00';
      ctx.shadowColor = '#ffaa00';
      ctx.shadowBlur = 8;
      ctx.font = '7px serif';
      ctx.textAlign = 'center';
      ctx.fillText('❗', x + 8, y - 22);
      ctx.fillStyle = '#cc0033';
      ctx.shadowBlur = 0;
    } else {
      ctx.fillRect(x + 5, y - 17, 2, 5); // raised arm
    }
    // Clipboard in left hand
    ctx.fillStyle = '#ddd';
    ctx.fillRect(x - 10, y - 13, 5, 6);
    ctx.strokeStyle = '#999';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(x - 10, y - 13, 5, 6);
    // Flag pole
    ctx.fillStyle = '#888';
    ctx.fillRect(x + 7, y - 26, 1.5, 10);
    // Chequered flag
    for (let fi = 0; fi < 3; fi++) {
      for (let fj = 0; fj < 2; fj++) {
        ctx.fillStyle = ((fi + fj) % 2 === 0) ? '#fff' : '#111';
        ctx.fillRect(x + 8 + fi * 3 + flagWave * (fj * 0.3), y - 28 + fj * 3, 3, 3);
      }
    }
    // Face
    ctx.fillStyle = '#f4a460';
    ctx.shadowBlur = 0;
    ctx.fillRect(x - 4, y - 22, 8, 7);
    // Red cap
    ctx.fillStyle = '#cc0033';
    ctx.shadowColor = '#cc0033';
    ctx.shadowBlur = 8;
    ctx.fillRect(x - 5, y - 26, 10, 5);
    ctx.fillStyle = '#991122';
    ctx.fillRect(x - 6, y - 22, 9, 2); // brim
  }

  // ── Ambient Particles ─────────────────────────────────────────────────────
  function spawnAmbientParticles() {
    BUILDINGS.forEach((b) => {
      if (Math.random() > 0.3) return;
      const center = getBuildingCenter(b);
      const bx = center.x + (Math.random() - 0.5) * 30;
      const by = center.y + 10;

      let pType;
      switch (b.id) {
        case 'treasury':   pType = 'coin';  break;
        case 'pulsebreak': pType = 'note';  break;
        case 'pitwall':    pType = 'spark'; break;
        case 'command':    pType = 'data';  break;
        default: return;
      }

      ambientParticles.push({
        bId: b.id,
        x: bx,
        y: by,
        vx: (Math.random() - 0.5) * 0.8,
        vy: -(0.5 + Math.random() * 0.8),
        life: 60 + Math.floor(Math.random() * 40),
        maxLife: 100,
        type: pType,
      });
    });
  }

  function drawAmbientParticles() {
    ambientParticles = ambientParticles.filter(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.life--;
      const alpha = (p.life / p.maxLife);
      ctx.save();
      ctx.globalAlpha = alpha;

      switch (p.type) {
        case 'coin':
          ctx.fillStyle = '#ffb300';
          ctx.shadowColor = '#ffb300';
          ctx.shadowBlur = 4;
          ctx.beginPath();
          ctx.ellipse(p.x, p.y, 3, 1.5, 0, 0, Math.PI * 2);
          ctx.fill();
          break;

        case 'note':
          ctx.fillStyle = '#bf5fff';
          ctx.shadowColor = '#bf5fff';
          ctx.shadowBlur = 6;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
          ctx.fill();
          ctx.beginPath();
          ctx.arc(p.x + 5, p.y + 2, 2, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#bf5fff';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(p.x + 2, p.y);
          ctx.lineTo(p.x + 2, p.y - 5);
          ctx.lineTo(p.x + 7, p.y - 3);
          ctx.lineTo(p.x + 7, p.y + 2);
          ctx.stroke();
          break;

        case 'spark':
          ctx.fillStyle = '#ff9500';
          ctx.shadowColor = '#ff9500';
          ctx.shadowBlur = 4;
          ctx.fillRect(p.x, p.y, 1.5, 1.5);
          break;

        case 'data':
          ctx.fillStyle = '#00f0ff';
          ctx.shadowColor = '#00f0ff';
          ctx.shadowBlur = 4;
          ctx.fillRect(p.x, p.y, 1, 3);
          break;
      }

      ctx.restore();
      return p.life > 0;
    });
  }

  // ── Particles (burst on task completion) ─────────────────────────────────
  function spawnBurst(x, y, color) {
    for (let i = 0; i < 5; i++) {
      const angle = (Math.PI * 2 * i) / 5 + Math.random() * 0.4;
      const speed = 1.5 + Math.random() * 2.5;
      particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 1,
        color,
        life: 40 + Math.floor(Math.random() * 20),
        maxLife: 60,
      });
    }
  }

  function updateAndDrawParticles() {
    particles = particles.filter(p => {
      p.x  += p.vx;
      p.y  += p.vy;
      p.vy += 0.08;
      p.life--;
      const alpha = p.life / p.maxLife;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = p.color;
      ctx.shadowColor = p.color;
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 2.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      return p.life > 0;
    });
  }

  // ── Speech bubbles ─────────────────────────────────────────────────────────
  function drawBubble(bubble) {
    const { x, y, text, life, maxLife } = bubble;
    const progress = 1 - life / maxLife;
    const fadeAlpha = Math.min(progress * 5, 1) * Math.min((1 - progress) * 5, 1);
    const dy = -progress * 18;

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

  // ── CRT scanlines + vignette ───────────────────────────────────────────────
  function drawCRT() {
    const { w, h } = getSize();
    ctx.save();
    // Subtle scanlines every 4px
    for (let yy = 0; yy < h; yy += 4) {
      ctx.fillStyle = 'rgba(0,0,0,0.04)';
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

  // ── Agent logic ────────────────────────────────────────────────────────────
  function spawnAgents() {
    agents = [];
    for (let i = 0; i < 8; i++) {
      const typeIdx = i % AGENT_TYPES.length;
      const from = BUILDINGS[i % BUILDINGS.length];
      const to   = BUILDINGS[(i + 2) % BUILDINGS.length];
      agents.push({
        id: i,
        typeIdx,
        type: AGENT_TYPES[typeIdx],
        x: 0, y: 0,
        fromBuilding: from,
        toBuilding: to,
        progress: Math.random(),
        speed: 0.0018 + Math.random() * 0.0022,
        active: true,
        phase: Math.random() * Math.PI * 2,
        bubbleTimer: Math.floor(Math.random() * 200),
        nextBubble: 180 + Math.floor(Math.random() * 350),
        taskTimer: Math.floor(Math.random() * 300),
        nextTask: (8 + Math.random() * 7) * 60,
        trail: [],
      });
    }
  }

  function updateAgents() {
    BUILDINGS.forEach(b => { b.agentCount = 0; });

    agents.forEach(agent => {
      agent.progress += agent.speed;

      if (tick % 6 === agent.id % 6) {
        agent.trail = agent.trail || [];
        agent.trail.push({ x: agent.x, y: agent.y });
        if (agent.trail.length > 3) agent.trail.shift();
      }

      if (agent.progress >= 1) {
        agent.progress = 0;
        agent.fromBuilding = agent.toBuilding;
        const others = BUILDINGS.filter(b => b.id !== agent.fromBuilding.id);
        agent.toBuilding = others[Math.floor(Math.random() * others.length)];
        agent.bubbleTimer = agent.nextBubble;
      }

      const from = getBuildingCenter(agent.fromBuilding);
      const to   = getBuildingCenter(agent.toBuilding);
      const pos  = lerpPt(from, to, agent.progress);
      agent.x = pos.x;
      agent.y = pos.y;

      if (agent.progress > 0.8) {
        agent.toBuilding.agentCount = (agent.toBuilding.agentCount || 0) + 1;
      }

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

      agent.taskTimer++;
      if (agent.taskTimer >= agent.nextTask) {
        spawnBurst(agent.x, agent.y, agent.type.color);
        agent.taskTimer = 0;
        agent.nextTask = (8 + Math.random() * 7) * 60;
      }
    });

    bubbles = bubbles.filter(b => {
      b.life--;
      const a = agents.find(a => a.id === b.agentId);
      if (a) { b.x = a.x; b.y = a.y; }
      return b.life > 0;
    });

    _liveBubbles = _liveBubbles.filter(lb => { lb.life--; return lb.life > 0; });
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

    try {
      const r = await fetch('/agents/live-status');
      const d = await r.json();
      updateBuildingStates(d);
    } catch (_) {}
  }

  // ── Main render loop ───────────────────────────────────────────────────────
  function loop() {
    tick++;
    const { w, h } = getSize();

    ctx.clearRect(0, 0, w, h);

    // 1. Background (nebula, stars, aurora) — drawn without world transform
    drawBackground();

    // 2. World scale transform
    const scale = getScale();
    ctx.save();
    ctx.translate(w / 2, 0);
    ctx.scale(scale, scale);
    ctx.translate(-w / 2, 0);

    // 3. Neon grid ground
    drawGround();

    // 4. Energy beams (under buildings)
    drawEnergyBeams();

    // 5. Mark active buildings
    BUILDINGS.forEach(b => {
      b.active = activeAgentData.some(j => j.status === 'running');
    });

    // 6. Ambient particles (before buildings)
    spawnAmbientParticles();
    drawAmbientParticles();

    // 7. Buildings back→front
    const sorted = [...BUILDINGS].sort((a, b) => (a.col + a.row) - (b.col + b.row));
    sorted.forEach(b => drawBuilding(b));

    // 8. Agents (painter's algo by y)
    [...agents].sort((a, b) => a.y - b.y).forEach(a => drawAgent(a));

    // 9. Burst particles
    updateAndDrawParticles();

    // 10. Speech bubbles
    bubbles.forEach(b => drawBubble(b));

    // 11. End world transform
    ctx.restore();

    // 12. CRT post-effect
    drawCRT();

    updateAgents();

    animFrame = requestAnimationFrame(loop);
  }

  // ── Click handler ──────────────────────────────────────────────────────────
  function handleClick(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const s = getScale();
    const { w: cw } = getSize();
    for (const b of BUILDINGS) {
      const center = getBuildingCenter(b);
      const sx = (center.x - cw / 2) * s + cw / 2;
      const sy = center.y * s;
      const dx = mx - sx;
      const dy = my - sy;
      if (Math.abs(dx) < 55 * s && Math.abs(dy) < 45 * s) {
        if (b.tab) {
          if (typeof openPanel === 'function') {
            openPanel(b.tab);
          } else if (typeof showTab === 'function') {
            showTab(b.tab);
          }
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
    setInterval(fetchData, 8000);

    canvas.addEventListener('click', handleClick);
    window.addEventListener('resize', () => {
      resize();
      stars = null;
      shootingStars = null;
    });

    // Demo key: press T to cycle the first building through all agent states
    window.addEventListener('keydown', (e) => {
      if (e.key !== 't' && e.key !== 'T') return;
      const DEMO_STATES = ['running', 'waiting', 'recently_active', 'idle'];
      const bid = BUILDINGS[0] && BUILDINGS[0].id;
      if (!bid) return;
      const cur = (_buildingStates[bid] || {}).status || 'idle';
      const next = DEMO_STATES[(DEMO_STATES.indexOf(cur) + 1) % DEMO_STATES.length];
      const actions = {
        running: 'Uploading track batch to distributor…',
        waiting: '3 tracks pending founder review',
        recently_active: 'Completed Etsy listing refresh',
        idle: null,
      };
      _buildingStates[bid] = {
        status: next,
        running_agent: next === 'running' ? 'Demo Agent' : null,
        last_action: actions[next],
        pending_count: next === 'waiting' ? 3 : 0,
        activity_level: next === 'running' ? 1.0 : next === 'recently_active' ? 0.6 : next === 'waiting' ? 0.5 : 0.0,
      };
      if (actions[next]) {
        _liveBubbles.push({ buildingId: bid, text: actions[next], color: next === 'running' ? '#00e5ff' : next === 'waiting' ? '#ffaa00' : '#00e676', life: 180, maxLife: 180 });
      }
    });
  }

  function destroy() {
    if (animFrame) cancelAnimationFrame(animFrame);
    window.removeEventListener('resize', resize);
  }

  function updateBuildingStates(data) {
    if (!data || !data.buildings) return;
    data.buildings.forEach(b => {
      const prev = _buildingStates[b.building_id] || {};
      if (prev.status !== b.status && b.status === 'running' && b.running_agent) {
        _liveBubbles.push({ buildingId: b.building_id, text: (b.running_agent || 'Agent') + ' running…', color: '#00e5ff', life: 240, maxLife: 240 });
      }
      if (prev.status === 'running' && b.status !== 'running' && b.last_action) {
        _liveBubbles.push({ buildingId: b.building_id, text: b.last_action.slice(0, 32), color: '#00ff66', life: 300, maxLife: 300 });
      }
      _buildingStates[b.building_id] = b;
    });
  }

  return { init, destroy, updateBuildingStates };
})();
