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
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
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

    // Deep graphite-blue gradient — near-black, no rainbow
    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0,   '#04060c');
    bg.addColorStop(0.55,'#060a14');
    bg.addColorStop(1,   '#03050a');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    // Single cool light source glow behind the city
    const off = getOffset();
    const lg = ctx.createRadialGradient(w/2, off.y + 90, 40, w/2, off.y + 90, Math.max(w, h) * 0.75);
    lg.addColorStop(0, 'rgba(80,150,220,0.10)');
    lg.addColorStop(0.5, 'rgba(40,90,160,0.04)');
    lg.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = lg;
    ctx.fillRect(0, 0, w, h);

    // Fine suspended dust — monochrome, slow drift
    if (!stars) {
      stars = Array.from({ length: 90 }, () => ({
        x: Math.random(), y: Math.random(),
        r: 0.4 + Math.random() * 1.1,
        phase: Math.random() * Math.PI * 2,
        drift: 0.00003 + Math.random() * 0.00006,
      }));
    }
    stars.forEach(st => {
      st.y -= st.drift; if (st.y < -0.02) st.y = 1.02;
      const a = 0.10 + 0.14 * (0.5 + 0.5 * Math.sin(tick * 0.015 + st.phase));
      ctx.globalAlpha = a;
      ctx.fillStyle = '#bcd8f5';
      ctx.beginPath();
      ctx.arc(st.x * w, st.y * h, st.r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;

    // Radar sweep — one slow luminous wedge rotating about the city centre
    const cx = w / 2, cy = off.y + (iso(GRID_COLS/2, GRID_ROWS/2).y);
    const sweepA = (tick * 0.004) % (Math.PI * 2);
    const R = Math.max(w, h) * 0.7;
    const grad = ctx.createConicGradient
      ? ctx.createConicGradient(sweepA, cx, cy) : null;
    if (grad) {
      grad.addColorStop(0,    'rgba(120,190,255,0.055)');
      grad.addColorStop(0.06, 'rgba(120,190,255,0.012)');
      grad.addColorStop(0.12, 'rgba(120,190,255,0)');
      grad.addColorStop(1,    'rgba(120,190,255,0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // ── Ground grid — neon cyberpunk ───────────────────────────────────────────
  function drawGround() {
    const off = getOffset();

    // Hairline grid — barely-there minor lines, calm major lines
    for (let c = 0; c <= GRID_COLS; c++) {
      const isMajor = c % 3 === 0;
      ctx.beginPath();
      const s2 = iso(c, 0), e = iso(c, GRID_ROWS);
      ctx.moveTo(off.x + s2.x, off.y + s2.y);
      ctx.lineTo(off.x + e.x, off.y + e.y);
      ctx.strokeStyle = isMajor ? 'rgba(140,190,240,0.13)' : 'rgba(140,190,240,0.045)';
      ctx.lineWidth = isMajor ? 0.7 : 0.4;
      ctx.stroke();
    }
    for (let r = 0; r <= GRID_ROWS; r++) {
      const isMajor = r % 3 === 0;
      ctx.beginPath();
      const s2 = iso(0, r), e = iso(GRID_COLS, r);
      ctx.moveTo(off.x + s2.x, off.y + s2.y);
      ctx.lineTo(off.x + e.x, off.y + e.y);
      ctx.strokeStyle = isMajor ? 'rgba(140,190,240,0.13)' : 'rgba(140,190,240,0.045)';
      ctx.lineWidth = isMajor ? 0.7 : 0.4;
      ctx.stroke();
    }

    // Corner ticks at major intersections — instrument-panel detail
    for (let c = 0; c <= GRID_COLS; c += 3) {
      for (let r = 0; r <= GRID_ROWS; r += 3) {
        const p = iso(c, r);
        ctx.fillStyle = 'rgba(170,210,250,0.28)';
        ctx.fillRect(off.x + p.x - 1, off.y + p.y - 1, 2, 2);
      }
    }

    // Perimeter frame line
    ctx.beginPath();
    const p0 = iso(0,0), p1 = iso(GRID_COLS,0), p2 = iso(GRID_COLS,GRID_ROWS), p3 = iso(0,GRID_ROWS);
    ctx.moveTo(off.x+p0.x, off.y+p0.y); ctx.lineTo(off.x+p1.x, off.y+p1.y);
    ctx.lineTo(off.x+p2.x, off.y+p2.y); ctx.lineTo(off.x+p3.x, off.y+p3.y);
    ctx.closePath();
    ctx.strokeStyle = 'rgba(150,200,250,0.22)';
    ctx.lineWidth = 1;
    ctx.stroke();
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
    ctx.font = '600 9px Inter, sans-serif';
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
    const { bl, br } = buildingCorners(b);
    const cx = ox + (bl.x + br.x) / 2;
    const cy = oy + (bl.y + br.y) / 2 + 16;
    const { r, g, b: bv } = hexToRgb(b.color);

    ctx.save();
    // Tick mark + division name — engraved-plate restraint
    ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + bv + ',0.9)';
    ctx.fillRect(cx - 14, cy - 4, 3, 3);
    ctx.font = '600 9.5px Inter, sans-serif';
    ctx.fillStyle = 'rgba(228,238,250,0.92)';
    ctx.shadowColor = 'rgba(0,0,0,0.9)';
    ctx.shadowBlur = 4;
    ctx.textAlign = 'left';
    ctx.fillText(b.label, cx - 8, cy);
    ctx.shadowBlur = 0;
    const tw = ctx.measureText(b.label).width;
    ctx.strokeStyle = 'rgba(' + r + ',' + g + ',' + bv + ',0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx - 14, cy + 5);
    ctx.lineTo(cx - 8 + tw, cy + 5);
    ctx.stroke();
    ctx.restore();
  }

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

    const cx = ox + (tr.x + br.x) / 2;
    const cy = oy + (tr.y + br.y) / 2 - BH / 2;
    const bst = _buildingStates[b.id] || {};
    const ts = bst.status === 'running' ? 2.2 : bst.status === 'recently_active' ? 1.4 : 1.0;

    drawHoloEmblem(b, cx, cy, ts);
    ctx.restore();
  }

  // ── Holographic section emblems — each division's living signature ────────
  function drawHoloEmblem(b, cx, cy, ts) {
    const t = tick * 0.02 * ts;
    const col = b.color;
    ctx.save();
    ctx.strokeStyle = col;
    ctx.fillStyle = col;
    ctx.lineWidth = 1.4;
    ctx.shadowColor = col;
    ctx.shadowBlur = 10;
    ctx.globalAlpha = 0.9;

    switch (b.id) {
      case 'pulsebreak': {
        // Living waveform — the PulseBreak signature
        ctx.beginPath();
        for (let i = -26; i <= 26; i += 2) {
          const env = Math.exp(-(i * i) / 320);
          const yv = Math.sin(i * 0.55 + t * 4) * 13 * env * (0.6 + 0.4 * Math.sin(t * 2));
          if (i === -26) ctx.moveTo(cx + i, cy + yv);
          else ctx.lineTo(cx + i, cy + yv);
        }
        ctx.stroke();
        // Halo ring
        ctx.globalAlpha = 0.35;
        ctx.beginPath(); ctx.arc(cx, cy, 22 + Math.sin(t * 2) * 2, 0, Math.PI * 2); ctx.stroke();
        break;
      }
      case 'pitwall': {
        // Racing line sweeping through an apex + speed ticks
        ctx.beginPath();
        ctx.moveTo(cx - 26, cy + 14);
        ctx.bezierCurveTo(cx - 8, cy + 12, cx - 12, cy - 10, cx + 4, cy - 8);
        ctx.bezierCurveTo(cx + 18, cy - 6, cx + 16, cy + 6, cx + 26, cy + 2);
        ctx.setLineDash([10, 6]);
        ctx.lineDashOffset = -t * 26;
        ctx.stroke();
        ctx.setLineDash([]);
        // Apex dot
        const at = (t * 0.9) % 1;
        const px2 = cx - 26 + 52 * at;
        ctx.globalAlpha = 0.9;
        ctx.beginPath(); ctx.arc(cx + 4, cy - 8, 2.4, 0, Math.PI * 2); ctx.fill();
        // Speed chevrons
        ctx.globalAlpha = 0.5;
        for (let i = 0; i < 3; i++) {
          const chx = cx - 18 + ((t * 18 + i * 14) % 42);
          ctx.beginPath();
          ctx.moveTo(chx, cy + 18); ctx.lineTo(chx + 5, cy + 21); ctx.lineTo(chx, cy + 24);
          ctx.stroke();
        }
        break;
      }
      case 'command': {
        // Radar scope: rings + rotating sweep + blips
        ctx.globalAlpha = 0.4;
        [8, 15, 22].forEach(rr => { ctx.beginPath(); ctx.arc(cx, cy, rr, 0, Math.PI * 2); ctx.stroke(); });
        ctx.globalAlpha = 0.25;
        ctx.beginPath(); ctx.moveTo(cx - 24, cy); ctx.lineTo(cx + 24, cy); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx, cy - 24); ctx.lineTo(cx, cy + 24); ctx.stroke();
        // Sweep
        const sa = t * 1.6;
        const sg = ctx.createConicGradient ? ctx.createConicGradient(sa, cx, cy) : null;
        if (sg) {
          sg.addColorStop(0, 'rgba(0,240,255,0.5)');
          sg.addColorStop(0.12, 'rgba(0,240,255,0)');
          sg.addColorStop(1, 'rgba(0,240,255,0)');
          ctx.globalAlpha = 0.8;
          ctx.fillStyle = sg;
          ctx.beginPath(); ctx.arc(cx, cy, 22, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = col;
        }
        // Blips
        ctx.globalAlpha = 0.5 + 0.5 * Math.sin(t * 3);
        ctx.beginPath(); ctx.arc(cx + 9, cy - 6, 1.8, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx - 11, cy + 8, 1.5, 0, Math.PI * 2); ctx.fill();
        break;
      }
      case 'printforge': {
        // Rotating gear with a molten core
        const teeth = 8, R1 = 16, R2 = 21;
        ctx.beginPath();
        for (let i = 0; i <= teeth * 2; i++) {
          const a = (i / (teeth * 2)) * Math.PI * 2 + t * 0.8;
          const rr = i % 2 === 0 ? R2 : R1;
          const px2 = cx + Math.cos(a) * rr, py2 = cy + Math.sin(a) * rr;
          if (i === 0) ctx.moveTo(px2, py2); else ctx.lineTo(px2, py2);
        }
        ctx.closePath();
        ctx.globalAlpha = 0.55;
        ctx.stroke();
        // Core
        const coreG = ctx.createRadialGradient(cx, cy, 0, cx, cy, 9);
        coreG.addColorStop(0, 'rgba(255,220,150,0.95)');
        coreG.addColorStop(1, 'rgba(255,112,32,0)');
        ctx.globalAlpha = 0.7 + 0.3 * Math.sin(t * 2.4);
        ctx.fillStyle = coreG;
        ctx.beginPath(); ctx.arc(cx, cy, 9, 0, Math.PI * 2); ctx.fill();
        break;
      }
      case 'treasury': {
        // Rising ledger bars + sterling mark
        ctx.globalAlpha = 0.7;
        const bars = [10, 16, 8, 20, 14];
        bars.forEach((bh2, i) => {
          const grow = Math.min(1, ((t * 0.5 + i * 0.2) % 2));
          const hgt = bh2 * (0.5 + 0.5 * Math.min(grow, 1));
          const bx = cx - 22 + i * 10;
          ctx.globalAlpha = 0.35 + 0.08 * i;
          ctx.fillRect(bx, cy + 14 - hgt, 6, hgt);
        });
        ctx.globalAlpha = 0.95;
        ctx.font = '700 17px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('£', cx, cy - 6);
        break;
      }
      case 'livery': {
        // Chequered apex flag rippling
        const cols2 = 6, rows2 = 3, cw = 7, ch = 5;
        for (let i = 0; i < cols2; i++) {
          for (let j = 0; j < rows2; j++) {
            const wave = Math.sin(t * 3 + i * 0.7) * 2.4;
            const on = (i + j) % 2 === 0;
            ctx.globalAlpha = on ? 0.85 : 0.18;
            ctx.fillRect(cx - (cols2 * cw) / 2 + i * cw, cy - 8 + j * ch + wave, cw - 1, ch - 1);
          }
        }
        break;
      }
    }
    ctx.restore();
  }

  // ── Buildings — cyberpunk glass towers ────────────────────────────────────
  function drawBuilding(b) {
    const off = getOffset();
    const { tl, tr, br, bl } = buildingCorners(b);
    const ox = off.x, oy = off.y;

    const isActive = b.active;
    const st = _buildingStates[b.id] || {};
    const stateGlow = st.status === 'running' ? 2.2 : st.status === 'waiting' ? 1.6 : st.status === 'recently_active' ? 1.3 : 1.0;
    const { r, g, b: bv } = hexToRgb(b.color);

    // ── Drop shadow + tight floor glow ──
    const baseCx = ox + (tl.x + br.x) / 2;
    const baseCy = oy + (tl.y + br.y) / 2;
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.beginPath();
    ctx.ellipse(baseCx + 6, baseCy + 6, 58, 26, 0, 0, Math.PI * 2);
    ctx.fill();
    const gnd = ctx.createRadialGradient(baseCx, baseCy, 0, baseCx, baseCy, 64);
    gnd.addColorStop(0, `rgba(${r},${g},${bv},${(0.10 * stateGlow).toFixed(3)})`);
    gnd.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gnd;
    ctx.fillRect(baseCx - 64, baseCy - 36, 128, 72);
    ctx.restore();

    // ── LEFT FACE — smoked glass ──
    const leftGrad = ctx.createLinearGradient(ox + bl.x, oy + bl.y - BH, ox + bl.x, oy + bl.y);
    leftGrad.addColorStop(0, `rgba(${Math.floor(r*0.10)+10},${Math.floor(g*0.10)+14},${Math.floor(bv*0.10)+22},0.92)`);
    leftGrad.addColorStop(1, 'rgba(6,9,16,0.95)');
    ctx.beginPath();
    ctx.moveTo(ox + bl.x, oy + bl.y);
    ctx.lineTo(ox + br.x, oy + br.y);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.fillStyle = leftGrad;
    ctx.fill();

    // Data hairlines on left face
    ctx.save();
    ctx.strokeStyle = `rgba(${r},${g},${bv},0.10)`;
    ctx.lineWidth = 0.6;
    for (let i = 1; i < 5; i++) {
      const tt = i / 5;
      ctx.beginPath();
      ctx.moveTo(ox + bl.x, oy + bl.y - BH * tt);
      ctx.lineTo(ox + br.x, oy + br.y - BH * tt);
      ctx.stroke();
    }
    ctx.restore();

    // ── RIGHT FACE — display glass ──
    const rightGrad = ctx.createLinearGradient(ox + tr.x, oy + tr.y - BH, ox + tr.x, oy + tr.y);
    rightGrad.addColorStop(0, `rgba(${Math.floor(r*0.16)+14},${Math.floor(g*0.16)+18},${Math.floor(bv*0.16)+28},0.92)`);
    rightGrad.addColorStop(1, 'rgba(8,12,20,0.95)');
    ctx.beginPath();
    ctx.moveTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y);
    ctx.lineTo(ox + tr.x, oy + tr.y);
    ctx.closePath();
    ctx.fillStyle = rightGrad;
    ctx.fill();

    // ── EMBLEM on the display face ──
    drawBuildingInterior(b, ox, oy);

    // ── TOP FACE — dark glass with a travelling sheen ──
    const topGrad = ctx.createLinearGradient(ox + tl.x, oy + tl.y - BH, ox + br.x, oy + br.y - BH);
    topGrad.addColorStop(0, `rgba(${Math.floor(r*0.22)+18},${Math.floor(g*0.22)+22},${Math.floor(bv*0.22)+34},0.96)`);
    topGrad.addColorStop(1, `rgba(${Math.floor(r*0.10)+10},${Math.floor(g*0.10)+12},${Math.floor(bv*0.10)+20},0.96)`);
    ctx.beginPath();
    ctx.moveTo(ox + tl.x, oy + tl.y - BH);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.fillStyle = topGrad;
    ctx.fill();

    // Sheen sweep across the roof
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(ox + tl.x, oy + tl.y - BH);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.clip();
    const sweepT = ((tick * 0.4 + b.col * 40) % 260) / 260;
    const sx0 = ox + tl.x - 60 + sweepT * (br.x - tl.x + 120);
    const sheen = ctx.createLinearGradient(sx0 - 26, 0, sx0 + 26, 0);
    sheen.addColorStop(0, 'rgba(255,255,255,0)');
    sheen.addColorStop(0.5, 'rgba(255,255,255,0.07)');
    sheen.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = sheen;
    ctx.fillRect(ox + tl.x - 70, oy + tl.y - BH - 40, (br.x - tl.x) + 140, 80);
    ctx.restore();

    // ── EDGES — precise rim light, glow only for live states ──
    ctx.save();
    if (stateGlow > 1.0 || isActive) {
      ctx.shadowColor = b.color;
      ctx.shadowBlur = 10 * stateGlow;
    }
    ctx.strokeStyle = `rgba(${r},${g},${bv},0.65)`;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.moveTo(ox + tl.x, oy + tl.y - BH);
    ctx.lineTo(ox + tr.x, oy + tr.y - BH);
    ctx.lineTo(ox + br.x, oy + br.y - BH);
    ctx.lineTo(ox + bl.x, oy + bl.y - BH);
    ctx.closePath();
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = `rgba(${r},${g},${bv},0.28)`;
    ctx.lineWidth = 1;
    [tr, br, bl].forEach(pt => {
      ctx.beginPath();
      ctx.moveTo(ox + pt.x, oy + pt.y - BH);
      ctx.lineTo(ox + pt.x, oy + pt.y);
      ctx.stroke();
    });
    // Inner white highlight along the near top edge
    ctx.strokeStyle = 'rgba(255,255,255,0.16)';
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(ox + bl.x, oy + bl.y - BH + 1);
    ctx.lineTo(ox + br.x, oy + br.y - BH + 1);
    ctx.stroke();
    ctx.restore();

    // ── AGENT COUNT BADGE ──
    const center = getBuildingCenter(b);
    if (b.agentCount > 0) {
      drawAgentBadge(center.x, center.y - 34, b.agentCount, b.color);
    }
    // Roof tint overlay for live states — refined
    if (st.status === 'running' || st.status === 'waiting') {
      const tintPulse = 0.08 + 0.07 * Math.abs(Math.sin(tick * (st.status === 'running' ? 0.11 : 0.06)));
      ctx.save();
      ctx.globalAlpha = tintPulse;
      ctx.fillStyle = st.status === 'running' ? '#00e5ff' : '#ffaa00';
      ctx.beginPath();
      ctx.moveTo(ox + tl.x, oy + tl.y - BH);
      ctx.lineTo(ox + tr.x, oy + tr.y - BH);
      ctx.lineTo(ox + br.x, oy + br.y - BH);
      ctx.lineTo(ox + bl.x, oy + bl.y - BH);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
    if (isActive) {
      drawHologram(b, ox, oy);
    }
  }

  function drawBuildingOverlay(b) {
    const off = getOffset();
    const ox = off.x, oy = off.y;
    const st = _buildingStates[b.id] || {};
    if (st.status === 'running' || st.status === 'waiting' || st.status === 'recently_active') {
      drawActivityBadge(b, ox, oy, st);
    }
    drawBuildingSign(b, ox, oy);
    drawLiveActionBubble(b, ox, oy, st);
  }

  function drawActivityBadge(b, ox, oy, state) {
    const { tl, tr } = buildingCorners(b);
    const cx = ox + (tl.x + tr.x) / 2;
    const cy = oy + tl.y - BH - 20;

    const CFG = {
      running:         { col: '#31d3f5', label: 'RUNNING',  spin: true  },
      waiting:         { col: '#ffb84d', label: 'NEEDS YOU', spin: false },
      recently_active: { col: '#4ade80', label: 'ACTIVE',   spin: false },
    };
    const cfg = CFG[state.status];
    if (!cfg) return;

    ctx.save();
    ctx.font = '700 8.5px Inter, sans-serif';
    const tw = ctx.measureText(cfg.label).width;
    const bw = tw + 30, bh = 18;
    const bx = cx - bw / 2, by = cy - bh / 2;

    roundRect(ctx, bx, by, bw, bh, 9);
    ctx.fillStyle = 'rgba(10,14,24,0.9)';
    ctx.fill();
    ctx.strokeStyle = cfg.col + '66';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Indicator: spinner arc for running, breathing dot otherwise
    const ix = bx + 12, iy = cy;
    ctx.strokeStyle = cfg.col;
    ctx.fillStyle = cfg.col;
    if (cfg.spin) {
      const a = tick * 0.12;
      ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.arc(ix, iy, 4, a, a + Math.PI * 1.4); ctx.stroke();
    } else {
      const pulse = state.status === 'waiting' ? 0.5 + 0.5 * Math.abs(Math.sin(tick * 0.08)) : 1;
      ctx.globalAlpha = pulse;
      ctx.beginPath(); ctx.arc(ix, iy, 3, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
    }

    ctx.fillStyle = 'rgba(232,240,250,0.95)';
    ctx.textAlign = 'left';
    ctx.fillText(cfg.label, ix + 9, cy + 3);
    ctx.restore();
  }

  function drawLiveActionBubble(b, ox, oy, state) {
    const { tl, tr } = buildingCorners(b);
    const cx = ox + (tl.x + tr.x) / 2;
    const cy = oy + tl.y - BH - 42;

    const lb = _liveBubbles.find(x => x.buildingId === b.id && x.life > 0);
    if (!lb) return;   // transient chips only — stale text lives in the panel

    const alpha = Math.min(lb.life / lb.maxLife * 3, 1) * Math.min((1 - lb.life / lb.maxLife) * 6 + 0.1, 1);
    const text = lb.text.length > 30 ? lb.text.slice(0, 29) + '…' : lb.text;

    ctx.save();
    ctx.globalAlpha = Math.max(0, alpha);
    ctx.font = '500 10px Inter, sans-serif';
    const tw = ctx.measureText(text).width;
    const bw = tw + 26, bh = 21;
    const bx = cx - bw / 2, by = cy - bh;

    roundRect(ctx, bx, by, bw, bh, 10);
    ctx.fillStyle = 'rgba(12,16,26,0.94)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.14)';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = lb.color || '#7fd4ff';
    ctx.beginPath();
    ctx.arc(bx + 11, by + bh / 2, 2.4, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = 'rgba(230,240,250,0.95)';
    ctx.textAlign = 'left';
    ctx.fillText(text, bx + 19, by + 14);
    ctx.restore();
  }

  function drawAgentBadge(x, y, count, color) {
    ctx.save();
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    roundRect(ctx, x - 9, y - 9, 18, 14, 4);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.font = '600 11px Inter, sans-serif';
    ctx.fillStyle = '#000';
    ctx.textAlign = 'center';
    ctx.fillText(String(count), x, y + 2);
    ctx.restore();
  }

  // ── Agent characters ──────────────────────────────────────────────────────
  // ── Agents — luminous division entities with light trails ─────────────────
  const AGENT_GLYPHS = {
    Driver:    (x, y, c) => {   // speed chevrons
      ctx.beginPath();
      ctx.moveTo(x - 3.5, y - 3); ctx.lineTo(x + 0.5, y); ctx.lineTo(x - 3.5, y + 3);
      ctx.moveTo(x + 0.5, y - 3); ctx.lineTo(x + 4.5, y); ctx.lineTo(x + 0.5, y + 3);
      ctx.stroke();
    },
    DJ:        (x, y, c) => {   // mini waveform
      ctx.beginPath();
      for (let i = -5; i <= 5; i++) {
        const env = Math.exp(-(i * i) / 10);
        const yv = Math.sin(i * 1.2 + tick * 0.15) * 3.4 * env;
        if (i === -5) ctx.moveTo(x + i, y + yv); else ctx.lineTo(x + i, y + yv);
      }
      ctx.stroke();
    },
    Commander: (x, y, c) => {   // crosshair
      ctx.beginPath(); ctx.arc(x, y, 3.4, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x - 5.5, y); ctx.lineTo(x - 2, y); ctx.moveTo(x + 2, y); ctx.lineTo(x + 5.5, y);
      ctx.moveTo(x, y - 5.5); ctx.lineTo(x, y - 2); ctx.moveTo(x, y + 2); ctx.lineTo(x, y + 5.5);
      ctx.stroke();
    },
    Forger:    (x, y, c) => {   // spark diamond
      ctx.beginPath();
      ctx.moveTo(x, y - 4.5); ctx.lineTo(x + 3.5, y); ctx.lineTo(x, y + 4.5); ctx.lineTo(x - 3.5, y);
      ctx.closePath(); ctx.stroke();
      ctx.beginPath(); ctx.arc(x, y, 1.1, 0, Math.PI * 2); ctx.fill();
    },
    Merchant:  (x, y, c) => {   // sterling
      ctx.font = '700 9px Inter, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('£', x, y + 0.5);
      ctx.textBaseline = 'alphabetic';
    },
    Engineer:  (x, y, c) => {   // chequer 2×2
      ctx.fillRect(x - 3.5, y - 3.5, 3.5, 3.5);
      ctx.fillRect(x, y, 3.5, 3.5);
      ctx.globalAlpha = 0.35;
      ctx.fillRect(x, y - 3.5, 3.5, 3.5);
      ctx.fillRect(x - 3.5, y, 3.5, 3.5);
      ctx.globalAlpha = 1;
    },
  };

  function drawFootprints(agent) {
    // Light trail — a fading streak of recent positions
    const trail = agent.trail || [];
    if (trail.length < 2) return;
    const agType = AGENT_TYPES[agent.typeIdx !== undefined ? agent.typeIdx : 0];
    ctx.save();
    ctx.lineCap = 'round';
    for (let i = 1; i < trail.length; i++) {
      const a = (i / trail.length) * 0.35;
      ctx.strokeStyle = agType.color;
      ctx.globalAlpha = a;
      ctx.lineWidth = 1 + (i / trail.length) * 2;
      ctx.beginPath();
      ctx.moveTo(trail[i - 1].x, trail[i - 1].y);
      ctx.lineTo(trail[i].x, trail[i].y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawAgent(agent) {
    const { x, y } = agent;
    const typeIdx = agent.typeIdx !== undefined ? agent.typeIdx : (agent.id % AGENT_TYPES.length);
    const agType = AGENT_TYPES[typeIdx];
    const phase = agent.phase || agent.id || 0;
    const bob = Math.sin(tick * 0.06 + phase) * 2;

    drawFootprints(agent);

    const agentBuildingId = agent.toBuilding ? agent.toBuilding.id : null;
    const agentBSt = agentBuildingId ? (_buildingStates[agentBuildingId] || {}) : {};
    const isBusy = agentBSt.status === 'running';

    const ay = y - 10 + bob;
    const { r, g, b: bv } = hexToRgb(agType.color);

    ctx.save();

    // Ground shadow
    ctx.globalAlpha = 0.35;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(x, y + 2, 7, 2.6, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // Vertical light tether
    const tether = ctx.createLinearGradient(x, y, x, ay);
    tether.addColorStop(0, `rgba(${r},${g},${bv},0)`);
    tether.addColorStop(1, `rgba(${r},${g},${bv},0.35)`);
    ctx.strokeStyle = tether;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, ay + 6); ctx.stroke();

    // Aura
    const aura = ctx.createRadialGradient(x, ay, 0, x, ay, 15);
    aura.addColorStop(0, `rgba(${r},${g},${bv},0.30)`);
    aura.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = aura;
    ctx.beginPath(); ctx.arc(x, ay, 15, 0, Math.PI * 2); ctx.fill();

    // Core — glass sphere
    const core = ctx.createRadialGradient(x - 2, ay - 2.5, 0.5, x, ay, 8);
    core.addColorStop(0, 'rgba(255,255,255,0.95)');
    core.addColorStop(0.35, `rgba(${Math.min(255,r+70)},${Math.min(255,g+70)},${Math.min(255,bv+70)},0.85)`);
    core.addColorStop(1, `rgba(${Math.floor(r*0.4)},${Math.floor(g*0.4)},${Math.floor(bv*0.4)},0.55)`);
    ctx.fillStyle = core;
    ctx.beginPath(); ctx.arc(x, ay, 8, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = `rgba(${r},${g},${bv},0.7)`;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(x, ay, 8, 0, Math.PI * 2); ctx.stroke();

    // Orbit ring — rotating open arc; second ring when its division is running
    const ringA = tick * (isBusy ? 0.12 : 0.05) + phase;
    ctx.strokeStyle = `rgba(${r},${g},${bv},0.8)`;
    ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(x, ay, 11.5, ringA, ringA + Math.PI * 1.35); ctx.stroke();
    if (isBusy) {
      ctx.globalAlpha = 0.55;
      ctx.beginPath(); ctx.arc(x, ay, 14, -ringA * 0.8, -ringA * 0.8 + Math.PI); ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Division glyph inside the core
    ctx.strokeStyle = 'rgba(10,14,22,0.9)';
    ctx.fillStyle = 'rgba(10,14,22,0.9)';
    ctx.lineWidth = 1.3;
    const glyph = AGENT_GLYPHS[agType.name];
    if (glyph) glyph(x, ay, agType.color);

    // Name plate
    ctx.font = '600 8px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(226,236,248,0.85)';
    ctx.shadowColor = 'rgba(0,0,0,0.8)';
    ctx.shadowBlur = 3;
    ctx.fillText(agType.name.toUpperCase(), x, ay - 17);

    ctx.restore();
  }

  function spawnAmbientParticles() {
    if (tick % 26 !== 0 || ambientParticles.length > 40) return;
    const b = BUILDINGS[Math.floor(Math.random() * BUILDINGS.length)];
    const c = getBuildingCenter(b);
    ambientParticles.push({
      type: 'mote',
      color: b.color,
      x: c.x + (Math.random() - 0.5) * 46,
      y: c.y - 20 - Math.random() * 20,
      vx: (Math.random() - 0.5) * 0.08,
      vy: -0.25 - Math.random() * 0.25,
      life: 140, maxLife: 140,
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
        case 'mote': {
          const mg = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 3.5);
          mg.addColorStop(0, p.color);
          mg.addColorStop(1, 'rgba(0,0,0,0)');
          ctx.globalAlpha = alpha * 0.5;
          ctx.fillStyle = mg;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
          ctx.fill();
          break;
        }
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
    const dy = -progress * 14;

    ctx.save();
    ctx.globalAlpha = Math.max(0, fadeAlpha);
    ctx.font = '500 10px Inter, sans-serif';
    const tw = ctx.measureText(text).width;
    const bw = tw + 26;
    const bh = 21;
    const bx = x - bw / 2;
    const by = y - 54 + dy;

    roundRect(ctx, bx, by, bw, bh, 10);
    ctx.fillStyle = 'rgba(12,16,26,0.92)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.14)';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = '#7fd4ff';
    ctx.beginPath();
    ctx.arc(bx + 11, by + bh / 2, 2.4, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = 'rgba(230,240,250,0.95)';
    ctx.textAlign = 'left';
    ctx.fillText(text, bx + 19, by + 14);
    ctx.restore();
  }

  function drawCRT() {
    const { w, h } = getSize();
    const vg = ctx.createRadialGradient(w / 2, h / 2, h * 0.3, w / 2, h / 2, h * 0.95);
    vg.addColorStop(0, 'rgba(0,0,0,0)');
    vg.addColorStop(1, 'rgba(0,0,0,0.5)');
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, w, h);
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
      if (!agent.pauseUntil || tick >= agent.pauseUntil) {
        agent.progress += agent.speed;
      }

      if (tick % 3 === agent.id % 3) {
        agent.trail = agent.trail || [];
        agent.trail.push({ x: agent.x, y: agent.y });
        if (agent.trail.length > 10) agent.trail.shift();
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

  // ── Live event stream (SSE) — falls back to polling if unavailable ────────
  let _sse = null;
  let _pollTimer = null;

  function startPolling() {
    if (_pollTimer) return;
    fetchData();
    _pollTimer = setInterval(fetchData, 8000);
  }

  function connectEvents() {
    if (typeof EventSource === 'undefined') { startPolling(); return; }
    try {
      _sse = new EventSource('/events');
      _sse.addEventListener('state', (e) => {
        try {
          const snap = JSON.parse(e.data);
          if (snap.live) updateBuildingStates(snap.live);
          if (snap.overview && snap.overview.revenue_today != null) {
            revenueToday = `£${snap.overview.revenue_today.toFixed(0)}`;
          }
        } catch (_) {}
      });
      _sse.onerror = () => {
        // Connection lost — EventSource auto-reconnects; poll meanwhile
        startPolling();
      };
      _sse.onopen = () => {
        if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
      };
    } catch (_) {
      startPolling();
    }
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
    sorted.forEach(b => drawBuildingOverlay(b));

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
  const AGENT_TAP_LINES = {
    Driver:    ['Scouting Etsy trends 🏎', 'Checking print sales…', 'Pitwall looking sharp!'],
    DJ:        ['Mixing a new DnB drop 🎧', 'That bassline though…', 'Track queue is stacked!'],
    Commander: ['Coordinating the fleet ⚡', 'All agents accounted for', 'Reviewing the mission…'],
    Forger:    ['Forging fresh designs 🔥', 'Print quality: pristine', 'New artwork incoming!'],
    Merchant:  ['Counting the gold 💰', 'Revenue ledger updated', 'Margins looking healthy'],
    Engineer:  ['Tuning the livery 🏁', 'Paint scheme perfected', 'Race-ready designs!'],
  };

  function handleClick(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const s = getScale();
    const { w: cw } = getSize();

    // Tap a walking agent → they stop and talk to you
    for (const agent of agents) {
      const sx = (agent.x - cw / 2) * s + cw / 2;
      const sy = agent.y * s;
      if (Math.abs(mx - sx) < 22 && Math.abs(my - sy) < 26) {
        const lines = AGENT_TAP_LINES[agent.type.name] || ['Hello, founder!'];
        const msg = lines[Math.floor(Math.random() * lines.length)];
        bubbles = bubbles.filter(b => b.agentId !== agent.id);
        bubbles.push({ agentId: agent.id, x: agent.x, y: agent.y,
                       text: `${agent.type.name}: ${msg}`, life: 150, maxLife: 150 });
        agent.pauseUntil = tick + 130;          // stop walking while talking
        spawnBurst(agent.x, agent.y, agent.type.color);
        return;
      }
    }

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

    fetchData();          // initial paint (scheduler + overview + live status)
    connectEvents();      // then switch to push updates

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
