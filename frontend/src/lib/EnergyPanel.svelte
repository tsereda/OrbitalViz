<script>
  import { onDestroy } from 'svelte';

  export let apiUrl = 'http://localhost:8000';
  export let selectedMolecule = 'water';
  export let moleculeInfo = null;   // {atoms: [{element, coords}], ...}
  export let moleculeMeta = null;   // {id, name, tbi_context, scan_bond}

  // ── Scan setup ───────────────────────────────────────────────────────
  let scanAtom1 = 0;
  let scanAtom2 = 1;
  let rMin = 0.8;
  let rMax = 3.2;
  let nSteps = 14;
  let useRHF = true;
  let useDFT = true;
  let useCAS = true;

  // ── Job state ────────────────────────────────────────────────────────
  let jobId = null;
  let jobStatus = 'idle';   // idle | running | complete | error
  let jobPoints = [];
  let jobProgress = 0;
  let errorMsg = '';
  let pollTimer = null;

  // ── Selected scan point ──────────────────────────────────────────────
  let hoverIdx = -1;

  // Automatically seed atom pair from scan_bond hint when molecule changes
  $: if (moleculeMeta?.scan_bond) {
    scanAtom1 = moleculeMeta.scan_bond[0];
    scanAtom2 = moleculeMeta.scan_bond[1];
  } else if (moleculeInfo?.atoms?.length >= 2) {
    scanAtom1 = 0;
    scanAtom2 = 1;
  }

  // Reset job when molecule changes
  $: if (selectedMolecule) {
    cancelPoll();
    jobId = null;
    jobStatus = 'idle';
    jobPoints = [];
    jobProgress = 0;
    errorMsg = '';
    hoverIdx = -1;
  }

  function cancelPoll() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  onDestroy(cancelPoll);

  async function startScan() {
    errorMsg = '';
    jobPoints = [];
    jobProgress = 0;
    jobStatus = 'running';
    hoverIdx = -1;
    cancelPoll();

    const methods = [];
    if (useRHF) methods.push('rhf');
    if (useDFT) methods.push('dft');
    if (useCAS) methods.push('casscf');

    try {
      const res = await fetch(`${apiUrl}/api/pes_scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          molecule_id: selectedMolecule,
          atom1: scanAtom1,
          atom2: scanAtom2,
          r_min: rMin,
          r_max: rMax,
          n_steps: nSteps,
          methods,
        }),
      });
      if (!res.ok) { throw new Error(`HTTP ${res.status}`); }
      const data = await res.json();
      jobId = data.job_id;
      pollTimer = setInterval(pollJob, 1500);
    } catch (e) {
      jobStatus = 'error';
      errorMsg = 'Failed to start scan: ' + e.message;
    }
  }

  async function pollJob() {
    if (!jobId) return;
    try {
      const res = await fetch(`${apiUrl}/api/pes_scan/${jobId}`);
      const data = await res.json();
      jobPoints = data.points || [];
      jobProgress = data.progress || 0;
      if (data.status === 'complete' || data.status === 'error') {
        cancelPoll();
        jobStatus = data.status;
        if (data.error) errorMsg = data.error;
      }
    } catch (e) {
      console.error('Poll error:', e);
    }
  }

  // ── Chart geometry ───────────────────────────────────────────────────
  const W = 308, H = 190;
  const ML = 54, MR = 12, MT = 16, MB = 38;
  const PW = W - ML - MR;
  const PH = H - MT - MB;
  const HA_TO_KCAL = 627.509474;

  $: chartData = buildChart(jobPoints, useRHF, useDFT, useCAS);

  function buildChart(points, rhf, dft, cas) {
    if (!points.length) return null;
    const rs = points.map(p => p.r);
    const rMin_ = Math.min(...rs);
    const rMax_ = Math.max(...rs);

    const allE = [];
    if (rhf) points.forEach(p => p.e_rhf != null && allE.push(p.e_rhf));
    if (dft) points.forEach(p => p.e_dft != null && allE.push(p.e_dft));
    if (cas) points.forEach(p => p.e_casscf != null && allE.push(p.e_casscf));
    if (!allE.length) return null;

    const eRef = Math.min(...allE);
    const eMaxRaw = Math.max(...allE);
    const span = (eMaxRaw - eRef) * HA_TO_KCAL;
    const eSpan = span > 0 ? span * 1.08 : 1;

    const toKcal = e => (e - eRef) * HA_TO_KCAL;
    const xPx = r => ML + ((r - rMin_) / (rMax_ - rMin_ || 1)) * PW;
    const yPx = e => MT + PH - (e / eSpan) * PH;

    const line = (arr, key) => arr
      .filter(p => p[key] != null)
      .map(p => `${xPx(p.r).toFixed(1)},${yPx(toKcal(p[key])).toFixed(1)}`).join(' ');

    // X ticks
    const xTicks = niceRange(rMin_, rMax_, 5);
    const yTicks = niceRange(0, eSpan, 5);

    // Find max DFT–CASSCF divergence point
    let maxDivR = null, maxDiv = 0;
    if (dft && cas) {
      for (const p of points) {
        if (p.e_dft != null && p.e_casscf != null) {
          const d = Math.abs(toKcal(p.e_dft) - toKcal(p.e_casscf));
          if (d > maxDiv) { maxDiv = d; maxDivR = p.r; }
        }
      }
    }

    return {
      rMin: rMin_, rMax: rMax_, eSpan,
      xPx, yPx, toKcal,
      rhfLine: rhf ? line(points, 'e_rhf') : '',
      dftLine: dft ? line(points, 'e_dft') : '',
      casLine: cas ? line(points, 'e_casscf') : '',
      rhfPts: rhf ? points.filter(p => p.e_rhf != null) : [],
      dftPts: dft ? points.filter(p => p.e_dft != null) : [],
      casPts: cas ? points.filter(p => p.e_casscf != null) : [],
      xTicks, yTicks,
      maxDivR, maxDiv: maxDiv.toFixed(1),
    };
  }

  function niceRange(lo, hi, n) {
    if (lo === hi) return [lo];
    const step = niceStep((hi - lo) / n);
    const start = Math.ceil(lo / step) * step;
    const ticks = [];
    for (let v = start; v <= hi + 1e-9; v += step) ticks.push(+v.toFixed(6));
    return ticks;
  }
  function niceStep(raw) {
    const exp = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / exp;
    if (f < 1.5) return exp;
    if (f < 3.5) return 2 * exp;
    if (f < 7.5) return 5 * exp;
    return 10 * exp;
  }

  // ── Occupation sparklines ────────────────────────────────────────────
  $: occupationSeries = buildOccSeries(jobPoints);

  function buildOccSeries(points) {
    const withOcc = points.filter(p => p.occupations?.length);
    if (!withOcc.length) return [];
    const nOrb = withOcc[0].occupations.length;
    return Array.from({ length: nOrb }, (_, i) => ({
      label: `NO ${i + 1}`,
      data: withOcc.map(p => ({ r: p.r, occ: p.occupations[i] })),
    }));
  }

  function occSparkPath(series, w, h) {
    if (!series.data.length) return '';
    const rs = series.data.map(d => d.r);
    const rlo = Math.min(...rs), rhi = Math.max(...rs);
    const xp = r => ((r - rlo) / (rhi - rlo || 1)) * w;
    const yp = occ => (1 - occ / 2) * h;  // occ range 0–2
    return series.data.map((d, i) =>
      `${i === 0 ? 'M' : 'L'}${xp(d.r).toFixed(1)} ${yp(d.occ).toFixed(1)}`
    ).join(' ');
  }

  $: atomLabels = moleculeInfo?.atoms?.map((a, i) => `${a.element}${i + 1}`) ?? [];

  function fmt(v, dec = 4) {
    return v == null ? '–' : v.toFixed(dec);
  }

  $: hoveredPoint = hoverIdx >= 0 ? jobPoints[hoverIdx] : null;
  $: HA = 627.509474;
</script>

<div class="ep">
  <div class="ep-title">Bond Energy Analysis</div>

  <!-- TBI context badge -->
  {#if moleculeMeta?.tbi_context}
    <div class="tbi-badge">{moleculeMeta.tbi_context}</div>
  {/if}

  <!-- Setup -->
  <div class="ep-section">
    <div class="ep-label">Atom pair</div>
    <div class="atom-row">
      <select bind:value={scanAtom1} disabled={jobStatus === 'running'}>
        {#each atomLabels as lbl, i}
          <option value={i}>{lbl}</option>
        {/each}
      </select>
      <span class="arrow">→</span>
      <select bind:value={scanAtom2} disabled={jobStatus === 'running'}>
        {#each atomLabels as lbl, i}
          <option value={i}>{lbl}</option>
        {/each}
      </select>
    </div>
  </div>

  <div class="ep-section">
    <div class="ep-label">Range (Å)</div>
    <div class="range-row">
      <input type="number" bind:value={rMin} min="0.4" max="10" step="0.1" disabled={jobStatus === 'running'} />
      <span class="to">to</span>
      <input type="number" bind:value={rMax} min="0.5" max="15" step="0.1" disabled={jobStatus === 'running'} />
      <span class="steps-label">×</span>
      <input type="number" bind:value={nSteps} min="4" max="40" step="1" class="steps-input" disabled={jobStatus === 'running'} />
    </div>
  </div>

  <div class="ep-section">
    <div class="ep-label">Methods</div>
    <div class="method-row">
      <label class="mcheck"><input type="checkbox" bind:checked={useRHF} disabled={jobStatus === 'running'} /><span class="dot rhf-dot"></span>RHF</label>
      <label class="mcheck"><input type="checkbox" bind:checked={useDFT} disabled={jobStatus === 'running'} /><span class="dot dft-dot"></span>DFT/B3LYP</label>
      <label class="mcheck"><input type="checkbox" bind:checked={useCAS} disabled={jobStatus === 'running'} /><span class="dot cas-dot"></span>CASSCF</label>
    </div>
  </div>

  <button
    class="run-btn"
    on:click={startScan}
    disabled={jobStatus === 'running' || scanAtom1 === scanAtom2 || (!useRHF && !useDFT && !useCAS)}
  >
    {#if jobStatus === 'running'}
      <span class="btn-spinner"></span> Scanning…
    {:else}
      ▶ Run Scan
    {/if}
  </button>

  <!-- Progress -->
  {#if jobStatus === 'running'}
    <div class="progress-wrap">
      <div class="progress-bar">
        <div class="progress-fill" style="width:{jobProgress * 100}%"></div>
      </div>
      <span class="progress-label">{jobPoints.length} / {nSteps} points</span>
    </div>
  {/if}

  {#if errorMsg}
    <div class="error-msg">{errorMsg}</div>
  {/if}

  <!-- Energy Chart -->
  {#if chartData}
    <div class="chart-wrap">
      <div class="chart-header">
        <span class="chart-title">Relative Energy (kcal/mol)</span>
        {#if chartData.maxDiv > 0.1}
          <span class="div-badge" title="Max DFT–CASSCF divergence">Δ {chartData.maxDiv} kcal/mol @ {chartData.maxDivR?.toFixed(2)} Å</span>
        {/if}
      </div>

      <svg viewBox="0 0 {W} {H}" class="chart-svg">
        <!-- Grid lines -->
        {#each chartData.yTicks as yt}
          <line
            x1={ML} y1={chartData.yPx(yt).toFixed(1)}
            x2={W - MR} y2={chartData.yPx(yt).toFixed(1)}
            stroke="#1e1e1e" stroke-width="1"
          />
        {/each}
        {#each chartData.xTicks as xt}
          <line
            x1={chartData.xPx(xt).toFixed(1)} y1={MT}
            x2={chartData.xPx(xt).toFixed(1)} y2={MT + PH}
            stroke="#1e1e1e" stroke-width="1"
          />
        {/each}

        <!-- Axes -->
        <line x1={ML} y1={MT} x2={ML} y2={MT + PH} stroke="#333" stroke-width="1.5"/>
        <line x1={ML} y1={MT + PH} x2={W - MR} y2={MT + PH} stroke="#333" stroke-width="1.5"/>

        <!-- Y ticks + labels -->
        {#each chartData.yTicks as yt}
          {@const yp = chartData.yPx(yt)}
          <line x1={ML - 4} y1={yp} x2={ML} y2={yp} stroke="#444" stroke-width="1"/>
          <text x={ML - 6} y={yp} text-anchor="end" dominant-baseline="middle"
            fill="#555" font-size="9" font-family="'SF Mono',Menlo,monospace">
            {yt.toFixed(yt < 1 ? 2 : 1)}
          </text>
        {/each}

        <!-- X ticks + labels -->
        {#each chartData.xTicks as xt}
          {@const xp = chartData.xPx(xt)}
          <line x1={xp} y1={MT + PH} x2={xp} y2={MT + PH + 4} stroke="#444" stroke-width="1"/>
          <text x={xp} y={MT + PH + 14} text-anchor="middle"
            fill="#555" font-size="9" font-family="'SF Mono',Menlo,monospace">
            {xt.toFixed(2)}
          </text>
        {/each}

        <!-- Axis labels -->
        <text x={ML + PW / 2} y={H - 4} text-anchor="middle"
          fill="#444" font-size="9">r (Å)</text>
        <text transform="rotate(-90) translate({-(MT + PH/2)} 11)"
          text-anchor="middle" fill="#444" font-size="9">ΔE (kcal/mol)</text>

        <!-- Max divergence marker -->
        {#if chartData.maxDivR}
          {@const xd = chartData.xPx(chartData.maxDivR)}
          <line x1={xd} y1={MT} x2={xd} y2={MT + PH}
            stroke="#ff6644" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
        {/if}

        <!-- Data lines -->
        {#if useRHF && chartData.rhfLine}
          <polyline points={chartData.rhfLine} fill="none" stroke="#888" stroke-width="1.5" stroke-linejoin="round"/>
        {/if}
        {#if useDFT && chartData.dftLine}
          <polyline points={chartData.dftLine} fill="none" stroke="#ffaa44" stroke-width="1.8" stroke-linejoin="round"/>
        {/if}
        {#if useCAS && chartData.casLine}
          <polyline points={chartData.casLine} fill="none" stroke="#4a9eff" stroke-width="2" stroke-linejoin="round"/>
        {/if}

        <!-- Data points (hover targets) -->
        {#each jobPoints as pt, i}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <rect
            x={chartData.xPx(pt.r) - 8}
            y={MT}
            width="16"
            height={PH}
            fill="transparent"
            class="hover-hit"
            on:mouseenter={() => hoverIdx = i}
            on:mouseleave={() => hoverIdx = -1}
          />
        {/each}

        <!-- Hover indicator -->
        {#if hoverIdx >= 0 && jobPoints[hoverIdx]}
          {@const pt = jobPoints[hoverIdx]}
          {@const xh = chartData.xPx(pt.r)}
          <line x1={xh} y1={MT} x2={xh} y2={MT + PH} stroke="#666" stroke-width="1"/>
          {#if useRHF && pt.e_rhf != null}
            <circle cx={xh} cy={chartData.yPx(chartData.toKcal(pt.e_rhf))} r="3.5" fill="#888"/>
          {/if}
          {#if useDFT && pt.e_dft != null}
            <circle cx={xh} cy={chartData.yPx(chartData.toKcal(pt.e_dft))} r="3.5" fill="#ffaa44"/>
          {/if}
          {#if useCAS && pt.e_casscf != null}
            <circle cx={xh} cy={chartData.yPx(chartData.toKcal(pt.e_casscf))} r="3.5" fill="#4a9eff"/>
          {/if}
        {/if}
      </svg>

      <!-- Legend -->
      <div class="legend">
        {#if useRHF}<span class="legend-item"><span class="legend-line rhf-line"></span>RHF</span>{/if}
        {#if useDFT}<span class="legend-item"><span class="legend-line dft-line"></span>DFT/B3LYP</span>{/if}
        {#if useCAS}<span class="legend-item"><span class="legend-line cas-line"></span>CASSCF</span>{/if}
      </div>

      <!-- Hover readout -->
      {#if hoveredPoint}
        <div class="readout">
          <span class="readout-r">r = {hoveredPoint.r.toFixed(3)} Å</span>
          {#if useRHF && hoveredPoint.e_rhf != null}
            <span class="readout-item rhf-text">RHF {(chartData.toKcal(hoveredPoint.e_rhf)).toFixed(2)}</span>
          {/if}
          {#if useDFT && hoveredPoint.e_dft != null}
            <span class="readout-item dft-text">DFT {(chartData.toKcal(hoveredPoint.e_dft)).toFixed(2)}</span>
          {/if}
          {#if useCAS && hoveredPoint.e_casscf != null}
            <span class="readout-item cas-text">CAS {(chartData.toKcal(hoveredPoint.e_casscf)).toFixed(2)}</span>
          {/if}
          {#if useDFT && useCAS && hoveredPoint.e_dft != null && hoveredPoint.e_casscf != null}
            <span class="readout-item diff-text">|Δ| {Math.abs(chartData.toKcal(hoveredPoint.e_dft) - chartData.toKcal(hoveredPoint.e_casscf)).toFixed(2)} kcal/mol</span>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Raw energy table (collapsible) -->
    <details class="raw-table-wrap">
      <summary class="raw-table-summary">Raw energies (Hartree)</summary>
      <div class="raw-table-scroll">
        <table class="raw-table">
          <thead>
            <tr>
              <th>r (Å)</th>
              {#if useRHF}<th>E_RHF</th>{/if}
              {#if useDFT}<th>E_DFT</th>{/if}
              {#if useCAS}<th>E_CASSCF</th>{/if}
            </tr>
          </thead>
          <tbody>
            {#each jobPoints as pt}
              <tr>
                <td>{pt.r.toFixed(3)}</td>
                {#if useRHF}<td>{fmt(pt.e_rhf)}</td>{/if}
                {#if useDFT}<td>{fmt(pt.e_dft)}</td>{/if}
                {#if useCAS}<td>{fmt(pt.e_casscf)}</td>{/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </details>

    <!-- CASSCF occupation sparklines -->
    {#if useCAS && occupationSeries.length}
      <div class="occ-section">
        <div class="ep-label">CASSCF natural orbital occupations vs r</div>
        <div class="occ-grid">
          {#each occupationSeries as series, si}
            {@const avgOcc = series.data.reduce((a, d) => a + d.occ, 0) / series.data.length}
            <div class="spark-row">
              <span class="spark-label" style="color: {avgOcc > 1.9 || avgOcc < 0.1 ? '#555' : '#aaa'}">
                {series.label}
              </span>
              <svg viewBox="0 0 80 24" class="sparkline">
                <!-- 0–2 occupation range -->
                <line x1="0" y1="12" x2="80" y2="12" stroke="#1e1e1e" stroke-width="0.5"/>
                <path d={occSparkPath(series, 80, 24)} fill="none"
                  stroke={avgOcc > 1.5 ? '#44cc88' : avgOcc < 0.5 ? '#555' : '#4a9eff'}
                  stroke-width="1.5"/>
              </svg>
              <span class="spark-val">{avgOcc.toFixed(3)}</span>
            </div>
          {/each}
        </div>
        <div class="occ-hint">Occupations near 2.0 = doubly occupied, near 0.0 = empty, near 1.0 = singly occupied (diradical)</div>
      </div>
    {/if}
  {:else if jobStatus === 'idle'}
    <div class="empty-state">
      <div class="empty-icon">∿</div>
      <div class="empty-text">Configure a scan above to compare DFT and CASSCF energies along a bond stretch</div>
    </div>
  {/if}
</div>

<style>
  .ep {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: 0.85rem 0.85rem 1.5rem;
    font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    color: #ccc;
    min-height: 0;
  }

  .ep-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid #1e1e1e;
    margin-bottom: 0.1rem;
  }

  .tbi-badge {
    font-size: 0.65rem;
    color: #44cc88;
    background: #44cc8812;
    border: 1px solid #44cc8830;
    border-radius: 6px;
    padding: 0.3rem 0.5rem;
    line-height: 1.4;
  }

  .ep-section { display: flex; flex-direction: column; gap: 0.3rem; }

  .ep-label {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #555;
    font-weight: 500;
  }

  .atom-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .atom-row select, select {
    flex: 1;
    padding: 0.35rem 0.5rem;
    background: #1a1a1a;
    color: #ccc;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    font-size: 0.75rem;
    font-family: 'SF Mono', Menlo, monospace;
    appearance: none;
    cursor: pointer;
  }
  select:focus { outline: none; border-color: #4a9eff; }
  select:disabled { opacity: 0.5; cursor: not-allowed; }

  .arrow { color: #555; font-size: 0.8rem; flex-shrink: 0; }
  .to { color: #555; font-size: 0.7rem; flex-shrink: 0; }

  .range-row {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .range-row input[type="number"] {
    flex: 1;
    padding: 0.35rem 0.4rem;
    background: #1a1a1a;
    color: #ccc;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    font-size: 0.75rem;
    font-family: 'SF Mono', Menlo, monospace;
    text-align: center;
    min-width: 0;
  }
  .range-row input[type="number"]:focus { outline: none; border-color: #4a9eff; }
  .range-row input[type="number"]:disabled { opacity: 0.5; }

  .steps-label { color: #555; font-size: 0.7rem; flex-shrink: 0; }
  .steps-input { max-width: 44px !important; }

  .method-row {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .mcheck {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.75rem;
    color: #999;
    cursor: pointer;
    user-select: none;
  }
  .mcheck input { accent-color: #4a9eff; cursor: pointer; }

  .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .rhf-dot { background: #888; }
  .dft-dot { background: #ffaa44; }
  .cas-dot { background: #4a9eff; }

  .run-btn {
    width: 100%;
    padding: 0.55rem 1rem;
    background: #4a9eff;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.8rem;
    font-family: inherit;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
  }
  .run-btn:hover:not(:disabled) { background: #3a8eef; }
  .run-btn:active:not(:disabled) { transform: scale(0.98); }
  .run-btn:disabled { opacity: 0.45; cursor: not-allowed; }

  .btn-spinner {
    width: 12px; height: 12px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .progress-wrap {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .progress-bar {
    flex: 1;
    height: 4px;
    background: #1e1e1e;
    border-radius: 2px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4a9eff, #44cc88);
    border-radius: 2px;
    transition: width 0.4s ease-out;
  }
  .progress-label {
    font-size: 0.65rem;
    color: #555;
    font-family: 'SF Mono', Menlo, monospace;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .error-msg {
    font-size: 0.72rem;
    color: #ff6644;
    background: #ff664412;
    border: 1px solid #ff664430;
    border-radius: 6px;
    padding: 0.4rem 0.5rem;
  }

  /* ── Chart ── */
  .chart-wrap {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .chart-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .chart-title {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #555;
  }

  .div-badge {
    font-size: 0.62rem;
    color: #ff6644;
    background: #ff664412;
    border: 1px solid #ff664430;
    border-radius: 4px;
    padding: 0.1rem 0.35rem;
    white-space: nowrap;
    cursor: help;
  }

  .chart-svg {
    width: 100%;
    display: block;
    overflow: visible;
  }

  .hover-hit { cursor: crosshair; }

  .legend {
    display: flex;
    gap: 0.8rem;
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.68rem;
    color: #666;
  }

  .legend-line {
    width: 18px;
    height: 2px;
    border-radius: 1px;
    flex-shrink: 0;
  }
  .rhf-line { background: #888; }
  .dft-line { background: #ffaa44; }
  .cas-line { background: #4a9eff; }

  .readout {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 0.6rem;
    padding: 0.3rem 0.5rem;
    background: #141414;
    border: 1px solid #222;
    border-radius: 6px;
    font-size: 0.68rem;
    font-family: 'SF Mono', Menlo, monospace;
  }
  .readout-r { color: #666; }
  .readout-item { }
  .rhf-text { color: #888; }
  .dft-text { color: #ffaa44; }
  .cas-text { color: #4a9eff; }
  .diff-text { color: #ff6644; }

  /* ── Raw table ── */
  .raw-table-wrap {
    margin-top: 0.2rem;
  }
  .raw-table-summary {
    font-size: 0.65rem;
    color: #444;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0.25rem 0;
    user-select: none;
  }
  .raw-table-summary:hover { color: #666; }

  .raw-table-scroll {
    overflow-x: auto;
    margin-top: 0.3rem;
    max-height: 160px;
    overflow-y: auto;
  }
  .raw-table-scroll::-webkit-scrollbar { width: 3px; height: 3px; }
  .raw-table-scroll::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 2px; }

  .raw-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.64rem;
    font-family: 'SF Mono', Menlo, monospace;
  }
  .raw-table th {
    padding: 0.2rem 0.4rem;
    text-align: right;
    color: #444;
    border-bottom: 1px solid #1e1e1e;
    white-space: nowrap;
  }
  .raw-table th:first-child, .raw-table td:first-child { text-align: left; }
  .raw-table td {
    padding: 0.15rem 0.4rem;
    color: #888;
    text-align: right;
    white-space: nowrap;
  }
  .raw-table tr:nth-child(odd) td { background: #111; }

  /* ── Occupation sparklines ── */
  .occ-section {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-top: 0.2rem;
  }

  .occ-grid {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .spark-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .spark-label {
    font-size: 0.62rem;
    font-family: 'SF Mono', Menlo, monospace;
    width: 36px;
    flex-shrink: 0;
    text-align: right;
  }

  .sparkline {
    flex: 1;
    height: 20px;
  }

  .spark-val {
    font-size: 0.62rem;
    font-family: 'SF Mono', Menlo, monospace;
    color: #555;
    width: 38px;
    flex-shrink: 0;
    text-align: right;
  }

  .occ-hint {
    font-size: 0.62rem;
    color: #3a3a3a;
    font-style: italic;
    line-height: 1.4;
  }

  /* ── Empty state ── */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.6rem;
    padding: 1.5rem 1rem;
    text-align: center;
  }

  .empty-icon {
    font-size: 2rem;
    color: #2a2a2a;
    line-height: 1;
  }

  .empty-text {
    font-size: 0.72rem;
    color: #3a3a3a;
    line-height: 1.5;
    max-width: 220px;
  }
</style>
