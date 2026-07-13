// ---------------------------------------------------------------------------
// Visual Reuse Demo - Frontend Logic
// ---------------------------------------------------------------------------

// State
const imageHistory = [];
let nextPresetIndex = 0;

// ---------------------------------------------------------------------------
// Tab management
// ---------------------------------------------------------------------------

function switchTab(tab) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + tab).classList.remove('hidden');
  document.querySelector('[data-tab="' + tab + '"]').classList.add('active');
  if (tab === 'analytics') refreshAnalytics();
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function reuseBadge(changeType) {
  const badges = {
    'no_change': '<span class="badge badge-hit">REUSED</span>',
    'background_change': '<span class="badge badge-partial">PARTIAL REUSE</span>',
    'outfit_change': '<span class="badge badge-partial">PARTIAL REUSE</span>',
    'accessory_change': '<span class="badge badge-partial">PARTIAL REUSE</span>',
    'full_miss': '<span class="badge badge-miss">NEW RESULT</span>',
    'full_change': '<span class="badge badge-miss">NEW RESULT</span>',
  };
  return badges[changeType] || '<span class="badge badge-miss">MISS</span>';
}

function formatMs(ms) {
  if (ms >= 1000) return (ms / 1000).toFixed(1) + 's';
  return Math.round(ms) + 'ms';
}

function formatCost(dollars) {
  if (dollars >= 1) return '$' + dollars.toFixed(0);
  if (dollars >= 0.01) return '$' + dollars.toFixed(2);
  return '$' + dollars.toFixed(4);
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (loading) {
    btn.disabled = true;
    btn.dataset.origText = btn.textContent;
    btn.innerHTML = '<span class="spinner"></span> Working...';
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.origText || 'Generate';
  }
}

// ---------------------------------------------------------------------------
// Workflow Path Visualization
// ---------------------------------------------------------------------------

function getReuseTier(data) {
  if (data.change_type === 'no_change') return 'l1';
  if (data.reuse_hit && ['background_change', 'outfit_change', 'accessory_change'].includes(data.change_type)) return 'partial';
  return 'gen';
}

function startPipelineAnimation() {
  const tiers = ['pipe-l1', 'pipe-l2', 'pipe-gen'];
  tiers.forEach(id => {
    const el = document.getElementById(id);
    el.className = 'pipeline-tier';
  });
  // Animate checking state with stagger
  setTimeout(() => document.getElementById('pipe-l1').classList.add('tier-checking'), 100);
  setTimeout(() => document.getElementById('pipe-l2').classList.add('tier-checking'), 400);
  setTimeout(() => document.getElementById('pipe-gen').classList.add('tier-checking'), 700);
}

function renderPipeline(data) {
  const tier = getReuseTier(data);
  const l1 = document.getElementById('pipe-l1');
  const l2 = document.getElementById('pipe-l2');
  const gen = document.getElementById('pipe-gen');

  // Reset all
  [l1, l2, gen].forEach(el => {
    el.className = 'pipeline-tier';
  });

  if (tier === 'l1') {
    l1.classList.add('tier-hit');
  } else if (tier === 'l2') {
    l1.classList.add('tier-pass');
    l2.classList.add('tier-hit');
  } else if (tier === 'partial') {
    l1.classList.add('tier-pass');
    l2.classList.add('tier-pass');
    gen.classList.add('tier-gen');
  } else {
    // full miss
    l1.classList.add('tier-pass');
    l2.classList.add('tier-pass');
    gen.classList.add('tier-gen');
  }
}

function resetPipeline() {
  ['pipe-l1', 'pipe-l2', 'pipe-gen'].forEach(id => {
    const el = document.getElementById(id);
    el.className = 'pipeline-tier';
  });
}

// ---------------------------------------------------------------------------
// Part Breakdown
// ---------------------------------------------------------------------------

const ALL_PARTS = [
  'Face & Hair', 'Upper Body', 'Upper Garment',
  'Lower Garment', 'Footwear', 'Background',
  'Style & Lighting', 'Framing Guide'
];

function renderPartBreakdown(reused, regenerated, changeType) {
  const tiles = document.querySelectorAll('#part-breakdown .part-tile');

  tiles.forEach(tile => {
    const name = tile.dataset.part;
    const statusEl = tile.querySelector('.part-tile-status');

    tile.classList.remove('part-reused', 'part-new', 'part-idle');

    if (changeType === 'full_miss' || (regenerated.length === 1 && regenerated[0] === 'all')) {
      tile.classList.add('part-new');
      statusEl.textContent = 'NEW';
    } else if (changeType === 'no_change') {
      tile.classList.add('part-reused');
      statusEl.textContent = 'REUSED';
    } else if (reused.includes(name)) {
      tile.classList.add('part-reused');
      statusEl.textContent = 'REUSED';
    } else if (regenerated.includes(name)) {
      tile.classList.add('part-new');
      statusEl.textContent = 'NEW';
    } else {
      tile.classList.add('part-idle');
      statusEl.textContent = '--';
    }
  });
}

function resetPartBreakdown() {
  const tiles = document.querySelectorAll('#part-breakdown .part-tile');
  tiles.forEach(tile => {
    tile.classList.remove('part-reused', 'part-new', 'part-idle');
    tile.querySelector('.part-tile-status').textContent = '--';
  });
}

// ---------------------------------------------------------------------------
// Decision Layer (epic-cache-router-lab)
// ---------------------------------------------------------------------------

const ROUTE_BADGES = {
  'return_cached': '<span class="badge badge-hit">RETURN CACHED</span>',
  'surgical_edit': '<span class="badge badge-partial">SURGICAL EDIT</span>',
  'camera_or_pose_change': '<span class="badge badge-partial">CAMERA / POSE</span>',
  'identity_locked_regen': '<span class="badge badge-regen">IDENTITY-LOCKED REGEN</span>',
  'fresh_generation': '<span class="badge badge-miss">FRESH GENERATION</span>',
  'manual_review': '<span class="badge badge-review">MANUAL REVIEW</span>',
};

const ROUTE_LABELS = {
  'return_cached': 'Return Cached',
  'surgical_edit': 'Surgical Edit',
  'camera_or_pose_change': 'Camera / Pose',
  'identity_locked_regen': 'Identity-Locked Regen',
  'fresh_generation': 'Fresh Generation',
  'manual_review': 'Manual Review',
};

function renderDecisionLayer(router) {
  if (!router) return;

  document.getElementById('dl-route-badge').innerHTML =
    ROUTE_BADGES[router.route] || '<span class="badge badge-miss">' + router.route + '</span>';
  document.getElementById('dl-rationale').textContent = router.rationale || '';

  document.getElementById('dl-mode').textContent = router.generation_mode || '--';
  document.getElementById('dl-start').textContent = router.starting_point || '--';
  document.getElementById('dl-matched').textContent = router.matched_panel_id || 'none';

  const cont = router.continuity || {};
  const driftEl = document.getElementById('dl-drift');
  driftEl.textContent = (cont.drift_score != null) ? cont.drift_score.toFixed(3) : '--';
  driftEl.className = 'font-mono ' + (cont.drift_score > 0.25 ? 'text-amber-400' : 'text-emerald-400/80');

  const costEl = document.getElementById('dl-cost');
  costEl.textContent = (router.estimated_cost_units != null) ? router.estimated_cost_units.toFixed(2) : '--';
  costEl.className = 'font-mono ' + (router.estimated_cost_units === 0 ? 'text-emerald-400' : 'text-white/60');

  const gatesEl = document.getElementById('dl-gates');
  if (cont.passed === true) {
    gatesEl.textContent = 'PASS';
    gatesEl.className = 'font-mono text-emerald-400';
  } else if (cont.passed === false) {
    gatesEl.textContent = 'FAIL';
    gatesEl.className = 'font-mono text-amber-400';
  } else {
    gatesEl.textContent = '--';
    gatesEl.className = 'font-mono text-white/60';
  }

  const backend = router.backend_profile || {};
  const backendEl = document.getElementById('dl-backend');
  const OPERATION_LABELS = {
    'serve_cached': 'serve cached',
    'multi_reference_edit': 'klein multi-ref edit',
    'multi_reference_regen': 'klein multi-ref regen',
    'text_to_image': 'klein txt2img',
    'hold_for_review': 'hold',
  };
  backendEl.textContent = OPERATION_LABELS[backend.operation] || '--';
  if (backend.detail) backendEl.title = backend.detail;

  const refkvEl = document.getElementById('dl-refkv');
  if (backend.reference_kv) {
    refkvEl.textContent = 'step-0, reused x' + (backend.steps || 4);
    refkvEl.className = 'font-mono text-emerald-400/80';
    if (backend.published_speedup) refkvEl.title = backend.published_speedup;
  } else {
    refkvEl.textContent = 'n/a';
    refkvEl.className = 'font-mono text-white/40';
  }

  const chips = [];
  (router.risk_flags || []).forEach(f => chips.push('<span class="dl-chip">' + f + '</span>'));
  (cont.failure_reasons || []).forEach(r => chips.push('<span class="dl-chip dl-chip-warn">' + r + '</span>'));
  if (router.requires_review) chips.push('<span class="dl-chip dl-chip-warn">human review</span>');
  document.getElementById('dl-flags').innerHTML = chips.join('');
}

function resetDecisionLayer() {
  document.getElementById('dl-route-badge').innerHTML = '';
  document.getElementById('dl-rationale').textContent = 'Run a request to see the routing decision.';
  ['dl-mode', 'dl-start', 'dl-drift', 'dl-cost', 'dl-matched', 'dl-gates', 'dl-backend', 'dl-refkv'].forEach(id => {
    const el = document.getElementById(id);
    el.textContent = '--';
    el.className = 'font-mono text-white/60';
  });
  document.getElementById('dl-flags').innerHTML = '';
}

function renderRouterAnalytics(router) {
  if (!router) return;
  const cost = router.cost || {};

  const savings = cost.estimated_savings_ratio;
  document.getElementById('dl-stat-savings').textContent =
    (savings != null && cost.total_requests > 0) ? (savings * 100).toFixed(0) + '%' : '--';
  document.getElementById('dl-stat-avoided').textContent =
    (cost.avoided_model_calls != null) ? cost.avoided_model_calls : '--';
  document.getElementById('dl-stat-drift').textContent =
    (router.avg_drift_score != null) ? router.avg_drift_score.toFixed(3) : '--';

  const unsafeEl = document.getElementById('dl-stat-unsafe');
  unsafeEl.textContent = (router.unsafe_reuse_count != null) ? router.unsafe_reuse_count : '--';
  unsafeEl.className = 'text-2xl font-bold font-mono ' +
    (router.unsafe_reuse_count > 0 ? 'text-red-400' : 'text-emerald-400');

  document.getElementById('dl-stat-baseline').textContent =
    (cost.baseline_cost_units != null) ? cost.baseline_cost_units.toFixed(2) + ' units' : '--';
  document.getElementById('dl-stat-routed').textContent =
    (cost.routed_cost_units != null) ? cost.routed_cost_units.toFixed(2) + ' units' : '--';
  document.getElementById('dl-stat-review').textContent =
    (cost.review_count != null) ? cost.review_count : '--';
  document.getElementById('dl-stat-panels').textContent =
    (router.stored_panels != null) ? router.stored_panels : '--';

  const barsEl = document.getElementById('dl-route-bars');
  const dist = router.route_distribution || {};
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  if (total > 0) {
    const colors = {
      'return_cached': 'bg-emerald-500',
      'surgical_edit': 'bg-blue-500',
      'camera_or_pose_change': 'bg-sky-500',
      'identity_locked_regen': 'bg-amber-500',
      'fresh_generation': 'bg-red-500',
      'manual_review': 'bg-purple-500',
    };
    barsEl.innerHTML = Object.entries(dist).map(([route, count]) => {
      const pct = ((count / total) * 100).toFixed(0);
      const barColor = colors[route] || 'bg-gray-500';
      const lbl = ROUTE_LABELS[route] || route;
      return '<div>' +
        '<div class="flex justify-between text-xs mb-1"><span class="text-white/40">' + lbl + '</span><span class="text-white/30 font-mono">' + count + ' (' + pct + '%)</span></div>' +
        '<div class="h-1.5 bg-white/[0.04] rounded-full overflow-hidden"><div class="h-full ' + barColor + ' rounded-full" style="width:' + pct + '%"></div></div>' +
        '</div>';
    }).join('');
  } else {
    barsEl.innerHTML = '<div class="text-white/30 text-sm">No data yet</div>';
  }
}

// ---------------------------------------------------------------------------
// Image demo
// ---------------------------------------------------------------------------

async function runImage() {
  const prompt = document.getElementById('img-prompt').value.trim();
  if (!prompt) return;

  setLoading('img-run-btn', true);

  // Show loading in image display
  document.getElementById('img-display').innerHTML =
    '<div class="flex flex-col items-center gap-2"><span class="spinner"></span><span class="text-white/30 text-xs">Preparing image...</span></div>';

  // Reset part breakdown and start pipeline animation
  resetPartBreakdown();
  startPipelineAnimation();

  try {
    const res = await fetch('/api/image/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    const data = await res.json();

    displayResult(data);
    highlightUsedPreset(prompt);

    // Add to history
    data._ts = Date.now();
    imageHistory.unshift(data);
    renderImageHistory();

  } catch (err) {
    document.getElementById('img-display').innerHTML =
      '<div class="text-red-400/60 text-sm">Error: ' + err.message + '</div>';
    resetPipeline();
  } finally {
    setLoading('img-run-btn', false);
  }
}

function highlightUsedPreset(prompt) {
  const buttons = document.querySelectorAll('#img-presets .preset-chip');
  buttons.forEach(btn => {
    btn.classList.remove('preset-used');
    if (btn.dataset.prompt === prompt) {
      btn.classList.add('preset-used');
    }
  });
}

// ---------------------------------------------------------------------------
// Display result in main view (reused by generate + history click)
// ---------------------------------------------------------------------------

function displayResult(data) {
  // Update image display
  if (data.image_available) {
    document.getElementById('img-display').innerHTML =
      '<img src="/images/' + data.image_hash + '.png?t=' + (data._ts || Date.now()) + '" alt="Generated image" class="w-full h-full object-contain cursor-pointer" onclick="openLightbox(0)">';
  } else {
    document.getElementById('img-display').innerHTML =
      '<div class="text-red-400/60 text-sm">Image generation failed</div>';
  }

  // Update reuse badge
  document.getElementById('img-reuse-badge').innerHTML = reuseBadge(data.change_type);

  // Update summary metrics
  const changeLabels = {
    'no_change': 'EXACT HIT',
    'background_change': 'SCENE UPDATE',
    'outfit_change': 'OUTFIT UPDATE',
    'accessory_change': 'ACCESSORY UPDATE',
    'full_miss': 'NEW RESULT',
    'full_change': 'NEW RESULT',
  };
  document.getElementById('img-change-type').textContent = changeLabels[data.change_type] || data.change_type;

  const changeColor = data.reuse_hit ? 'text-emerald-400' : 'text-amber-400';
  document.getElementById('img-change-type').className = 'font-mono ' + changeColor;

  // Latency
  document.getElementById('img-total-latency').textContent = formatMs(data.total_latency_ms);
  document.getElementById('img-total-latency').className = 'font-mono text-sm ' +
    (data.reuse_hit ? 'text-emerald-400' : 'text-amber-400');

  // Cost (summary bar)
  document.getElementById('img-cost').textContent = data.cost_saved > 0 ? formatCost(data.cost_saved) + ' saved' : '--';
  document.getElementById('img-cost').className = 'font-mono text-sm ' +
    (data.cost_saved > 0 ? 'text-emerald-400' : 'text-white/30');

  // Cost (detail card)
  const costDetailEl = document.getElementById('img-cost-detail');
  if (costDetailEl) {
    costDetailEl.textContent = data.cost_saved > 0 ? formatCost(data.cost_saved) : '--';
    costDetailEl.className = 'font-mono ' + (data.cost_saved > 0 ? 'text-emerald-400/80' : 'text-white/30');
  }

  // Parts
  const reusedCount = data.parts_reused ? data.parts_reused.length : 0;
  const regenCount = data.parts_refreshed ? (data.parts_refreshed[0] === 'all' ? 8 : data.parts_refreshed.length) : 0;
  document.getElementById('img-parts-reused').textContent = reusedCount + '/8';
  document.getElementById('img-parts-refresh').textContent = regenCount + '/8';

  // Part breakdown grid
  renderPartBreakdown(
    data.parts_reused || [],
    data.parts_refreshed || [],
    data.change_type
  );

  // Pipeline visualization
  renderPipeline(data);

  // Decision layer card
  renderDecisionLayer(data.router);

  // Update prompt input
  if (data.prompt) {
    document.getElementById('img-prompt').value = data.prompt;
  }
}

function loadFromHistory(index) {
  const d = imageHistory[index];
  if (!d) return;
  displayResult(d);
  highlightUsedPreset(d.prompt || '');
}

function renderImageHistory() {
  const container = document.getElementById('img-history-list');
  container.innerHTML = imageHistory.slice(0, 20).map((d, i) => {
    const changeLabels = {
      'no_change': 'REUSE',
      'background_change': 'BG',
      'outfit_change': 'OUT',
      'accessory_change': 'ACC',
      'full_miss': 'GEN',
    };
    const label = changeLabels[d.change_type] || 'GEN';
    const color = d.reuse_hit ? 'color:#2dd4bf' : (d.change_type === 'full_miss' ? 'color:#f87171' : 'color:#fbbf24');

    if (d.image_available) {
      return '<div class="img-history-card" onclick="loadFromHistory(' + i + ')" title="' + (d.prompt || '').replace(/"/g, '&quot;') + '">' +
        '<img src="/images/' + d.image_hash + '.png?t=' + (d._ts || '') + '" alt="">' +
        '<div class="overlay">' +
        '<span style="' + color + '">' + label + '</span>' +
        '<span style="color:rgba(255,255,255,0.35)">' + formatMs(d.total_latency_ms) + '</span>' +
        '</div></div>';
    }
    return '<div class="img-history-card flex items-center justify-center" style="background:#1a1a22" onclick="loadFromHistory(' + i + ')">' +
      '<div class="text-center p-1"><div style="' + color + ';font-size:8px">' + label + '</div>' +
      '<div style="color:rgba(255,255,255,0.2);font-size:7px" class="mt-0.5">' + formatMs(d.total_latency_ms) + '</div></div></div>';
  }).join('');
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

async function refreshAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();

    document.getElementById('stat-runs').textContent = data.total_runs;
    document.getElementById('stat-hit-rate').textContent = (data.hit_rate * 100).toFixed(0) + '%';
    document.getElementById('stat-calls').textContent = data.total_calls;
    document.getElementById('stat-saved').textContent = formatCost(data.total_cost_saved);

    const img = data.image;
    document.getElementById('img-stat-runs').textContent = img.runs;
    document.getElementById('img-stat-rate').textContent = (img.hit_rate * 100).toFixed(0) + '%';
    document.getElementById('img-stat-hits').textContent = img.hits;
    document.getElementById('img-stat-misses').textContent = img.misses;
    document.getElementById('img-stat-bar').style.width = (img.hit_rate * 100) + '%';
    document.getElementById('img-stat-saved').textContent = formatCost(img.cost_saved);

    const ctBars = document.getElementById('change-type-bars');
    const ct = data.change_types || {};
    const total = Object.values(ct).reduce((a, b) => a + b, 0);
    if (total > 0) {
      const colors = {
        'full_miss': 'bg-red-500',
        'background_change': 'bg-blue-500',
        'outfit_change': 'bg-amber-500',
        'accessory_change': 'bg-purple-500',
        'no_change': 'bg-emerald-500',
      };
      const labels = {
        'full_miss': 'New Result',
        'background_change': 'Scene Update',
        'outfit_change': 'Outfit Update',
        'accessory_change': 'Accessory Update',
        'no_change': 'Exact Reuse',
      };
      ctBars.innerHTML = Object.entries(ct).map(([type, count]) => {
        const pct = ((count / total) * 100).toFixed(0);
        const barColor = colors[type] || 'bg-gray-500';
        const lbl = labels[type] || type;
        return '<div>' +
          '<div class="flex justify-between text-xs mb-1"><span class="text-white/40">' + lbl + '</span><span class="text-white/30 font-mono">' + count + ' (' + pct + '%)</span></div>' +
          '<div class="h-1.5 bg-white/[0.04] rounded-full overflow-hidden"><div class="h-full ' + barColor + ' rounded-full" style="width:' + pct + '%"></div></div>' +
          '</div>';
      }).join('');
    }

    renderRouterAnalytics(data.router);

  } catch (err) {
    // Silent fail
  }
}

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

async function resetReuse() {
  if (!confirm('Reset all reuses and analytics?')) return;

  try {
    await fetch('/api/reset/all', { method: 'POST' });
    imageHistory.length = 0;
    renderImageHistory();
    resetPartBreakdown();
    resetPipeline();
    resetDecisionLayer();
    document.getElementById('img-reuse-badge').innerHTML = '';
    document.getElementById('img-change-type').textContent = '--';
    document.getElementById('img-change-type').className = 'font-mono text-white/50';
    document.getElementById('img-total-latency').textContent = '--';
    document.getElementById('img-total-latency').className = 'font-mono text-sm text-white/40';
    document.getElementById('img-cost').textContent = '--';
    document.getElementById('img-cost').className = 'font-mono text-sm text-white/40';
    document.getElementById('img-parts-reused').textContent = '--';
    document.getElementById('img-parts-refresh').textContent = '--';
    const costDetailEl = document.getElementById('img-cost-detail');
    if (costDetailEl) {
      costDetailEl.textContent = '--';
      costDetailEl.className = 'font-mono text-white/30';
    }
    document.getElementById('img-display').innerHTML =
      '<span class="text-white/20 text-sm">Click a preset to begin the demo</span>';
    document.querySelectorAll('#img-presets .preset-chip').forEach(btn => {
      btn.classList.remove('preset-used');
    });
    refreshAnalytics();
  } catch (err) {
    alert('Reset failed: ' + err.message);
  }
}

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

async function loadPresets() {
  try {
    const res = await fetch('/api/presets/image');
    const presets = await res.json();

    document.getElementById('img-presets').innerHTML = presets.map((p, i) => {
      const expectBadge = {
        'full_miss': '<span style="font-size:8px;color:#f87171;margin-left:3px">0/8</span>',
        'background_change': '<span style="font-size:8px;color:#60a5fa;margin-left:3px">7/8</span>',
        'outfit_change': '<span style="font-size:8px;color:#fbbf24;margin-left:3px">3/8</span>',
        'accessory_change': '<span style="font-size:8px;color:#a78bfa;margin-left:3px">7/8</span>',
        'no_change': '<span style="font-size:8px;color:#2dd4bf;margin-left:3px">8/8</span>',
      };
      const badge = expectBadge[p.expect] || '';
      return '<button class="preset-chip" data-index="' + i + '" onclick="document.getElementById(\'img-prompt\').value=this.dataset.prompt;runImage()" data-prompt="' +
        p.prompt.replace(/"/g, '&quot;') + '">' +
        '<span class="preset-number">' + (i + 1) + '</span>' + p.label + badge + '</button>';
    }).join('');
  } catch (err) {
    // Fail silently
  }
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

async function checkHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();

    const updates = [
      { id: 'h-mode', ok: data.reuse_engine_ready, label: 'Mock' },
      { id: 'h-parts', ok: data.parts_ready, label: 'Parts' },
    ];

    updates.forEach(({ id, ok, label }) => {
      const el = document.getElementById(id);
      if (!el) return;
      const dot = el.querySelector('span');
      if (dot) {
        dot.className = 'w-1.5 h-1.5 rounded-full ' + (ok ? 'bg-emerald-500' : (ok === false ? 'bg-red-500' : 'bg-amber-500'));
      }
      // Update label text (second text node)
      const textNode = el.childNodes[el.childNodes.length - 1];
      if (textNode && textNode.nodeType === Node.TEXT_NODE) {
        textNode.textContent = label;
      }
    });
  } catch {
    // Silent fail
  }
}

// ---------------------------------------------------------------------------
// Image lightbox
// ---------------------------------------------------------------------------

function openLightbox(historyIndex) {
  const d = imageHistory[historyIndex];
  if (!d) return;

  const changeLabels = {
    'no_change': 'REUSED',
    'background_change': 'BG SWAP',
    'outfit_change': 'OUTFIT REGEN',
    'accessory_change': 'ACCESSORY',
    'full_miss': 'NEW RESULT',
  };
  const label = changeLabels[d.change_type] || 'MISS';
  const badgeClass = d.reuse_hit ? 'badge-hit' : (d.change_type === 'full_miss' ? 'badge-miss' : 'badge-partial');
  const imgSrc = d.image_available ? '/images/' + d.image_hash + '.png?t=' + (d._ts || '') : '';

  const backdrop = document.createElement('div');
  backdrop.className = 'lightbox-backdrop';
  backdrop.onclick = (e) => { if (e.target === backdrop) closeLightbox(); };

  backdrop.innerHTML =
    '<div class="lightbox-content">' +
      '<button class="lightbox-close" onclick="closeLightbox()">&times;</button>' +
      (imgSrc ? '<img src="' + imgSrc + '" alt="Generated image">' : '<div class="text-white/30 p-12">No image</div>') +
      '<div class="lightbox-meta">' +
        '<div><span class="badge ' + badgeClass + '">' + label + '</span> &nbsp; <span class="font-mono">' + formatMs(d.total_latency_ms) + '</span></div>' +
        '<div class="text-white/30 text-xs font-mono">' + (d.parts_reused ? d.parts_reused.length : 0) + '/8 reused</div>' +
      '</div>' +
      '<div class="text-white/25 text-xs mt-1 truncate font-mono" style="max-width:80vw">' + (d.prompt || '') + '</div>' +
    '</div>';

  document.body.appendChild(backdrop);
  document.addEventListener('keydown', lightboxKeyHandler);
}

function closeLightbox() {
  const el = document.querySelector('.lightbox-backdrop');
  if (el) el.remove();
  document.removeEventListener('keydown', lightboxKeyHandler);
}

function lightboxKeyHandler(e) {
  if (e.key === 'Escape') closeLightbox();
}

// ---------------------------------------------------------------------------
// Canonical image drag-and-drop
// ---------------------------------------------------------------------------

function handleCanonicalDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('border-primary', 'bg-primary/5');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) {
    uploadCanonicalImage(file);
  }
}

function handleCanonicalSelect(e) {
  const file = e.target.files[0];
  if (file && file.type.startsWith('image/')) {
    uploadCanonicalImage(file);
  }
}

async function uploadCanonicalImage(file) {
  const img = document.getElementById('canonical-img');
  const reader = new FileReader();
  reader.onload = (e) => { img.src = e.target.result; };
  reader.readAsDataURL(file);

  const formData = new FormData();
  formData.append('file', file);
  try {
    const resp = await fetch('/api/canonical-image', {
      method: 'POST',
      body: formData,
    });
    if (!resp.ok) throw new Error('Upload failed');
    loadParts();
  } catch (err) {
    // Silent fail
  }
}

async function loadParts() {
  const grid = document.getElementById('parts-grid');

  // Try reused parts first
  try {
    const reused = await fetch('/api/parts');
    if (reused.ok) {
      const data = await reused.json();
      if (data.parts && data.parts.length > 0) {
        renderParts(data.parts);
        return;
      }
    }
  } catch (_) { /* continue to load */ }

  // Show loading, then load
  grid.innerHTML = Array.from({length: 8}, () =>
    '<div class="comp-part-tile"><span class="spinner" style="width:10px;height:10px;border-width:1px"></span></div>'
  ).join('');

  try {
    const resp = await fetch('/api/parts', { method: 'POST' });
    if (!resp.ok) throw new Error('Parts unavailable');
    const data = await resp.json();
    renderParts(data.parts);
  } catch (err) {
    grid.innerHTML = Array.from({length: 8}, (_, i) =>
      '<div class="comp-part-tile"><span class="text-white/15 text-[7px]">' + (i+1) + '</span></div>'
    ).join('');
  }
}

// Map part name to object-position so the tile shows the relevant body area
const PART_CROP_POSITION = {
  'Face & Hair': 'center 15%',
  'Upper Body': 'center 20%',
  'Upper Garment': 'center 30%',
  'Lower Garment': 'center 55%',
  'Footwear': 'center 90%',
  'Background': 'center center',
  'Style & Lighting': 'center center',
  'Framing Guide': 'center center',
};

function renderParts(parts) {
  const grid = document.getElementById('parts-grid');
  const tiles = parts.map(l => {
    const pos = PART_CROP_POSITION[l.name] || 'center center';
    return '<div class="comp-part-tile filled" title="' + (l.description || '') + '">' +
      '<img src="data:image/png;base64,' + l.crop + '" alt="' + l.name + '" style="object-position:' + pos + '">' +
      '<div class="part-label"><span>' + l.name + '</span></div>' +
    '</div>';
  });
  while (tiles.length < 8) {
    tiles.push('<div class="comp-part-tile"><span class="text-white/15 text-[7px]">' + (tiles.length+1) + '</span></div>');
  }
  grid.innerHTML = tiles.join('');
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  loadPresets();
  loadParts();
  checkHealth();
  setInterval(checkHealth, 15000);

  // Auto-refresh analytics when visible
  setInterval(() => {
    if (!document.getElementById('panel-analytics').classList.contains('hidden')) {
      refreshAnalytics();
    }
  }, 5000);
});
