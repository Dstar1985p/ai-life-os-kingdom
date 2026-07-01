/**
 * Kingdom ISO — Isometric pixel-art game map for the Kingdom AI dashboard.
 * Renders 6 venture buildings in isometric 3-D with animated agent sprites,
 * speech bubbles, CRT scanlines, particle bursts, footprints, and agent badges.
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
    { id: 'printforge', label: 'PRINT FORGE',  col: 0, row: 4, cols: 2, rows: 2, color: '#fb923c', glow: 'rgba(251,146,60,0.4)',  tab: 'pitwall',    icon: '🖨' },
    { id: 'treasury',   label: 'TREASURY',     col: 4, row: 5, cols: 2, rows: 2, color: '#00ff88', glow: 'rgba(0,255,136,0.4)',   tab: 'overview',   icon: '💰' },
    { id: 'livery',     label: 'LIVERY FORGE', col: 8, row: 5, cols: 2, rows: 2, color: '#ff3366', glow: 'rgba(255,51,102,0.4)',  tab: 'livery',     icon: '🏁' },
  ];

  // ── Agent types ────────────────────────────────────────────────────────────
  const AGENT_TYPES = [
    { color: '#00e5ff', name: 'Scout'   },
    { color: '#ffb300', name: 'Forge'   },
    { color: '#c084fc', name: 'Vibes'   },
    { color: '#00ff88', name: 'Trade'   },
    { color: '#fb923c', name: 'Builder' },
    { color: '#f472b6', name: 'Recon'   },
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
  let particles = [];   // burst particles
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
      w: canvas.clientWidth  || canvas.offsetWidth  || 800,
      h: canvas.clientHeight || canvas.offsetHeight || 600,
    };
  }

  function getScale() {
    const { w, h } = getSize();
    // The actual bounding box of all 6 buildings (cols 0-10, rows 0-7)
    const mapW = (GRID_COLS + GRID_ROWS) * (TW / 2);
    const mapH = (GRID_COLS + GRID_ROWS) * (TH / 2) + BH * 2;
    // Fill 90% width or 78% height (leave room for HUD), whichever is tighter
    const scaleX = (w * 0.90) / mapW;
    const scaleY = (h * 0.78) / mapH;
    return Math.min(scaleX, scaleY, 2.8);
  }

  function getOffset() {
    const { w, h } = getSize();
    const s = getScale();
    // Actual rendered map height
    const mapH = ((GRID_COLS + GRID_ROWS) * (TH / 2) + BH * 2) * s;
    // Center vertically between HUD top bar (12%) and bottom bar (48px)
    const topPad  = h * 0.13;
    const botPad  = 56;
    const usableH = h - topPad - botPad;
    const y = topPad + (usableH - mapH) / 2 + BH * s;
    return { x: w / 2, y: Math.max(y, topPad + BH * s * 0.5) };
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

  // ── Stars ──────────────────────────────────────────────────────────────────
  let shootingStars = null;

  function ensureStars() {
    if (!stars) {
      stars = Array.from({ length: 150 }, () => ({
        x: Math.random(),
        y: Math.random() * 0.45,
        r: 0.3 + Math.random() * 2.0,
        phase: Math.random() * Math.PI * 2,
      }));
    }
    if (!shootingStars) {
      shootingStars = Array.from({ length: 5 }, (_, i) => ({
        phase: i * (1800 / 5), // stagger over 30s at 60fps
        period: 1800,          // 30s cycle
        y: 0.05 + Math.random() * 0.3,
        angle: 0.3 + Math.random() * 0.3,
      }));
    }
  }

  function drawStars() {
    ensureStars();
    const { w, h } = getSize();
    stars.forEach(s => {
      const alpha = 0.25 + 0.45 * Math.sin(tick * 0.03 + s.phase);
      ctx.fillStyle = `rgba(255,255,255,${alpha.toFixed(3)})`;
      ctx.beginPath();
      ctx.arc(s.x * w, s.y * h, s.r, 0, Math.PI * 2);
      ctx.fill();
    });
    // Shooting stars
    shootingStars.forEach(ss => {
      const t = ((tick + ss.phase) % ss.period) / ss.period;
      if (t > 0.12) return; // only visible for ~12% of cycle
      const progress = t / 0.12;
      const tailLen = 120;
      const sx = progress * (w + tailLen);
      const sy = ss.y * h + sx * Math.tan(ss.angle);
      const ex = sx - tailLen;
      const ey = sy - tailLen * Math.tan(ss.angle);
      const alpha = Math.min(progress * 5, 1) * (1 - progress);
      const grad = ctx.createLinearGradient(ex, ey, sx, sy);
      grad.addColorStop(0, `rgba(255,255,255,0)`);
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

  // ── Ground grid ────────────────────────────────────────────────────────────
  function drawGround() {
    const off = getOffset();
    // Draw isometric grid lines instead of filled diamonds
    ctx.strokeStyle = 'rgba(0,229,255,0.08)';
    ctx.lineWidth = 0.5;
    // Horizontal iso lines (constant row)
    for (let r = 0; r <= GRID_ROWS; r++) {
      ctx.beginPath();
      const start = iso(0, r);
      const end = iso(GRID_COLS, r);
      ctx.moveTo(off.x + start.x, off.y + start.y);
      ctx.lineTo(off.x + end.x, off.y + end.y);
      ctx.stroke();
    }
    // Vertical iso lines (constant col)
    for (let c = 0; c <= GRID_COLS; c++) {
      ctx.beginPath();
      const start = iso(c, 0);
      const end = iso(c, GRID_ROWS);
      ctx.moveTo(off.x + start.x, off.y + start.y);
      ctx.lineTo(off.x + end.x, off.y + end.y);
      ctx.stroke();
    }
    // Subtle pulsing intersection dots
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
  }

  // ── Road paths between buildings ──────────────────────────────────────────
  function drawRoads() {
    const ROADS = [
      ['pitwall', 'printforge'],
      ['pitwall', 'treasury'],
      ['pulsebreak', 'command'],
      ['treasury', 'livery'],
    ];
    ROADS.forEach(([aId, bId]) => {
      const bA = BUILDINGS.find(b => b.id === aId);
      const bB = BUILDINGS.find(b => b.id === bId);
      if (!bA || !bB) return;
      const cA = getBuildingCenter(bA);
      const cB = getBuildingCenter(bB);
      ctx.save();
      ctx.strokeStyle = 'rgba(0,229,255,0.12)';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 8]);
      ctx.beginPath();
      ctx.moveTo(cA.x, cA.y + BH);
      ctx.lineTo(cB.x, cB.y + BH);
      ctx.stroke();
      ctx.setLineDash([]);
      // Moving packet
      const t = (tick * 0.008) % 1;
      const px = cA.x + (cB.x - cA.x) * t;
      const py = cA.y + BH + (cB.y - cA.y) * t;
      ctx.fillStyle = '#00e5ff';
      ctx.shadowColor = '#00e5ff';
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.arc(px, py, 2.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    });
  }

  // ── Buildings ──────────────────────────────────────────────────────────────
  function drawBuilding(b) {
    const off = getOffset();
    const { tl, tr, br, bl } = buildingCorners(b);
    const ox = off.x, oy = off.y;

    const isActive = b.active;
    // Active buildings get a stronger pulsing glow cycling 20→40→20 over ~2s
    const glowIntensity = isActive ? 20 + 20 * (0.5 + 0.5 * Math.sin(tick * 0.065)) : 0;

    if (isActive) {
      ctx.save();
      ctx.shadowColor = b.color;
      ctx.shadowBlur = glowIntensity;
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

    // Windows on RIGHT face (2×2 grid of flickering windows)
    drawWindows(b, ox, oy, tr, br);

    // Door on LEFT face
    {
      const doorW = 8, doorH = 12;
      // Centre of the left face bottom edge
      const faceCx = ox + (bl.x + br.x) / 2;
      const faceBotY = oy + (bl.y + br.y) / 2;
      const dx = faceCx - doorW / 2;
      const dy = faceBotY - doorH;
      ctx.save();
      ctx.fillStyle = shadeColor(b.color, -90);
      ctx.fillRect(dx, dy, doorW, doorH);
      ctx.strokeStyle = shadeColor(b.color, 30);
      ctx.lineWidth = 1;
      ctx.strokeRect(dx, dy, doorW, doorH);
      // Door arch
      ctx.beginPath();
      ctx.arc(faceCx, dy, doorW / 2, Math.PI, 0);
      ctx.fillStyle = shadeColor(b.color, -90);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    // Roof detail: icon on top face centre
    {
      const topCx = ox + (tl.x + tr.x + bl.x + br.x) / 4;
      const topCy = oy + (tl.y + tr.y + bl.y + br.y) / 4 - BH;
      ctx.save();
      ctx.font = '16px serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowColor = b.color;
      ctx.shadowBlur = 8;
      ctx.fillText(b.icon, topCx, topCy);
      ctx.restore();

      // Antenna: thin line + blinking dot
      const antX = topCx;
      const antY = topCy - 8;
      ctx.save();
      ctx.strokeStyle = 'rgba(200,200,200,0.6)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(antX, antY);
      ctx.lineTo(antX, antY - 20);
      ctx.stroke();
      const blinkAlpha = 0.5 + 0.5 * Math.sin(tick * 0.1);
      ctx.fillStyle = `rgba(255,80,80,${blinkAlpha.toFixed(3)})`;
      ctx.shadowColor = 'red';
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.arc(antX, antY - 20, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

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

    // Agent count badge above building
    if (b.agentCount > 0) {
      drawAgentBadge(center.x, center.y - 34, b.agentCount, b.color);
    }
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

  function drawWindows(b, ox, oy, tr, br) {
    const numW = b.cols;
    const numH = 2; // 2 rows of windows
    for (let ci = 0; ci < numW; ci++) {
      for (let ri = 0; ri < numH; ri++) {
        const tx = (ci + 1) / (numW + 1);
        const wx = ox + tr.x + (br.x - tr.x) * tx;
        const wy = oy + tr.y + (br.y - tr.y) * tx - BH * (0.3 + ri * 0.35);
        const winIdx = ci * numH + ri;
        const lit = Math.sin(tick * 0.05 + winIdx * 2.1 + b.col) > -0.3;
        ctx.save();
        ctx.fillStyle = lit ? 'rgba(200,240,255,0.9)' : 'rgba(0,229,255,0.15)';
        ctx.shadowColor = '#00e5ff';
        ctx.shadowBlur = lit ? 7 : 2;
        ctx.fillRect(wx - 4, wy - 4, 4, 4);
        ctx.restore();
      }
    }
  }

  // ── Agent sprites & footprints ────────────────────────────────────────────
  function drawFootprints(agent) {
    const trail = agent.trail || [];
    trail.forEach((pt, i) => {
      const alpha = (i + 1) / trail.length * 0.35;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = agent.type.color;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    });
  }

  function drawAgent(agent) {
    const { x, y, type } = agent;

    // Draw footprints first (behind agent)
    drawFootprints(agent);

    const walk = Math.sin(tick * 0.18 + (agent.phase || agent.id));

    ctx.save();
    ctx.shadowColor = type.color;
    ctx.shadowBlur = 8;

    // Shadow
    ctx.globalAlpha = 0.3;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(x, y + 1, 4, 1.5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // Legs (two 2×4 alternating)
    ctx.fillStyle = shadeColor(type.color, -30);
    const legSwing = walk * 2.5;
    ctx.fillRect(x - 3, y - 4 + legSwing,  2, 4);
    ctx.fillRect(x + 1, y - 4 - legSwing,  2, 4);

    // Body (4×8)
    ctx.fillStyle = shadeColor(type.color, -10);
    ctx.fillRect(x - 2, y - 12, 4, 8);

    // Arms (2×4 swinging on each side)
    const armSwing = walk * 3;
    ctx.fillStyle = type.color;
    ctx.fillRect(x - 5, y - 11 + armSwing, 2, 4);
    ctx.fillRect(x + 3,  y - 11 - armSwing, 2, 4);

    // Head (6×6)
    ctx.fillStyle = shadeColor(type.color, 40);
    ctx.fillRect(x - 3, y - 18, 6, 6);

    // Eyes
    ctx.fillStyle = 'rgba(255,255,255,0.9)';
    ctx.fillRect(x - 2, y - 17, 1, 1);
    ctx.fillRect(x + 1, y - 17, 1, 1);

    ctx.restore();

    // Name label above
    ctx.save();
    ctx.font = '8px monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = type.color;
    ctx.shadowColor = type.color;
    ctx.shadowBlur = 6;
    ctx.fillText(type.name, x, y - 22);
    ctx.restore();
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
      p.vy += 0.08; // gravity
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

  // ── Scanlines + vignette ───────────────────────────────────────────────────
  function drawCRT() {
    const { w, h } = getSize();
    ctx.save();
    for (let yy = 0; yy < h; yy += 3) {
      ctx.fillStyle = 'rgba(0,0,0,0.05)';
      ctx.fillRect(0, yy, w, 1);
    }
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
        taskTimer: Math.floor(Math.random() * 300),
        nextTask: (8 + Math.random() * 7) * 60, // 8-15s at ~60fps
        trail: [],
      });
    }
  }

  function updateAgents() {
    // Reset building agent counts
    BUILDINGS.forEach(b => { b.agentCount = 0; });

    agents.forEach(agent => {
      agent.progress += agent.speed;

      // Record footprint every 6 frames
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

      // Count agent near destination building
      if (agent.progress > 0.8) {
        agent.toBuilding.agentCount = (agent.toBuilding.agentCount || 0) + 1;
      }

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

      // Task completion burst
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

    // Background
    ctx.fillStyle = '#030410';
    ctx.fillRect(0, 0, w, h);

    // Stars
    drawStars();

    // Scale the entire world to fill the screen
    const scale = getScale();
    ctx.save();
    ctx.translate(w / 2, 0);
    ctx.scale(scale, scale);
    ctx.translate(-w / 2, 0);

    // Ground
    drawGround();

    // Roads between buildings
    drawRoads();

    // Mark active buildings
    BUILDINGS.forEach(b => {
      b.active = activeAgentData.some(j => j.status === 'running');
    });

    // Draw buildings back→front
    const sorted = [...BUILDINGS].sort((a, b) => (a.col + a.row) - (b.col + b.row));
    sorted.forEach(b => drawBuilding(b));

    // Agents sorted by y (painter's algorithm)
    [...agents].sort((a, b) => a.y - b.y).forEach(a => drawAgent(a));

    // Particles
    updateAndDrawParticles();

    // Bubbles
    bubbles.forEach(b => drawBubble(b));

    ctx.restore(); // end world scale

    // CRT effects (applied after scale restore, over full canvas)
    drawCRT();

    // Update agent state
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
      // Transform center coords the same way the draw loop does
      const sx = (center.x - cw / 2) * s + cw / 2;
      const sy = center.y * s;
      const dx = mx - sx;
      const dy = my - sy;
      if (Math.abs(dx) < 55 * s && Math.abs(dy) < 45 * s) {
        if (b.tab) {
          // Prefer the new slide-in panel; fall back to showTab
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
