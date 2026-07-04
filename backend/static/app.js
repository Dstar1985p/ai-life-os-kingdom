/* ══════════════════════════════════════════════════════════
   KINGDOM OS — Frontend JavaScript
   ══════════════════════════════════════════════════════════ */

/* ─── UTILS ─── */
async function fetchJSON(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return await r.json();
  } catch(e) { return null; }
}

function badge(status) {
  const map = {
    green: '<span class="badge badge-green">● ON TRACK</span>',
    amber: '<span class="badge badge-amber">● CAUTION</span>',
    red: '<span class="badge badge-red">● AT RISK</span>',
  };
  return map[status] || '<span class="badge badge-muted">● UNKNOWN</span>';
}

function fmtMoney(n) { return '£' + (parseFloat(n)||0).toFixed(2); }
function fmtPct(n) { return (parseFloat(n)||0).toFixed(1) + '%'; }

/* ─── TAB NAVIGATION ─── */
function showTab(tab) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  const page = document.getElementById('page-' + tab);
  if (page) page.classList.add('active');
  const tabBtn = document.querySelector(`[data-tab="${tab}"]`);
  if (tabBtn) tabBtn.classList.add('active');
  // Lazy-load tab data
  if (tab === 'pitwall') loadPitwallTab();
  if (tab === 'pulsebreak') loadPulsebreakTab();
  if (tab === 'agents') loadAgentsTab();
  if (tab === 'opportunities') loadOpportunitiesTab();
  if (tab === 'livery') loadLiveryTab();
  if (tab === 'intelligence') loadIntelligenceTab();
  if (tab === 'command') loadCommandTab();
  if (tab === 'tools') loadToolsTab();
  if (tab === 'roadmap') loadGoldStandard();
}

/* ─── OVERVIEW ─── */
async function loadOverview() {
  const [kingdomData, schedulerStatus] = await Promise.all([
    loadKingdomMap(),
    fetchJSON('/scheduler/status'),
  ]);
  renderScheduler(schedulerStatus);

  // Load other panels in parallel
  const [brief, health, lessons, revenueData, recon, mission] = await Promise.all([
    fetchJSON('/brief/morning'),
    fetchJSON('/kingdom/health'),
    fetchJSON('/lessons'),
    fetchJSON('/revenue/insights'),
    fetchJSON('/revenue-recon'),
    loadDailyMission(),
  ]);

  renderActivity(kingdomData?.agent_activity || [], lessons || []);
  renderMissionPanel(mission);
  renderRevenue(revenueData);
  renderHealth(health, brief);
  renderRecon(recon);
  loadAttribution();
  loadReminders();
  loadRetro();
}

/* ─── KINGDOM MAP CANVAS ─── */
let _kingdomDistricts = [];
let _animFrame = null;
let _canvasData = {};
let activeDistrict = null;

function initCanvas() {
  // Use fullscreen canvas in game-root; fall back to old canvas
  const canvas = document.getElementById('kingdom-map-canvas-fullscreen') ||
                 document.getElementById('kingdom-map-canvas');
  if (!canvas) return;
  // Ensure the fullscreen canvas fills its container
  canvas.id = 'kingdom-map-canvas-fullscreen';
  KingdomISO.init(canvas);
}
// ── LEGACY CANVAS STUB (replaced by KingdomISO) ──


async function loadKingdomMap() {
  const data = await fetchJSON('/kingdom/map');
  if (!data) return null;
  _kingdomDistricts = data.districts || [];
  const res = data.resources || {};
  const setRes = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setRes('res-gold', fmtMoney(res.gold));
  setRes('res-knowledge', res.knowledge || 0);
  setRes('res-focus', fmtPct(res.focus));
  setRes('res-stability', (res.stability||0) + '/100');

  // Update canvas status
  if (_canvasData.statusMap) {
    (_kingdomDistricts||[]).forEach(d => {
      const active = (d.active_agents||0) > 0;
      const key = (d.id||'').replace(/_/g,'');
      _canvasData.statusMap[key] = active;
    });
  }

  // Build district cards
  const order = ['pulsebreak_arena','command_tower','venture_lab','pitwall_workshop','printify_studio','knowledge_vault'];
  const html = order.map(id => {
    const d = _kingdomDistricts.find(x=>x.id===id);
    if (!d) return '';
    const workers = d.active_agents > 0 ?
      `<div class="district-workers">${Array(Math.min(d.active_agents,3)).fill('<div class="worker-dot"></div>').join('')}</div>` : '';
    return `<div class="district-card" style="--glow:rgba(${glowByDistrict(d.id)},0.08)" onclick="toggleDistrict('${d.id}')">
      <div class="district-emoji">${d.emoji}</div>
      <div class="district-name">${d.name}</div>
      <div class="district-desc">${d.description}</div>
      ${workers}
    </div>`;
  }).join('');
  document.getElementById('kingdom-map').innerHTML = html;
  return data;
}

function glowByDistrict(id) {
  const m = {pulsebreak_arena:'192,132,252',command_tower:'0,229,255',venture_lab:'0,255,136',
    pitwall_workshop:'255,179,0',printify_studio:'251,146,60',knowledge_vault:'96,165,250'};
  return m[id] || '255,255,255';
}

const DISTRICT_ACTIONS = {
  pitwall_workshop:[{label:'▶ Print Forge AI',fn:"triggerAgent('Print Forge AI')"},{label:'▶ Printify Studio',fn:"triggerAgent('Printify Studio')"},{label:'🔍 SEO Agent',fn:"triggerAgent('SEO Agent')"},{label:'💰 Price Optimizer',fn:"triggerAgent('Price Optimizer')"}],
  pulsebreak_arena:[{label:'▶ Vibes AI',fn:"triggerAgent('Vibes AI')"},{label:'▶ Music Licensing',fn:"triggerAgent('Music Licensing')"},{label:'📱 Content Agent',fn:"triggerAgent('Content Agent')"}],
  command_tower:[{label:'🔧 AI Engineer',fn:"triggerAgent('AI Engineer')"},{label:'▶ Opportunity Scout',fn:"triggerAgent('Opportunity Scout')"},{label:'📈 Revenue Forecaster',fn:"triggerAgent('Revenue Forecaster')"}],
  venture_lab:[{label:'▶ Opportunity Scout',fn:"triggerAgent('Opportunity Scout')"},{label:'▶ ROI Reaper',fn:"triggerAgent('ROI Reaper')"},{label:'▶ Trend Watcher',fn:"triggerAgent('Trend Watcher')"}],
  printify_studio:[{label:'▶ Printify Studio',fn:"triggerAgent('Printify Studio')"},{label:'💰 Price Optimizer',fn:"triggerAgent('Price Optimizer')"}],
  knowledge_vault:[{label:'🔧 AI Engineer',fn:"triggerAgent('AI Engineer')"},{label:'📥 Export Report',fn:"window.open('/export/weekly-report.txt','_blank')"}],
};

function toggleDistrict(id) {
  const el = document.getElementById('district-detail');
  if (activeDistrict===id) { el.classList.remove('active'); activeDistrict=null; return; }
  activeDistrict=id; el.classList.add('active');
  const d = _kingdomDistricts.find(x=>x.id===id);
  if (!d) return;
  document.getElementById('detail-title').textContent = `${d.emoji} ${d.name}`;
  const rows = Object.entries(d.stats||{}).map(([k,v]) => {
    const val = typeof v==='number'?(Number.isInteger(v)?v:v.toFixed(2)):v;
    return `<div class="detail-metric"><span style="color:var(--muted)">${k.replace(/_/g,' ')}</span><span style="color:var(--text);font-weight:600">${val}</span></div>`;
  }).join('');
  const acts = DISTRICT_ACTIONS[id]||[];
  const btns = acts.map(a=>`<button onclick="${a.fn};document.getElementById('district-action-result').textContent='Running...';" class="btn btn-sm" style="margin-right:5px;margin-bottom:5px">${a.label}</button>`).join('');
  document.getElementById('detail-content').innerHTML =
    (rows?`<div style="margin-bottom:12px">${rows}</div>`:'') +
    '<div style="font-size:0.62rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-bottom:8px">Quick Actions</div>' +
    `<div style="display:flex;flex-wrap:wrap;gap:5px">${btns||'<div style="color:var(--muted)">No actions</div>'}</div>` +
    '<div id="district-action-result" style="font-size:0.72rem;color:var(--green);margin-top:8px;min-height:18px"></div>';
}

/* ─── TICKER ─── */


/* ─── ACTIVITY FEED ─── */
function renderActivity(runs, lessons) {
  const items = [];
  (runs||[]).slice(0,5).forEach(r => {
    items.push(`<div class="activity-item">
      <div class="activity-time">${new Date(r.run_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</div>
      <div><div class="activity-agent">${r.agent}</div><div class="activity-text">ran — ${fmtMoney(r.revenue_gbp||0)} attributed</div></div>
    </div>`);
  });
  (lessons||[]).slice(0,4).forEach(l => {
    const text = (l.lesson||'').slice(0,80);
    items.push(`<div class="activity-item">
      <div class="activity-time" style="color:var(--purple)">${l.source||'system'}</div>
      <div class="activity-text" style="color:var(--muted)">${text}${(l.lesson||'').length>80?'…':''}</div>
    </div>`);
  });
  const el = document.getElementById('activity-feed');
  if (el) el.innerHTML = items.length ? items.join('') : '<div style="color:var(--muted);font-size:0.75rem;padding:8px 0">No recent activity</div>';
}

/* ─── SCHEDULER ─── */
function renderScheduler(status) {
  const agents = status?.agents||[];
  const el = document.getElementById('scheduler-status');
  if (!el) return;
  if (!agents.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">Scheduler not running</div>'; return; }
  el.innerHTML = agents.slice(0,8).map(a => `<div class="agent-chip" onclick="triggerAgent('${a.name}')" title="Click to run now">
    <span class="pulse-dot ${a.scheduler_running?'green':'muted'}"></span>
    <div class="chip-info"><div class="chip-name">${a.name}</div><div class="chip-interval">${a.interval}</div></div>
    <span class="chip-run">▶</span>
  </div>`).join('');
}

/* ─── REVENUE ─── */
function renderRevenue(data) {
  const el = document.getElementById('revenue-content');
  if (!el) return;
  if (!data) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No revenue data</div>'; return; }
  el.innerHTML = `
    <div class="big-metric" style="margin-bottom:12px">
      <div class="value" style="color:var(--amber)">${fmtMoney(data.total_estimated_revenue||0)}</div>
      <div class="label">Total Estimated Revenue</div>
    </div>
    <div class="metric-row"><span class="metric-key">Top Theme</span><span class="metric-val">${data.top_theme||'—'}</span></div>
    <div class="metric-row"><span class="metric-key">Top Category</span><span class="metric-val">${data.top_category||'—'}</span></div>
    <div class="metric-row"><span class="metric-key">Concentration</span><span class="metric-val">${data.concentration_pct||0}%</span></div>
    <div class="metric-row"><span class="metric-key">Confidence</span><span class="metric-val">${data.confidence||0}%</span></div>
    <div style="margin-top:10px;font-size:0.75rem;color:var(--cyan);padding:8px;background:rgba(0,229,255,0.05);border-radius:8px;border:1px solid rgba(0,229,255,0.12)">
      ▸ ${data.recommended_next_product||'Validate demand first'}
    </div>`;
}

/* ─── HEALTH ─── */
function renderHealth(health, brief) {
  const el = document.getElementById('health-content');
  if (!el) return;
  const ks = brief?.kingdom_health_status || 'amber';
  const colMap = {green:'var(--green)',amber:'var(--amber)',red:'var(--red)'};
  el.innerHTML = `
    <div class="big-metric" style="margin-bottom:12px">
      <div class="value" style="color:${colMap[ks]||'var(--amber)'}">${badge(ks)}</div>
      <div class="label">Kingdom Status</div>
    </div>
    ${brief ? `
    <div class="metric-row"><span class="metric-key">Founder Capacity</span><span class="metric-val">${brief.founder_capacity||'—'}%</span></div>
    <div class="metric-row"><span class="metric-key">Decision Accuracy</span><span class="metric-val">${((brief.decision_accuracy||0)*100).toFixed(0)}%</span></div>
    <div class="metric-row"><span class="metric-key">Assumption Risk</span><span class="metric-val" style="color:var(--amber);font-size:0.72rem">${(brief.assumption_risk||'').slice(0,35)}</span></div>
    ` : '<div style="color:var(--muted);font-size:0.75rem">No brief data</div>'}`;
}

/* ─── RECON ─── */
function renderRecon(recon) {
  // used in opportunities tab
  const el = document.getElementById('recon-content');
  if (!el || !recon || !recon.length) return;
  el.innerHTML = recon.slice(0,5).map(r => {
    const ks = r.kingdom_score||0;
    return `<div class="opp-card">
      <div class="opp-card-header">
        <div class="opp-title">${r.title.slice(0,50)}</div>
        <div class="opp-score">${ks}</div>
      </div>
      <div class="opp-meta">${r.category||''}</div>
      ${badge(r.traffic_light_status||'amber')}
    </div>`;
  }).join('');
}

/* ─── ATTRIBUTION ─── */
async function loadAttribution() {
  const el = document.getElementById('attribution-content');
  if (!el) return;
  try {
    const data = await fetchJSON('/revenue-attribution/summary');
    if (!data || !data.category_weights || !data.category_weights.length) {
      el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem;padding:8px 0">No attribution data yet — sales will appear here once Etsy orders are matched to listings.</div>';
      return;
    }
    const max = Math.max(...data.category_weights.map(w=>w.weight), 1);
    el.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px">` +
      data.category_weights.map(w => {
        const pct = Math.round((w.weight/max)*100);
        return `<div class="attr-row" style="flex-direction:column;padding:10px;border:1px solid var(--border);border-radius:10px;background:var(--surface)">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span class="attr-cat">${w.category}</span>
            <span class="attr-sales">${w.sales_count||0} sales</span>
          </div>
          <div class="progress-bar" style="margin:0"><div class="progress-fill green" style="width:${pct}%"></div></div>
          <div style="display:flex;justify-content:space-between;margin-top:4px">
            <span style="font-size:0.62rem;color:var(--muted)">Weight</span>
            <span style="font-size:0.68rem;color:var(--cyan)">${w.weight.toFixed(3)}</span>
          </div>
        </div>`;
      }).join('') + '</div>';
  } catch(e) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">Attribution data unavailable</div>';
  }
}

/* ─── RETRO ─── */
async function loadRetro() {
  try {
    const retro = await fetchJSON('/retro/latest');
    if (!retro || !retro.week_start) return;
    const card = document.getElementById('retro-card');
    if (card) card.style.display = '';
    const wins = (retro.wins||[]).map(w=>`<div style="font-size:0.75rem;color:var(--green);padding:3px 0">✅ ${w}</div>`).join('');
    const missed = (retro.missed||[]).map(m=>`<div style="font-size:0.75rem;color:var(--amber);padding:3px 0">⚠ ${m}</div>`).join('');
    const insights = (retro.insights||[]).map(i=>`<div style="font-size:0.75rem;color:var(--cyan);padding:3px 0">▸ ${i}</div>`).join('');
    const el = document.getElementById('retro-content');
    if (el) el.innerHTML = `
      <div style="font-size:0.7rem;color:var(--muted);margin-bottom:10px">Week of ${retro.week_start} · Score: <span style="color:var(--amber);font-weight:700">${retro.performance_score||'?'}/100</span></div>
      ${wins}${missed}${insights}`;
  } catch(e) {}
}
async function generateRetro() {
  try {
    await fetch('/retro/generate', {method:'POST'});
    showToast('Retro regenerated', 'success');
    loadRetro();
  } catch(e) { showToast('Error', 'error'); }
}

/* ─── MISSION ─── */
async function loadDailyMission() {
  try {
    return await fetchJSON('/mission/today');
  } catch(e) { return null; }
}
function renderMissionPanel(m) {
  const el = document.getElementById('mission-panel-content');
  if (!el) return;
  if (!m) { el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">No mission data</div>'; return; }
  const rankClass = r => r===1?'':r===2?' rank-2':' rank-3';
  const actions = (m.actions||[]).map(a => `
    <div class="mission-action">
      <div class="mission-rank${rankClass(a.rank)}">${a.rank}</div>
      <div class="mission-content">
        <div class="mission-title">${a.title||''}</div>
        <div class="mission-why">${a.why||''}</div>
        <div class="mission-meta">~${a.estimated_minutes||'?'} min · ${a.venture||''} · ${a.agent||''}</div>
        <div class="outcome-btns">
          <button class="outcome-btn pos" onclick="recordOutcome('quest',${a.quest_id||0},'positive',this)">✓ Done &amp; worked</button>
          <button class="outcome-btn neg" onclick="recordOutcome('quest',${a.quest_id||0},'negative',this)">✗ Skipped</button>
        </div>
      </div>
    </div>`).join('');
  el.innerHTML = `
    <div class="mission-theme">${m.theme||'Daily Focus'}</div>
    <div class="mission-motivational">${m.motivational_line||''}</div>
    ${actions}
    <div style="margin-top:10px;text-align:right"><button id="mission-regen-btn" onclick="regenerateMission()" class="btn btn-sm">↻ Regenerate</button></div>`;
}
async function regenerateMission() {
  const btn = document.getElementById('mission-regen-btn');
  if (btn) { btn.textContent = 'Generating...'; btn.disabled = true; }
  try {
    const m = await fetch('/mission/regenerate', {method:'POST'}).then(r=>r.json());
    renderMissionPanel(m);
  } catch(e) { if(btn) { btn.textContent='↻ Regenerate'; btn.disabled=false; } }
}

/* ─── REMINDERS ─── */
async function loadReminders() {
  try {
    const data = await fetchJSON('/reminders/active');
    if (!data) return;
    const count = data.count||0;
    const badge = document.getElementById('reminders-badge');
    const badge2 = document.getElementById('reminder-count-badge');
    [badge, badge2].forEach(b => {
      if (!b) return;
      b.textContent = count;
      b.style.display = count>0 ? 'inline-flex' : 'none';
    });
    const el = document.getElementById('reminders-panel-content');
    if (el) renderRemindersList(data.reminders||[], el);
  } catch(e) {}
}
function renderRemindersList(reminders, el) {
  if (!reminders.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem;padding:8px 0">No active reminders — kingdom is on track!</div>'; return; }
  const sevColor = s => s==='urgent'?'var(--red)':s==='warning'?'var(--amber)':'var(--muted)';
  el.innerHTML = reminders.map(r => `
    <div class="mission-action" style="border-color:${sevColor(r.severity)}30">
      <div class="mission-content">
        <div class="mission-title" style="color:${sevColor(r.severity)}">${r.title}</div>
        <div class="mission-why">${r.description}</div>
        <button onclick="dismissReminder('${r.id}',this)" class="btn btn-xs" style="margin-top:6px">Dismiss</button>
      </div>
    </div>`).join('');
}
async function dismissReminder(id, btn) {
  if (btn) btn.disabled = true;
  try {
    await fetch(`/reminders/dismiss/${encodeURIComponent(id)}`, {method:'POST'});
    loadReminders();
  } catch(e) { if(btn) btn.disabled=false; }
}

/* ─── AGENT TRIGGER ─── */
async function triggerAgent(name) {
  const el = document.getElementById('action-result');  // legacy hook, may be absent
  showToast(`Running ${name}…`, 'info', 2500);
  if (el) { el.style.color='var(--amber)'; el.textContent=`Running ${name}...`; }
  try {
    const r = await fetch(`/scheduler/run/${encodeURIComponent(name)}`, {method:'POST'});
    const d = await r.json();
    if (d.status==='ok') {
      showToast(`✓ ${name} finished`, 'success');
      if (el) { el.style.color='var(--green)'; el.textContent=`✓ ${name}: ${d.opportunities_created||0} new`; }
      if ((d.opportunities_created||0)>0) triggerCelebration('AGENT SUCCESS!', name+': '+(d.opportunities_created||0)+' new opportunities','🔥');
      setTimeout(() => {
        loadKingdomMap(); loadAttribution();
        // Refresh visible panel content so the run's output appears immediately
        try {
          if (typeof loadLicensingConcepts === 'function') loadLicensingConcepts();
          if (typeof loadContentPosts === 'function') loadContentPosts();
          if (typeof loadReviewQueue === 'function') loadReviewQueue();
          if (typeof refreshTodayBadge === 'function') refreshTodayBadge();
        } catch(_) {}
      }, 800);
    } else {
      if (el) { el.style.color='var(--red)'; el.textContent=`✗ ${d.error||'Error'}`; }
    }
    showToast(`${name}: ${d.status==='ok'?'Success':'Failed'}`, d.status==='ok'?'success':'error');
  } catch(e) {
    if (el) { el.style.color='var(--red)'; el.textContent='✗ Request failed'; }
    showToast('Request failed', 'error');
  }
}

async function triggerAgentInPanel(name, statusId) {
  const el = statusId ? document.getElementById(statusId) : null;
  if (el) { el.style.display='block'; el.style.color='var(--amber)'; el.textContent=`⏳ Running ${name}…`; }
  showToast(`${name} starting…`, 'info');
  try {
    const r = await fetch(`/scheduler/run/${encodeURIComponent(name)}`, {method:'POST'});
    const d = await r.json();
    if (d.status==='ok') {
      const msg = `✓ ${name} done · ${d.opportunities_created||0} new · ${d.actions_taken||0} actions`;
      if (el) { el.style.color='var(--green)'; el.textContent=msg; }
      showToast(msg, 'success');
      if ((d.opportunities_created||0)>0) triggerCelebration('AGENT SUCCESS!', name,'🔥');
      setTimeout(() => { loadPulsebreakTab(); }, 800);
    } else {
      const msg = `✗ ${d.error||'Agent failed'}`;
      if (el) { el.style.color='var(--red)'; el.textContent=msg; }
      showToast(msg, 'error');
    }
    setTimeout(() => { if(el) el.style.display='none'; }, 8000);
  } catch(e) {
    if (el) { el.style.color='var(--red)'; el.textContent='✗ Network error'; }
    showToast('Request failed', 'error');
  }
}

async function runAllAgents() {
  const names = ['Print Forge AI', 'Vibes AI', 'Opportunity Scout', 'SEO Agent', 'Content Agent'];
  showToast('Running all agents…', 'info');
  for (const n of names) await triggerAgent(n);
  showToast('All agents complete', 'success');
}

/* ─── PITWALL TAB ─── */
async function loadPitwallTab() {
  const [listings, revenueData, orders] = await Promise.all([
    fetchJSON('/leaderboard/opportunities?category=Pitwall'),
    fetchJSON('/revenue/insights'),
    fetchJSON('/printify/orders'),
  ]);
  renderPitwallListings(listings);
  renderPitwallEtsy(revenueData);
  loadABTests();
  renderOrders(orders);
  loadAvatars('Pitwall Classics');
}

function renderPitwallListings(data) {
  const el = document.getElementById('pitwall-listings');
  if (!el) return;
  const items = Array.isArray(data) ? data.filter(o=>(o.category||'').includes('Pitwall')) : [];
  if (!items.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No Pitwall listings yet — run Print Forge AI</div>'; return; }
  el.innerHTML = items.slice(0,6).map((o,i) => `<div class="lb-row">
    <div class="lb-rank ${['r1','r2','r3'][i]||'rn'}">${i+1}</div>
    <div><div class="lb-title">${o.title.slice(0,45)}</div><div class="lb-cat">${o.category||''}</div></div>
    <div class="lb-score">${o.kingdom_score||0}</div>
  </div>`).join('');
}

function renderPitwallEtsy(data) {
  const el = document.getElementById('pitwall-etsy');
  if (!el || !data) return;
  el.innerHTML = `
    <div class="big-metric" style="margin-bottom:14px">
      <div class="value" style="color:var(--amber)">${fmtMoney(data.total_estimated_revenue||0)}</div>
      <div class="label">Estimated Revenue</div>
    </div>
    <div class="metric-row"><span class="metric-key">Top Category</span><span class="metric-val">${data.top_category||'—'}</span></div>
    <div class="metric-row"><span class="metric-key">Top Theme</span><span class="metric-val">${data.top_theme||'—'}</span></div>
    <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-amber btn-sm" onclick="triggerAgent('Print Forge AI')">▶ Print Forge</button>
      <button class="btn btn-sm" onclick="triggerAgent('SEO Agent')">🔍 SEO</button>
      <button class="btn btn-sm" onclick="triggerAgent('Price Optimizer')">💰 Prices</button>
    </div>`;
}

/* ─── A/B TESTS ─── */
async function loadABTests() {
  const el = document.getElementById('ab-tests-list');
  if (!el) return;
  try {
    const data = await fetchJSON('/launch/ab-tests');
    if (!data || !data.length) {
      el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">No A/B tests yet — create your first test below</div>';
      return;
    }
    el.innerHTML = data.slice(0,4).map(t => {
      const va = t.variant_a||{}, vb = t.variant_b||{};
      const winner = t.winner;
      return `<div class="ab-card">
        <div class="ab-header">
          <div class="ab-name">${t.name}</div>
          <div>${badge(t.status==='running'?'amber':t.status==='complete'?'green':'muted')}</div>
        </div>
        <div class="ab-variants">
          <div class="ab-variant ${winner==='a'?'winner':''}">
            <div class="ab-variant-label">A ${winner==='a'?'👑':''}</div>
            <div style="font-size:0.72rem;color:var(--text)">${va.label||t.variant_a_text||'—'}</div>
            <div style="font-size:0.68rem;color:var(--muted);margin-top:3px">Conv: ${va.conversions||0}</div>
          </div>
          <div class="ab-variant ${winner==='b'?'winner':''}">
            <div class="ab-variant-label">B ${winner==='b'?'👑':''}</div>
            <div style="font-size:0.72rem;color:var(--text)">${vb.label||t.variant_b_text||'—'}</div>
            <div style="font-size:0.68rem;color:var(--muted);margin-top:3px">Conv: ${vb.conversions||0}</div>
          </div>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">A/B test data unavailable</div>';
  }
}

function showABTestForm() {
  const f = document.getElementById('ab-test-form');
  if (f) f.style.display = f.style.display==='none' ? '' : 'none';
}

async function createABTest() {
  const name = document.getElementById('ab-name')?.value?.trim();
  const vA = document.getElementById('ab-variant-a')?.value?.trim();
  const vB = document.getElementById('ab-variant-b')?.value?.trim();
  const venture = document.getElementById('ab-venture')?.value;
  const metric = document.getElementById('ab-metric')?.value;
  if (!name || !vA || !vB) { showToast('Fill in all fields', 'warning'); return; }
  try {
    const res = await fetch('/launch/ab-tests', {method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,variant_a_text:vA,variant_b_text:vB,venture,metric})});
    const d = await res.json();
    showToast('A/B Test created', 'success');
    document.getElementById('ab-test-form').style.display='none';
    loadABTests();
  } catch(e) { showToast('Failed to create test', 'error'); }
}

/* ─── ORDERS ─── */
async function loadOrders() {
  const el = document.getElementById('orders-list');
  if (!el) return;
  const data = await fetchJSON('/printify/orders');
  renderOrders(data);
}
function renderOrders(data) {
  const el = document.getElementById('orders-list');
  if (!el) return;
  const orders = data?.orders || data || [];
  if (!orders.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No orders yet</div>'; return; }
  el.innerHTML = orders.slice(0,6).map(o => `<div class="lb-row">
    <div style="flex:1">
      <div style="font-size:0.78rem;font-weight:600;color:var(--text)">${o.title||o.product_title||'Order'}</div>
      <div style="font-size:0.65rem;color:var(--muted)">${o.status||''} · ${new Date(o.created_at||o.date||Date.now()).toLocaleDateString()}</div>
    </div>
    <span class="badge badge-green">${fmtMoney(o.revenue||o.item_price||0)}</span>
  </div>`).join('');
}

/* ─── AVATARS ─── */
async function loadAvatars(venture) {
  const el = document.getElementById('avatars-list');
  if (!el) return;
  const url = venture ? `/avatars?venture=${encodeURIComponent(venture)}` : '/avatars';
  const data = await fetchJSON(url);
  const avatars = data?.avatars || data || [];
  if (!avatars.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No customer avatars yet</div>'; return; }
  el.innerHTML = avatars.slice(0,4).map(a => `<div class="track-card">
    <div class="track-art" style="background:linear-gradient(135deg,#0a1a0a,#0a1433)">🧑</div>
    <div class="track-info">
      <div class="track-title">${a.name||'Avatar'}</div>
      <div class="track-genre">${a.venture||''} · ${a.age_range||''}</div>
      <div class="track-meta">${asList(a.pain_points).slice(0,2).join(' · ')}</div>
    </div>
  </div>`).join('');
}

/* ─── PULSEBREAK TAB ─── */
async function loadPulsebreakTab() {
  loadRenderStatus();
  loadReviewQueue();
  loadTrackLibrary();
  loadLicensingConcepts();
  loadPitchTracker();
  loadSoundDNA();
  loadLicensingRevenue();
  loadYouTubeContent();
  loadContentPosts();
}

async function loadRenderStatus() {
  const host = document.getElementById('review-queue');
  if (!host) return;
  let strip = document.getElementById('render-status-strip');
  try {
    const d = await fetchJSON('/vibes/render-status');
    const jobs = (d.jobs || []).filter(j => j.status !== 'done' || ((Date.now() - new Date(j.finished_at)) < 36e5));
    if (!jobs.length) { if (strip) strip.remove(); return; }
    if (!strip) {
      strip = document.createElement('div');
      strip.id = 'render-status-strip';
      host.parentElement.insertBefore(strip, host);
    }
    const ICONS = { queued:'⏳', rendering:'🎬', uploading:'⬆️', done:'✅', error:'❌' };
    strip.innerHTML = jobs.map(j => `
      <div style="display:flex;gap:8px;align-items:center;border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-bottom:6px;background:var(--surface);font-size:0.72rem">
        <span>${ICONS[j.status]||'•'}</span>
        <div style="flex:1;min-width:0">
          <div style="font-weight:600">${j.track_name}</div>
          <div style="color:var(--muted)">${j.detail||j.status}</div>
        </div>
      </div>`).join('');
    if (jobs.some(j => ['queued','rendering','uploading'].includes(j.status))) {
      setTimeout(loadRenderStatus, 15000);
    }
  } catch (_) {}
}

async function loadReviewQueue() {
  const el = document.getElementById('review-queue');
  if (!el) return;
  try {
    const data = await fetchJSON('/vibes/review');
    const queue = data?.tracks || data?.queue || data || [];
    if (!queue.length) {
      el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem;padding:8px 0">Review queue empty — upload a track to get started</div>';
      return;
    }
    el.innerHTML = queue.slice(0,5).map(t => { const name = t.track_name||t.id; return `<div class="track-card">
      <div class="track-art">🎵</div>
      <div class="track-info">
        <div class="track-title">${name}</div>
        <div class="track-genre">${t.sub_genre||t.genre||'DnB'} · ${t.bpm||'?'} BPM</div>
        <div class="track-meta">Quality: ${t.quality_score??'pending'}${t.duration_secs?` · ${Math.round(t.duration_secs)}s`:''}</div>
        <audio controls preload="none" data-track="${name}" onplay="onReviewAudioPlay(this)" onpause="onReviewAudioStop(this)" onended="onReviewAudioStop(this)" style="width:100%;height:36px;margin:8px 0 4px" src="/vibes/review/${encodeURIComponent(name)}/audio"></audio>
        <div class="track-actions">
          <button class="btn btn-green btn-xs" onclick="approveTrack('${name}',this)">✓ Approve</button>
          <button class="btn btn-red btn-xs" onclick="rejectTrack('${name}',this)">✗ Reject</button>
        </div>
      </div>
    </div>`; }).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">Review queue unavailable</div>';
  }
}

async function loadTrackLibrary() {
  const el = document.getElementById('track-library');
  if (!el) return;
  try {
    const data = await fetchJSON('/vibes/library');
    const tracks = data?.tracks || data || [];
    if (!tracks.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem;padding:8px 0">No tracks yet</div>'; return; }
    el.innerHTML = tracks.slice(0,10).map(t => `<div class="track-card">
      <div class="track-art" style="background:linear-gradient(135deg,#1a0533,#0a1a33)">🎵</div>
      <div class="track-info">
        <div class="track-title">${t.track_name||t.title||t.filename||'Track'}</div>
        <div class="track-genre">${t.sub_genre||t.genre||'DnB'} · ${t.bpm||'?'} BPM</div>
        <div class="track-meta">${t.status||''}${t.audio_available===false?' · <span style="color:var(--amber)">⚠ audio file lost — metadata kept for Sound DNA; re-upload to release</span>':''}</div>
      </div>
      <div class="track-score">${t.quality_score||'—'}</div>
    </div>`).join('') +
    `<div style="font-size:0.62rem;color:var(--muted);margin-top:6px">${tracks.length} track(s) in library — every upload feeds the Sound DNA, whatever its status.</div>`;
  } catch(e) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">Track library unavailable</div>';
  }
}

async function approveTrack(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'Approving…'; }
  try {
    const r = await fetch(`/vibes/review/${encodeURIComponent(id)}/approve`, {method:'POST'});
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    buzz([12, 40, 12]);
    showToast('✓ Approved — video render queued (takes a while, watch the strip above)', 'success', 5000);
    loadReviewQueue(); loadTrackLibrary(); loadRenderStatus();
  } catch(e) {
    showToast('Approve failed: ' + e.message, 'error', 5000);
    if (btn) { btn.disabled = false; btn.textContent = '✓ Approve'; }
  }
}

async function rejectTrack(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'Rejecting…'; }
  try {
    const r = await fetch(`/vibes/review/${encodeURIComponent(id)}/reject`, {method:'POST'});
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    showToast('Track rejected', 'info');
    loadReviewQueue();
  } catch(e) {
    showToast('Reject failed: ' + e.message, 'error', 5000);
    if (btn) { btn.disabled = false; btn.textContent = '✗ Reject'; }
  }
}

/* ─── FILE UPLOAD ─── */
function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.add('drag-over');
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.remove('drag-over');
  const file = e.dataTransfer?.files?.[0];
  if (file) { uploadTrack(file); startAudioVisualiser(file); }
}
function handleFileSelect(e) {
  const file = e.target.files?.[0];
  if (file) { uploadTrack(file); startAudioVisualiser(file); }
}
function uploadTrack(file) {
  const progressEl = document.getElementById('upload-progress');
  const pct = document.getElementById('upload-pct');
  const bar = document.getElementById('upload-bar');
  const fname = document.getElementById('upload-filename');
  if (progressEl) progressEl.style.display = '';
  if (fname) fname.textContent = file.name;

  const formData = new FormData();
  formData.append('file', file);
  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) {
      const p = Math.round(e.loaded/e.total*100);
      if (pct) pct.textContent = p+'%';
      if (bar) bar.style.width = p+'%';
    }
  };
  xhr.onload = () => {
    if (xhr.status===200||xhr.status===201) {
      showToast('Track uploaded successfully!', 'success');
      triggerCelebration('TRACK UPLOADED!', file.name, '🎵');
      setTimeout(() => { loadReviewQueue(); loadTrackLibrary(); }, 500);
    } else {
      showToast('Upload failed: '+xhr.statusText, 'error');
    }
    if (progressEl) progressEl.style.display = 'none';
  };
  xhr.onerror = () => { showToast('Upload failed', 'error'); if(progressEl) progressEl.style.display='none'; };
  xhr.open('POST', '/vibes/library/upload');
  xhr.send(formData);
}

/* ─── LICENSING ─── */
async function loadLicensingConcepts() {
  const el = document.getElementById('licensing-concepts-list');
  if (!el) return;
  try {
    const data = await fetchJSON('/music-licensing/concepts');
    if (!data?.concepts?.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No concepts yet — click Generate</div>'; return; }
    el.innerHTML = data.concepts.slice(0,5).map((c, i) => {
      const ev=c.evidence||{};
      const title = ev.track_title||c.title||'Concept';
      const platforms = ev.recommended_platforms||[];
      return `<div class="track-card" style="flex-direction:column;gap:8px">
        <div style="display:flex;gap:10px;align-items:flex-start">
          <div class="track-art" style="font-size:1.2rem">💿</div>
          <div class="track-info" style="flex:1">
            <div class="track-title">${title}</div>
            <div class="track-genre">${ev.sub_genre||''} ${platforms.length?'· '+platforms.join(', '):''}</div>
            ${ev.estimated_monthly_revenue_gbp?`<div class="track-meta" style="color:var(--green)">Est. £${ev.estimated_monthly_revenue_gbp.toFixed(2)}/mo</div>`:''}
          </div>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-xs btn-primary" onclick="pitchConcept(${i},'${encodeURIComponent(title)}')">📤 Pitch</button>
          <button class="btn btn-xs" style="border-color:rgba(0,229,255,0.4);color:var(--cyan)" onclick="copyConceptBrief(${i},'${encodeURIComponent(JSON.stringify(ev))}')">📋 Copy Brief</button>
          <button class="btn btn-xs" style="border-color:rgba(0,255,102,0.4);color:var(--green)" onclick="draftLicenseEmail(${i},'${encodeURIComponent(title)}','${platforms[0]||''}')">✉ Draft Email</button>
        </div>
      </div>`;
    }).join('');
  } catch(e) { if(el) el.innerHTML='<div style="color:var(--muted)">Could not load</div>'; }
}

async function loadLicensingRevenue() {
  const el = document.getElementById('licensing-revenue-estimate');
  if (!el) return;
  try {
    const data = await fetchJSON('/music-licensing/revenue-estimate');
    if (data?.total_monthly_estimate_gbp !== undefined) {
      el.textContent = `Est. £${data.total_monthly_estimate_gbp.toFixed(2)}/mo passive (${data.concept_count||0} concepts)`;
    }
  } catch(e) {}
}

async function generateLicensingConcepts() {
  try {
    const res = await fetch('/music-licensing/generate', {method:'POST'});
    const data = await res.json();
    const total = (data.opportunities_created||0) + (data.opportunities_updated||0);
    showToast(total ? `✓ ${total} licensing concept(s) ready below` : 'No concepts generated — check Vibes AI has tracks', total ? 'success' : 'error', 4000);
    loadLicensingConcepts();
  loadPitchTracker();
  loadSoundDNA(); loadLicensingRevenue();
  } catch(e) { showToast('Failed', 'error'); }
}

function pitchConcept(idx, titleEnc) {
  const title = decodeURIComponent(titleEnc);
  showToast(`Pitching "${title}" — drafting…`, 'info');
  fetch('/music-licensing/pitch', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({title, index: idx})})
    .then(r => r.json())
    .then(data => {
      if (data?.pitch_draft) {
        navigator.clipboard.writeText(data.pitch_draft).catch(() => {});
        showToast('Pitch drafted & copied to clipboard!', 'success');
      }
    })
    .catch(() => showToast('Pitch failed', 'error'));
}

function copyConceptBrief(idx, evEnc) {
  try {
    const ev = JSON.parse(decodeURIComponent(evEnc));
    const text = `Track: ${ev.track_title||'—'}\nGenre: ${ev.sub_genre||'—'}\nPlatforms: ${(ev.recommended_platforms||[]).join(', ')}\nEst. Revenue: £${ev.estimated_monthly_revenue_gbp?.toFixed(2)||'—'}/mo\nNotes: ${ev.notes||'—'}`;
    navigator.clipboard.writeText(text).then(() => showToast('Brief copied to clipboard', 'success'));
  } catch(e) { showToast('Could not copy', 'error'); }
}

function draftLicenseEmail(idx, titleEnc, platform) {
  const title = decodeURIComponent(titleEnc);
  const body = `Hi,\n\nI'd like to submit "${title}" for licensing consideration on ${platform||'your platform'}.\n\nThis is a Drum & Bass track produced by PulseBreak. I can provide stems, metadata, and ISRC on request.\n\nBest,\n[Your name]`;
  const mailto = `mailto:licensing@${(platform||'platform').toLowerCase().replace(/\s+/g,'')}.com?subject=${encodeURIComponent('Licensing Submission: '+title)}&body=${encodeURIComponent(body)}`;
  window.open(mailto);
}

async function loadYouTubeContent() {
  const el = document.getElementById('youtube-content');
  if (!el) return;
  try {
    const data = await fetchJSON('/youtube/performance');
    if (!data || !data.videos || !data.videos.length) {
      el.innerHTML = `<div style="text-align:center;padding:16px 8px">
        <div style="font-size:2rem;margin-bottom:8px">▶</div>
        <div style="font-size:0.78rem;color:var(--text);font-weight:600;margin-bottom:6px">No YouTube data yet</div>
        <div style="font-size:0.68rem;color:var(--muted);margin-bottom:12px">Connect your YouTube channel to track views, engagement, and top-performing genres across your DnB releases.</div>
        <button class="btn btn-sm btn-primary" onclick="triggerAgent('Content Agent')">▶ Run Content Agent</button>
      </div>`;
      return;
    }
    el.innerHTML = data.videos.slice(0,4).map(v => `<div class="lb-row">
      <div style="font-size:1.2rem">▶</div>
      <div style="flex:1">
        <div style="font-size:0.78rem;font-weight:600;color:var(--text)">${v.title?.slice(0,50)||'Track'}</div>
        <div style="font-size:0.65rem;color:var(--muted)">${v.genre||''} · ${(v.views||0).toLocaleString()} views</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:0.85rem;font-weight:700;color:var(--purple)">${v.engagement_score||0}</div>
        <div style="font-size:0.6rem;color:var(--muted)">eng. score</div>
      </div>
    </div>`).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">YouTube data unavailable</div>';
  }
}

async function loadContentPosts() {
  const el = document.getElementById('content-posts');
  if (!el) return;
  try {
    const data = await fetchJSON('/content/posts');
    const posts = data?.posts || data || [];
    if (!posts.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No content posts yet — run Content Agent</div>'; return; }
    el.innerHTML = posts.slice(0,4).map(p => `<div class="opp-card">
      <div class="opp-card-header">
        <div class="opp-title">${p.platform||'Social'}</div>
        <span class="badge badge-purple">${p.venture||''}</span>
      </div>
      <div style="font-size:0.75rem;color:var(--text);line-height:1.6;margin:6px 0">${(p.content||p.caption||'').slice(0,150)}${(p.content||p.caption||'').length>150?'…':''}</div>
      ${p.hashtags?`<div style="font-size:0.65rem;color:var(--cyan);margin-top:4px">${p.hashtags}</div>`:''}
    </div>`).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">Content unavailable</div>';
  }
}

/* ─── AGENTS TAB ─── */
async function loadAgentsTab() {
  const [schedulerStatus, agentEcon, perf] = await Promise.all([
    fetchJSON('/scheduler/status'),
    fetchJSON('/agent-economics/dashboard'),
    fetchJSON('/agent-economics/performance'),
  ]);
  renderAgentGrid(schedulerStatus);
  renderAgentEcon(agentEcon);
  renderPerformance(perf);
}

function renderAgentGrid(status) {
  const agents = status?.agents || [];
  const el = document.getElementById('agent-grid-content');
  if (!el) return;
  if (!agents.length) { el.innerHTML='<div class="loading">No scheduler data</div>'; return; }
  el.innerHTML = '<div class="agent-grid">' + agents.map(a => `
    <div class="agent-chip" onclick="triggerAgent('${a.name}')">
      <span class="pulse-dot ${a.scheduler_running?'green':'muted'}"></span>
      <div class="chip-info">
        <div class="chip-name">${a.name}</div>
        <div class="chip-interval">${a.interval} · ${a.next_run ? 'Next: '+new Date(a.next_run).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) : '—'}</div>
      </div>
      <span class="chip-run">▶</span>
    </div>`).join('') + '</div>';
}

function renderAgentEcon(data) {
  const el = document.getElementById('agent-econ-content');
  if (!el || !data) return;
  const agents = data.agent_breakdown || data.agents || [];
  el.innerHTML = agents.slice(0,6).map(a => `<div class="metric-row">
    <span class="metric-key">${a.agent||a.name}</span>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="font-size:0.68rem;color:var(--muted)">${a.tokens_used||0} tokens</span>
      <span class="metric-val" style="color:var(--green)">${fmtMoney(a.revenue_attributed||0)}</span>
    </div>
  </div>`).join('') || '<div style="color:var(--muted);font-size:0.75rem">No economics data yet</div>';
}

async function loadPerformance() {
  const el = document.getElementById('perf-content');
  if (!el) return;
  const data = await fetchJSON('/agent-economics/performance');
  renderPerformance(data);
}

function renderPerformance(data) {
  const el = document.getElementById('perf-content');
  if (!el || !data) return;
  const agents = data.agent_performance || data.agents || [];
  el.innerHTML = agents.slice(0,6).map(a => `<div class="metric-row">
    <span class="metric-key">${a.agent}</span>
    <div style="display:flex;align-items:center;gap:6px">
      <div class="progress-bar" style="width:60px;margin:0"><div class="progress-fill cyan" style="width:${a.success_rate||0}%"></div></div>
      <span class="metric-val">${a.runs_7d||0}x</span>
    </div>
  </div>`).join('') || '<div style="color:var(--muted);font-size:0.75rem">No performance data</div>';
}

/* ─── OPPORTUNITIES TAB ─── */
async function loadOpportunitiesTab() {
  const [leaderboard, recon, forecast, goals] = await Promise.all([
    fetchJSON('/leaderboard/opportunities'),
    fetchJSON('/revenue-recon'),
    fetchJSON('/forecast-agent/latest'),
    fetchJSON('/goals/summary'),
  ]);
  renderLeaderboard(leaderboard);
  renderRecon(recon);
  renderForecast(forecast);
  renderGoals(goals);
  loadMarketScoutResults();
  loadGigScoutResults();
}

/* ─── MARKET SCOUT ─── */
async function runMarketScout() {
  const btn = document.getElementById('market-scout-btn');
  const btn2 = document.getElementById('market-scout-btn2');
  const status = document.getElementById('market-scout-status');
  [btn, btn2].forEach(b => { if(b){b.disabled=true; b.textContent='Scanning…';} });
  if (status) status.innerHTML = '🔍 Scanning Etsy market data across 25 keywords… this takes ~30–60 seconds.';

  try {
    const r = await fetch('/market-scout/run', {method:'POST'});
    const d = await r.json();
    if (status) {
      if (d.status === 'ok' || d.opportunities_created >= 0) {
        status.innerHTML = `✅ Scan complete — <strong style="color:var(--green)">${d.opportunities_created} new</strong> + ${d.opportunities_updated} updated opportunities found.`;
        loadMarketScoutResults();
        loadOpportunitiesTab();
      } else {
        status.innerHTML = `⚠️ ${d.error || 'Scan finished with no results — check Etsy connection.'}`;
      }
    }
  } catch(e) {
    if (status) status.innerHTML = `❌ Scan failed: ${e.message}`;
  } finally {
    [btn, btn2].forEach(b => { if(b){b.disabled=false; b.textContent=b.id==='market-scout-btn'?'🔍 Market Scout':'▶ Run Scan';} });
  }
}

async function loadMarketScoutResults() {
  const container = document.getElementById('market-scout-niches');
  const wrapper = document.getElementById('market-scout-results');
  if (!container) return;
  try {
    const d = await fetchJSON('/market-scout/opportunities?limit=12');
    const opps = d.opportunities || [];
    if (!opps.length) return;
    wrapper.style.display = 'block';
    container.innerHTML = opps.map(o => {
      const score = o.kingdom_score || 0;
      const col = score >= 70 ? 'var(--green)' : score >= 50 ? 'var(--amber)' : 'var(--red)';
      const compCol = o.competition_level === 'Low' ? 'var(--green)' : o.competition_level === 'Medium' ? 'var(--amber)' : 'var(--red)';
      return `<div class="card" style="padding:14px;border-color:rgba(0,255,136,0.1)">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
          <div style="font-size:0.78rem;font-weight:700;color:var(--text);flex:1;margin-right:8px;line-height:1.3">${o.title}</div>
          <div style="font-size:1.3rem;font-weight:800;color:${col};flex-shrink:0">${score}</div>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
          <span style="font-size:0.65rem;padding:2px 6px;border-radius:4px;background:rgba(0,255,136,0.1);color:var(--green)">${o.venture || o.category}</span>
          <span style="font-size:0.65rem;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.06);color:var(--muted)">${o.effort || ''} effort</span>
          <span style="font-size:0.65rem;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.06);color:${compCol}">${o.competition_level || ''} competition</span>
        </div>
        <div style="font-size:0.7rem;color:var(--muted);margin-bottom:6px">${o.market_gap || ''}</div>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div style="font-size:0.7rem;color:var(--cyan)">Est. ${o.estimated_revenue || '?'}</div>
          <div style="font-size:0.65rem;color:var(--muted)">Avg £${o.avg_price_gbp || 0} · ${o.avg_views || 0} views</div>
        </div>
        ${o.next_action ? `<div style="font-size:0.68rem;color:var(--amber);margin-top:6px;padding:6px 8px;background:rgba(255,179,0,0.07);border-radius:4px;border-left:2px solid var(--amber)">▶ ${o.next_action}</div>` : ''}
      </div>`;
    }).join('');
  } catch(e) { /* silent — results may not exist yet */ }
}

function renderLeaderboard(data) {
  const el = document.getElementById('leaderboard-content');
  if (!el) return;
  const items = Array.isArray(data) ? data : [];
  if (!items.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No opportunities yet</div>'; return; }
  el.innerHTML = items.slice(0,6).map((o,i) => `<div class="lb-row">
    <div class="lb-rank ${['r1','r2','r3'][i]||'rn'}">${i+1}</div>
    <div>
      <div class="lb-title">${o.title.slice(0,40)}</div>
      <div class="lb-cat">${o.category||''}</div>
    </div>
    <div style="text-align:right">
      <div class="lb-score">${o.kingdom_score}</div>
      <div class="outcome-btns" style="margin-top:4px">
        <button class="outcome-btn pos btn-xs" onclick="recordOutcome('opportunity',${o.id},'positive',this)">✓</button>
        <button class="outcome-btn neg btn-xs" onclick="recordOutcome('opportunity',${o.id},'negative',this)">✗</button>
      </div>
    </div>
  </div>`).join('');
}

function renderForecast(data) {
  const el = document.getElementById('forecast-content');
  if (!el || !data) return;
  el.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px">
      <div class="big-metric"><div class="value" style="color:var(--green);font-size:1.5rem">${fmtMoney(data.next_30_days_gbp||0)}</div><div class="label">30-Day Forecast</div></div>
      <div class="big-metric"><div class="value" style="color:var(--cyan);font-size:1.5rem">${fmtMoney(data.next_90_days_gbp||0)}</div><div class="label">90-Day Forecast</div></div>
      <div class="big-metric"><div class="value" style="color:var(--amber);font-size:1.5rem">${data.confidence||0}%</div><div class="label">Confidence</div></div>
    </div>
    <div class="metric-row"><span class="metric-key">Growth Rate</span><span class="metric-val">${data.growth_rate||0}%/month</span></div>
    <div class="metric-row"><span class="metric-key">Key Risk</span><span class="metric-val" style="color:var(--amber);font-size:0.72rem">${(data.key_risk||'').slice(0,50)}</span></div>`;
}

async function loadGoals() {
  try { renderGoals(await fetchJSON('/goals/summary')); } catch(_) {}
}

function renderGoals(data) {
  const el = document.getElementById('goals-content');
  if (!el || !data) return;
  const pct = data.overall_pct || 0;
  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
      <div class="big-metric">
        <div class="value" style="color:var(--cyan);font-size:1.8rem">${data.on_track||0}/${data.total_goals||0}</div>
        <div class="label">Goals On Track</div>
      </div>
      <div style="flex:1">
        <div style="font-size:0.7rem;color:var(--muted);margin-bottom:4px">Overall Progress</div>
        <div class="progress-bar"><div class="progress-fill cyan" style="width:${pct}%"></div></div>
        <div style="font-size:0.72rem;color:var(--cyan);margin-top:4px">${pct}%</div>
      </div>
    </div>
    ${(data.goals||[]).slice(0,4).map(g => `<div class="metric-row">
      <span class="metric-key">${g.title||''}</span>
      <span class="metric-val">${g.progress_pct||0}%</span>
    </div>`).join('')}`;
}

/* ─── INTELLIGENCE TAB ─── */
async function loadIntelligenceTab() {
  const [lessons, crisis] = await Promise.all([
    fetchJSON('/lessons'),
    fetchJSON('/crisis/status'),
  ]);
  renderLessons(lessons);
  renderCrisis(crisis);
  loadLearningCards();
  loadSonicFingerprint();
  loadPortfolioAdvice();
}

async function loadLearningCards() {
  const el = document.getElementById('learning-cards');
  if (!el) return;
  try {
    const d = await fetchJSON('/insights/learning-cards');
    if (!d.cards || !d.cards.length) {
      el.innerHTML = '<div style="color:var(--muted);font-size:0.72rem">No learnings yet — cards appear as agents gather performance data.</div>';
      return;
    }
    el.innerHTML = d.cards.map(c => `
      <div style="border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:10px;background:var(--surface)">
        <div style="font-weight:700;font-size:0.8rem;margin-bottom:4px">${c.icon} ${escapeHtml(c.agent)} <span style="color:var(--muted);font-weight:400;font-size:0.62rem">· ${c.runs_7d||0} run(s) this week</span></div>
        <div style="font-size:0.74rem;margin-bottom:4px"><span style="color:#00e676">Learned:</span> ${escapeHtml(c.learned)}</div>
        <div style="font-size:0.74rem;margin-bottom:6px"><span style="color:#00e5ff">Changing:</span> ${escapeHtml(c.changing)}</div>
        ${(c.evidence||[]).length ? `<details style="font-size:0.66rem;color:var(--muted)"><summary style="cursor:pointer">Evidence (${c.evidence.length})</summary>${c.evidence.map(e=>`<div style="padding:3px 0 0 10px">• <b>${escapeHtml(e.label)}</b> ${escapeHtml(e.value)}</div>`).join('')}</details>` : ''}
      </div>`).join('');
  } catch(e) { el.innerHTML = '<div style="color:var(--muted);font-size:0.72rem">Unavailable</div>'; }
}

async function loadSonicFingerprint() {
  const el = document.getElementById('sonic-fingerprint');
  if (!el) return;
  try {
    const d = await fetchJSON('/insights/sonic-fingerprint');
    if (d.status !== 'ok') { el.innerHTML = `<div style="color:var(--muted);font-size:0.72rem">${escapeHtml(d.message||'No data yet')}</div>`; return; }
    const p = d.winning_profile || {};
    el.innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">
        ${p.bpm?`<span class="badge">~${Math.round(p.bpm)} BPM</span>`:''}
        ${(p.top_sub_genres||[]).map(g=>`<span class="badge" style="border-color:#bf5fff;color:#bf5fff">${escapeHtml(g)}</span>`).join('')}
        ${p.dynamic_range_db?`<span class="badge">${p.dynamic_range_db} dB range</span>`:''}
      </div>
      <div style="font-size:0.76rem;margin-bottom:8px">${escapeHtml(d.brief||'')}</div>
      ${d.suggested_suno_prompt?`<div style="border:1px dashed var(--border);border-radius:8px;padding:8px;font-size:0.7rem;color:var(--muted)">Suno prompt: <span style="color:var(--text)">${escapeHtml(d.suggested_suno_prompt)}</span>
        <button class="btn btn-xs" style="margin-left:6px" onclick="navigator.clipboard.writeText('${d.suggested_suno_prompt.replace(/'/g,"\\'")}');this.textContent='Copied!'">Copy</button></div>`:''}
      <div style="font-size:0.62rem;color:var(--muted);margin-top:6px">Based on ${d.tracks_analysed} track(s), top ${d.winners_count} by ${d.ranked_by.replace('_',' ')}</div>`;
  } catch(e) { el.innerHTML = '<div style="color:var(--muted);font-size:0.72rem">Unavailable</div>'; }
}

async function loadPortfolioAdvice() {
  const el = document.getElementById('portfolio-advice');
  if (!el) return;
  try {
    const d = await fetchJSON('/insights/portfolio');
    if (d.status !== 'ok') { el.innerHTML = `<div style="color:var(--muted);font-size:0.72rem">${escapeHtml(d.message||'No data yet')}</div>`; return; }
    el.innerHTML = (d.table||[]).map(r => `
      <div class="metric-row">
        <span class="metric-key">${escapeHtml(r.venture)}</span>
        <span class="metric-val">£${r.net_revenue} · ${r.founder_taps} tap(s)${r.revenue_per_tap!=null?` · £${r.revenue_per_tap}/tap`:''}</span>
      </div>`).join('') +
      (d.advice||[]).map(a=>`<div style="font-size:0.72rem;color:#ffd54f;margin-top:8px">💡 ${escapeHtml(a)}</div>`).join('');
  } catch(e) { el.innerHTML = '<div style="color:var(--muted);font-size:0.72rem">Unavailable</div>'; }
}

async function loadPitchTracker() {
  const el = document.getElementById('pitch-tracker');
  if (!el) return;
  try {
    const d = await fetchJSON('/music-licensing/pitches');
    if (!d.pitches || !d.pitches.length) return;
    const STATUS_COL = { draft:'var(--muted)', sent:'#00e5ff', replied:'#00e676' };
    el.innerHTML = d.pitches.slice(0,8).map(pt => `
      <div style="display:flex;gap:8px;align-items:center;border:1px solid var(--border);border-radius:8px;padding:8px;margin-bottom:6px;font-size:0.7rem">
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;overflow-wrap:anywhere">${escapeHtml(pt.concept||'Pitch')}</div>
          <div style="color:${STATUS_COL[pt.status]||'var(--muted)'}">${pt.status.toUpperCase()}${pt.days_waiting!=null?` · waiting ${pt.days_waiting}d`:''}${pt.needs_follow_up?' · ⚠ follow up':''}</div>
        </div>
        ${pt.status==='draft'?`<button class="btn btn-xs" onclick="pitchAction(${pt.id},'mark-sent',this)">Mark sent</button>`:''}
        ${pt.status==='sent'?`<button class="btn btn-xs btn-green" onclick="pitchAction(${pt.id},'mark-replied',this)">Got reply</button>`:''}
        ${pt.needs_follow_up?`<button class="btn btn-xs" onclick="copyFollowUp(${pt.id},this)">Copy follow-up</button>`:''}
      </div>`).join('');
  } catch(_) {}
}

async function pitchAction(id, action, btn) {
  try {
    await fetch(`/music-licensing/pitch/${id}/${action}`, { method:'POST' });
    loadPitchTracker();
  } catch(_) { if (btn) btn.textContent = 'Failed'; }
}

async function copyFollowUp(id, btn) {
  try {
    const d = await fetchJSON('/music-licensing/follow-ups');
    const f = (d.follow_ups||[]).find(x => x.id === id);
    if (f && f.follow_up_draft) {
      await navigator.clipboard.writeText(f.follow_up_draft);
      btn.textContent = 'Copied!';
    }
  } catch(_) { btn.textContent = 'Failed'; }
}

function renderLessons(lessons) {
  const el = document.getElementById('lessons-content');
  if (!el) return;
  const items = Array.isArray(lessons) ? lessons : [];
  if (!items.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No lessons yet</div>'; return; }
  el.innerHTML = items.slice(0,8).map(l => `<div class="activity-item">
    <div class="activity-time" style="color:var(--purple)">${l.source||'system'}</div>
    <div>
      <div class="activity-text">${(l.lesson||'').slice(0,120)}${(l.lesson||'').length>120?'…':''}</div>
      <div style="font-size:0.62rem;color:var(--muted);margin-top:3px">Confidence: ${l.confidence_score||0}%</div>
    </div>
  </div>`).join('');
}

function renderCrisis(data) {
  const el = document.getElementById('crisis-content');
  if (!el) return;
  if (!data) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No crisis data</div>'; return; }
  const isCrisis = data.is_crisis;
  const banner = document.getElementById('crisis-banner');
  if (banner && isCrisis) {
    banner.textContent = `⚠ CRISIS ALERT: ${data.crisis_level} — ${data.total_severity} severity points`;
    banner.classList.add('show');
  }
  el.innerHTML = `
    <div class="big-metric" style="margin-bottom:12px">
      <div class="value" style="color:${isCrisis?'var(--red)':'var(--green)'}">
        ${isCrisis?'🚨 CRISIS':'✅ STABLE'}
      </div>
      <div class="label">${data.crisis_level||'Normal'}</div>
    </div>
    <div class="metric-row"><span class="metric-key">Severity Score</span><span class="metric-val" style="color:${isCrisis?'var(--red)':'var(--green)'}">${data.total_severity||0}</span></div>
    ${(data.alerts||[]).slice(0,3).map(a=>`<div class="activity-item">
      <div class="activity-time" style="color:var(--red)">ALERT</div>
      <div class="activity-text">${a.message||a}</div>
    </div>`).join('')}`;
}

/* ─── COUNCIL ─── */
function conveneCouncil() {
  const proposal = document.getElementById('council-proposal')?.value?.trim();
  const context = document.getElementById('council-context')?.value?.trim();
  if (!proposal) { showToast('Enter a proposal first', 'warning'); return; }
  const resultEl = document.getElementById('council-result');
  if (resultEl) resultEl.innerHTML = '<div class="loading">Convening council</div>';
  fetch('/council/convene', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({proposal,context})})
  .then(r=>r.json()).then(data => {
    if (!resultEl) return;
    if (data.error) { resultEl.innerHTML=`<div style="color:var(--red)">${data.error}</div>`; return; }
    const vc=data.verdict==='PROCEED'?'var(--green)':data.verdict==='REJECT'?'var(--red)':'var(--amber)';
    const vi=data.verdict==='PROCEED'?'✅':data.verdict==='REJECT'?'❌':'⚠';
    const voteC=v=>v==='for'?'var(--green)':v==='against'?'var(--red)':'var(--amber)';
    resultEl.innerHTML=`
      <div style="background:${vc}22;border:1px solid ${vc};border-radius:10px;padding:12px;text-align:center;font-weight:700;font-size:1rem;color:${vc};margin-bottom:10px">
        ${vi} ${data.verdict} · <span style="font-size:0.8rem;font-weight:400">Confidence ${data.confidence}%</span></div>
      <div style="font-size:0.72rem;color:var(--muted);text-align:center;margin-bottom:10px">🟢 ${data.for_count} for · 🔴 ${data.against_count} against · 🟡 ${data.neutral_count} neutral</div>
      ${(data.votes||[]).map(v=>`<div style="border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-top:6px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600;font-size:0.8rem">${v.agent_name}</span>
          <span style="color:${voteC(v.vote)};font-size:0.75rem;font-weight:700">${v.vote?.toUpperCase()}</span>
        </div>
        <div style="font-size:0.72rem;color:var(--muted);margin-top:3px">${v.key_concern}</div>
      </div>`).join('')}`;
  }).catch(err => { if(resultEl) resultEl.innerHTML=`<div style="color:var(--red)">Error: ${err}</div>`; });
}

/* ─── COMMAND CENTRE TAB ─── */
function showCCSub(sub) {
  document.querySelectorAll('.cc-section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.cc-subtab').forEach(b => b.classList.remove('active'));
  const el = document.getElementById('cc-' + sub);
  if (el) el.style.display = '';
  const btn = document.querySelector(`.cc-subtab[data-cc="${sub}"]`);
  if (btn) btn.classList.add('active');
  if (sub === 'rooms') loadRooms();
  if (sub === 'treasury') loadTreasuryPeriod('1m');
  if (sub === 'commander') loadCommanderPanel();
  if (sub === 'marketing') loadMarketingContent();
}

function loadCommandTab() {
  loadRooms();
}

async function loadRooms() {
  const el = document.getElementById('rooms-grid');
  const data = await fetchJSON('/rooms');
  if (!data || !data.rooms) { el.innerHTML = '<div style="color:var(--muted)">Could not load rooms.</div>'; return; }
  const statusColour = s => s === 'active' ? 'var(--green)' : s === 'paused' ? 'var(--muted)' : s === 'stalled' ? 'var(--amber)' : s === 'error' ? 'var(--red)' : 'var(--muted)';
  const statusDot = s => s === 'active' ? '●' : s === 'paused' ? '⏸' : s === 'stalled' ? '◐' : s === 'error' ? '✕' : '○';
  el.innerHTML = data.rooms.map(r => `
    <div class="card" style="border-color:${r.colour}33">
      <div class="card-header">
        <div class="card-icon" style="background:linear-gradient(135deg,${r.colour}33,${r.colour}11);font-size:1.3rem">${r.icon}</div>
        <div class="card-title">${r.name}</div>
        <div class="card-action"><button class="btn btn-sm" onclick="runAllInRoom('${r.id}')">▶ Run All</button></div>
      </div>
      <div style="font-size:0.7rem;color:var(--muted);margin-bottom:10px">${r.description}</div>
      <div style="display:flex;gap:10px;margin-bottom:10px;font-size:0.68rem">
        <span style="color:var(--green)">● ${r.active_count} active</span>
        <span style="color:var(--muted)">○ ${r.idle_count} idle</span>
        ${r.error_count ? `<span style="color:var(--red)">✕ ${r.error_count} issues</span>` : ''}
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${r.agents.map(a => `
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.72rem;padding:6px 8px;border-radius:6px;background:rgba(255,255,255,0.02)">
            <span style="display:flex;flex-direction:column;gap:2px">
              <span>${a.agent}${a.paused ? ` <span style="color:var(--muted);font-size:0.65rem">(${a.paused_by || 'paused'})</span>` : ''}</span>
              ${a.paused && a.paused_reason ? `<span style="color:var(--amber);font-size:0.6rem;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${a.paused_reason}">⚠ ${a.paused_reason}</span>` : ''}
            </span>
            <span style="display:flex;align-items:center;gap:6px">
              <span style="color:${statusColour(a.status)}">${statusDot(a.status)} ${a.status}</span>
              <button class="btn btn-sm" style="padding:2px 6px;font-size:0.65rem" onclick="toggleAgentPause('${a.agent}', ${a.paused})">${a.paused ? '▶ Resume' : '⏸'}</button>
            </span>
          </div>`).join('')}
      </div>
    </div>`).join('');
}

async function runAllInRoom(roomId) {
  if (!confirm('Run all agents in this room? This triggers multiple AI calls and may cost tokens. Proceed?')) return;
  try {
    const r = await fetch(`/rooms/${roomId}/run-all`, { method: 'POST' });
    await r.json();
    loadRooms();
  } catch (e) {}
}

async function toggleAgentPause(agentName, isPaused) {
  try {
    const path = isPaused ? 'resume' : 'pause';
    const opts = { method: 'POST' };
    if (!isPaused) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify({ reason: 'Paused from Rooms UI' });
    }
    await fetch(`/rooms/agent/${encodeURIComponent(agentName)}/${path}`, opts);
    loadRooms();
  } catch (e) {}
}

/* Content Drafts */
async function loadContentDrafts(status = 'draft') {
  const el = document.getElementById('content-drafts-list');
  el.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const params = status ? `?status=${status}&limit=50` : '?limit=50';
    const r = await fetch('/content-drafts' + params);
    const data = await r.json();
    if (!data.drafts || !data.drafts.length) {
      el.innerHTML = `<div class="card" style="padding:20px;color:var(--muted)">No ${status || ''} drafts found.</div>`;
      return;
    }
    el.innerHTML = data.drafts.map(d => {
      let content = {};
      try { content = JSON.parse(d.content_json); } catch {}
      const text = content.content || content.text || content.optimised_title || JSON.stringify(content).slice(0, 200);
      const platform = d.platform || content.platform || '';
      const statusColor = d.status === 'approved' ? 'var(--green)' : d.status === 'published' ? 'var(--cyan)' : d.status === 'rejected' ? 'var(--red)' : 'var(--amber)';
      return `<div class="card" style="margin-bottom:10px;padding:14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:0.72rem;color:var(--muted)">${d.venture}${platform ? ' · ' + platform : ''} · ${d.content_type} · ${d.source_agent || 'AI'}</span>
          <span style="font-size:0.7rem;color:${statusColor};font-weight:600">${d.status}</span>
        </div>
        <p style="font-size:0.8rem;margin:0 0 10px;line-height:1.5;color:#ccc">${text}</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${d.status === 'draft' || d.status === 'approved' ? `<button class="btn btn-sm" style="background:var(--green);color:#000" onclick="approveDraft(${d.id})">✓ Approve</button>` : ''}
          ${d.status === 'approved' ? `<button class="btn btn-sm" style="background:var(--cyan);color:#000" onclick="publishDraft(${d.id})">↑ Mark Published</button>` : ''}
          ${d.status === 'draft' ? `<button class="btn btn-sm" style="background:var(--red);color:#fff" onclick="rejectDraft(${d.id})">✕ Reject</button>` : ''}
          <button class="btn btn-sm" onclick="navigator.clipboard.writeText(${JSON.stringify(text)}).then(()=>alert('Copied!'))" style="background:#333">⎘ Copy</button>
        </div>
      </div>`;
    }).join('');
  } catch(e) { el.innerHTML = `<div class="card" style="color:var(--red)">Error: ${e.message}</div>`; }
}
async function approveDraft(id) {
  await fetch(`/content-drafts/${id}/approve`, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  loadContentDrafts();
}
async function rejectDraft(id) {
  await fetch(`/content-drafts/${id}/reject`, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  loadContentDrafts();
}
async function publishDraft(id) {
  await fetch(`/content-drafts/${id}/publish`, {method:'POST'});
  loadContentDrafts('approved');
}

/* Treasury */
async function loadTreasuryPeriod(period) {
  document.querySelectorAll('.tp-btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`.tp-btn[data-period="${period}"]`);
  if (btn) btn.classList.add('active');

  const daysMap = {'1d':1,'7d':7,'1m':30,'3m':90,'6m':180,'1y':365,'all':0};
  const days = period in daysMap ? daysMap[period] : 30;

  const [pnl, breakdown, subs, apiCosts, agentCosts] = await Promise.all([
    fetchJSON(`/treasury/pnl/${period}`),
    fetchJSON(`/treasury/breakdown?days=${days}`),
    fetchJSON('/treasury/subscriptions'),
    fetchJSON(`/treasury/api-costs?days=${days}`),
    fetchJSON(`/treasury/agent-costs?days=${days}`),
  ]);

  if (pnl) {
    document.getElementById('tr-income').textContent = fmtMoney(pnl.total_income);
    document.getElementById('tr-expenses').textContent = fmtMoney(pnl.total_expenses);
    document.getElementById('tr-net').textContent = fmtMoney(pnl.net_profit);
    const byV = document.getElementById('tr-by-venture');
    const entries = Object.entries(pnl.by_venture || {});
    byV.innerHTML = entries.length ? entries.map(([v, d]) => `
      <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:0.78rem">
        <span>${v}</span>
        <span style="color:${d.net >= 0 ? 'var(--green)' : 'var(--red)'}">${fmtMoney(d.net)} <span style="color:var(--muted)">(£${d.income} in / £${d.expenses} out)</span></span>
      </div>`).join('') : '<div style="color:var(--muted);font-size:0.75rem">No transactions yet.</div>';
  }

  if (breakdown) {
    const c = breakdown.costs || {};
    document.getElementById('tr-cost-breakdown').innerHTML = `
      <div style="display:flex;justify-content:space-between;font-size:0.78rem;padding:6px 0"><span>API costs</span><span>${fmtMoney(c.api_cost_gbp)} (${c.breakdown_pct?.api ?? 0}%)</span></div>
      <div style="display:flex;justify-content:space-between;font-size:0.78rem;padding:6px 0"><span>Subscriptions</span><span>${fmtMoney(c.subscription_cost_gbp)} (${c.breakdown_pct?.subscriptions ?? 0}%)</span></div>
      <div style="display:flex;justify-content:space-between;font-size:0.78rem;padding:6px 0;border-top:1px solid var(--border);margin-top:4px"><span>Production</span><span>${fmtMoney(c.production_cost_gbp)} (${c.breakdown_pct?.production ?? 0}%)</span></div>
      <div style="display:flex;justify-content:space-between;font-size:0.85rem;padding:8px 0;font-weight:700;border-top:1px solid var(--border);margin-top:4px"><span>Total</span><span>${fmtMoney(c.total_cost_gbp)}</span></div>`;
  }

  if (subs) {
    document.getElementById('tr-subscriptions').innerHTML = (subs.known_subscriptions || []).map(s => `
      <div style="display:flex;justify-content:space-between;font-size:0.76rem;padding:6px 0;border-bottom:1px solid var(--border)">
        <span>${s.name}</span><span style="color:var(--muted)">${s.cost_gbp ? '£' + s.cost_gbp.toFixed(2) : '—'} / ${s.period}${s.note ? ' · ' + s.note : ''}</span>
      </div>`).join('') + `<div style="font-size:0.75rem;margin-top:8px;color:var(--cyan)">Estimated monthly fixed: £${subs.estimated_monthly_fixed_cost_gbp}</div>`;
  }

  if (apiCosts) {
    document.getElementById('tr-api-costs').innerHTML = `
      <div style="font-size:1.3rem;font-weight:800;color:var(--cyan)">£${apiCosts.total_estimated_cost_gbp}</div>
      <div style="font-size:0.7rem;color:var(--muted);margin-bottom:8px">${apiCosts.total_tokens.toLocaleString()} tokens over ${apiCosts.period_days}d</div>
      ${Object.entries(apiCosts.by_source_tokens || {}).map(([src, tok]) => `
        <div style="display:flex;justify-content:space-between;font-size:0.74rem;padding:4px 0"><span style="text-transform:capitalize">${src}</span><span>${tok.toLocaleString()} tokens</span></div>`).join('')}`;
  }

  if (agentCosts) {
    const rows = Object.entries(agentCosts.by_feature || {});
    document.getElementById('tr-agent-costs').innerHTML = rows.length ? rows.map(([feature, d]) => `
      <div style="display:flex;justify-content:space-between;font-size:0.76rem;padding:6px 0;border-bottom:1px solid var(--border)">
        <span>${feature} <span style="color:var(--muted);font-size:0.65rem;text-transform:capitalize">(${d.provider})</span></span>
        <span>£${d.estimated_cost_gbp} <span style="color:var(--muted)">· ${d.tokens.toLocaleString()} tok</span></span>
      </div>`).join('') + `<div style="font-size:0.75rem;margin-top:8px;color:var(--cyan)">Total: £${agentCosts.total_estimated_cost_gbp}</div>`
      : '<div style="color:var(--muted);font-size:0.75rem">No agent spend recorded yet.</div>';
  }
}

/* Commander */
function loadCommanderPanel() {
  loadCommanderStatus();
  loadCommanderBriefing();
  loadCommanderReport();
}

async function loadCommanderStatus() {
  const data = await fetchJSON('/commander/status');
  const badgeEl = document.getElementById('commander-health-badge');
  const contentEl = document.getElementById('commander-status-content');
  if (!data) { contentEl.innerHTML = '<div style="color:var(--muted)">Unavailable</div>'; return; }
  badgeEl.innerHTML = badge(data.health);
  contentEl.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:0.76rem;margin-bottom:8px">
      <div>Runs (24h): <b>${data.total_runs_24h}</b></div>
      <div>Stalled: <b style="color:${data.stalled_agents.length ? 'var(--amber)' : 'var(--green)'}">${data.stalled_agents.length}</b></div>
      <div>Revenue today: <b>${fmtMoney(data.revenue_today_gbp)}</b></div>
      <div>Revenue yesterday: <b>${fmtMoney(data.revenue_yesterday_gbp)}</b></div>
      <div>Spend today: <b>£${data.agent_cost_today_gbp}</b></div>
      <div>Active opps: <b>${data.active_opportunities_count}</b></div>
    </div>
    ${data.stalled_agents.length ? `<div style="font-size:0.72rem;color:var(--amber)">Stalled: ${data.stalled_agents.join(', ')}</div>` : ''}`;
}

async function loadCommanderBriefing() {
  const data = await fetchJSON('/commander/briefing');
  const el = document.getElementById('commander-briefing-content');
  if (!data) { el.innerHTML = '<div style="color:var(--muted)">Unavailable</div>'; return; }
  el.innerHTML = `
    <div style="font-size:0.76rem;margin-bottom:8px">Overnight: ${data.overnight_runs} runs · ${fmtMoney(data.overnight_revenue_gbp)} revenue · £${data.overnight_cost_gbp} cost</div>
    ${(data.needs_attention || []).map(n => `<div style="font-size:0.72rem;color:var(--amber);padding:4px 0">⚠ ${n}</div>`).join('')}`;
}

async function loadCommanderReport() {
  const data = await fetchJSON('/commander/report');
  const el = document.getElementById('commander-report-content');
  if (!data) { el.innerHTML = '<div style="color:var(--muted)">Unavailable</div>'; return; }
  el.innerHTML = `<div style="font-size:0.78rem;white-space:pre-wrap">${data.report}</div>${data.created_at ? `<div style="font-size:0.65rem;color:var(--muted);margin-top:8px">${new Date(data.created_at).toLocaleString()}</div>` : ''}`;
}

async function runCommanderCycle() {
  const el = document.getElementById('commander-report-content');
  el.innerHTML = '<div class="loading">Running oversight cycle…</div>';
  try {
    await fetch('/commander/run', { method: 'POST' });
    loadCommanderPanel();
  } catch (e) { el.innerHTML = '<div style="color:var(--red)">Error running cycle.</div>'; }
}

async function sendCommanderChat() {
  const input = document.getElementById('commander-chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  const msgsEl = document.getElementById('commander-chat-messages');
  msgsEl.innerHTML += `<div style="align-self:flex-end;background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.2);border-radius:10px;padding:8px 12px;max-width:80%;font-size:0.78rem">${msg}</div>`;
  input.value = '';
  msgsEl.scrollTop = msgsEl.scrollHeight;
  try {
    const r = await fetch('/commander/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg }),
    });
    const data = await r.json();
    const actions = (data.recommended_actions || []).map(a => `<div style="font-size:0.68rem;color:var(--cyan);margin-top:4px">▸ ${a}</div>`).join('');
    msgsEl.innerHTML += `<div style="align-self:flex-start;background:rgba(255,51,102,0.08);border:1px solid rgba(255,51,102,0.2);border-radius:10px;padding:8px 12px;max-width:85%;font-size:0.78rem">${data.reply || '(no response)'}${actions}</div>`;
  } catch (e) {
    msgsEl.innerHTML += `<div style="color:var(--red);font-size:0.75rem">Commander unreachable.</div>`;
  }
  msgsEl.scrollTop = msgsEl.scrollHeight;
}

/* Marketing Factory */
async function generateMarketing(kind) {
  const venture = document.getElementById('mk-venture').value;
  const product = document.getElementById('mk-product').value;
  const el = document.getElementById('mk-generate-result');
  el.innerHTML = '<div class="loading">Generating…</div>';
  const endpoints = {
    instagram: { url: '/marketing/generate/instagram', body: { venture, product_title: product } },
    tiktok: { url: '/marketing/generate/tiktok', body: { venture } },
    email: { url: '/marketing/generate/email', body: { venture } },
  };
  const cfg = endpoints[kind];
  try {
    const r = await fetch(cfg.url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg.body) });
    if (!r.ok) { el.innerHTML = '<div style="color:var(--amber)">AI unavailable — check API keys.</div>'; return; }
    const data = await r.json();
    el.innerHTML = `<pre style="white-space:pre-wrap;font-size:0.74rem;background:rgba(0,255,136,0.04);border:1px solid rgba(0,255,136,0.15);border-radius:8px;padding:12px">${JSON.stringify(data, null, 2)}</pre>`;
    loadMarketingContent();
  } catch (e) { el.innerHTML = '<div style="color:var(--red)">Error generating content.</div>'; }
}

async function runMarketingFactory() {
  const el = document.getElementById('mk-generate-result');
  el.innerHTML = '<div class="loading">Running full marketing factory…</div>';
  try {
    await fetch('/marketing/run', { method: 'POST' });
    el.innerHTML = '<div style="color:var(--green);font-size:0.78rem">Factory run complete.</div>';
    loadMarketingContent();
  } catch (e) { el.innerHTML = '<div style="color:var(--red)">Error.</div>'; }
}

async function loadMarketingContent() {
  const el = document.getElementById('mk-content-list');
  const data = await fetchJSON('/marketing/content');
  if (!data || !data.content || !data.content.length) { el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem">No content generated yet.</div>'; return; }
  el.innerHTML = data.content.map(c => `
    <div style="border-bottom:1px solid var(--border);padding:8px 0;font-size:0.74rem">
      <div style="white-space:pre-wrap">${c.lesson}</div>
      <div style="font-size:0.62rem;color:var(--muted);margin-top:4px">${new Date(c.created_at).toLocaleString()}</div>
    </div>`).join('');
}

/* ─── TOOLS TAB ─── */
async function loadToolsTab() {
  loadChecklist();
}

/* ─── SCENARIO MODELLER ─── */
function runScenario() {
  const listings = parseFloat(document.getElementById('sc-listings')?.value)||5;
  const price = parseFloat(document.getElementById('sc-price')?.value)||18.99;
  const conv = parseFloat(document.getElementById('sc-conv')?.value)||2.5;
  const el = document.getElementById('scenario-result');
  if (!el) return;
  const weeklyViews = listings * 100;
  const weeklySales = weeklyViews * (conv/100);
  const weeklyRev = weeklySales * price;
  const margin = 0.38;
  const weeklyProfit = weeklyRev * margin;
  el.style.display = '';
  el.innerHTML = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="big-metric" style="background:rgba(0,255,136,0.05);padding:10px;border-radius:8px">
      <div class="value" style="font-size:1.4rem;color:var(--green)">${fmtMoney(weeklyRev)}</div>
      <div class="label">WEEKLY REV</div>
    </div>
    <div class="big-metric" style="background:rgba(0,229,255,0.05);padding:10px;border-radius:8px">
      <div class="value" style="font-size:1.4rem;color:var(--cyan)">${fmtMoney(weeklyProfit)}</div>
      <div class="label">WEEKLY PROFIT</div>
    </div>
    <div class="big-metric" style="background:rgba(0,255,136,0.05);padding:10px;border-radius:8px">
      <div class="value" style="font-size:1.4rem;color:var(--green)">${fmtMoney(weeklyRev*4.33)}</div>
      <div class="label">MONTHLY REV</div>
    </div>
    <div class="big-metric" style="background:rgba(255,179,0,0.05);padding:10px;border-radius:8px">
      <div class="value" style="font-size:1.4rem;color:var(--amber)">${fmtMoney(weeklyRev*52)}</div>
      <div class="label">ANNUAL REV</div>
    </div>
  </div>
  <div style="font-size:0.65rem;color:var(--muted);margin-top:8px">${listings} listings · ${conv}% conv · £${price} avg · 38% margin</div>`;
}

/* ─── CHECKLIST ─── */
let _allChecklist = [];
async function loadChecklist() {
  try {
    const data = await fetchJSON('/launch/checklist');
    _allChecklist = data?.items || data || [];
    renderChecklist(_allChecklist);
  } catch(e) {}
}
function renderChecklist(items) {
  const el = document.getElementById('checklist-items');
  const prog = document.getElementById('checklist-progress');
  if (!el) return;
  if (!items.length) { el.innerHTML='<div style="color:var(--muted);font-size:0.75rem">No checklist items</div>'; return; }
  const done = items.filter(i=>i.completed).length;
  if (prog) { prog.textContent = `${done}/${items.length} complete`; }
  el.innerHTML = items.map((item,i) => `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)">
    <input type="checkbox" ${item.completed?'checked':''} onchange="toggleChecklistItem(${item.id||i},this)" style="cursor:pointer;accent-color:var(--green)">
    <div style="flex:1">
      <div style="font-size:0.78rem;color:${item.completed?'var(--muted)':'var(--text)'};text-decoration:${item.completed?'line-through':'none'}">${item.item||item.title||''}</div>
      <div style="font-size:0.62rem;color:var(--muted)">${item.venture||''}</div>
    </div>
  </div>`).join('');
}
function filterChecklist(venture) {
  if (venture==='all') { renderChecklist(_allChecklist); return; }
  renderChecklist(_allChecklist.filter(i=>i.venture===venture));
}
async function toggleChecklistItem(id, el) {
  try {
    await fetch(`/launch/checklist/${id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({completed: !el.checked ? false : true})});
    loadChecklist();
  } catch(e) { el.checked = !el.checked; }
}
async function addChecklistItem() {
  const title = document.getElementById('new-checklist-item')?.value?.trim();
  const venture = document.getElementById('new-checklist-venture')?.value;
  if (!title) return;
  try {
    await fetch('/launch/checklist', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item: title, venture})});
    document.getElementById('new-checklist-item').value = '';
    loadChecklist();
    showToast('Item added', 'success');
  } catch(e) { showToast('Error', 'error'); }
}

/* ─── BACKUP ─── */
async function createBackup() {
  try {
    const res = await fetch('/backup/create', {method:'POST'});
    const data = await res.json();
    document.getElementById('backup-result').textContent = 'Backup: ' + (data.filename||'created');
    showToast('Backup created', 'success');
  } catch(e) { showToast('Backup failed', 'error'); }
}

/* ─── OUTCOME RECORDING ─── */
async function recordOutcome(entityType, entityId, outcome, btnEl) {
  // Backend vocabulary is success/failure/partial
  const mapped = { positive:'success', negative:'failure' }[outcome] || outcome;
  try {
    const r = await fetch('/outcomes/record', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({entity_type:entityType, entity_id:entityId, outcome:mapped})
    });
    if (!r.ok) {
      const err = await r.json().catch(()=>({}));
      throw new Error(err.detail || 'HTTP ' + r.status);
    }
    if (btnEl) { btnEl.disabled=true; btnEl.textContent=mapped==='success'?'✓ Done':'✗ Noted'; }
    showToast('Outcome recorded', 'success');
  } catch(e) { showToast('Recording failed: ' + e.message,'error'); }
}

/* ─── CHAR MODAL ─── */
let _charModalAgent = null;
async function openCharModal(agent) {
  _charModalAgent = agent;
  const bg = document.getElementById('char-modal-bg');
  const body = document.getElementById('modal-body');
  if (!bg || !body) return;
  bg.classList.add('open');
  body.innerHTML = '<div class="loading">Loading agent data</div>';
  try {
    const data = await fetchJSON(`/agents/${encodeURIComponent(agent)}/profile`);
    if (!data) { body.innerHTML='<div class="modal-header"><div class="modal-title">'+agent+'</div><button class="modal-close" onclick="closeCharModal()">✕</button></div><div style="color:var(--muted);font-size:0.8rem;padding:8px">No profile data available</div>'; return; }
    const ks = data.kingdom_score||0;
    const scoreColor = ks>=80?'var(--green)':ks>=60?'var(--amber)':'var(--red)';
    body.innerHTML = `
      <div class="modal-header">
        <div class="modal-title">${data.name||agent}</div>
        <button class="modal-close" onclick="closeCharModal()">✕</button>
      </div>
      <div style="font-size:0.75rem;color:var(--muted);margin-bottom:12px">${data.mission||''}</div>
      ${data.last_run ? `<div class="modal-section-title">Last Run</div>
        <div class="modal-row"><span class="modal-label">Status</span><span class="modal-value">${data.last_run.status||''}</span></div>
        <div class="modal-row"><span class="modal-label">Opps Created</span><span class="modal-value">${data.last_run.opportunities_created||0}</span></div>` : ''}
      ${data.opportunities?.length ? `
        <div class="modal-section-title">Top Opportunities</div>
        ${data.opportunities.slice(0,3).map(o=>`<div class="modal-card">
          <div class="modal-card-title">${o.title?.slice(0,45)||''}</div>
          <div class="modal-card-sub">${o.category||''} · Score: ${o.kingdom_score||0}</div>
          <div class="score-bar"><div class="score-fill" style="width:${o.kingdom_score||0}%;background:linear-gradient(90deg,var(--amber),var(--green))"></div></div>
        </div>`).join('')}` : ''}
      <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="modal-action-btn" onclick="triggerAgent('${data.name||agent}');closeCharModal()">▶ Run ${data.name||agent}</button>
      </div>`;
  } catch(e) {
    body.innerHTML = `<div class="modal-header"><div class="modal-title">${agent}</div><button class="modal-close" onclick="closeCharModal()">✕</button></div><div style="color:var(--muted)">Could not load profile</div>`;
  }
}
function closeCharModal() {
  document.getElementById('char-modal-bg')?.classList.remove('open');
}

/* ─── CHAT ─── */
let chatOpen = false;
function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chat-drawer').classList.toggle('open', chatOpen);
}
async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const agent = document.getElementById('chat-agent-select').value;
  const message = (input?.value||'').trim();
  if (!message) return;
  input.value = '';
  appendChatMsg('user', null, message, []);
  const sendBtn = document.getElementById('chat-send');
  if(sendBtn){sendBtn.disabled=true;sendBtn.textContent='...';}
  try {
    const res = await fetch('/chat/message', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,message})});
    const data = await res.json();
    appendChatMsg('agent', data.agent, data.reply, data.suggested_actions||[]);
  } catch(e) {
    appendChatMsg('agent','System','Unable to reach agent — check API connection.',[]);
  }
  if(sendBtn){sendBtn.disabled=false;sendBtn.textContent='SEND';}
}
function appendChatMsg(type, agentName, text, actions) {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + type;
  let html = '';
  if (type==='agent' && agentName) html += `<div class="msg-agent">${agentName.toUpperCase()}</div>`;
  html += `<div>${text}</div>`;
  if (actions?.length) {
    html += '<div class="chat-actions">'+actions.map(a=>`<span class="chat-action-tag" onclick="document.getElementById('chat-input').value='${a.replace(/'/g,"\\'")}'">` +a+'</span>').join('')+'</div>';
  }
  div.innerHTML = html;
  msgs?.appendChild(div);
  if(msgs) msgs.scrollTop = msgs.scrollHeight;
}

/* ─── TOAST ─── */
function showToast(message, type='info', duration=3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const existing = container.querySelectorAll('.toast:not(.removing)');
  if (existing.length >= 4) _removeToast(existing[0]);
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icon = type==='success'?'✓':type==='warning'?'⚠':type==='error'?'✗':'ℹ';
  t.innerHTML = `<span>${icon}</span><span style="flex:1">${message}</span>`;
  t.onclick = () => _removeToast(t);
  container.appendChild(t);
  setTimeout(() => _removeToast(t), duration);
}
function _removeToast(el) {
  if(!el||el.classList.contains('removing')) return;
  el.classList.add('removing');
  setTimeout(() => { try{el.remove();}catch(e){} }, 260);
}

/* ─── CELEBRATION ─── */
function triggerCelebration(title, subtitle, emoji) {
  const overlay = document.getElementById('celebration-overlay');
  if (!overlay) return;
  document.getElementById('celebration-title').textContent = title||'ACHIEVEMENT UNLOCKED';
  document.getElementById('celebration-subtitle').textContent = subtitle||'';
  document.getElementById('celebration-emoji-main').textContent = emoji||'🏆';
  const rain = document.getElementById('celeb-rain');
  const emojis = ['💰','🏆','🔥','⭐','✨','💎','🎯','🚀'];
  rain.innerHTML = '';
  for(let i=0;i<18;i++){
    const s=document.createElement('span');
    s.textContent=emojis[i%emojis.length];
    s.style.cssText=`left:${Math.random()*100}%;animation-duration:${2+Math.random()*2}s;animation-delay:${Math.random()*1.5}s`;
    rain.appendChild(s);
  }
  overlay.classList.add('active');
  setTimeout(()=>overlay.classList.remove('active'),3200);
}

/* ─── SETTINGS ─── */
function openSettings() { document.getElementById('settings-panel')?.classList.add('open'); loadSettingsScheduler(); }
function closeSettings() { document.getElementById('settings-panel')?.classList.remove('open'); }
async function loadSettingsScheduler() {
  const el = document.getElementById('settings-scheduler');
  if (!el) return;
  const data = await fetchJSON('/scheduler/status');
  const agents = data?.agents||[];
  el.innerHTML = agents.slice(0,6).map(a=>`<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:0.7rem">
    <span style="color:var(--text)">${a.name}</span>
    <span style="color:var(--muted)">${a.interval}</span>
  </div>`).join('');
}
function saveVentureSettings() {}
async function saveRevenueTargets() {
  showToast('Targets saved', 'success');
}
async function resetLearningWeights() {
  if (!confirm('Reset all learning weights? This cannot be undone.')) return;
  try {
    await fetch('/learning/reset', {method:'POST'});
    document.getElementById('settings-danger-result').textContent = 'Learning weights reset.';
    showToast('Learning weights reset', 'info');
  } catch(e) { showToast('Error', 'error'); }
}
function toggleKeyVisibility(id, btn) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.type==='password') { el.type='text'; btn.textContent='HIDE'; }
  else { el.type='password'; btn.textContent='SHOW'; }
}

/* ─── HELP ─── */
function openHelp() { document.getElementById('help-overlay')?.classList.add('open'); }
function closeHelp() { document.getElementById('help-overlay')?.classList.remove('open'); }

/* ─── UPDATE ─── */
async function checkForUpdate() {
  try {
    const data = await fetchJSON('/update/status');
    if (data?.update_available) {
      document.getElementById('upd-version').textContent = 'v'+data.latest_version+' ready (you have v'+data.current_version+')';
      document.getElementById('update-banner').classList.add('show');
    }
  } catch(e) {}
}
async function applyUpdate() {
  const btn = document.querySelector('#update-banner .upd-btn');
  if(btn){btn.textContent='DOWNLOADING...';btn.disabled=true;}
  try {
    await fetch('/update/apply',{method:'POST'});
    if(btn) btn.textContent='RESTARTING...';
    setTimeout(()=>location.reload(),4000);
  } catch(e) { if(btn){btn.textContent='FAILED — retry';btn.disabled=false;} }
}

/* ─── KEYBOARD ─── */
document.addEventListener('keydown', e => {
  if (e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA') return;
  if (e.key==='?') openHelp();
  else if (e.key==='Escape') { closeHelp(); closeSettings(); closeCharModal(); document.getElementById('chat-drawer')?.classList.remove('open'); chatOpen=false; }
  else if (e.key.toLowerCase()==='r') { showToast('Refreshing…','info'); loadOverview(); }
  else if (e.key.toLowerCase()==='c') toggleChat();
  else if (e.key.toLowerCase()==='m') showTab('overview');
});

/* ─── ONBOARDING ─── */
let obStep = 1;
const OB_STEPS = [
  {
    title:'Welcome to Kingdom OS',
    body:`<p>Your autonomous AI revenue engine is ready.</p>
    <p style="margin-top:10px">We have two ventures:</p>
    <ul style="margin-top:8px;padding-left:16px;display:flex;flex-direction:column;gap:6px">
      <li><strong style="color:var(--amber)">🏎 Pitwall Classics</strong> — Motorsport art prints on Etsy/Printify</li>
      <li><strong style="color:var(--purple)">🎵 PulseBreak</strong> — DnB music licensing &amp; social content</li>
    </ul>
    <p style="margin-top:10px;color:var(--muted)">14 agents work autonomously 24/7 to find opportunities, test ideas, and generate revenue. You approve; they execute.</p>`,
    btnText:'Set Targets →',
  },
  {
    title:'Revenue Targets',
    body:`<p>Set your monthly revenue targets for each venture.</p>
    <label class="ob-label" style="margin-top:14px">Pitwall Classics Monthly Target (£)</label>
    <input type="number" class="settings-input" id="ob-pitwall-target" placeholder="500" value="500">
    <label class="ob-label">PulseBreak Monthly Target (£)</label>
    <input type="number" class="settings-input" id="ob-pb-target" placeholder="500" value="500">`,
    btnText:'Add API Keys →',
  },
  {
    title:'API Keys — Set in Railway',
    body:`<p style="color:var(--muted);margin-bottom:14px">Keys are set as <strong style="color:var(--cyan)">Railway environment variables</strong> — they persist across deploys and are never lost.</p>
    <div style="background:rgba(0,229,255,0.06);border:1px solid rgba(0,229,255,0.2);border-radius:10px;padding:12px;font-size:0.78rem;line-height:1.8">
      <div>1. Go to <strong>railway.app</strong> → your service</div>
      <div>2. Tap <strong>Variables</strong> tab</div>
      <div>3. Add these variables:</div>
      <div style="margin-top:8px;font-family:monospace;font-size:0.72rem;display:flex;flex-direction:column;gap:4px">
        <div style="color:var(--green)">ANTHROPIC_API_KEY = sk-ant-...</div>
        <div style="color:var(--amber)">PRINTIFY_API_TOKEN = your token</div>
        <div style="color:var(--purple)">ETSY_CLIENT_ID = your keystring</div>
      </div>
    </div>
    <p style="margin-top:10px;font-size:0.75rem;color:var(--muted)">Railway auto-restarts when you save. Keys are secure and never wiped.</p>`,
    btnText:"Got it! Let's Go 🚀",
  },
  {
    title:'Kingdom OS is Ready!',
    body:`<div style="text-align:center;padding:20px 0">
      <div style="font-size:3rem;margin-bottom:12px">⚔️</div>
      <p>Your autonomous revenue engine is online.</p>
      <p style="margin-top:10px;color:var(--muted)">The agents will start working immediately. Check back in a few hours to see your first opportunities!</p>
      <div style="margin-top:16px;padding:12px;background:rgba(0,255,136,0.06);border:1px solid rgba(0,255,136,0.2);border-radius:10px;font-size:0.78rem;color:var(--green)">
        ✓ Agents running every 4–48 hours<br>✓ Revenue attribution tracking sales<br>✓ Learning weights improving over time
      </div>
    </div>`,
    btnText:'Enter Kingdom →',
    last:true,
  },
];
function renderOBStep() {
  const step = OB_STEPS[obStep-1];
  document.querySelectorAll('.ob-step-dot').forEach((d,i)=>{d.classList.toggle('active',i===obStep-1);});
  document.getElementById('ob-body').innerHTML = `<h3 style="font-size:1rem;font-weight:700;margin-bottom:10px;color:var(--text)">${step.title}</h3>${step.body}`;
  document.getElementById('ob-footer').innerHTML = `
    ${obStep>1&&!step.last?'<button class="btn" onclick="obStep--;renderOBStep()">← Back</button>':'<span></span>'}
    <div style="display:flex;gap:8px;align-items:center">
      ${!step.last?'<button class="btn" style="color:var(--muted);font-size:0.75rem" onclick="skipOnboarding()">Skip setup →</button>':''}
      <button class="btn btn-primary" onclick="obNext()">${step.btnText}</button>
    </div>`;
}
async function obNext() {
  if (obStep===4) {
    document.getElementById('onboarding-overlay').classList.add('hidden');
    localStorage.setItem('kingdom_onboarded','1');
    triggerCelebration('KINGDOM UNLOCKED!','Your revenue engine is online','⚔️');
    return;
  }
  obStep++;
  renderOBStep();
}
function skipOnboarding() {
  document.getElementById('onboarding-overlay').classList.add('hidden');
  localStorage.setItem('kingdom_onboarded','1');
}
function checkOnboarding() {
  if (!localStorage.getItem('kingdom_onboarded')) {
    document.getElementById('onboarding-overlay').classList.remove('hidden');
    renderOBStep();
  }
}

/* ─── LIVERY FORGE ─── */
async function loadLiveryTab() {
  const r = await fetchJSON('/livery/commissions');
  document.getElementById('lv-total').textContent = r.total || 0;
  document.getElementById('lv-revenue').textContent = '£' + (r.total_revenue_gbp || 0).toFixed(0);
  document.getElementById('lv-pipeline').textContent = '£' + (r.pipeline_value_gbp || 0).toFixed(0);
  document.getElementById('lv-pending').textContent = (r.by_status?.preview_ready || 0) + (r.by_status?.approved || 0);
  renderCommissions(r.commissions || []);
}

function renderCommissions(list) {
  const el = document.getElementById('commission-list');
  if (!el) return;
  if (!list.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem;padding:16px 0;text-align:center">No commissions yet — click "+ New Commission" to add your first brief.</div>';
    return;
  }
  const statusCol = {draft:'var(--muted)',preview_ready:'var(--cyan)',approved:'var(--green)',delivered:'#f97316'};
  const statusLabel = {draft:'Draft',preview_ready:'Preview Ready',approved:'✅ Approved',delivered:'🏁 Delivered'};
  el.innerHTML = list.map(c => `
    <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">
      <div style="width:42px;height:42px;border-radius:8px;background:rgba(249,115,22,0.15);border:1px solid rgba(249,115,22,0.3);display:flex;align-items:center;justify-content:center;font-size:1.2rem;font-weight:900;color:#f97316;flex-shrink:0">${c.racing_number||'?'}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:0.8rem;font-weight:700;color:var(--text)">${c.client_name||'Anonymous'} — ${(c.car_class||'').toUpperCase()} · ${(c.style||'').toUpperCase()}</div>
        <div style="font-size:0.68rem;color:var(--muted);margin-top:2px">${c.game||''} ${c.driver_name ? '· '+c.driver_name : ''} ${c.notes ? '· '+c.notes.slice(0,50) : ''}</div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:0.75rem;font-weight:700;color:${statusCol[c.status]||'var(--muted)'}">${statusLabel[c.status]||c.status}</div>
        <div style="font-size:0.7rem;color:var(--green);margin-top:2px">£${c.price_gbp||0}</div>
      </div>
      <div style="display:flex;gap:5px;flex-shrink:0">
        ${c.preview_url
          ? `<button class="btn btn-sm" onclick="viewCommissionPreview(${c.id})" style="font-size:0.65rem;padding:4px 8px">👁 Preview</button>`
          : `<button class="btn btn-sm" onclick="generateCommissionPreview(${c.id})" style="font-size:0.65rem;padding:4px 8px;background:rgba(249,115,22,0.15);border-color:rgba(249,115,22,0.4);color:#f97316">🎨 Generate</button>`}
        ${c.status === 'preview_ready' ? `<button class="btn btn-sm btn-green" onclick="approveCommission(${c.id})" style="font-size:0.65rem;padding:4px 8px">✅ Approve</button>` : ''}
        ${c.status === 'approved' ? `<button class="btn btn-sm" onclick="deliverCommission(${c.id})" style="font-size:0.65rem;padding:4px 8px;background:rgba(249,115,22,0.2);border-color:rgba(249,115,22,0.5);color:#f97316">🏁 Mark Delivered</button>` : ''}
      </div>
    </div>`).join('');
}

function showNewCommissionForm() {
  const el = document.getElementById('new-commission-card');
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

async function createCommission() {
  const body = {
    client_name: document.getElementById('lv-client').value,
    car_class: document.getElementById('lv-car').value,
    style: document.getElementById('lv-style').value,
    racing_number: document.getElementById('lv-number').value || '17',
    driver_name: document.getElementById('lv-driver').value,
    primary_colour: document.getElementById('lv-primary').value,
    secondary_colour: document.getElementById('lv-secondary').value,
    sponsor_text: document.getElementById('lv-sponsor').value,
    game: document.getElementById('lv-game').value,
    notes: document.getElementById('lv-notes').value,
    price_gbp: parseFloat(document.getElementById('lv-price').value) || 40,
  };
  try {
    const r = await fetch('/livery/commissions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json();
    showToast(`Commission #${d.id} created — click Generate to make the preview`, 'success');
    document.getElementById('new-commission-card').style.display = 'none';
    loadLiveryTab();
  } catch(e) { showToast('Failed to create commission', 'error'); }
}

async function previewLiveryDraft() {
  const car = document.getElementById('lv-car').value;
  const style = document.getElementById('lv-style').value;
  const num = document.getElementById('lv-number').value || '17';
  const panel = document.getElementById('livery-preview-panel');
  const svg_el = document.getElementById('livery-preview-svg');
  panel.style.display = 'block';
  svg_el.innerHTML = '<div class="loading">Generating preview…</div>';
  try {
    const r = await fetch(`/livery/demo?car_class=${car}&style=${style}&number=${encodeURIComponent(num)}`);
    const svg = await r.text();
    svg_el.innerHTML = svg;
    document.getElementById('livery-preview-actions').innerHTML = `<span style="font-size:0.7rem;color:var(--muted)">Draft preview — ${car.toUpperCase()} · ${style.toUpperCase()}</span>`;
  } catch(e) { svg_el.innerHTML = '<div style="color:var(--red)">Preview failed</div>'; }
}

async function generateCommissionPreview(id) {
  showToast('Generating livery…', 'info');
  try {
    const r = await fetch(`/livery/commissions/${id}/generate`, {method:'POST'});
    const d = await r.json();
    if (d.preview_url) {
      showToast('Livery generated — click Preview to review', 'success');
      loadLiveryTab();
    }
  } catch(e) { showToast('Generation failed', 'error'); }
}

async function viewCommissionPreview(id) {
  const panel = document.getElementById('livery-preview-panel');
  const svgEl = document.getElementById('livery-preview-svg');
  const actions = document.getElementById('livery-preview-actions');
  panel.style.display = 'block';
  svgEl.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const r = await fetch(`/livery/commissions/${id}/preview`);
    const svg = await r.text();
    svgEl.innerHTML = svg;
    actions.innerHTML = `
      <a href="/livery/commissions/${id}/preview" download="livery_${id}.svg" class="btn btn-sm" style="font-size:0.68rem">💾 Download SVG</a>
      <button class="btn btn-sm btn-green" onclick="approveCommission(${id})" style="font-size:0.68rem">✅ Approve</button>`;
    panel.scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { svgEl.innerHTML = '<div style="color:var(--red)">Preview unavailable</div>'; }
}

async function approveCommission(id) {
  await fetch(`/livery/commissions/${id}/approve`, {method:'POST'});
  showToast('Commission approved — ready to deliver!', 'success');
  loadLiveryTab();
}

async function deliverCommission(id) {
  await fetch(`/livery/commissions/${id}/deliver`, {method:'POST'});
  showToast('Marked as delivered 🏁 — revenue recorded!', 'success');
  loadLiveryTab();
}

async function loadLiveryDemoGallery() {
  const gallery = document.getElementById('livery-gallery');
  const grid = document.getElementById('gallery-grid');
  gallery.style.display = 'block';
  grid.innerHTML = '<div class="loading">Loading style gallery…</div>';
  const styles = ['gulf','martini','jps','rothmans','neon','aggressive','retro','clean','stealth'];
  const previews = await Promise.allSettled(
    styles.map(s => fetch(`/livery/demo?car_class=gt3&style=${s}&number=1`).then(r => r.text()).then(svg => ({style:s, svg})))
  );
  grid.innerHTML = previews.map(p => {
    if (p.status !== 'fulfilled') return '';
    const {style, svg} = p.value;
    return `<div style="background:#050505;border-radius:8px;padding:8px;border:1px solid rgba(249,115,22,0.15);cursor:pointer"
      onclick="document.getElementById('lv-style').value='${style}';showNewCommissionForm()">
      <div style="overflow:hidden;border-radius:4px">${svg}</div>
      <div style="text-align:center;font-size:0.7rem;font-weight:700;color:#f97316;margin-top:6px;text-transform:uppercase">${style}</div>
    </div>`;
  }).join('');
  gallery.scrollIntoView({behavior:'smooth', block:'start'});
}

async function loadGigDescription() {
  const panel = document.getElementById('gig-copy-panel');
  const content = document.getElementById('gig-copy-content');
  panel.style.display = 'block';
  content.innerHTML = '<div class="loading">Claude is writing your Fiverr gig…</div>';
  try {
    const d = await fetchJSON('/livery/gig-description');
    if (d.error) { content.innerHTML = `<div style="color:var(--red)">${d.error}</div>`; return; }
    content.innerHTML = `
      <div style="margin-bottom:14px">
        <div style="font-size:0.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Gig Title</div>
        <div style="font-size:0.9rem;font-weight:700;color:var(--cyan);padding:10px;background:rgba(0,229,255,0.08);border-radius:6px;border-left:3px solid var(--cyan)">${d.title||''}</div>
      </div>
      <div style="margin-bottom:14px">
        <div style="font-size:0.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Description</div>
        <div style="font-size:0.75rem;color:var(--text);padding:10px;background:var(--surface);border-radius:6px;white-space:pre-wrap;line-height:1.6">${d.description||''}</div>
      </div>
      ${d.packages ? `<div style="margin-bottom:14px">
        <div style="font-size:0.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Packages</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
          ${(d.packages||[]).map(p=>`<div style="padding:10px;background:rgba(0,255,136,0.06);border:1px solid rgba(0,255,136,0.15);border-radius:6px">
            <div style="font-weight:700;color:var(--green);font-size:0.75rem">${p.name||''}</div>
            <div style="color:var(--amber);font-weight:800;font-size:1rem;margin:4px 0">${p.price||''}</div>
            <div style="font-size:0.65rem;color:var(--muted)">${p.includes||p.description||''}</div>
          </div>`).join('')}
        </div>
      </div>` : ''}
      ${d.faqs ? `<div>
        <div style="font-size:0.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">FAQs</div>
        ${(d.faqs||[]).map(f=>`<div style="margin-bottom:8px;padding:8px;background:var(--surface);border-radius:6px">
          <div style="font-size:0.72rem;font-weight:700;color:var(--text)">${f.question||f.q||''}</div>
          <div style="font-size:0.7rem;color:var(--muted);margin-top:4px">${f.answer||f.a||''}</div>
        </div>`).join('')}
      </div>` : ''}`;
  } catch(e) { content.innerHTML = '<div style="color:var(--red)">Generation failed</div>'; }
}

/* ─── GIG SCOUT ─── */
async function runGigScout() {
  const btns = ['gig-scout-btn','gig-scout-btn2'].map(id => document.getElementById(id));
  const status = document.getElementById('gig-scout-status');
  btns.forEach(b => { if(b){b.disabled=true; b.textContent='Analysing…';} });
  if (status) status.innerHTML = '💼 Claude is scoring 17+ Fiverr gig categories against our capabilities… ~30 seconds.';

  try {
    const r = await fetch('/gig-scout/run', {method:'POST'});
    const d = await r.json();
    if (status) {
      if (d.opportunities_created >= 0) {
        status.innerHTML = `✅ Done — <strong style="color:#c084fc">${d.opportunities_created} new gig opportunities</strong> scored and ranked.`;
        loadGigScoutResults();
      } else {
        status.innerHTML = `⚠️ ${d.error || 'Analysis finished — no high-scoring gigs found this run.'}`;
      }
    }
  } catch(e) {
    if (status) status.innerHTML = `❌ Failed: ${e.message}`;
  } finally {
    btns.forEach(b => { if(b){b.disabled=false; b.textContent=b.id==='gig-scout-btn'?'💼 Gig Scout':'▶ Analyse Gigs';} });
  }
}

async function loadGigScoutResults() {
  const cards = document.getElementById('gig-scout-cards');
  const summary = document.getElementById('gig-scout-summary');
  const wrapper = document.getElementById('gig-scout-results');
  const headline = document.getElementById('gig-scout-headline');
  if (!cards) return;
  try {
    const d = await fetchJSON('/gig-scout/opportunities?limit=16');
    const opps = d.opportunities || [];
    if (!opps.length) return;
    wrapper.style.display = 'block';

    // Headline
    const totalMkt = (d.total_market_value_gbp || 0).toLocaleString('en-GB', {style:'currency', currency:'GBP', maximumFractionDigits:0});
    if (headline) headline.textContent = `${opps.length} gig opportunities · ${totalMkt} total proven market value`;

    // Summary pills
    const byComp = {Low:0, Medium:0, High:0};
    opps.forEach(o => { if(byComp[o.competition]!==undefined) byComp[o.competition]++; });
    const topMkt = opps.reduce((a,b) => (a.implied_market_value_gbp||0)>(b.implied_market_value_gbp||0)?a:b, opps[0]);
    summary.innerHTML = [
      `<div style="background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.2);border-radius:8px;padding:8px 14px;text-align:center"><div style="font-size:1.4rem;font-weight:800;color:var(--green)">${byComp.Low}</div><div style="font-size:0.65rem;color:var(--muted)">Low Competition</div></div>`,
      `<div style="background:rgba(255,179,0,0.1);border:1px solid rgba(255,179,0,0.2);border-radius:8px;padding:8px 14px;text-align:center"><div style="font-size:1.4rem;font-weight:800;color:var(--amber)">${byComp.Medium}</div><div style="font-size:0.65rem;color:var(--muted)">Medium Comp.</div></div>`,
      `<div style="background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.2);border-radius:8px;padding:8px 14px;text-align:center"><div style="font-size:1.1rem;font-weight:800;color:#c084fc">${totalMkt}</div><div style="font-size:0.65rem;color:var(--muted)">Proven Market</div></div>`,
      topMkt ? `<div style="background:rgba(0,229,255,0.08);border:1px solid rgba(0,229,255,0.2);border-radius:8px;padding:8px 14px;flex:2"><div style="font-size:0.7rem;font-weight:700;color:var(--cyan)">🏆 Top Pick</div><div style="font-size:0.72rem;color:var(--text);margin-top:2px">${topMkt.title}</div><div style="font-size:0.65rem;color:var(--muted)">£${topMkt.implied_market_value_gbp?.toLocaleString()} market · ${topMkt.estimated_revenue}</div></div>` : '',
    ].join('');

    // Gig cards
    cards.innerHTML = opps.map(o => {
      const score = o.kingdom_score || 0;
      const scoreCol = score >= 70 ? 'var(--green)' : score >= 50 ? 'var(--amber)' : 'var(--red)';
      const compCol = o.competition === 'Low' ? 'var(--green)' : o.competition === 'Medium' ? 'var(--amber)' : 'var(--red)';
      const mktVal = (o.implied_market_value_gbp || 0).toLocaleString('en-GB', {style:'currency',currency:'GBP',maximumFractionDigits:0});
      const prodBadge = o.production_cost === 'Near-Zero' ? '🟢 Near-Zero cost' : o.production_cost === 'Low' ? '🟡 Low cost' : '🔴 Medium cost';
      return `<div class="card" style="padding:14px;border-color:rgba(139,92,246,0.15);position:relative">
        <div style="position:absolute;top:10px;right:10px;font-size:1.4rem;font-weight:800;color:${scoreCol}">${score}</div>
        <div style="font-size:0.78rem;font-weight:700;color:var(--text);margin-bottom:6px;padding-right:40px;line-height:1.3">${o.title}</div>
        <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px">
          <span style="font-size:0.62rem;padding:2px 6px;border-radius:4px;background:rgba(139,92,246,0.15);color:#c084fc">${o.platform || 'Fiverr'}</span>
          <span style="font-size:0.62rem;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.06);color:${compCol}">${o.competition || ''} comp.</span>
          <span style="font-size:0.62rem;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.06);color:var(--muted)">${prodBadge}</span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
          <div style="background:rgba(255,255,255,0.04);border-radius:6px;padding:6px;text-align:center">
            <div style="font-size:1rem;font-weight:700;color:#c084fc">£${o.typical_price_gbp || 0}</div>
            <div style="font-size:0.6rem;color:var(--muted)">per delivery</div>
          </div>
          <div style="background:rgba(255,255,255,0.04);border-radius:6px;padding:6px;text-align:center">
            <div style="font-size:0.85rem;font-weight:700;color:var(--cyan)">${mktVal}</div>
            <div style="font-size:0.6rem;color:var(--muted)">proven market</div>
          </div>
        </div>
        ${o.why_we_win ? `<div style="font-size:0.68rem;color:var(--muted);margin-bottom:6px">${o.why_we_win}</div>` : ''}
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <div style="font-size:0.7rem;color:var(--green)">Est. ${o.estimated_revenue || '?'}/mo</div>
          <div style="font-size:0.65rem;color:var(--muted)">${o.effort || ''} effort</div>
        </div>
        ${o.next_action ? `<div style="font-size:0.66rem;color:var(--amber);padding:5px 8px;background:rgba(255,179,0,0.07);border-radius:4px;border-left:2px solid var(--amber)">▶ ${o.next_action}</div>` : ''}
      </div>`;
    }).join('');
  } catch(e) { /* silent */ }
}

/* ─── PWA SERVICE WORKER ─── */
// Clear any stale caches from old SW versions on first load
if ('caches' in window) {
  caches.keys().then(keys => keys.filter(k => k !== 'kingdom-v2').forEach(k => caches.delete(k)));
}
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(err => console.warn('SW reg failed:', err));
  });
}

/* ─── PWA INSTALL PROMPT ─── */
let _pwaInstallPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  _pwaInstallPrompt = e;
  const btn = document.getElementById('pwa-install-btn');
  if (btn) { btn.style.display = 'flex'; }
});
window.addEventListener('appinstalled', () => {
  const btn = document.getElementById('pwa-install-btn');
  if (btn) btn.style.display = 'none';
  _pwaInstallPrompt = null;
});
function pwaInstall() {
  if (!_pwaInstallPrompt) return;
  _pwaInstallPrompt.prompt();
  _pwaInstallPrompt.userChoice.then(() => { _pwaInstallPrompt = null; });
}


/* ─── PIPELINE STATUS ─── */
async function loadPipelineStatus() {
  const el = document.getElementById('pipeline-status-grid');
  if (!el) return;
  try {
    const r = await fetch('/pipeline/status');
    const d = await r.json();
    const steps = d.steps || [];
    el.innerHTML = steps.map(s => {
      const ok = s.status === 'ok' || s.status === 'optional';
      const icon = s.status === 'ok' ? '✅' : s.status === 'optional' ? '🔵' : '❌';
      return `<div class="pipeline-step ${ok ? 'ok' : 'fail'}">
        <span class="ps-icon">${icon}</span>
        <div>
          <div class="ps-label">${s.step || s.label || ''}</div>
          <div class="ps-detail">${s.detail || ''}</div>
        </div>
      </div>`;
    }).join('');
    const score = steps.filter(s=>s.status==='ok'||s.status==='optional').length;
    const total = steps.length;
    const pct = Math.round(score/total*100);
    const summary = document.getElementById('pipeline-score');
    if (summary) {
      summary.textContent = `${score}/${total} steps healthy`;
      summary.style.color = pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--amber)' : 'var(--red)';
    }
  } catch(e) { el.innerHTML = '<p style="color:var(--muted)">Pipeline check unavailable</p>'; }
}

/* ─── KPI STRIP ─── */
async function loadKpiStrip() {
  const setKpi = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  const setClass = (id, cls) => { const el = document.getElementById(id); if (el) { el.classList.remove('profit','cost','agents','queue','health','revenue','target'); el.classList.add(cls); } };

  try {
    const [pnl, costs, sched, opps] = await Promise.allSettled([
      fetchJSON('/treasury/pnl?period=1m'),
      fetchJSON('/treasury/api-costs?days=1'),
      fetchJSON('/scheduler/status'),
      fetchJSON('/opportunities?limit=200'),
    ]);

    // Net P&L
    if (pnl.status === 'fulfilled' && pnl.value) {
      const v = pnl.value.net_pnl ?? pnl.value.net ?? 0;
      setKpi('kpi-net-pnl', fmtGBP(v));
      const cell = document.querySelector('.kpi-cell.profit');
      if (cell) { cell.style.borderTopColor = v >= 0 ? 'var(--profit-green)' : 'var(--cost-red)'; }
    }

    // Revenue today & target %
    if (pnl.status === 'fulfilled' && pnl.value) {
      const rev = pnl.value.revenue_today ?? pnl.value.revenue ?? 0;
      const target = pnl.value.monthly_target ?? 500;
      const revMonth = pnl.value.revenue_month ?? pnl.value.revenue ?? 0;
      setKpi('kpi-rev-today', fmtGBP(rev));
      const pct = target > 0 ? Math.min(100, (revMonth / target) * 100) : 0;
      setKpi('kpi-target-pct', pct.toFixed(0) + '%');
      const bar = document.getElementById('kpi-target-bar');
      if (bar) bar.style.width = pct + '%';
      // Hero stats
      const ovRev = document.getElementById('ov-rev-month');
      if (ovRev) ovRev.textContent = fmtGBP(revMonth);
      const ovRevTrend = document.getElementById('ov-rev-trend');
      if (ovRevTrend) { ovRevTrend.textContent = pct.toFixed(0) + '% of £' + target + ' target'; ovRevTrend.className = 'hs-trend neutral'; }
    }
    if (pnl.status === 'fulfilled' && pnl.value) {
      const v = pnl.value.net_pnl ?? pnl.value.net ?? 0;
      const ovPnl = document.getElementById('ov-pnl');
      if (ovPnl) ovPnl.textContent = fmtGBP(v);
      const ovPnlTrend = document.getElementById('ov-pnl-trend');
      if (ovPnlTrend) { ovPnlTrend.textContent = v >= 0 ? '▲ Profitable' : '▼ In deficit'; ovPnlTrend.className = 'hs-trend ' + (v >= 0 ? 'up' : 'down'); }
    }

    // API cost today
    if (costs.status === 'fulfilled' && costs.value) {
      const c = costs.value.total_cost_usd ?? costs.value.cost ?? 0;
      setKpi('kpi-api-cost', '$' + c.toFixed(3));
    }

    // Agents running / total
    if (sched.status === 'fulfilled' && sched.value) {
      const jobs = sched.value.jobs ?? [];
      const running = jobs.filter(j => j.status === 'running').length;
      setKpi('kpi-agents', running + ' / ' + jobs.length);
      const sub = document.getElementById('kpi-agents-sub');
      if (sub) sub.textContent = running > 0 ? 'active' : 'idle';
    }

    // Queue ready
    if (opps.status === 'fulfilled' && opps.value) {
      const items = opps.value.opportunities ?? opps.value ?? [];
      const ready = items.filter(o => o.status === 'ready' || o.status === 'pending').length;
      setKpi('kpi-queue', ready);
      const ovOpps = document.getElementById('ov-opps');
      if (ovOpps) ovOpps.textContent = ready;
      const ovOppsTrend = document.getElementById('ov-opps-trend');
      if (ovOppsTrend) { ovOppsTrend.textContent = ready > 0 ? '▲ ' + ready + ' ready to action' : 'none pending'; ovOppsTrend.className = 'hs-trend ' + (ready > 0 ? 'up' : 'neutral'); }
    }

    // System health
    try {
      const h = await fetchJSON('/health');
      const ok = h && (h.status === 'ok' || h.status === 'healthy');
      setKpi('kpi-health', ok ? '✓ OK' : '⚠ Warn');
      const cell = document.querySelector('.kpi-cell.health');
      if (cell) cell.style.borderTopColor = ok ? 'var(--profit-green)' : 'var(--cockpit-orange)';
    } catch (_) { setKpi('kpi-health', '? Unknown'); }
  } catch (e) {
    console.warn('KPI strip load error', e);
  }
}

/* ─── GOLD STANDARD CHECKLIST ─── */
async function loadGoldStandard() {
  const container = document.getElementById('gs-checklist');
  const scoreEl = document.getElementById('gs-score-num');
  const ringEl = document.getElementById('gs-ring-fill');
  const factsEl = document.getElementById('gs-score-facts');
  const lastEl = document.getElementById('gs-last-check');
  if (!container) return;
  container.innerHTML = '<p style="color:var(--muted);font-size:.8rem">Checking…</p>';

  const checks = [];
  const run = async (label, fn) => {
    try { const ok = await fn(); checks.push({ label, ok }); }
    catch (_) { checks.push({ label, ok: false }); }
  };

  await Promise.all([
    run('API health endpoint responding', async () => { const r = await fetchJSON('/health'); return r && (r.status === 'ok' || r.status === 'healthy'); }),
    run('Scheduler has registered jobs', async () => { const r = await fetchJSON('/scheduler/status'); return (r?.jobs?.length ?? 0) > 0; }),
    run('Treasury P&L endpoint live', async () => { const r = await fetchJSON('/treasury/pnl?period=1m'); return !!r; }),
    run('Opportunities endpoint live', async () => { const r = await fetchJSON('/opportunities?limit=1'); return !!r; }),
    run('Agent errors low (<10 today)', async () => { const r = await fetchJSON('/errors?limit=50'); const errs = r?.errors ?? r ?? []; const today = new Date().toISOString().slice(0,10); return errs.filter(e => (e.created_at ?? '').startsWith(today)).length < 10; }),
    run('AI brain callable', async () => { const r = await fetchJSON('/commander/chat-history?limit=1'); return !!r; }),
    run('Livery Forge routes live', async () => { const r = await fetchJSON('/livery/styles'); return !!(r?.styles?.length); }),
    run('Goals endpoint live', async () => { const r = await fetchJSON('/goals'); return !!r; }),
    run('Knowledge graph endpoint live', async () => { const r = await fetchJSON('/knowledge'); return Array.isArray(r); }),
    run('Treasury API costs tracked', async () => { const r = await fetchJSON('/treasury/api-costs?days=7'); return !!r; }),
  ]);

  const passed = checks.filter(c => c.ok).length;
  const total = checks.length;
  const score = Math.round((passed / total) * 100);

  // SVG ring
  if (ringEl) {
    const circ = 2 * Math.PI * 54; // r=54
    ringEl.style.strokeDasharray = circ;
    ringEl.style.strokeDashoffset = circ * (1 - score / 100);
    ringEl.style.stroke = score >= 80 ? 'var(--profit-green)' : score >= 60 ? 'var(--cockpit-orange)' : 'var(--cockpit-red)';
  }
  if (scoreEl) scoreEl.textContent = score;
  if (factsEl) factsEl.textContent = passed + ' / ' + total + ' checks passed';
  if (lastEl) lastEl.textContent = 'Last checked: ' + new Date().toLocaleTimeString();

  container.innerHTML = checks.map(c => `
    <div class="gs-item ${c.ok ? 'pass' : 'fail'}">
      <span class="gs-dot">${c.ok ? '✓' : '✗'}</span>
      <span>${c.label}</span>
    </div>`).join('');
}

/* ─── GAME PANEL SYSTEM ─── */
const PANEL_TAB_LABELS = {
  today:         'Today — needs you',
  overview:      'Treasury',
  pitwall:       'Pitwall Classics',
  pulsebreak:    'PulseBreak DnB',
  agents:        'Agents',
  opportunities: 'Opportunities',
  livery:        'Livery Forge',
  intelligence:  'Intelligence',
  command:       'Command Centre',
  tools:         'Tools',
  roadmap:       'Roadmap',
};

// Track which page div is currently live in the panel
let _panelState = { tab: null, el: null, parent: null };

function openPanel(tab) {
  const panel   = document.getElementById('side-panel');
  const titleEl = document.getElementById('side-panel-title');
  const bodyEl  = document.getElementById('side-panel-body');
  if (!panel) return;

  // Return the previous page element to its original home
  if (_panelState.el && _panelState.parent) {
    _panelState.el.style.removeProperty('display');
    _panelState.parent.appendChild(_panelState.el);
  }

  titleEl.textContent = PANEL_TAB_LABELS[tab] || tab.toUpperCase();
  bodyEl.innerHTML = '';

  const srcPage = document.getElementById('page-' + tab);
  if (srcPage) {
    // MOVE the actual element (not a clone) so getElementById works correctly
    _panelState = { tab, el: srcPage, parent: srcPage.parentElement };
    srcPage.style.setProperty('display', 'block', 'important');
    bodyEl.appendChild(srcPage);
  } else {
    _panelState = { tab: null, el: null, parent: null };
    bodyEl.innerHTML = '<div style="color:rgba(0,229,255,0.5);padding:20px;font-family:\'Press Start 2P\',monospace;font-size:0.55rem;text-align:center">Loading…</div>';
  }

  panel.classList.add('open');
  panel.scrollTop = 0;
  document.getElementById('kingdom-map-canvas').style.pointerEvents = 'none';
  document.getElementById('panel-backdrop').style.display = 'block';

  // Trigger lazy-loads — now getElementById finds the real elements
  const loaders = {
    today:         loadTodayTab,
    pitwall:       loadPitwallTab,
    pulsebreak:    loadPulsebreakTab,
    agents:        loadAgentsTab,
    opportunities: loadOpportunitiesTab,
    livery:        loadLiveryTab,
    intelligence:  loadIntelligenceTab,
    command:       loadCommandTab,
    tools:         loadToolsTab,
    roadmap:       loadGoldStandard,
  };
  if (loaders[tab]) loaders[tab]();
}

function closePanel() {
  const panel = document.getElementById('side-panel');
  if (!panel) return;

  // Return the page element to its original parent in the hidden DOM
  if (_panelState.el && _panelState.parent) {
    _panelState.el.style.removeProperty('display');
    _panelState.parent.appendChild(_panelState.el);
    _panelState = { tab: null, el: null, parent: null };
  }

  panel.classList.remove('open');
  document.getElementById('kingdom-map-canvas').style.pointerEvents = 'auto';
  document.getElementById('panel-backdrop').style.display = 'none';
  stopVisDemo();
  if (typeof stopAllAudio === 'function') stopAllAudio();
}

/* ─── AUDIO VISUALISER ─── */
let _visAudioCtx = null, _visAnalyser = null, _visRaf = null, _visDemoRaf = null, _visDemoMode = false;

function toggleVisDemo() {
  if (_visDemoMode) { stopVisDemo(); return; }
  _visDemoMode = true;
  const btn = document.getElementById('vis-demo-btn');
  if (btn) btn.textContent = '\u25a0 Stop';
  const st = document.getElementById('vis-status');
  if (st) st.textContent = 'Demo mode — synthetic DnB waveform';
  _drawVisDemo();
}

function stopVisDemo() {
  _visDemoMode = false;
  if (_visDemoRaf) { cancelAnimationFrame(_visDemoRaf); _visDemoRaf = null; }
  const btn = document.getElementById('vis-demo-btn');
  if (btn) btn.textContent = '\u25b6 Demo';
  const st = document.getElementById('vis-status');
  if (st) st.textContent = 'Select a file above to visualise';
}

/* ── Turntable style shared by the demo preview and the real-audio preview ──
   Mirrors the actual video renderer (backend/services/visualiser.py): black
   background, the PulseBreak logo spinning like a vinyl disc, and a smooth
   neon-green (#c8ff00) corona that breathes with the music instead of
   separate rainbow spike lines. */
const PB_LOGO_SRC = '/static/pulsebreak_logo.png';
let _pbLogoImg = null, _pbLogoReady = false;
function _getPBLogo() {
  if (!_pbLogoImg) {
    _pbLogoImg = new Image();
    _pbLogoImg.onload = () => { _pbLogoReady = true; };
    _pbLogoImg.onerror = () => { _pbLogoImg = 'failed'; };
    _pbLogoImg.src = PB_LOGO_SRC;
  }
  return _pbLogoReady ? _pbLogoImg : null;
}

/* discAngle persists per canvas across frames via a WeakMap keyed on canvas */
const _pbDiscAngles = new WeakMap();

function _drawTurntableFrame(ctx2, W, H, t, bass, mid, hi, bandAt, canvas) {
  const LIME = '#c8ff00';
  const cx = W/2, cy = H/2;
  const discR = Math.min(W,H) * 0.24;

  // Black background with a long trail (never blue/purple — brand is black+lime)
  ctx2.fillStyle = 'rgba(0,0,0,0.22)';
  ctx2.fillRect(0,0,W,H);

  // Subtle bass-driven vignette so the frame doesn't look flat
  const glow = ctx2.createRadialGradient(cx,cy,discR*0.5,cx,cy,Math.max(W,H)*0.6);
  glow.addColorStop(0, `rgba(200,255,0,${0.05+bass*0.08})`);
  glow.addColorStop(1, 'transparent');
  ctx2.fillStyle = glow; ctx2.fillRect(0,0,W,H);

  // ── Smooth neon-green corona (one continuous flowing shape, not spikes) ──
  const N = 64;
  const raw = new Array(N);
  for (let i=0;i<N;i++) raw[i] = bandAt(i, N);
  // heavy neighbour smoothing (two passes) → fluid wave instead of jagged bars
  const smoothOnce = (arr) => {
    const out = new Array(N);
    for (let i=0;i<N;i++){
      let s=0, wsum=0;
      for (let k=-4;k<=4;k++){
        const w = [1,2,4,8,12,8,4,2,1][k+4];
        s += arr[(i+k+N)%N]*w; wsum += w;
      }
      out[i] = s/wsum;
    }
    return out;
  };
  const smooth = smoothOnce(smoothOnce(raw));
  const pump = 1 + bass*0.12;
  // Precompute points then draw with quadratic curves through midpoints for
  // a fluid, rounded outline (no faceted corners)
  const pts = [];
  for (let i=0;i<N;i++){
    const ang = (i/N)*Math.PI*2 - Math.PI/2;
    const r = (discR*1.05 + (discR*0.12 + smooth[i]*discR*0.85)*pump);
    pts.push([cx+Math.cos(ang)*r, cy+Math.sin(ang)*r]);
  }
  ctx2.save();
  ctx2.beginPath();
  ctx2.moveTo((pts[0][0]+pts[N-1][0])/2, (pts[0][1]+pts[N-1][1])/2);
  for (let i=0;i<N;i++){
    const next = pts[(i+1)%N];
    const mid = [(pts[i][0]+next[0])/2, (pts[i][1]+next[1])/2];
    ctx2.quadraticCurveTo(pts[i][0], pts[i][1], mid[0], mid[1]);
  }
  ctx2.closePath();
  ctx2.fillStyle = 'rgba(200,255,0,0.16)';
  ctx2.shadowColor = LIME; ctx2.shadowBlur = 18+bass*20;
  ctx2.fill();
  ctx2.lineWidth = 2.5;
  ctx2.strokeStyle = 'rgba(235,255,180,0.9)';   // white-hot lime rim
  ctx2.stroke();
  ctx2.restore();

  // ── Spinning PulseBreak logo disc ──
  let angle = _pbDiscAngles.get(canvas) || 0;
  angle += 3.3 + bass*3.0;                       // ≈33⅓ rpm baseline, kicks with bass
  _pbDiscAngles.set(canvas, angle % 360);
  const logo = _getPBLogo();
  ctx2.save();
  ctx2.beginPath(); ctx2.arc(cx,cy,discR,0,Math.PI*2); ctx2.clip();
  ctx2.translate(cx,cy); ctx2.rotate(angle*Math.PI/180); ctx2.translate(-cx,-cy);
  if (logo) {
    ctx2.drawImage(logo, cx-discR, cy-discR, discR*2, discR*2);
  } else {
    // Fallback vinyl while the logo loads (or if missing)
    ctx2.fillStyle = '#0e0e10';
    ctx2.fillRect(cx-discR, cy-discR, discR*2, discR*2);
    for (let gr = discR*0.4; gr < discR; gr += discR*0.12) {
      ctx2.strokeStyle = 'rgba(60,70,60,0.8)'; ctx2.lineWidth = 1;
      ctx2.beginPath(); ctx2.arc(cx,cy,gr,0,Math.PI*2); ctx2.stroke();
    }
    ctx2.fillStyle = LIME;
    ctx2.beginPath(); ctx2.arc(cx,cy,discR*0.06,0,Math.PI*2); ctx2.fill();
  }
  ctx2.restore();
  // Thin lime ring around the disc edge
  ctx2.strokeStyle = 'rgba(200,255,0,0.6)'; ctx2.lineWidth = 2;
  ctx2.beginPath(); ctx2.arc(cx,cy,discR,0,Math.PI*2); ctx2.stroke();
}

function _drawVisDemo() {
  const canvas = document.getElementById('vis-canvas');
  if (!canvas || !_visDemoMode) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.offsetWidth || 360;
  const H = canvas.offsetHeight || 280;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx2 = canvas.getContext('2d');
  ctx2.scale(dpr, dpr);
  let t = 0;
  function frame() {
    if (!_visDemoMode) return;
    // Synthetic 174bpm DnB energy — same cadence as before, new visuals
    const kick  = Math.max(0, 1 - (t%21)/5);
    const snare = t%21 > 10 ? Math.max(0,1-(t%21-10)/4) : 0;
    const bass  = (Math.sin(t*0.07)*0.5+0.5)*0.7 + kick*0.3;
    const mid   = Math.sin(t*0.13+1)*0.3+0.3 + snare*0.2;
    const hi    = Math.random()*0.15*(Math.sin(t*0.4)>0.5?1:0.3) + snare*0.3;
    const bandAt = (i, n) => {
      const band = i < n*0.33 ? bass : i < n*0.66 ? mid : hi;
      return Math.max(0, Math.min(1, band + Math.sin(t*0.2+i*0.7)*0.08));
    };
    _drawTurntableFrame(ctx2, W, H, t, bass, mid, hi, bandAt, canvas);
    t++;
    _visDemoRaf = requestAnimationFrame(frame);
  }
  frame();
}

function startAudioVisualiser(file) {
  stopVisDemo();
  const canvas = document.getElementById('vis-canvas');
  const st = document.getElementById('vis-status');
  if (!canvas) return;
  if (st) st.textContent = 'Visualising: ' + file.name;
  if (_visAudioCtx) _visAudioCtx.close();
  if (_visRaf) cancelAnimationFrame(_visRaf);
  _visAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const reader = new FileReader();
  reader.onload = async e => {
    try {
      const buf = await _visAudioCtx.decodeAudioData(e.target.result);
      const src = _visAudioCtx.createBufferSource();
      _visAnalyser = _visAudioCtx.createAnalyser();
      _visAnalyser.fftSize = 512;
      src.buffer = buf;
      src.connect(_visAnalyser);
      _visAnalyser.connect(_visAudioCtx.destination);
      src.start(0);
      _drawVisAnalyser(canvas, _visAnalyser);
    } catch(err) {
      if (st) st.textContent = 'Preview unavailable — track uploaded OK';
    }
  };
  reader.readAsArrayBuffer(file);
}

function _drawVisAnalyser(canvas, analyser) {
  const data = new Uint8Array(analyser.frequencyBinCount);
  let t = 0, lastW = 0, lastH = 0;
  const ctx2 = canvas.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  function frame() {
    _visRaf = requestAnimationFrame(frame);
    analyser.getByteFrequencyData(data);
    const W = canvas.offsetWidth || 360, H = canvas.offsetHeight || 280;
    if (W !== lastW || H !== lastH) {           // only realloc when size changes
      canvas.width = W*dpr; canvas.height = H*dpr;
      lastW = W; lastH = H;
    }
    ctx2.setTransform(dpr,0,0,dpr,0,0);
    const n = data.length;
    const bass = data.slice(0,10).reduce((a,v)=>a+v,0)/10/255;
    const mid  = data.slice(10,80).reduce((a,v)=>a+v,0)/70/255;
    const hi   = data.slice(80,n).reduce((a,v)=>a+v,0)/(n-80)/255;
    const bandAt = (i, count) => {
      const bin = Math.floor((i/count)**1.3 * n*0.8);
      return data[Math.min(bin, n-1)]/255;
    };
    _drawTurntableFrame(ctx2, W, H, t, bass, mid, hi, bandAt, canvas);
    t++;
  }
  frame();
}

/* ─── CONTENT POSTS GENERATION ─── */
async function generateContentPosts() {
  const el = document.getElementById('content-posts');
  if (!el) return;
  el.innerHTML = '<div class="loading">Generating content…</div>';
  try {
    await fetch('/agents/trigger', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({agent:'Content Agent'}) });
  } catch(_) {}
  setTimeout(loadContentPosts, 2500);
}

// Close panel on Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closePanel(); closeHudMenu(); }
});

// Mobile: make the close button respond to raw touches (some mobile browsers
// swallow synthetic clicks over canvas-adjacent fixed elements), and support
// swipe-right-to-close on the panel header.
(function initPanelTouch() {
  const btn = document.getElementById('side-panel-close');
  if (btn) btn.addEventListener('touchend', e => { e.preventDefault(); closePanel(); }, { passive: false });
  const header = document.getElementById('side-panel-header');
  const panel = document.getElementById('side-panel');
  if (!header || !panel) return;
  let sx = null, sy = null;
  panel.addEventListener('touchstart', e => {
    sx = e.touches[0].clientX; sy = e.touches[0].clientY;
  }, { passive: true });
  panel.addEventListener('touchend', e => {
    if (sx === null) return;
    const dx = e.changedTouches[0].clientX - sx;
    const dy = e.changedTouches[0].clientY - sy;
    if (dx > 90 && Math.abs(dy) < 60) closePanel();   // swipe right anywhere → close
    sx = sy = null;
  }, { passive: true });
})();

function openHudMenu()  { const m = document.getElementById('hud-menu-modal'); if(m) m.classList.add('open'); }
function closeHudMenu() { const m = document.getElementById('hud-menu-modal'); if(m) m.classList.remove('open'); }

/* ─── HUD LOADER (XP / gold / agents) ─── */
async function loadHUD() {
  try {
    const [overview, sched] = await Promise.all([
      fetchJSON('/api/overview').catch(() => null),
      fetchJSON('/scheduler/status').catch(() => null),
    ]);

    // Gold
    const gold = overview?.revenue_today ?? overview?.monthly_revenue ?? 0;
    const goldEl = document.getElementById('hud-gold');
    if (goldEl) goldEl.textContent = '💰 £' + parseFloat(gold).toFixed(2) + ' GOLD';

    // Agents
    const jobs = sched?.jobs || [];
    const activeCount = jobs.filter(j => j.status === 'running').length;
    const totalCount  = jobs.length;
    const agentsEl = document.getElementById('hud-agents');
    if (agentsEl) agentsEl.textContent = `⚡ ${activeCount || totalCount} AGENTS`;

    // XP / Level (cosmetic: based on active jobs and opportunities)
    const opps = overview?.total_opportunities ?? 0;
    const xpRaw = (opps * 50) + (totalCount * 100);
    const level = Math.floor(xpRaw / 1000) + 1;
    const xpInLevel = xpRaw % 1000;
    const xpPct = (xpInLevel / 1000 * 100).toFixed(1);

    const levelEl = document.getElementById('hud-level-badge');
    if (levelEl) levelEl.textContent = 'LVL ' + level;
    const fillEl = document.getElementById('hud-xp-fill');
    if (fillEl) fillEl.style.width = xpPct + '%';
    const xpLbl = document.getElementById('hud-xp-label');
    if (xpLbl) xpLbl.textContent = `XP ${xpInLevel.toLocaleString()} / 1,000`;

    // Quest log — populate from running agents
    const questsEl = document.getElementById('hud-quests');
    if (questsEl && jobs.length > 0) {
      const quests = jobs.slice(0, 3).map(j =>
        `<div class="hud-quest"><span class="hud-quest-dot">●</span>${j.name || j.id}</div>`
      );
      if (quests.length) questsEl.innerHTML = quests.join('');
    }

    // Bottom ticker
    const tickerEl = document.getElementById('hud-ticker');
    if (tickerEl) {
      const now = new Date().toLocaleTimeString('en-GB', {hour:'2-digit',minute:'2-digit'});
      const runningName = jobs.find(j=>j.status==='running')?.name || 'IDLE';
      tickerEl.textContent = `${now}  ◆  ${runningName.toUpperCase()}`;
    }
  } catch (_) {}
}

/* ─── BOOT ─── */
document.addEventListener('DOMContentLoaded', () => {
  checkOnboarding();
  const wantTab = new URLSearchParams(location.search).get('tab');
  if (wantTab) setTimeout(() => { try { openPanel(wantTab); } catch(_){} }, 900);
  // City canvas boots lazily on first toggle — Command Center is home
  loadOverview();
  loadAttribution();
  loadPipelineStatus();
  loadKpiStrip();
  loadHUD();
  setTimeout(checkForUpdate, 5000);
  setInterval(loadOverview, 5*60*1000);
  setInterval(loadReminders, 90*1000);
  setInterval(loadPipelineStatus, 10*60*1000);
  setInterval(loadKpiStrip, 60*1000);
  setInterval(loadHUD, 60*1000);

  // Chat enter key
  document.getElementById('chat-input')?.addEventListener('keydown', e => {
    if (e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChatMessage();}
  });
});


/* ─── TODAY QUEUE ─── */
async function loadTodayTab() {
  const el = document.getElementById('today-list');
  if (!el) return;
  el.innerHTML = '<div style="color:var(--muted);font-size:0.8rem">Loading…</div>';
  let data;
  try {
    data = await fetchJSON('/today');
  } catch (e) {
    el.innerHTML = '<div style="color:#ff5555;font-size:0.8rem">Could not load the Today queue.</div>';
    return;
  }
  updateTodayBadge(data.total);
  if (!data.items || !data.items.length) {
    el.innerHTML = `<div style="text-align:center;padding:40px 12px;color:var(--muted)">
      <div style="font-size:2rem;margin-bottom:10px">✅</div>
      <div style="font-size:0.85rem">Nothing needs you right now.</div>
      <div style="font-size:0.7rem;margin-top:6px">Agents will queue tracks, drafts and opportunities here for approval.</div>
    </div>`;
    return;
  }
  el.innerHTML = data.items.map((it, i) => `
    <div class="today-item" id="today-item-${i}" style="border:1px solid var(--border);border-radius:10px;padding:12px;background:var(--surface)">
      <div style="display:flex;gap:8px;align-items:baseline">
        <span>${it.icon || '•'}</span>
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:0.85rem;overflow-wrap:anywhere">${escapeHtml(it.title || '')}</div>
          ${it.venture ? `<div style="font-size:0.65rem;color:var(--accent);letter-spacing:1px">${escapeHtml(it.venture)}</div>` : ''}
          ${it.detail ? `<div style="font-size:0.75rem;color:var(--muted);margin-top:4px;overflow-wrap:anywhere">${escapeHtml(it.detail)}</div>` : ''}
        </div>
      </div>
      <div style="display:flex;gap:8px;margin-top:10px">
        <button onclick='todayAct(${i}, ${JSON.stringify(JSON.stringify(it.approve))}, true)' style="flex:1;padding:10px;border-radius:8px;border:1px solid #00e676;background:rgba(0,230,118,0.12);color:#00e676;font-size:0.8rem;cursor:pointer">✓ Approve</button>
        <button onclick='todayAct(${i}, ${JSON.stringify(JSON.stringify(it.reject))}, false)' style="flex:1;padding:10px;border-radius:8px;border:1px solid #ff5555;background:rgba(255,85,85,0.1);color:#ff5555;font-size:0.8rem;cursor:pointer">✕ Reject</button>
      </div>
    </div>`).join('');
}

async function todayAct(idx, actionJson, approved) {
  const action = JSON.parse(actionJson);
  const card = document.getElementById('today-item-' + idx);
  try {
    const r = await fetch(action.url, {
      method: action.method || 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: action.body ? JSON.stringify(action.body) : undefined,
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    buzz(12);
    if (card) {
      card.style.opacity = '0.45';
      card.innerHTML = `<div style="text-align:center;color:${approved ? '#00e676' : '#ff5555'};font-size:0.8rem;padding:6px">${approved ? '✓ Approved' : '✕ Rejected'}</div>`;
      setTimeout(() => card.remove(), 1200);
    }
    refreshTodayBadge();
  } catch (e) {
    if (card) card.insertAdjacentHTML('beforeend', '<div style="color:#ff5555;font-size:0.7rem;margin-top:6px">Failed — try again.</div>');
  }
}

function updateTodayBadge(n) {
  const b = document.getElementById('today-badge');
  if (!b) return;
  if (n > 0) { b.textContent = n; b.style.display = 'inline-block'; }
  else b.style.display = 'none';
}

async function refreshTodayBadge() {
  try {
    const d = await fetchJSON('/today');
    updateTodayBadge(d.total || 0);
  } catch (_) {}
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// Badge on load + periodic refresh
refreshTodayBadge();
setInterval(refreshTodayBadge, 60000);


/* Coerce a value that may be a JSON string, comma list, or array into an array */
function asList(v) {
  if (Array.isArray(v)) return v;
  if (typeof v === 'string') {
    try { const j = JSON.parse(v); if (Array.isArray(j)) return j; } catch (_) {}
    return v ? v.split(',').map(s => s.trim()).filter(Boolean) : [];
  }
  return [];
}


/* ─── SOUND DNA ─── */
async function loadSoundDNA() {
  const el = document.getElementById('sound-dna');
  if (!el) return;
  try {
    const d = await fetchJSON('/vibes/sound-dna');
    if (d.status !== 'ok') { el.innerHTML = `<div style="color:var(--muted);font-size:0.7rem">${escapeHtml(d.message||'No data yet')}</div>`; return; }
    const dna = d.dna || {};
    el.innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">
        ${dna.bpm?`<span class="badge">~${Math.round(dna.bpm)} BPM</span>`:''}
        ${dna.dynamic_range_db?`<span class="badge">${dna.dynamic_range_db} dB dynamics</span>`:''}
        ${(dna.genre_mix||[]).slice(0,3).map(g=>`<span class="badge" style="border-color:#bf5fff;color:#bf5fff">${escapeHtml(g.sub_genre)} ×${g.tracks}</span>`).join('')}
        ${(dna.signature_moods||[]).map(m=>`<span class="badge" style="border-color:#00e676;color:#00e676">${escapeHtml(m)}</span>`).join('')}
      </div>` +
      (d.prompt_bank||[]).slice(0,4).map((b,i) => `
      <div style="border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-bottom:6px;font-size:0.68rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <b>${escapeHtml(b.sub_genre)}</b>
          <button class="btn btn-xs" onclick="copyDnaPrompt(${i},this)">Copy prompt</button>
        </div>
        <div id="dna-prompt-${i}" style="color:var(--muted);overflow-wrap:anywhere">${escapeHtml(b.suno_prompt)}</div>
      </div>`).join('') +
      `<div style="font-size:0.6rem;color:var(--muted);margin-top:4px">Built from ${d.tracks_analysed} track(s) in your library — updates as you upload more.</div>`;
  } catch(_) { el.innerHTML = '<div style="color:var(--muted);font-size:0.7rem">Unavailable</div>'; }
}

async function copyDnaPrompt(i, btn) {
  const el = document.getElementById('dna-prompt-' + i);
  if (!el) return;
  try { await navigator.clipboard.writeText(el.textContent); btn.textContent = 'Copied!'; }
  catch(_) { btn.textContent = 'Failed'; }
}


/* ─── NOW PLAYING MINI-PLAYER ───
   Only one review track plays at a time; a sticky bar shows what's playing
   with a big stop button that always works. */
function onReviewAudioPlay(el) {
  document.querySelectorAll('audio[data-track]').forEach(a => { if (a !== el) a.pause(); });
  let bar = document.getElementById('now-playing-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'now-playing-bar';
    bar.style.cssText = 'position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:10px;' +
      'background:rgba(3,4,16,0.97);border:1px solid #00e5ff;border-radius:10px;padding:10px 12px;' +
      'margin-bottom:10px;box-shadow:0 0 18px rgba(0,229,255,0.3)';
    const body = document.getElementById('side-panel-body');
    if (body) body.prepend(bar);
  }
  bar.innerHTML = `
    <span style="font-size:1.1rem;animation:pulse 1s infinite">🎧</span>
    <div style="flex:1;min-width:0">
      <div style="font-size:0.62rem;color:var(--muted);letter-spacing:1px">NOW PLAYING</div>
      <div style="font-size:0.8rem;font-weight:700;color:#00e5ff;overflow-wrap:anywhere">${escapeHtml(el.dataset.track||'Track')}</div>
    </div>
    <button onclick="stopAllAudio()" style="min-width:44px;min-height:44px;border-radius:10px;border:1.5px solid #ff5555;background:rgba(255,85,85,0.15);color:#ff5555;font-size:1rem;cursor:pointer">⏹</button>`;
  bar.style.display = 'flex';
}

function onReviewAudioStop() {
  // Hide the bar only if nothing is still playing
  const playing = [...document.querySelectorAll('audio[data-track]')].some(a => !a.paused && !a.ended);
  if (!playing) {
    const bar = document.getElementById('now-playing-bar');
    if (bar) bar.style.display = 'none';
  }
}

function stopAllAudio() {
  document.querySelectorAll('audio').forEach(a => { a.pause(); a.currentTime = 0; });
  const bar = document.getElementById('now-playing-bar');
  if (bar) bar.style.display = 'none';
}

/* ═══ COMMAND CENTER HOME ═══ */
let _cityInited = false;

function toggleCityView() {
  const on = document.body.classList.toggle('city-mode');
  if (on && !_cityInited) { _cityInited = true; initCanvas(); }
  const btn = document.getElementById('hud-menu-btn');
  if (btn) btn.textContent = on ? '⌂ HOME' : '⚔ MENU';
}
// Menu button doubles as Home when in city mode
(function hookMenuHome(){
  const btn = document.getElementById('hud-menu-btn');
  if (!btn) return;
  btn.onclick = () => {
    if (document.body.classList.contains('city-mode')) toggleCityView();
    else openHudMenu();
  };
})();

/* ── Rotating wireframe core sphere ── */
function startCoreSphere() {
  const cv = document.getElementById('core-sphere');
  if (!cv) return;
  const ctx2 = cv.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  // Fibonacci point cloud on a unit sphere
  const N = 220;
  const pts = [];
  const ga = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < N; i++) {
    const yy = 1 - (i / (N - 1)) * 2;
    const rr = Math.sqrt(1 - yy * yy);
    const th = ga * i;
    pts.push([Math.cos(th) * rr, yy, Math.sin(th) * rr]);
  }
  const sats = Array.from({length: 5}, (_, i) => ({
    tilt: (i / 5) * Math.PI, speed: 0.004 + i * 0.0013, phase: i * 2.1, rad: 1.35 + i * 0.16,
  }));

  let t = 0, lastW = 0, lastH = 0;
  let _sphereRot = 0;
  function frame() {
    if (document.body.classList.contains('city-mode') || document.hidden) { requestAnimationFrame(frame); return; }
    // Half frame rate on phones — indistinguishable, half the battery cost
    if (window.innerWidth < 700 && (t & 1)) { t++; requestAnimationFrame(frame); return; }
    const W = cv.offsetWidth || 360, H = cv.offsetHeight || 250;
    if (W !== lastW || H !== lastH) { cv.width = W * dpr; cv.height = H * dpr; lastW = W; lastH = H; }
    ctx2.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx2.clearRect(0, 0, W, H);
    const cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.34;
    // The core IS the system: spin speeds up with running agents,
    // halo warms amber when things need the founder, flashes gold on revenue
    const speed = 0.008 * (1 + Math.min(_ciState.running, 4) * 0.6);
    _sphereRot += speed;
    const rotY = _sphereRot, tiltX = 0.35;
    if (_ciState.revFlash > 0) _ciState.revFlash--;

    let haloCol = '70,150,230', haloA = 0.14;
    if (_ciState.revFlash > 0) { haloCol = '255,200,80'; haloA = 0.14 + 0.14 * (_ciState.revFlash / 120); }
    else if (_ciState.waiting > 0) { haloCol = '255,180,80'; haloA = 0.12 + 0.05 * Math.sin(t * 0.05); }
    else if (_ciState.running > 0) { haloA = 0.20 + 0.06 * Math.sin(t * 0.08); }

    const halo = ctx2.createRadialGradient(cx, cy, R * 0.4, cx, cy, R * 2.1);
    halo.addColorStop(0, `rgba(${haloCol},${haloA.toFixed(3)})`);
    halo.addColorStop(1, 'rgba(0,0,0,0)');
    ctx2.fillStyle = halo;
    ctx2.fillRect(0, 0, W, H);

    // Point cloud with depth-scaled alpha
    pts.forEach(p0 => {
      let [x, y, z] = p0;
      const x1 = x * Math.cos(rotY) + z * Math.sin(rotY);
      const z1 = -x * Math.sin(rotY) + z * Math.cos(rotY);
      const y1 = y * Math.cos(tiltX) - z1 * Math.sin(tiltX);
      const z2 = y * Math.sin(tiltX) + z1 * Math.cos(tiltX);
      const depth = (z2 + 1) / 2;
      const px = cx + x1 * R, py = cy + y1 * R;
      ctx2.globalAlpha = 0.12 + depth * 0.5;
      ctx2.fillStyle = depth > 0.72 ? '#bfe4ff' : '#3f87c9';
      ctx2.beginPath();
      ctx2.arc(px, py, 0.7 + depth * 1.0, 0, Math.PI * 2);
      ctx2.fill();
    });
    ctx2.globalAlpha = 1;

    // Meridian wireframe rings
    ctx2.strokeStyle = 'rgba(90,170,240,0.16)';
    ctx2.lineWidth = 0.8;
    for (let m = 0; m < 4; m++) {
      const a = rotY + (m / 4) * Math.PI;
      ctx2.beginPath();
      ctx2.ellipse(cx, cy, Math.abs(R * Math.cos(a)) + 0.001, R, 0, 0, Math.PI * 2);
      ctx2.stroke();
    }
    ctx2.beginPath();
    ctx2.ellipse(cx, cy, R, R * 0.32, 0, 0, Math.PI * 2);
    ctx2.stroke();

    // Orbiting satellites with trails
    sats.forEach(s2 => {
      const a = t * s2.speed + s2.phase;
      const or = R * s2.rad;
      const ox2 = Math.cos(a) * or, oy2 = Math.sin(a) * or * 0.3;
      const px = cx + ox2 * Math.cos(s2.tilt) - oy2 * Math.sin(s2.tilt);
      const py = cy + ox2 * Math.sin(s2.tilt) * 0.4 + oy2 * Math.cos(s2.tilt);
      ctx2.strokeStyle = 'rgba(90,170,240,0.10)';
      ctx2.beginPath();
      ctx2.ellipse(cx, cy, or, or * 0.3, s2.tilt * 0.4, 0, Math.PI * 2);
      ctx2.stroke();
      ctx2.fillStyle = '#9fd4ff';
      ctx2.shadowColor = '#5ab0ff'; ctx2.shadowBlur = 8;
      ctx2.beginPath(); ctx2.arc(px, py, 1.8, 0, Math.PI * 2); ctx2.fill();
      ctx2.shadowBlur = 0;
    });

    t++;
    requestAnimationFrame(frame);
  }
  frame();
}

/* ── Clock ── */
function startCIClock() {
  const el = document.getElementById('ci-clock');
  if (!el) return;
  const tickFn = () => {
    const d = new Date();
    el.textContent = d.toLocaleTimeString('en-GB', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  };
  tickFn();
  setInterval(tickFn, 1000);
}

/* ── Data modules ── */
let _ciState = { running: 0, waiting: 0, revenue: 0, revFlash: 0 };

async function loadCommandHome() {
  const [sched, lessons, overview, pipeline, health, live, perf] = await Promise.all([
    fetchJSON('/scheduler/status').catch(()=>null),
    fetchJSON('/lessons?limit=8').catch(()=>null),
    fetchJSON('/api/overview').catch(()=>null),
    fetchJSON('/pipeline/status').catch(()=>null),
    fetchJSON('/health').catch(()=>null),
    fetchJSON('/agents/live-status').catch(()=>null),
    fetchJSON('/agent-economics/performance').catch(()=>null),
  ]);

  // Feed the core sphere: it breathes with the system
  if (live) {
    _ciState.running = live.running_count || 0;
    _ciState.waiting = live.waiting_count || 0;
  }
  if (overview) {
    const rev = overview.revenue_today ?? 0;
    if (rev > _ciState.revenue) _ciState.revFlash = 120;   // gold pulse on new money
    _ciState.revenue = rev;
  }
  const _runsByAgent = {};
  (perf?.agent_performance || []).forEach(a => { _runsByAgent[a.agent] = a.runs_7d; });

  // System status pill
  const pill = document.getElementById('ci-system-status');
  if (pill && health) {
    const ok = health.status === 'healthy';
    pill.innerHTML = `<span class="ci-dot ${ok?'ok':'warn'}"></span>SYSTEM STATUS <b style="color:${ok?'#4ade80':'#ffb84d'}">${ok?'OPTIMAL':'DEGRADED'}</b>`;
  }

  // Core overview
  const ov = document.getElementById('ci-overview');
  if (ov) {
    const rows = [];
    const agents = sched?.agents || [];
    const running = agents.filter(a=>a.scheduler_running).length;
    rows.push({k:'Agents', v:`${agents.length} registered · ${running} scheduled`, ok:agents.length>0, go:'agents'});
    (pipeline?.steps||[]).forEach(st => rows.push({k:st.step, v:st.detail?.slice(0,42)||st.status, ok:st.status==='ok', go:'pulsebreak'}));
    if (overview) rows.push({k:'Revenue today', v:'£'+(overview.revenue_today??0).toFixed(2), ok:true, go:'overview'});
    ov.innerHTML = rows.map(r=>`
      <div class="ci-row ci-tap" onclick="openPanel('${r.go}')">
        <span class="ci-dot ${r.ok?'ok':'warn'}"></span>
        <span class="ci-k">${escapeHtml(r.k)}</span>
        <span class="ci-v">${escapeHtml(String(r.v))}</span>
      </div>`).join('');
  }

  // Intelligence feed
  const feed = document.getElementById('ci-feed');
  if (feed) {
    const items = (lessons?.lessons || lessons || []).slice(0,6);
    feed.innerHTML = items.length ? items.map(l=>`
      <div class="ci-row ci-tap" onclick="openPanel('intelligence')">
        <span class="ci-dot ok"></span>
        <div style="flex:1;min-width:0">
          <div class="ci-feed-txt">${escapeHtml((l.lesson||'').slice(0,110))}</div>
          <div class="ci-feed-src">${escapeHtml((l.source||'').toUpperCase())}<span class="ci-ago">${timeAgo(l.created_at)}</span></div>
        </div>
      </div>`).join('') : '<div class="ci-empty">No intelligence yet — run an agent.</div>';
  }

  // Active agents grid
  const ag = document.getElementById('ci-agents');
  if (ag && sched?.agents) {
    const maxRuns = Math.max(1, ...Object.values(_runsByAgent));
    ag.innerHTML = sched.agents.slice(0,8).map(a=>{
      const runs = _runsByAgent[a.name] || 0;
      const rel = runs / maxRuns;                      // real 7-day activity
      const bars = Array.from({length:10},(_,i)=>{
        const jitter = ((a.name.charCodeAt(i%a.name.length)*7+i*13)%30) - 15;
        const h = Math.max(8, Math.min(100, rel*80 + jitter));
        return `<i style="height:${h.toFixed(0)}%;animation-delay:${i*0.12}s"></i>`;
      }).join('');
      return `<div class="ci-agent" onclick="triggerAgent('${a.name.replace(/'/g,"\\'")}')" style="cursor:pointer">
        <div class="ci-agent-name">${escapeHtml(a.name)}</div>
        <div class="ci-agent-state ${a.scheduler_running?'on':'off'}">● ${a.scheduler_running?'ACTIVE':'STANDBY'}<span class="ci-runs">${runs}×/wk</span></div>
        <div class="ci-spark">${bars}</div>
      </div>`;
    }).join('');
  }

  // Gauges
  const gg = document.getElementById('ci-gauges');
  if (gg) {
    const agents = sched?.agents || [];
    const running = agents.filter(a=>a.scheduler_running).length;
    const pctA = agents.length ? Math.round(running/agents.length*100) : 0;
    let todayCount = 0;
    try { const t = await fetchJSON('/today'); todayCount = t?.total||0; } catch(_){}
    const rev = overview?.monthly_revenue ?? 0;
    const gauge = (pct, val, label, col, go) => {
      const r = 30, c = 2*Math.PI*r, off = c*(1-Math.min(pct,100)/100);
      return `<div class="ci-gauge ci-tap" onclick="openPanel('${go}')">
        <svg viewBox="0 0 74 74">
          <circle cx="37" cy="37" r="${r}" fill="none" stroke="rgba(120,180,255,0.12)" stroke-width="5"/>
          <circle cx="37" cy="37" r="${r}" fill="none" stroke="${col}" stroke-width="5"
            stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}"
            transform="rotate(-90 37 37)"/>
          <text x="37" y="42" text-anchor="middle" class="gv">${val}</text>
        </svg>
        <div class="gl">${label}</div>
      </div>`;
    };
    gg.innerHTML =
      gauge(pctA, running, 'Agents on', '#39c4f2', 'agents') +
      gauge(Math.min(todayCount*20,100), todayCount, 'Need you', todayCount>0?'#ffb84d':'#4ade80', 'today') +
      gauge(Math.min(rev,100), '£'+Math.round(rev), 'Month rev', '#4ade80', 'overview');
    // Today badge count doubles as core-state input
    _ciState.waiting = Math.max(_ciState.waiting, todayCount);
  }
}

function timeAgo(iso) {
  if (!iso) return '';
  const s2 = (Date.now() - new Date(iso + (iso.endsWith('Z')?'':'Z')).getTime()) / 1000;
  if (s2 < 90) return 'just now';
  if (s2 < 3600) return Math.round(s2/60) + 'm ago';
  if (s2 < 86400) return Math.round(s2/3600) + 'h ago';
  return Math.round(s2/86400) + 'd ago';
}

async function loadCIRevenue() {
  const el = document.getElementById('ci-revenue');
  if (!el) return;
  try {
    const o = await fetchJSON('/api/overview');
    const today = o?.revenue_today ?? 0, month = o?.monthly_revenue ?? 0;
    const daily = new Date().getDate() > 0 ? month / new Date().getDate() : 0;
    const up = today >= daily;
    el.innerHTML = `
      <div class="ci-rev-row">
        <div class="ci-rev-cell"><div class="ci-rev-v">£${today.toFixed(2)}</div><div class="ci-rev-l">Today</div></div>
        <div class="ci-rev-cell"><div class="ci-rev-v">£${month.toFixed(2)}</div><div class="ci-rev-l">This month</div></div>
        <div class="ci-rev-cell"><div class="ci-rev-v ${up?'up':'down'}">${up?'▲':'▼'}</div><div class="ci-rev-l">vs daily avg</div></div>
      </div>`;
  } catch(_) { el.innerHTML = '<div class="ci-empty">Revenue unavailable</div>'; }
}

/* ── 5. Voice input on TALK TO KINGDOM ── */
let _recognizing = false;
function talkToKingdom() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const bar = document.getElementById('ci-talk-bar');
  if (!SR || _recognizing) { toggleChat(); return; }
  try {
    const rec = new SR();
    rec.lang = 'en-GB';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    _recognizing = true;
    if (bar) { bar.classList.add('listening'); bar.childNodes.forEach(()=>{}); bar.innerHTML = '<span class="ci-talk-wave">〰〰〰</span> LISTENING… <span class="ci-talk-wave">〰〰〰</span>'; }
    const reset = () => {
      _recognizing = false;
      if (bar) bar.innerHTML = '<span class="ci-talk-wave">〰〰〰</span> TALK TO KINGDOM <span class="ci-talk-wave">〰〰〰</span>';
    };
    rec.onresult = (e) => {
      reset();
      const text = e.results[0][0].transcript;
      toggleChat();
      setTimeout(() => {
        const input = document.getElementById('chat-input');
        if (input) { input.value = text; sendChatMessage(); }
      }, 450);
    };
    rec.onerror = () => { reset(); toggleChat(); };
    rec.onend = reset;
    rec.start();
  } catch(_) { _recognizing = false; toggleChat(); }
}

// Boot the command home
if (document.getElementById('command-home')) {
  startCoreSphere();
  startCIClock();
  loadCommandHome();
  loadCIRevenue();
  setInterval(loadCommandHome, 30000);
  setInterval(loadCIRevenue, 60000);
}


/* ─── MOBILE POLISH ─── */
function buzz(pattern) {
  try { if (navigator.vibrate) navigator.vibrate(pattern); } catch(_) {}
}

/* Pull-to-refresh on the command home — essential in installed-PWA mode
   where there is no browser reload control */
(function initPullToRefresh() {
  const home = document.getElementById('command-home');
  if (!home) return;
  let startY = null, pulling = false;
  let indicator = null;
  const ensureIndicator = () => {
    if (indicator) return indicator;
    indicator = document.createElement('div');
    indicator.id = 'ptr-indicator';
    indicator.textContent = '↻';
    document.body.appendChild(indicator);
    return indicator;
  };
  home.addEventListener('touchstart', (e) => {
    if (home.scrollTop <= 0) { startY = e.touches[0].clientY; pulling = false; }
    else startY = null;
  }, { passive: true });
  home.addEventListener('touchmove', (e) => {
    if (startY === null) return;
    const dy = e.touches[0].clientY - startY;
    if (dy > 24) {
      pulling = true;
      const ind = ensureIndicator();
      ind.style.opacity = Math.min((dy - 24) / 70, 1);
      ind.style.transform = `translateX(-50%) translateY(${Math.min(dy * 0.35, 46)}px) rotate(${dy * 2}deg)`;
    }
  }, { passive: true });
  home.addEventListener('touchend', (e) => {
    if (startY === null) return;
    const dy = e.changedTouches[0].clientY - startY;
    const ind = ensureIndicator();
    if (pulling && dy > 90) {
      buzz(10);
      ind.classList.add('spinning');
      Promise.allSettled([loadCommandHome(), loadCIRevenue()]).then(() => {
        setTimeout(() => { ind.classList.remove('spinning'); ind.style.opacity = 0; }, 400);
        showToast('Refreshed', 'success', 1200);
      });
    } else {
      ind.style.opacity = 0;
    }
    startY = null; pulling = false;
  }, { passive: true });
})();

/* Battery guard: freeze all canvas work when the app is backgrounded */
let _appHidden = false;
document.addEventListener('visibilitychange', () => {
  _appHidden = document.hidden;
});
