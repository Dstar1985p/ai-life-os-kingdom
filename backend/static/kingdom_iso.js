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
    { id: 'pitwall',    label: 'PITWALL',      col: 1, row: 1, cols: 2, rows: 2, color: '#ff9500', glow: 'rgba(255,149,0,0.6)',   tab: 'pitwall',    icon: '🏎' },
    { id: 'pulsebreak', label: 'PULSEBREAK',   col: 5, row: 0, cols: 2, rows: 2, color: '#bf5fff', glow: 'rgba(191,95,255,0.6)',  tab: 'pulsebreak', icon: '🎵' },
    { id: 'command',    label: 'COMMAND',       col: 8, row: 2, cols: 2, rows: 2, color: '#00f0ff', glow: 'rgba(0,240,255,0.6)',   tab: 'command',    icon: '⚔️' },
    { id: 'printforge', label: 'PRINT FORGE',  col: 0, row: 4, cols: 2, rows: 2, color: '#ff7020', glow: 'rgba(255,112,32,0.6)',  tab: 'pitwall',    icon: '🖨' },
    { id: 'treasury',   label: 'TREASURY',     col: 4, row: 5, cols: 2, rows: 2, color: '#00ff66', glow: 'rgba(0,255,102,0.6)',   tab: 'overview',   icon: '💰' },
    { id: 'livery',     label: 'LIVERY FORGE', col: 8, row: 5, cols: 2, rows: 2, color: '#ff1a4a', glow: 'rgba(255,26,74,0.6)',   tab: 'livery',     icon: '🏁' },
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
    if (w < 600) {
      return Math.min((h * 0.72) / mapH, 1.6);
    }
    const scaleX = (w * 0.90) / mapW;
    const scaleY = (h * 0.78) / mapH;
    return Math.min(scaleX, scaleY, 2.8);
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
        phase: i * (1800 / 5),
        period: 1800,
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
    // Horizontal iso lines (constant row)
    for (let r = 0; r <= GRID_ROWS; r++) {
      const isAccent = (r % 3 === 0);
      ctx.strokeStyle = isAccent ? 'rgba(0,229,255,0.3)' : 'rgba(0,229,255,0.15)';
      ctx.lineWidth = isAccent ? 1 : 0.5;
      ctx.beginPath();
      const start = iso(0, r);
      const end = iso(GRID_COLS, r);
      ctx.moveTo(off.x + start.x, off.y + start.y);
      ctx.lineTo(off.x + end.x, off.y + end.y);
      ctx.stroke();
    }
    // Vertical iso lines (constant col)
    for (let c = 0; c <= GRID_COLS; c++) {
      const isAccent = (c % 3 === 0);
      ctx.strokeStyle = isAccent ? 'rgba(0,229,255,0.3)' : 'rgba(0,229,255,0.15)';
      ctx.lineWidth = isAccent ? 1 : 0.5;
      ctx.beginPath();
      const start = iso(c, 0);
      const end = iso(c, GRID_ROWS);
      ctx.moveTo(off.x + start.x, off.y + start.y);
      ctx.lineTo(off.x + end.x, off.y + end.y);
      ctx.stroke();
    }
    // Pulsing intersection dots
    for (let c = 0; c <= GRID_COLS; c += 2) {
      for (let r = 0; r <= GRID_ROWS; r += 2) {
        const p = iso(c, r);
        const alpha = 0.25 + 0.15 * Math.sin(tick * 0.04 + c + r);
        ctx.fillStyle = `rgba(0,229,255,${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(off.x + p.x, off.y + p.y, 2, 0, Math.PI * 2);
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

  // ── Neon signs on building right face ─────────────────────────────────────
  function drawBuildingSign(b, ox, oy, tr, br) {
    // Right face corners: top-right (tr) to bottom-right (br), height BH
    // The right face goes from (tr, tr.y-BH) at top to (br, br.y) at bottom
    // Centre of right face:
    const faceCx = ox + (tr.x + br.x) / 2;
    const faceTopY = oy + (tr.y + br.y) / 2 - BH;
    const faceBotY = oy + (tr.y + br.y) / 2;
    const faceH = BH;
    const faceW = Math.abs(br.x - tr.x) || 32;
    const midY = (faceTopY + faceBotY) / 2;

    ctx.save();

    switch (b.id) {
      case 'pitwall': {
        // Neon orange border around right face
        ctx.strokeStyle = '#ff9500';
        ctx.lineWidth = 2;
        ctx.shadowColor = '#ff9500';
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.moveTo(ox + tr.x, oy + tr.y - BH);
        ctx.lineTo(ox + br.x, oy + br.y - BH);
        ctx.lineTo(ox + br.x, oy + br.y);
        ctx.lineTo(ox + tr.x, oy + tr.y);
        ctx.closePath();
        ctx.stroke();

        // Chequered flag pattern across top of right face
        const sqSize = 4;
        const numSq = Math.ceil(faceW / sqSize);
        for (let i = 0; i < numSq; i++) {
          for (let j = 0; j < 2; j++) {
            if ((i + j) % 2 === 0) {
              ctx.fillStyle = 'rgba(255,255,255,0.7)';
            } else {
              ctx.fillStyle = 'rgba(0,0,0,0.7)';
            }
            const sx = faceCx - faceW / 2 + i * sqSize;
            const sy = faceTopY + j * sqSize;
            ctx.fillRect(sx, sy, sqSize, sqSize);
          }
        }

        // Racing car emoji
        ctx.shadowBlur = 10;
        ctx.font = '14px serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('🏎', faceCx, faceTopY + 10);
        break;
      }

      case 'pulsebreak': {
        // Audio waveform sine wave
        ctx.strokeStyle = '#bf5fff';
        ctx.lineWidth = 3;
        ctx.shadowColor = '#bf5fff';
        ctx.shadowBlur = 16;
        ctx.beginPath();
        const wavePoints = 30;
        for (let i = 0; i <= wavePoints; i++) {
          const wx = faceCx - faceW / 2 + (i / wavePoints) * faceW;
          const wy = midY + Math.sin((i / wavePoints) * Math.PI * 4 + tick * 0.1) * 8;
          if (i === 0) ctx.moveTo(wx, wy);
          else ctx.lineTo(wx, wy);
        }
        ctx.stroke();

        // Musical note symbol using lines (two dots + stems)
        ctx.fillStyle = '#bf5fff';
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(faceCx - 4, faceTopY + 10, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(faceCx + 4, faceTopY + 12, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#bf5fff';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(faceCx - 1, faceTopY + 10);
        ctx.lineTo(faceCx - 1, faceTopY + 4);
        ctx.lineTo(faceCx + 7, faceTopY + 2);
        ctx.lineTo(faceCx + 7, faceTopY + 12);
        ctx.stroke();
        break;
      }

      case 'command': {
        // Concentric crosshair circles
        const radii = [6, 12, 18];
        const spin = Math.sin(tick * 0.04) * Math.PI * 2;
        radii.forEach((r, i) => {
          ctx.strokeStyle = '#00f0ff';
          ctx.lineWidth = 1;
          ctx.shadowColor = '#00f0ff';
          ctx.shadowBlur = 10;
          ctx.beginPath();
          if (i === radii.length - 1) {
            // Outer ring: rotated arc for spin effect
            ctx.arc(faceCx, midY, r, spin, spin + Math.PI * 1.8);
          } else {
            ctx.arc(faceCx, midY, r, 0, Math.PI * 2);
          }
          ctx.stroke();
        });
        // Crosshair lines
        ctx.strokeStyle = 'rgba(0,240,255,0.6)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(faceCx - 20, midY);
        ctx.lineTo(faceCx - 6, midY);
        ctx.moveTo(faceCx + 6, midY);
        ctx.lineTo(faceCx + 20, midY);
        ctx.moveTo(faceCx, midY - 20);
        ctx.lineTo(faceCx, midY - 6);
        ctx.moveTo(faceCx, midY + 6);
        ctx.lineTo(faceCx, midY + 20);
        ctx.stroke();
        break;
      }

      case 'printforge': {
        // Printer icon
        ctx.strokeStyle = '#ff7020';
        ctx.lineWidth = 2;
        ctx.shadowColor = '#ff7020';
        ctx.shadowBlur = 8;
        // Printer body
        ctx.strokeRect(faceCx - 8, midY - 8, 16, 10);
        // Paper coming out
        ctx.strokeRect(faceCx - 5, midY + 2, 10, 14);
        // Lines on paper
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(faceCx - 3, midY + 6);
        ctx.lineTo(faceCx + 3, midY + 6);
        ctx.moveTo(faceCx - 3, midY + 9);
        ctx.lineTo(faceCx + 3, midY + 9);
        ctx.stroke();
        break;
      }

      case 'treasury': {
        // Gold coin stack — 3 overlapping ellipses
        ctx.shadowColor = '#00ff66';
        ctx.shadowBlur = 10;
        for (let i = 2; i >= 0; i--) {
          ctx.fillStyle = '#ffb300';
          ctx.strokeStyle = '#00ff66';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.ellipse(faceCx, midY + i * 4, 8, 3, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
        // £ symbol
        ctx.fillStyle = '#00ff66';
        ctx.font = 'bold 10px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.shadowBlur = 8;
        ctx.fillText('£', faceCx, midY - 10);
        break;
      }

      case 'livery': {
        // Racing livery diagonal stripes
        ctx.strokeStyle = '#ff1a4a';
        ctx.lineWidth = 2;
        ctx.shadowColor = '#ff1a4a';
        ctx.shadowBlur = 8;
        const stripeOffsets = [-10, 0, 10];
        stripeOffsets.forEach(off2 => {
          ctx.beginPath();
          ctx.moveTo(faceCx + off2 - 12, faceTopY + 4);
          ctx.lineTo(faceCx + off2 + 12, faceBotY - 4);
          ctx.stroke();
        });
        break;
      }
    }

    ctx.restore();
  }

  // ── Buildings ──────────────────────────────────────────────────────────────
  function drawBuilding(b) {
    const off = getOffset();
    const { tl, tr, br, bl } = buildingCorners(b);
    const ox = off.x, oy = off.y;

    const isActive = b.active;
    // Enhanced pulsing glow: 30→60→30 over ~2s
    const glowIntensity = isActive ? 30 + 30 * (0.5 + 0.5 * Math.sin(tick * 0.065)) : 0;

    // Ground glow radial gradient under building
    {
      const baseCx = ox + (bl.x + br.x) / 2;
      const baseCy = oy + (bl.y + br.y) / 2;
      const grd = ctx.createRadialGradient(baseCx, baseCy, 0, baseCx, baseCy, 60);
      // Extract rgb from glow string, use 0.15 alpha
      const glowColor = b.glow.replace(/[\d.]+\)$/, '0.15)');
      grd.addColorStop(0, glowColor);
      grd.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.save();
      ctx.fillStyle = grd;
      ctx.fillRect(baseCx - 60, baseCy - 30, 120, 60);
      ctx.restore();
    }

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

    // Neon sign on right face
    drawBuildingSign(b, ox, oy, tr, br);

    // Windows on RIGHT face (2×2 grid of flickering windows)
    drawWindows(b, ox, oy, tr, br);

    // Door on LEFT face
    {
      const doorW = 8, doorH = 12;
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
    ctx.font = '15px serif';
    ctx.shadowColor = b.color;
    ctx.shadowBlur = 10;
    ctx.fillText(b.icon, center.x, center.y - 18);
    ctx.font = 'bold 7px "Press Start 2P", monospace';
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = b.color;
    ctx.shadowBlur = 12;
    ctx.fillText(b.label, center.x, center.y - 4);
    ctx.restore();

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
    const numH = 2;
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

  // ── Agent sprites ─────────────────────────────────────────────────────────
  function drawFootprints(agent) {
    const trail = agent.trail || [];
    const color = AGENT_TYPES[agent.typeIdx] ? AGENT_TYPES[agent.typeIdx].color : '#00e5ff';
    trail.forEach((pt, i) => {
      const alpha = (i + 1) / trail.length * 0.35;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;
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

    drawFootprints(agent);

    const bob = Math.sin(tick * 0.15 + phase) * 1.5;

    ctx.save();

    // Drop shadow
    ctx.globalAlpha = 0.4;
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.ellipse(x, y + 1, 6, 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    ctx.shadowColor = agType.color;
    ctx.shadowBlur = 8;

    switch (typeIdx) {
      case 0: drawRacingDriver(x, y + bob, tick, phase); break;
      case 1: drawDJ(x, y + bob, tick, phase); break;
      case 2: drawCommander(x, y + bob, tick, phase); break;
      case 3: drawForgeWorker(x, y + bob, tick, phase); break;
      case 4: drawMerchant(x, y + bob, tick, phase); break;
      case 5: drawRaceEngineer(x, y + bob, tick, phase); break;
      default: drawRacingDriver(x, y + bob, tick, phase); break;
    }

    ctx.restore();

    // Name label
    ctx.save();
    ctx.font = "9px 'Press Start 2P', monospace";
    ctx.textAlign = 'center';
    ctx.fillStyle = agType.color;
    ctx.shadowColor = agType.color;
    ctx.shadowBlur = 6;
    ctx.fillText(agType.name, x, y + bob - 24);
    ctx.restore();
  }

  function drawRacingDriver(x, y, tick, phase) {
    const walk = Math.sin(tick * 0.18 + phase);
    // Legs
    ctx.fillStyle = '#333';
    ctx.fillRect(x - 4, y - 5 + walk * 2.5, 3, 5);
    ctx.fillRect(x + 1, y - 5 - walk * 2.5, 3, 5);
    // Body (white with amber centre stripe)
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(x - 4, y - 15, 8, 10);
    ctx.fillStyle = '#ff9500';
    ctx.fillRect(x - 1, y - 15, 2, 10);
    // Arms
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(x - 7, y - 14 + walk * 3, 2, 6);
    ctx.fillRect(x + 5, y - 14 - walk * 3, 2, 6);
    // Helmet (orange circle)
    ctx.fillStyle = '#ff6600';
    ctx.beginPath();
    ctx.arc(x, y - 20, 6, 0, Math.PI * 2);
    ctx.fill();
    // Visor slit (dark rect across middle)
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(x - 5, y - 22, 10, 3);
  }

  function drawDJ(x, y, tick, phase) {
    const walk = Math.sin(tick * 0.18 + phase);
    const armRaise = Math.sin(tick * 0.2 + phase) * 4;
    // Legs
    ctx.fillStyle = '#222';
    ctx.fillRect(x - 3, y - 5 + walk * 2, 2, 6);
    ctx.fillRect(x + 1, y - 5 - walk * 2, 2, 6);
    // Body (black with purple lightning)
    ctx.fillStyle = '#111';
    ctx.fillRect(x - 4, y - 15, 8, 10);
    // Lightning bolt on chest
    ctx.strokeStyle = '#c084fc';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x + 1, y - 15);
    ctx.lineTo(x - 1, y - 10);
    ctx.lineTo(x + 1, y - 10);
    ctx.lineTo(x - 1, y - 5);
    ctx.stroke();
    // Arms (one raised)
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 7, y - 14 + walk * 2, 2, 6);
    ctx.fillRect(x + 5, y - 14 - armRaise, 2, 6);
    // Head (square, skin tone)
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 5, y - 25, 10, 10);
    // Headphones (purple arc over top)
    ctx.strokeStyle = '#c084fc';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, y - 23, 6, Math.PI, 0);
    ctx.stroke();
    // Headphone cups
    ctx.fillStyle = '#c084fc';
    ctx.fillRect(x - 8, y - 26, 3, 4);
    ctx.fillRect(x + 5, y - 26, 3, 4);
  }

  function drawCommander(x, y, tick, phase) {
    const walk = Math.sin(tick * 0.18 + phase);
    const capeSway = Math.sin(tick * 0.08 + phase) * 3;
    // Cape (behind body — dark blue triangle, swaying)
    ctx.fillStyle = '#0a1a4a';
    ctx.beginPath();
    ctx.moveTo(x - 3, y - 13);
    ctx.lineTo(x + 3, y - 13);
    ctx.lineTo(x + capeSway, y);
    ctx.closePath();
    ctx.fill();
    // Legs
    ctx.fillStyle = '#004455';
    ctx.fillRect(x - 3, y - 5 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 5 - walk * 2, 2.5, 5);
    // Body (dark with cyan trim)
    ctx.fillStyle = '#0d2233';
    ctx.fillRect(x - 3, y - 13, 6, 8);
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 1;
    ctx.strokeRect(x - 3, y - 13, 6, 8);
    // Shoulder armour plate
    ctx.fillStyle = '#005577';
    ctx.fillRect(x - 7, y - 13, 14, 4);
    // Arms
    ctx.fillStyle = '#005577';
    ctx.fillRect(x - 7, y - 12 + walk * 2, 2, 5);
    ctx.fillRect(x + 5, y - 12 - walk * 2, 2, 5);
    // Helmet (cyan hexagon-ish)
    ctx.fillStyle = '#00e5ff';
    ctx.fillRect(x - 5, y - 25, 10, 10);
    // Visor T-shape
    ctx.fillStyle = '#001a22';
    ctx.fillRect(x - 4, y - 22, 8, 3);
    ctx.fillRect(x - 1, y - 25, 2, 8);
  }

  function drawForgeWorker(x, y, tick, phase) {
    const walk = Math.sin(tick * 0.18 + phase);
    // Legs (wide stance)
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 4, y - 5 + walk * 2, 3, 5);
    ctx.fillRect(x + 1, y - 5 - walk * 2, 3, 5);
    // Body (dark blue with orange hi-vis stripe)
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 4, y - 15, 8, 10);
    ctx.fillStyle = '#fb923c';
    ctx.fillRect(x - 4, y - 11, 8, 3);
    // Arms (wider)
    ctx.fillStyle = '#1a2233';
    ctx.fillRect(x - 8, y - 14 + walk * 2, 3, 6);
    ctx.fillRect(x + 5, y - 14 - walk * 2, 3, 6);
    // Wrench in right hand
    ctx.fillStyle = '#aaa';
    ctx.fillRect(x + 8, y - 15, 4, 2);
    ctx.fillRect(x + 9, y - 17, 2, 4);
    // Face
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 4, y - 23, 8, 8);
    // Hard hat (orange rounded rect + brim)
    ctx.fillStyle = '#fb923c';
    ctx.fillRect(x - 6, y - 27, 12, 6);
    // Brim line
    ctx.strokeStyle = '#c06000';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x - 7, y - 21);
    ctx.lineTo(x + 7, y - 21);
    ctx.stroke();
  }

  function drawMerchant(x, y, tick, phase) {
    const walk = Math.sin(tick * 0.18 + phase);
    const coinBounce = Math.abs(Math.sin(tick * 0.2 + phase)) * 3;
    // Legs
    ctx.fillStyle = '#1a3322';
    ctx.fillRect(x - 3, y - 5 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 5 - walk * 2, 2.5, 5);
    // Body (dark green with yellow buttons)
    ctx.fillStyle = '#0d2218';
    ctx.fillRect(x - 3, y - 15, 6, 10);
    ctx.fillStyle = '#ffb300';
    ctx.fillRect(x - 1, y - 14, 2, 2);
    ctx.fillRect(x - 1, y - 10, 2, 2);
    ctx.fillRect(x - 1, y - 6, 2, 2);
    // Arms
    ctx.fillStyle = '#0d2218';
    ctx.fillRect(x - 6, y - 14 + walk * 2, 2, 5);
    ctx.fillRect(x + 4, y - 14 - walk * 2, 2, 5);
    // Coin in right hand (bouncing)
    ctx.fillStyle = '#ffb300';
    ctx.shadowColor = '#ffb300';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(x + 8, y - 12 - coinBounce, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    // Monocle (tiny yellow circle at eye level)
    ctx.strokeStyle = '#ffb300';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(x + 1, y - 21, 2.5, 0, Math.PI * 2);
    ctx.stroke();
    // Face
    ctx.fillStyle = '#c8a882';
    ctx.fillRect(x - 4, y - 27, 8, 8);
    // Top hat (tall dark rect + brim)
    ctx.fillStyle = '#111';
    ctx.fillRect(x - 4, y - 37, 8, 10);
    // Hat brim
    ctx.fillRect(x - 6, y - 28, 12, 3);
  }

  function drawRaceEngineer(x, y, tick, phase) {
    const walk = Math.sin(tick * 0.18 + phase);
    const flagWave = Math.sin(tick * 0.2 + phase) * 4;
    // Legs
    ctx.fillStyle = '#8b0000';
    ctx.fillRect(x - 3, y - 5 + walk * 2, 2.5, 5);
    ctx.fillRect(x + 1, y - 5 - walk * 2, 2.5, 5);
    // Body (red jumpsuit with "1" on chest)
    ctx.fillStyle = '#cc0033';
    ctx.fillRect(x - 4, y - 15, 8, 10);
    // Racing number "1"
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 7px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('1', x, y - 7);
    // Arms
    ctx.fillStyle = '#cc0033';
    ctx.fillRect(x - 7, y - 14 + walk * 2, 2, 5);
    // Right arm raised holding flag
    ctx.fillRect(x + 5, y - 18, 2, 5);
    // Flag pole
    ctx.fillStyle = '#888';
    ctx.fillRect(x + 7, y - 24, 1, 8);
    // Chequered flag (alternating 2×2 squares) with wave
    const flagX = x + 8 + flagWave;
    for (let fi = 0; fi < 4; fi++) {
      for (let fj = 0; fj < 3; fj++) {
        ctx.fillStyle = ((fi + fj) % 2 === 0) ? '#ffffff' : '#000000';
        ctx.fillRect(flagX + fi * 2, y - 28 + fj * 2, 2, 2);
      }
    }
    // Face
    ctx.fillStyle = '#f4a460';
    ctx.fillRect(x - 4, y - 23, 8, 7);
    // Cap (red with brim)
    ctx.fillStyle = '#cc0033';
    ctx.fillRect(x - 6, y - 27, 12, 5);
    // Brim
    ctx.fillStyle = '#991122';
    ctx.fillRect(x - 6, y - 22, 8, 2);
  }

  // ── Ambient Particles ─────────────────────────────────────────────────────
  function spawnAmbientParticles() {
    BUILDINGS.forEach((b, bi) => {
      if (Math.random() > 0.3) return; // ~30% chance per frame per building
      const center = getBuildingCenter(b);
      const bx = center.x + (Math.random() - 0.5) * 30;
      const by = center.y + 10;

      let pType;
      switch (b.id) {
        case 'treasury':   pType = 'coin';  break;
        case 'pulsebreak': pType = 'note';  break;
        case 'pitwall':    pType = 'spark'; break;
        case 'command':    pType = 'data';  break;
        default: return; // no ambient for other buildings
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
          // Two dots + a stem
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
      const typeIdx = i % AGENT_TYPES.length;
      const from = BUILDINGS[i % BUILDINGS.length];
      const to   = BUILDINGS[(i + 2) % BUILDINGS.length];
      agents.push({
        id: i,
        typeIdx,
        type: AGENT_TYPES[typeIdx], // keep .type for burst color
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

    ctx.fillStyle = '#030410';
    ctx.fillRect(0, 0, w, h);

    drawStars();

    const scale = getScale();
    ctx.save();
    ctx.translate(w / 2, 0);
    ctx.scale(scale, scale);
    ctx.translate(-w / 2, 0);

    drawGround();
    drawRoads();

    BUILDINGS.forEach(b => {
      b.active = activeAgentData.some(j => j.status === 'running');
    });

    // Ambient particles (drawn before buildings)
    spawnAmbientParticles();
    drawAmbientParticles();

    // Draw buildings back→front
    const sorted = [...BUILDINGS].sort((a, b) => (a.col + a.row) - (b.col + b.row));
    sorted.forEach(b => drawBuilding(b));

    // Agents sorted by y (painter's algorithm)
    [...agents].sort((a, b) => a.y - b.y).forEach(a => drawAgent(a));

    // Burst particles
    updateAndDrawParticles();

    // Bubbles
    bubbles.forEach(b => drawBubble(b));

    ctx.restore();

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
