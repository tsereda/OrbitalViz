<script>
  import { Canvas, T } from '@threlte/core';
  import { OrbitControls, Text } from '@threlte/extras';
  import { onMount } from 'svelte';
  import OrbitalMesh from './OrbitalMesh.svelte';
  import MoleculeAtoms from './MoleculeAtoms.svelte';

  export let apiUrl = 'http://localhost:8000';

  let moleculeInfo = null;
  let orbitals = [];
  let isovalue = 0.02;
  let gridSize = 48;
  let loading = false;
  let displayMode = 'grid'; // 'grid' | 'overlay'
  let selectedIndices = '0,1,2,3';
  let errorMessage = '';

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

  const gridSpacing = 14; // Angstroms between orbitals in grid mode

  onMount(async () => {
    await fetchMoleculeInfo();
    await fetchAllOrbitals();
  });

  async function fetchMoleculeInfo() {
    try {
      const response = await fetch(`${apiUrl}/api/molecule/info`);
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

    const indices = selectedIndices.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));

    for (let i = 0; i < indices.length; i++) {
      const idx = indices[i];
      try {
        const response = await fetch(
          `${apiUrl}/api/orbital/${idx}?grid_size=${gridSize}&margin=5.0`
        );

        if (!response.ok) {
          console.error(`Failed to fetch orbital ${idx}: ${response.status}`);
          continue;
        }

        const arrayBuffer = await response.arrayBuffer();

        // Parse header (3 ints + 6 floats = 36 bytes)
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

        orbitals = [...orbitals, {
          index: idx,
          gridSize: gx,
          gridData: dataView,
          bounds: { min: [minX, minY, minZ], max: [maxX, maxY, maxZ] },
          visible: true,
          positiveColor: colors.pos,
          negativeColor: colors.neg,
          label: `MO ${idx}${occStr}`,
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
    // Center the grid
    const centerCol = (cols - 1) / 2;
    const totalRows = Math.ceil(orbitals.length / cols);
    const centerRow = (totalRows - 1) / 2;
    return [
      (col - centerCol) * gridSpacing,
      0,
      (row - centerRow) * gridSpacing,
    ];
  }

  function toggleOrbital(idx) {
    orbitals = orbitals.map(o =>
      o.index === idx ? { ...o, visible: !o.visible } : o
    );
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

<div class="multi-viewer">
  <div class="sidebar">
    <h2>🔬 OrbitalViz</h2>

    <div class="section">
      <h3>Display Mode</h3>
      <div class="mode-select">
        <button class:active={displayMode === 'grid'} on:click={() => displayMode = 'grid'}>
          ▦ Grid
        </button>
        <button class:active={displayMode === 'overlay'} on:click={() => displayMode = 'overlay'}>
          ◎ Overlay
        </button>
      </div>
    </div>

    <div class="section">
      <h3>Orbital Indices</h3>
      <div class="index-input">
        <input
          type="text"
          bind:value={selectedIndices}
          placeholder="e.g. 0,1,2,3"
          on:keydown={(e) => e.key === 'Enter' && handleRefresh()}
        />
        <button class="refresh-btn" on:click={handleRefresh} disabled={loading}>
          {loading ? '⏳' : '↻'}
        </button>
      </div>
      {#if moleculeInfo}
        <span class="hint">{moleculeInfo.num_orbitals} orbitals available</span>
      {/if}
    </div>

    <div class="section">
      <h3>Isovalue</h3>
      <label class="slider-label">
        <input type="range" bind:value={isovalue} min="0.005" max="0.1" step="0.001" />
        <span class="value">{isovalue.toFixed(3)}</span>
      </label>
    </div>

    <div class="section">
      <h3>Grid Resolution</h3>
      <select bind:value={gridSize} on:change={handleRefresh} disabled={loading}>
        <option value={32}>32 (Fast)</option>
        <option value={48}>48 (Balanced)</option>
        <option value={64}>64 (High)</option>
      </select>
    </div>

    <div class="section">
      <h3>Orbitals</h3>
      <div class="orbital-list">
        {#each orbitals as orbital, i}
          <div class="orbital-item" class:dimmed={!orbital.visible}>
            <label>
              <input type="checkbox" checked={orbital.visible} on:change={() => toggleOrbital(orbital.index)} />
              <span class="color-dots">
                <span class="color-dot" style="background: {orbital.positiveColor}"></span>
                <span class="color-dot" style="background: {orbital.negativeColor}"></span>
              </span>
              <span class="orbital-label">{orbital.label}</span>
            </label>
          </div>
        {/each}
      </div>
    </div>

    {#if moleculeInfo}
      <div class="section info">
        <h3>Molecule</h3>
        <div class="info-row">
          <span>Basis:</span>
          <span>{moleculeInfo.basis}</span>
        </div>
        <div class="info-row">
          <span>Energy:</span>
          <span>{moleculeInfo.energy?.toFixed(6)} Ha</span>
        </div>
        <div class="info-row">
          <span>Atoms:</span>
          <span>{moleculeInfo.atoms?.map(a => a.element).join(', ')}</span>
        </div>
      </div>
    {/if}

    {#if loading}
      <div class="loading">⏳ Loading orbital data...</div>
    {/if}

    {#if errorMessage}
      <div class="error">{errorMessage}</div>
    {/if}
  </div>

  <div class="canvas-container">
    <Canvas>
      {#key displayMode + orbitals.length}
        <T.PerspectiveCamera makeDefault position={getCameraPosition()} fov={50}>
          <OrbitControls enableDamping enablePan enableZoom />
        </T.PerspectiveCamera>
      {/key}

      <!-- Lighting -->
      <T.AmbientLight intensity={0.5} />
      <T.DirectionalLight position={[10, 10, 10]} intensity={1} />
      <T.DirectionalLight position={[-10, -10, -10]} intensity={0.5} />

      {#each orbitals as orbital, i (orbital.index)}
        {#if orbital.visible}
          {@const pos = getGridPosition(i)}
          <T.Group position={pos}>
            <!-- 3D Label above orbital -->
            <Text
              text={orbital.label}
              position={[0, 6.5, 0]}
              fontSize={0.7}
              color={orbital.positiveColor}
              anchorX="center"
              anchorY="bottom"
              depthOffset={-1}
            />

            <!-- Molecule atoms -->
            {#if moleculeInfo}
              <MoleculeAtoms atoms={moleculeInfo.atoms} />
            {/if}

            <!-- Orbital isosurface (positive + negative lobes) -->
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
    </Canvas>
  </div>
</div>

<style>
  .multi-viewer {
    width: 100%;
    height: 100vh;
    display: flex;
    background: #111;
    color: #e0e0e0;
    font-family: system-ui, -apple-system, sans-serif;
  }

  .sidebar {
    width: 260px;
    padding: 1rem;
    background: #1a1a1a;
    border-right: 1px solid #333;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .sidebar h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.2rem;
    color: #fff;
    letter-spacing: 0.02em;
  }

  .section {
    padding: 0.6rem 0;
    border-bottom: 1px solid #2a2a2a;
  }

  .section h3 {
    margin: 0 0 0.5rem 0;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #888;
  }

  .mode-select {
    display: flex;
    gap: 0.4rem;
  }

  .mode-select button {
    flex: 1;
    padding: 0.4rem 0.5rem;
    background: #2a2a2a;
    color: #bbb;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.15s;
  }

  .mode-select button:hover {
    background: #333;
  }

  .mode-select button.active {
    background: #4a9eff22;
    color: #4a9eff;
    border-color: #4a9eff;
  }

  .index-input {
    display: flex;
    gap: 0.4rem;
  }

  .index-input input {
    flex: 1;
    padding: 0.35rem 0.5rem;
    background: #222;
    color: #fff;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    font-size: 0.85rem;
    font-family: monospace;
  }

  .index-input input:focus {
    outline: none;
    border-color: #4a9eff;
  }

  .refresh-btn {
    padding: 0.35rem 0.6rem;
    background: #2a2a2a;
    color: #bbb;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    cursor: pointer;
    font-size: 1rem;
    transition: all 0.15s;
  }

  .refresh-btn:hover:not(:disabled) {
    background: #4a9eff;
    color: #fff;
  }

  .refresh-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .hint {
    font-size: 0.75rem;
    color: #666;
    margin-top: 0.25rem;
    display: block;
  }

  .slider-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .slider-label input[type="range"] {
    flex: 1;
    accent-color: #4a9eff;
  }

  .value {
    font-family: monospace;
    font-size: 0.85rem;
    min-width: 45px;
    text-align: right;
    color: #4a9eff;
  }

  select {
    width: 100%;
    padding: 0.35rem 0.5rem;
    background: #222;
    color: #fff;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    font-size: 0.85rem;
  }

  .orbital-list {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .orbital-item label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.85rem;
    cursor: pointer;
    padding: 0.2rem 0;
  }

  .orbital-item.dimmed {
    opacity: 0.4;
  }

  .color-dots {
    display: flex;
    gap: 2px;
  }

  .color-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    border: 1px solid rgba(255,255,255,0.2);
  }

  .orbital-label {
    font-family: monospace;
    font-size: 0.82rem;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    padding: 0.15rem 0;
  }

  .info-row span:first-child {
    color: #888;
  }

  .info-row span:last-child {
    font-family: monospace;
    color: #ccc;
  }

  .canvas-container {
    flex: 1;
    position: relative;
    touch-action: none;
  }

  .loading {
    color: #4a9eff;
    font-size: 0.85rem;
    padding: 0.5rem 0;
  }

  .error {
    color: #ff4444;
    font-size: 0.85rem;
    padding: 0.5rem 0;
  }

  /* Mobile */
  @media (max-width: 768px) {
    .multi-viewer {
      flex-direction: column;
    }
    .sidebar {
      width: 100%;
      max-height: 35vh;
      border-right: none;
      border-bottom: 1px solid #333;
    }
  }
</style>
