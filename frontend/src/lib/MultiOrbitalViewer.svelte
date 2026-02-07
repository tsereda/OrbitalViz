<script>
  import { Canvas, T } from '@threlte/core';
  import { OrbitControls, Text } from '@threlte/extras';
  import { onMount } from 'svelte';
  import OrbitalMesh from './OrbitalMesh.svelte';
  import MoleculeAtoms from './MoleculeAtoms.svelte';

  export let apiUrl = 'http://localhost:8000';

  let molecules = [];
  let selectedMolecule = 'water';
  let moleculeInfo = null;
  let orbitals = [];
  let isovalue = 0.02;
  let gridSize = 48;
  let loading = false;
  let displayMode = 'grid';
  let selectedSet = new Set([0]);
  let errorMessage = '';
  let panelOpen = false;

  const orbitalColorPairs = [
    { pos: '#4a9eff', neg: '#ff6644' },
    { pos: '#44cc88', neg: '#cc44aa' },
    { pos: '#ffaa22', neg: '#6644ff' },
    { pos: '#44dddd', neg: '#dd4444' },
    { pos: '#aa66ff', neg: '#66ff44' },
    { pos: '#ff44aa', neg: '#44aaff' },
    { pos: '#cccc22', neg: '#4466cc' },
    { pos: '#ff8866', neg: '#6688ff' },
  ];

  const gridSpacing = 14;

  onMount(async () => {
    await fetchMolecules();
    await fetchMoleculeInfo();
    await fetchAllOrbitals();
  });

  async function fetchMolecules() {
    try {
      const response = await fetch(`${apiUrl}/api/molecules`);
      molecules = await response.json();
    } catch (e) {
      console.error('Failed to fetch molecules:', e);
    }
  }

  async function fetchMoleculeInfo() {
    try {
      const response = await fetch(`${apiUrl}/api/molecule/info?molecule=${selectedMolecule}`);
      moleculeInfo = await response.json();
    } catch (error) {
      console.error('Failed to fetch molecule info:', error);
      errorMessage = 'Failed to connect to backend';
    }
  }

  async function fetchAllOrbitals() {
    loading = true;
    errorMessage = '';
    orbitals = [];

    const indices = [...selectedSet].sort((a, b) => a - b);

    for (let i = 0; i < indices.length; i++) {
      const idx = indices[i];
      try {
        const response = await fetch(
          `${apiUrl}/api/orbital/${idx}?grid_size=${gridSize}&margin=5.0&molecule=${selectedMolecule}`
        );

        if (!response.ok) {
          console.error(`Failed to fetch orbital ${idx}: ${response.status}`);
          continue;
        }

        const arrayBuffer = await response.arrayBuffer();
        const headerView = new DataView(arrayBuffer, 0, 36);
        const gx = headerView.getInt32(0, true);
        const minX = headerView.getFloat32(12, true);
        const minY = headerView.getFloat32(16, true);
        const minZ = headerView.getFloat32(20, true);
        const maxX = headerView.getFloat32(24, true);
        const maxY = headerView.getFloat32(28, true);
        const maxZ = headerView.getFloat32(32, true);
        const dataView = new Float32Array(arrayBuffer, 36);

        const colors = orbitalColorPairs[i % orbitalColorPairs.length];
        const occ = moleculeInfo?.occupations?.[idx];
        const occStr = occ !== undefined ? ` (${occ.toFixed(3)})` : '';
        const backendLabel = moleculeInfo?.orbital_labels?.[idx];
        const displayLabel = backendLabel ? `${backendLabel}${occStr}` : `MO ${idx + 1}${occStr}`;

        orbitals = [...orbitals, {
          index: idx,
          gridSize: gx,
          gridData: dataView,
          bounds: { min: [minX, minY, minZ], max: [maxX, maxY, maxZ] },
          visible: true,
          positiveColor: colors.pos,
          negativeColor: colors.neg,
          label: displayLabel,
        }];
      } catch (e) {
        console.error(`Failed to fetch orbital ${idx}:`, e);
      }
    }
    loading = false;
  }

  function getGridPosition(i) {
    if (displayMode === 'overlay') return [0, 0, 0];
    const cols = Math.ceil(Math.sqrt(orbitals.length));
    const row = Math.floor(i / cols);
    const col = i % cols;
    const centerCol = (cols - 1) / 2;
    const totalRows = Math.ceil(orbitals.length / cols);
    const centerRow = (totalRows - 1) / 2;
    return [
      (col - centerCol) * gridSpacing,
      0,
      (row - centerRow) * gridSpacing,
    ];
  }

  function toggleSelected(idx) {
    if (selectedSet.has(idx)) {
      selectedSet.delete(idx);
    } else {
      selectedSet.add(idx);
    }
    selectedSet = selectedSet;
    fetchAllOrbitals();
  }

  function setDisplayMode(mode) {
    displayMode = mode;
  }

  async function changeMolecule(e) {
    selectedMolecule = e.target.value;
    selectedSet = new Set([0]);
    await fetchMoleculeInfo();
    await fetchAllOrbitals();
  }

  function handleRefresh() {
    fetchAllOrbitals();
  }

  function getCameraPosition() {
    if (displayMode === 'overlay') return [12, 12, 12];
    const n = orbitals.length || 4;
    const cols = Math.ceil(Math.sqrt(n));
    const dist = Math.max(20, cols * gridSpacing * 0.8);
    return [dist, dist * 0.7, dist];
  }
</script>

<div class="phone-frame">
  <!-- Top bar -->
  <header class="top-bar">
    <span class="app-icon">⚛️</span>
    <h1>OrbitalViz</h1>
    {#if loading}
      <span class="loading-dot"></span>
    {/if}
  </header>

  <!-- Molecule selector -->
  <div class="molecule-bar">
    <select class="molecule-select" value={selectedMolecule} on:change={changeMolecule} disabled={loading}>
      {#each molecules as mol}
        <option value={mol.id}>{mol.name}</option>
      {/each}
    </select>
  </div>

  <!-- 3D Canvas -->
  <div class="canvas-area">
    <Canvas>
      <T.PerspectiveCamera makeDefault position={getCameraPosition()} fov={50}>
        <OrbitControls enableDamping enablePan enableZoom />
      </T.PerspectiveCamera>

      <T.AmbientLight intensity={0.5} />
      <T.DirectionalLight position={[10, 10, 10]} intensity={1} />
      <T.DirectionalLight position={[-10, -10, -10]} intensity={0.5} />

      {#key displayMode}
      {#each orbitals as orbital, i (orbital.index)}
        {#if orbital.visible}
          {@const pos = getGridPosition(i)}
          <T.Group position={pos}>
            <Text
              text={orbital.label}
              position={[0, 6.5, 0]}
              fontSize={0.7}
              color={orbital.positiveColor}
              anchorX="center"
              anchorY="bottom"
              depthOffset={-1}
            />
            {#if moleculeInfo}
              <MoleculeAtoms atoms={moleculeInfo.atoms} />
            {/if}
            <OrbitalMesh
              gridData={orbital.gridData}
              gridSize={orbital.gridSize}
              bounds={orbital.bounds}
              {isovalue}
              positiveColor={orbital.positiveColor}
              negativeColor={orbital.negativeColor}
              opacity={displayMode === 'overlay' ? 0.45 : 0.7}
            />
          </T.Group>
        {/if}
      {/each}
      {/key}
    </Canvas>

    {#if errorMessage}
      <div class="toast-error">{errorMessage}</div>
    {/if}
  </div>

  <!-- Bottom sheet -->
  <div class="bottom-sheet" class:open={panelOpen}>
    <button class="sheet-handle" on:click={() => panelOpen = !panelOpen}>
      <span class="handle-bar"></span>
    </button>

    <!-- Quick controls (always visible) -->
    <div class="quick-row">
      <div class="mode-toggle">
        <button class:active={displayMode === 'grid'} on:click={() => setDisplayMode('grid')}>Grid</button>
        <button class:active={displayMode === 'overlay'} on:click={() => setDisplayMode('overlay')}>Overlay</button>
      </div>
      <div class="iso-section">
        <div class="iso-header">
          <span class="iso-label">Isovalue</span>
          <span class="info-tip">
            ⓘ
            <span class="tip-bubble">Controls the density threshold for orbital surfaces. Lower = more diffuse, higher = denser lobes.</span>
          </span>
          <span class="iso-val">{isovalue.toFixed(3)}</span>
        </div>
        <input type="range" bind:value={isovalue} min="0.005" max="0.1" step="0.001" />
      </div>
    </div>

    <!-- Expanded content -->
    {#if panelOpen}
      <div class="sheet-content">
        <div class="ctrl-section">
          <h4>Orbitals</h4>
          <p class="occ-hint">Numbers in parentheses are electron occupation numbers</p>
          <div class="orbital-chips">
            {#if moleculeInfo}
              {#each Array(moleculeInfo.num_orbitals) as _, idx}
                {@const occ = moleculeInfo.occupations?.[idx]}
                {@const occStr = occ !== undefined ? ` (${occ.toFixed(3)})` : ''}
                {@const backendLabel = moleculeInfo.orbital_labels?.[idx]}
                {@const label = backendLabel ? `${backendLabel}${occStr}` : `MO ${idx + 1}${occStr}`}
                {@const colors = orbitalColorPairs[idx % orbitalColorPairs.length]}
                <button
                  class="chip"
                  class:selected={selectedSet.has(idx)}
                  disabled={loading}
                  on:click={() => toggleSelected(idx)}
                >
                  <span class="chip-dot" style="background: {colors.pos}"></span>
                  <span class="chip-label">{label}</span>
                </button>
              {/each}
            {/if}
          </div>
        </div>

        <div class="ctrl-section">
          <h4>Resolution</h4>
          <div class="res-btns">
            <button class:active={gridSize === 32} on:click={() => { gridSize = 32; handleRefresh(); }} disabled={loading}>32</button>
            <button class:active={gridSize === 48} on:click={() => { gridSize = 48; handleRefresh(); }} disabled={loading}>48</button>
            <button class:active={gridSize === 64} on:click={() => { gridSize = 64; handleRefresh(); }} disabled={loading}>64</button>
          </div>
        </div>

        {#if moleculeInfo}
          <div class="ctrl-section info-strip">
            <span>{moleculeInfo.basis}</span>
            <span>E = {moleculeInfo.energy?.toFixed(4)} Ha</span>
            <span>{moleculeInfo.atoms?.map(a => a.element).join(', ')}</span>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  /* ── Phone frame ── */
  .phone-frame {
    width: 100%;
    height: 100vh;
    max-width: 480px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    background: #0d0d0d;
    color: #e0e0e0;
    font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    position: relative;
    overflow: hidden;
    border-left: 1px solid #1a1a1a;
    border-right: 1px solid #1a1a1a;
  }

  /* ── Top bar ── */
  .top-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 1rem;
    background: #111;
    border-bottom: 1px solid #222;
    flex-shrink: 0;
    z-index: 10;
  }

  .top-bar .app-icon {
    font-size: 1.3rem;
  }

  .top-bar h1 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    color: #fff;
    flex: 1;
  }

  .loading-dot {
    width: 8px;
    height: 8px;
    background: #4a9eff;
    border-radius: 50%;
    animation: pulse 1s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 1; }
  }

  /* ── Molecule selector ── */
  .molecule-bar {
    padding: 0.4rem 0.75rem;
    background: #111;
    border-bottom: 1px solid #1a1a1a;
    flex-shrink: 0;
    z-index: 10;
  }

  .molecule-select {
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: #1a1a1a;
    color: #fff;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    font-size: 0.9rem;
    font-family: inherit;
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M3 5l3 3 3-3' fill='none' stroke='%23888' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 0.75rem center;
    cursor: pointer;
  }

  .molecule-select:focus {
    outline: none;
    border-color: #4a9eff;
  }

  /* ── Canvas ── */
  .canvas-area {
    flex: 1;
    position: relative;
    touch-action: none;
    min-height: 0;
  }

  .toast-error {
    position: absolute;
    bottom: 1rem;
    left: 50%;
    transform: translateX(-50%);
    background: #ff4444cc;
    color: #fff;
    padding: 0.4rem 1rem;
    border-radius: 20px;
    font-size: 0.8rem;
    z-index: 20;
  }

  /* ── Bottom sheet ── */
  .bottom-sheet {
    flex-shrink: 0;
    background: #151515;
    border-top: 1px solid #2a2a2a;
    border-radius: 18px 18px 0 0;
    padding: 0 0.75rem 0.5rem;
    transition: max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    max-height: 100px;
    overflow: hidden;
    z-index: 20;
  }

  .bottom-sheet.open {
    max-height: 55vh;
    overflow-y: auto;
  }

  .sheet-handle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 0.5rem 0 0.25rem;
    background: none;
    border: none;
    cursor: pointer;
  }

  .handle-bar {
    width: 36px;
    height: 4px;
    background: #444;
    border-radius: 2px;
    transition: background 0.2s;
  }

  .sheet-handle:hover .handle-bar {
    background: #666;
  }

  /* ── Quick row ── */
  .quick-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.25rem 0 0.4rem;
  }

  .mode-toggle {
    display: flex;
    background: #222;
    border-radius: 8px;
    overflow: hidden;
    flex-shrink: 0;
  }

  .mode-toggle button {
    padding: 0.35rem 0.65rem;
    background: transparent;
    color: #888;
    border: none;
    font-size: 0.78rem;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s;
  }

  .mode-toggle button.active {
    background: #4a9eff;
    color: #fff;
  }

  .iso-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-width: 0;
  }

  .iso-header {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .iso-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #666;
    font-weight: 500;
  }

  .iso-section input[type="range"] {
    width: 100%;
    accent-color: #4a9eff;
    height: 4px;
  }

  .iso-val {
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 0.75rem;
    color: #4a9eff;
    margin-left: auto;
  }

  .info-tip {
    font-size: 0.8rem;
    color: #555;
    cursor: help;
    flex-shrink: 0;
    position: relative;
    line-height: 1;
  }

  .info-tip:hover {
    color: #4a9eff;
  }

  .tip-bubble {
    display: none;
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    width: 210px;
    padding: 0.5rem 0.65rem;
    background: #222;
    color: #ccc;
    border: 1px solid #3a3a3a;
    border-radius: 8px;
    font-size: 0.72rem;
    font-style: normal;
    line-height: 1.4;
    text-transform: none;
    letter-spacing: normal;
    z-index: 100;
    pointer-events: none;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  }

  .tip-bubble::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 5px solid transparent;
    border-top-color: #222;
  }

  .info-tip:hover .tip-bubble {
    display: block;
  }

  .occ-hint {
    margin: 0 0 0.4rem;
    font-size: 0.68rem;
    color: #555;
    font-style: italic;
    line-height: 1.3;
  }

  /* ── Expanded content ── */
  .sheet-content {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding-bottom: 0.5rem;
  }

  .ctrl-section {
    padding: 0.3rem 0;
  }

  .ctrl-section h4 {
    margin: 0 0 0.4rem;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #666;
    font-weight: 500;
  }

  /* ── Orbital chips ── */
  .orbital-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .chip {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.3rem 0.55rem;
    background: #1e1e1e;
    color: #999;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    font-size: 0.75rem;
    font-family: 'SF Mono', 'Menlo', monospace;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .chip:hover:not(:disabled) {
    border-color: #555;
    color: #ccc;
  }

  .chip.selected {
    background: #4a9eff18;
    border-color: #4a9eff;
    color: #4a9eff;
  }

  .chip:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .chip-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .chip-label {
    line-height: 1;
  }

  /* ── Resolution buttons ── */
  .res-btns {
    display: flex;
    gap: 0.35rem;
  }

  .res-btns button {
    flex: 1;
    padding: 0.35rem;
    background: #1e1e1e;
    color: #999;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    font-size: 0.8rem;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s;
  }

  .res-btns button.active {
    background: #4a9eff18;
    border-color: #4a9eff;
    color: #4a9eff;
  }

  .res-btns button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── Info strip ── */
  .info-strip {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: #555;
    font-family: 'SF Mono', 'Menlo', monospace;
    padding-top: 0.4rem;
    border-top: 1px solid #1e1e1e;
  }

  /* ── Scrollbar ── */
  .bottom-sheet::-webkit-scrollbar {
    width: 3px;
  }

  .bottom-sheet::-webkit-scrollbar-thumb {
    background: #333;
    border-radius: 2px;
  }

  /* ── Wide screens ── */
  @media (min-width: 481px) {
    :global(body) {
      background: #000;
    }
    .phone-frame {
      box-shadow: 0 0 60px rgba(74, 158, 255, 0.04);
    }
  }
</style>
