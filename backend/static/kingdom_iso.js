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
  const BH = 44;           // building wall height in pixels
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

  // ── Buildings — cyberpunk glass towers ────────────────────────────────────
  function drawBuilding(b) {
    const off = getOffset();
    const { tl, tr, br, bl } = buildingCorners(b);
    const ox = off.x, oy = off.y;

    const isActive = b.active;
    const pulse = 0.5 + 0.5 * Math.sin(tick * 0.065);
    const glowStrength = isActive ? 30 + 30 * pulse : 8;

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

    // ── HOLOGRAPHIC PANEL when active ──
    if (isActive) {
      drawHologram(b, ox, oy);
    }

    // ── ROOF SIGN ──
    drawBuildingSign(b, ox, oy);
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

    switch (typeIdx) {
      case 0: _drawDriver(x, ay, walk); break;    // Pitwall — Racing Driver
      case 1: _drawDJ(x, ay, walk); break;         // PulseBreak — DJ
      case 2: _drawCommander(x, ay, walk); break;  // Command — Commander
      case 3: _drawForger(x, ay, walk); break;     // PrintForge — Forge Worker
      case 4: _drawMerchant(x, ay, walk); break;   // Treasury — Merchant
      case 5: _drawEngineer(x, ay, walk); break;   // Livery — Engineer
      default: _drawDriver(x, ay, walk); break;
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

  function _drawDriver(x, y, walk) {
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
    ctx.fillRect(x - 7, y - 13 + walk * 2.5, 2.5, 5);
    ctx.fillRect(x + 4, y - 13 - walk * 2.5, 2.5, 5);
    // Helmet (orange, neon glow)
    ctx.shadowBlur = 14;
    ctx.fillStyle = '#ff6600';
    ctx.beginPath();
    ctx.arc(x, y - 19, 6, 0, Math.PI * 2);
    ctx.fill();
    // Visor
    ctx.fillStyle = '#001a2e';
    ctx.fillRect(x - 5, y - 21, 10, 3);
  }

  function _drawDJ(x, y, walk) {
    const armRaise = Math.sin(tick * 0.22) * 5;
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
    // Arms — right arm raised
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 7, y - 13 + walk * 2, 2, 5);
    ctx.fillRect(x + 5, y - 13 - armRaise, 2, 5);
    // Head
    ctx.shadowBlur = 0;
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 4, y - 24, 8, 9);
    // Headphones arc
    ctx.strokeStyle = '#c084fc';
    ctx.lineWidth = 3;
    ctx.shadowColor = '#c084fc';
    ctx.shadowBlur = 10;
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
  }

  function _drawCommander(x, y, walk) {
    const capeSway = Math.sin(tick * 0.06) * 3;
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
    ctx.fillRect(x - 7, y - 11 + walk * 2, 2, 5);
    ctx.fillRect(x + 5, y - 11 - walk * 2, 2, 5);
    // Helmet
    ctx.fillStyle = '#00e5ff';
    ctx.shadowColor = '#00e5ff';
    ctx.shadowBlur = 12;
    ctx.fillRect(x - 5, y - 24, 10, 10);
    // T-visor
    ctx.fillStyle = '#001a22';
    ctx.fillRect(x - 4, y - 21, 8, 3);
    ctx.fillRect(x - 1, y - 24, 2, 8);
  }

  function _drawForger(x, y, walk) {
    // Legs
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 4, y - 4 + walk * 2, 3, 5);
    ctx.fillRect(x + 1, y - 4 - walk * 2, 3, 5);
    // Boilersuit
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 4, y - 14, 8, 10);
    // Hi-vis stripe
    ctx.fillStyle = '#fb923c';
    ctx.fillRect(x - 4, y - 10, 8, 3);
    // Arms
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 8, y - 13 + walk * 2, 3, 5);
    ctx.fillRect(x + 5, y - 13 - walk * 2, 3, 5);
    // Wrench in right hand
    ctx.fillStyle = '#bbb';
    ctx.fillRect(x + 8, y - 15, 4, 2);
    ctx.fillRect(x + 9, y - 17, 2, 5);
    // Face
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 4, y - 22, 8, 7);
    // Hard hat (orange)
    ctx.fillStyle = '#fb923c';
    ctx.shadowColor = '#fb923c';
    ctx.shadowBlur = 10;
    ctx.fillRect(x - 5, y - 26, 10, 5);
    ctx.fillRect(x - 7, y - 22, 14, 2); // brim
  }

  function _drawMerchant(x, y, walk) {
    const coinBounce = Math.abs(Math.sin(tick * 0.2)) * 4;
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
    ctx.fillRect(x - 6, y - 13 + walk * 2, 2, 5);
    ctx.fillRect(x + 4, y - 13 - walk * 2, 2, 5);
    // Bouncing coin
    ctx.fillStyle = '#ffb300';
    ctx.shadowColor = '#ffb300';
    ctx.shadowBlur = 12;
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

  function _drawEngineer(x, y, walk) {
    const flagWave = Math.sin(tick * 0.18) * 4;
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
    ctx.fillRect(x + 5, y - 17, 2, 5); // raised arm
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
    setInterval(fetchData, 30000);

    canvas.addEventListener('click', handleClick);
    window.addEventListener('resize', () => {
      resize();
      stars = null;
      shootingStars = null;
    });
  }

  function destroy() {
    if (animFrame) cancelAnimationFrame(animFrame);
    window.removeEventListener('resize', resize);
  }

  return { init, destroy };
})();
