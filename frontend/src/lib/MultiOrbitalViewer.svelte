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
  let detailsOpen = false;
  let detailsData = null;
  let detailsLoading = false;
  let detailsExpandedSections = {};
  let computeOpen = false;
  let pendingMolecule = 'water';
  let pendingGridSize = 48;
  let pendingSelectedSet = new Set([0]);
  let computeProgress = '';
  let computedCount = 0;
  let computeTotal = 0;

  const orbitalColorPairs = [
    { pos: '#4a9eff', neg: '#ff6644' },
    { pos: '#44cc88', neg: '#cc44aa' },
    { pos: '#ffaa22', neg: '#6644ff' },
    { pos: '#44dddd', neg: '#dd4444' },
    { pos: '#aa66ff', neg: '#66ff44' },
    { pos: '#ff44aa', neg: '#44aaff' },
    { pos: '#cccc22', neg: '#4466cc' },
    { pos: '#ff8866', neg: '#6688ff' },
    { pos: '#ff3333', neg: '#3333ff' },  // Red / Blue
    { pos: '#3366ff', neg: '#ff3366' },  // Blue / Red
    { pos: '#ff0000', neg: '#0066ff' },  // Pure Red / Deep Blue
    { pos: '#0088ff', neg: '#ff4400' },  // Bright Blue / Orange-Red
  ];

  const gridSpacing = 26;

  onMount(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/molecules`);
      if (res.ok) {
        molecules = await res.json();
      } else {
        errorMessage = 'Failed to load molecule list from server.';
      }
    } catch (e) {
      errorMessage = 'Cannot connect to compute server. Please try refreshing.';
    }
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
    computeTotal = indices.length;
    computedCount = 0;
    computeProgress = `Computing ${indices.length} orbital(s)...`;

    try {
      // Use batch endpoint for better performance
      const indicesStr = indices.join(',');
      const response = await fetch(
        `${apiUrl}/api/orbitals/batch?indices=${indicesStr}&grid_size=${gridSize}&margin=5.0&molecule=${selectedMolecule}`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch orbitals: ${response.status}`);
      }

      const arrayBuffer = await response.arrayBuffer();
      let offset = 0;
      
      // Parse header
      const headerView = new DataView(arrayBuffer);
      const numOrbitals = headerView.getInt32(offset, true); offset += 4;
      const gx = headerView.getInt32(offset, true); offset += 4;
      const gy = headerView.getInt32(offset, true); offset += 4;
      const gz = headerView.getInt32(offset, true); offset += 4;
      
      // Read orbital indices
      const orbitalIndices = [];
      for (let i = 0; i < numOrbitals; i++) {
        orbitalIndices.push(headerView.getInt32(offset, true));
        offset += 4;
      }
      
      // Read bounds
      const minX = headerView.getFloat32(offset, true); offset += 4;
      const minY = headerView.getFloat32(offset, true); offset += 4;
      const minZ = headerView.getFloat32(offset, true); offset += 4;
      const maxX = headerView.getFloat32(offset, true); offset += 4;
      const maxY = headerView.getFloat32(offset, true); offset += 4;
      const maxZ = headerView.getFloat32(offset, true); offset += 4;
      
      // Read orbital data
      const gridDataSize = gx * gy * gz;
      const newOrbitals = [];
      
      for (let i = 0; i < numOrbitals; i++) {
        const idx = orbitalIndices[i];
        const dataView = new Float32Array(arrayBuffer, offset, gridDataSize);
        offset += gridDataSize * 4; // 4 bytes per float32

        const colors = orbitalColorPairs[i % orbitalColorPairs.length];
        const occ = moleculeInfo?.occupations?.[idx];
        const occStr = occ !== undefined ? ` (${occ.toFixed(3)})` : '';
        const backendLabel = moleculeInfo?.orbital_labels?.[idx];
        const displayLabel = backendLabel ? `${backendLabel}${occStr}` : `MO ${idx + 1}${occStr}`;

        newOrbitals.push({
          index: idx,
          gridSize: gx,
          gridData: dataView,
          bounds: { min: [minX, minY, minZ], max: [maxX, maxY, maxZ] },
          visible: true,
          positiveColor: colors.pos,
          negativeColor: colors.neg,
          label: displayLabel,
        });
        
        computedCount = i + 1;
      }
      
      orbitals = newOrbitals;
    } catch (e) {
      console.error('Failed to fetch orbitals:', e);
      errorMessage = `Failed to fetch orbitals: ${e.message}`;
    }
    
    computedCount = indices.length;
    computeProgress = '';
    loading = false;
  }

  function getGridPosition(i) {
    if (displayMode === 'overlay') return [0, 0, 0];
    const cols = Math.ceil(Math.sqrt(orbitals.length * 1.5));
    const row = Math.floor(i / cols);
    const col = i % cols;
    const centerCol = (cols - 1) / 2;
    const totalRows = Math.ceil(orbitals.length / cols);
    const centerRow = (totalRows - 1) / 2;
    return [
      (col - centerCol) * gridSpacing,
      -(row - centerRow) * gridSpacing,
      0,
    ];
  }

  function togglePendingSelected(idx) {
    if (pendingSelectedSet.has(idx)) {
      pendingSelectedSet.delete(idx);
    } else {
      pendingSelectedSet.add(idx);
    }
    pendingSelectedSet = pendingSelectedSet;
  }

  function pendingSelectAll() {
    if (!moleculeInfo) return;
    for (let i = 0; i < moleculeInfo.num_orbitals; i++) pendingSelectedSet.add(i);
    pendingSelectedSet = pendingSelectedSet;
  }

  function pendingSelectNone() {
    pendingSelectedSet = new Set();
    pendingSelectedSet = pendingSelectedSet;
  }

  function togglePendingGroup(indices) {
    const allSelected = indices.every(i => pendingSelectedSet.has(i));
    if (allSelected) {
      indices.forEach(i => pendingSelectedSet.delete(i));
    } else {
      indices.forEach(i => pendingSelectedSet.add(i));
    }
    pendingSelectedSet = pendingSelectedSet;
  }

  async function runComputation() {
    selectedMolecule = pendingMolecule;
    gridSize = pendingGridSize;
    selectedSet = new Set(pendingSelectedSet);
    detailsData = null;
    computeOpen = false;
    await fetchMoleculeInfo();
    await fetchAllOrbitals();
  }

  async function handlePendingMoleculeChange(e) {
    pendingMolecule = e.target.value;
    pendingSelectedSet = new Set([0]);
    // Fetch info for the pending molecule so we can show orbital choices
    try {
      const response = await fetch(`${apiUrl}/api/molecule/info?molecule=${pendingMolecule}`);
      moleculeInfo = await response.json();
    } catch (error) {
      console.error('Failed to fetch molecule info:', error);
    }
  }

  // NOTE: reference moleculeInfo directly so Svelte detects the dependency
  $: orbitalGroups = (() => {
    if (!moleculeInfo) return [];
    const groups = { 'Bonding': [], 'Antibonding': [], 'Lone Pair / Atomic': [] };
    for (let idx = 0; idx < moleculeInfo.num_orbitals; idx++) {
      const lbl = moleculeInfo.orbital_labels?.[idx] || '';
      if (lbl.includes('σ*(') || lbl.includes('π*(')) {
        groups['Antibonding'].push(idx);
      } else if (lbl.includes('σ(') || lbl.includes('π(')) {
        groups['Bonding'].push(idx);
      } else {
        groups['Lone Pair / Atomic'].push(idx);
      }
    }
    return Object.entries(groups).filter(([, idxs]) => idxs.length > 0);
  })();

  $: pendingCount = pendingSelectedSet.size;

  function setDisplayMode(mode) {
    displayMode = mode;
  }

  function handleRefresh() {
    fetchAllOrbitals();
  }

  async function openDetails() {
    detailsOpen = true;
    if (detailsData?.molecule_id === selectedMolecule) return;
    detailsLoading = true;
    try {
      const res = await fetch(`${apiUrl}/api/molecule/details?molecule=${selectedMolecule}`);
      detailsData = await res.json();
      detailsExpandedSections = { geom: true, elec: true, basis: true, energy: true, casscf: true, orbitals: true };
    } catch (e) {
      console.error('Failed to fetch details:', e);
    }
    detailsLoading = false;
  }

  function toggleDetailSection(key) {
    detailsExpandedSections[key] = !detailsExpandedSections[key];
    detailsExpandedSections = detailsExpandedSections;
  }

  function getCameraPosition() {
    if (displayMode === 'overlay') return [12, 12, 12];
    const n = orbitals.length || 4;
    const cols = Math.ceil(Math.sqrt(n * 1.5));
    const rows = Math.ceil(n / cols);
    const spread = Math.max(cols, rows) * gridSpacing;
    const dist = Math.max(25, spread * 0.9);
    return [0, 0, dist];
  }
</script>

<div class="phone-frame">
  <!-- Top bar -->
  <header class="top-bar">
    <h1>OrbitalViz</h1>
    {#if loading}
      <div class="loading-status">
        <div class="header-spinner"></div>
        <span class="loading-text">Computing...</span>
      </div>
    {/if}
    <div class="top-actions">
      <button class="compute-btn" on:click={() => { computeOpen = true; pendingMolecule = selectedMolecule; pendingGridSize = gridSize; pendingSelectedSet = new Set(selectedSet); }} disabled={loading}>
        Compute
      </button>
      <button class="details-btn" on:click={openDetails} title="Molecule Details">Details</button>
    </div>
  </header>

  <!-- Current molecule label -->
  {#if moleculeInfo}
    <div class="current-molecule-bar">
      <span class="current-mol-name">{molecules.find(m => m.id === selectedMolecule)?.name || selectedMolecule}</span>
      <span class="current-mol-meta">{selectedSet.size} orbital{selectedSet.size !== 1 ? 's' : ''} &middot; grid {gridSize}</span>
    </div>
  {/if}

  <!-- Loading overlay (computation in progress) -->
  {#if loading}
    <div class="loading-overlay">
      <div class="loading-card">
        <div class="spinner"></div>
        <div class="loading-message">{computeProgress || 'Computing...'}</div>
        {#if computeTotal > 0}
          <div class="progress-bar">
            <div class="progress-fill" style="width: {(computedCount / computeTotal) * 100}%"></div>
          </div>
          <div class="progress-text">{computedCount} / {computeTotal} orbitals</div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- 3D Canvas -->
  <div class="canvas-area">
    <Canvas>
      <T.PerspectiveCamera makeDefault position={getCameraPosition()} fov={50}>
        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          enablePan
          panSpeed={0.8}
          enableZoom
          zoomSpeed={0.8}
          rotateSpeed={0.5}
          minDistance={5}
          maxDistance={300}
          enableRotate
          oncreate={(ref) => { ref.listenToKeyEvents(window); }}
        />
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
            i
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

  <!-- Computation Panel Modal -->
  {#if computeOpen}
    <div class="modal-overlay" on:click|self={() => computeOpen = false} on:keydown={e => e.key === 'Escape' && (computeOpen = false)} role="dialog" aria-modal="true">
      <div class="modal-panel compute-panel">
        <div class="modal-header">
          <h2>Computation Setup</h2>
          <button class="modal-close" on:click={() => computeOpen = false}>✕</button>
        </div>
        <div class="modal-body">
          <!-- Molecule selection -->
          <div class="compute-section">
            <h4>Molecule</h4>
            <select class="molecule-select" value={pendingMolecule} on:change={handlePendingMoleculeChange}>
              {#each molecules as mol}
                <option value={mol.id}>{mol.name}</option>
              {/each}
            </select>
          </div>

          <!-- Resolution -->
          <div class="compute-section">
            <h4>Grid Resolution</h4>
            <div class="res-btns">
              <button class:active={pendingGridSize === 32} on:click={() => pendingGridSize = 32}>32 <span class="res-sub">Fast</span></button>
              <button class:active={pendingGridSize === 48} on:click={() => pendingGridSize = 48}>48 <span class="res-sub">Balanced</span></button>
              <button class:active={pendingGridSize === 64} on:click={() => pendingGridSize = 64}>64 <span class="res-sub">High</span></button>
            </div>
          </div>

          <!-- Orbital selection -->
          <div class="compute-section">
            <div class="orbitals-header">
              <h4>Orbitals <span class="pending-count">({pendingCount} selected)</span></h4>
              <div class="select-actions">
                <button class="select-btn" on:click={pendingSelectAll}>All</button>
                <button class="select-btn" on:click={pendingSelectNone}>None</button>
              </div>
            </div>
            <p class="occ-hint">Select which orbitals to compute and visualize</p>
            {#if moleculeInfo}
              {#each orbitalGroups as [groupName, indices]}
                <div class="orbital-group">
                  <button class="group-header" on:click={() => togglePendingGroup(indices)}>
                    <span class="group-name">{groupName}</span>
                    <span class="group-count">{indices.filter(i => pendingSelectedSet.has(i)).length}/{indices.length}</span>
                  </button>
                  <div class="orbital-chips">
                    {#each indices as idx}
                      {@const occ = moleculeInfo.occupations?.[idx]}
                      {@const occStr = occ !== undefined ? ` (${occ.toFixed(3)})` : ''}
                      {@const backendLabel = moleculeInfo.orbital_labels?.[idx]}
                      {@const label = backendLabel ? `${backendLabel}${occStr}` : `MO ${idx + 1}${occStr}`}
                      {@const colors = orbitalColorPairs[idx % orbitalColorPairs.length]}
                      <button
                        class="chip"
                        class:selected={pendingSelectedSet.has(idx)}
                        on:click={() => togglePendingSelected(idx)}
                      >
                        <span class="chip-dot" style="background: {colors.pos}"></span>
                        <span class="chip-label">{label}</span>
                      </button>
                    {/each}
                  </div>
                </div>
              {/each}
            {/if}
          </div>

          <!-- Run button -->
          <button class="run-compute-btn" on:click={runComputation} disabled={pendingCount === 0 || loading}>
            {#if loading}
              Computing...
            {:else}
              Compute {pendingCount} Orbital{pendingCount !== 1 ? 's' : ''}
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Details Modal -->
  {#if detailsOpen}
    <div class="modal-overlay" on:click|self={() => detailsOpen = false} on:keydown={e => e.key === 'Escape' && (detailsOpen = false)} role="dialog" aria-modal="true">
      <div class="modal-panel">
        <div class="modal-header">
          <h2>Molecule Details</h2>
          <button class="modal-close" on:click={() => detailsOpen = false}>✕</button>
        </div>
        {#if detailsLoading}
          <div class="modal-loading">Computing...</div>
        {:else if detailsData}
          <div class="modal-body">

            <!-- Geometry -->
            <button class="detail-section-header" on:click={() => toggleDetailSection('geom')}>
              <span>Geometry</span>
              <span class="chevron" class:open={detailsExpandedSections['geom']}>▸</span>
            </button>
            {#if detailsExpandedSections['geom']}
              <div class="detail-section-body">
                <table class="detail-table">
                  <thead><tr><th>Atom</th><th>Z</th><th>x (Å)</th><th>y (Å)</th><th>z (Å)</th><th>Mass</th></tr></thead>
                  <tbody>
                    {#each detailsData.atoms as a}
                      <tr>
                        <td class="mono">{a.element}{a.index+1}</td>
                        <td>{a.nuclear_charge}</td>
                        <td class="mono">{a.coords_angstrom[0].toFixed(4)}</td>
                        <td class="mono">{a.coords_angstrom[1].toFixed(4)}</td>
                        <td class="mono">{a.coords_angstrom[2].toFixed(4)}</td>
                        <td>{a.mass}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
                <h5>Bond Lengths</h5>
                <div class="detail-kv-list">
                  {#each detailsData.bond_lengths as b}
                    <div class="kv"><span class="k">{b.label}</span><span class="v">{b.distance_angstrom.toFixed(4)} Å ({b.distance_bohr.toFixed(4)} a₀)</span></div>
                  {/each}
                </div>
                {#if detailsData.bond_angles.length}
                  <h5>Bond Angles</h5>
                  <div class="detail-kv-list">
                    {#each detailsData.bond_angles as a}
                      <div class="kv"><span class="k">{a.label}</span><span class="v">{a.angle_degrees.toFixed(2)}°</span></div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}

            <!-- Electrons -->
            <button class="detail-section-header" on:click={() => toggleDetailSection('elec')}>
              <span>Electronic Structure</span>
              <span class="chevron" class:open={detailsExpandedSections['elec']}>▸</span>
            </button>
            {#if detailsExpandedSections['elec']}
              <div class="detail-section-body">
                <div class="detail-kv-list">
                  <div class="kv"><span class="k">Total electrons</span><span class="v">{detailsData.electrons.total_electrons}</span></div>
                  <div class="kv"><span class="k">Alpha / Beta</span><span class="v">{detailsData.electrons.alpha_electrons} / {detailsData.electrons.beta_electrons}</span></div>
                  <div class="kv"><span class="k">Spin multiplicity</span><span class="v">{detailsData.electrons.spin_multiplicity} (2S = {detailsData.electrons.two_s})</span></div>
                  <div class="kv"><span class="k">Charge</span><span class="v">{detailsData.electrons.charge}</span></div>
                </div>
              </div>
            {/if}

            <!-- Basis Set -->
            <button class="detail-section-header" on:click={() => toggleDetailSection('basis')}>
              <span>Basis Set</span>
              <span class="chevron" class:open={detailsExpandedSections['basis']}>▸</span>
            </button>
            {#if detailsExpandedSections['basis']}
              <div class="detail-section-body">
                <div class="detail-kv-list">
                  <div class="kv"><span class="k">Basis</span><span class="v">{detailsData.basis.name}</span></div>
                  <div class="kv"><span class="k">AO count</span><span class="v">{detailsData.basis.num_ao}</span></div>
                  <div class="kv"><span class="k">Shells</span><span class="v">{detailsData.basis.num_shells}</span></div>
                  <div class="kv"><span class="k">Type</span><span class="v">{detailsData.basis.spherical ? 'Spherical' : 'Cartesian'}</span></div>
                </div>
                <h5>Shells by Atom</h5>
                <div class="detail-kv-list">
                  {#each Object.entries(detailsData.basis.shells_by_atom) as [atom, shells]}
                    <div class="kv"><span class="k">{atom}</span><span class="v mono">{shells.join(', ')}</span></div>
                  {/each}
                </div>
                <h5>AO Labels</h5>
                <div class="ao-labels-grid">
                  {#each detailsData.basis.ao_labels as lbl, i}
                    <span class="ao-tag">{i}: {lbl.trim()}</span>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Energies -->
            <button class="detail-section-header" on:click={() => toggleDetailSection('energy')}>
              <span>Energies</span>
              <span class="chevron" class:open={detailsExpandedSections['energy']}>▸</span>
            </button>
            {#if detailsExpandedSections['energy']}
              <div class="detail-section-body">
                <div class="detail-kv-list">
                  <div class="kv"><span class="k">Nuclear repulsion</span><span class="v mono">{detailsData.nuclear_repulsion_energy.toFixed(8)} Ha</span></div>
                  <div class="kv"><span class="k">RHF total energy</span><span class="v mono">{detailsData.energies.rhf_total.toFixed(8)} Ha</span></div>
                  <div class="kv"><span class="k">CASSCF total energy</span><span class="v mono">{detailsData.energies.casscf_total.toFixed(8)} Ha</span></div>
                  <div class="kv"><span class="k">Correlation energy</span><span class="v mono">{detailsData.energies.correlation_energy.toFixed(8)} Ha</span></div>
                </div>
              </div>
            {/if}

            <!-- CASSCF -->
            <button class="detail-section-header" on:click={() => toggleDetailSection('casscf')}>
              <span>CASSCF Configuration</span>
              <span class="chevron" class:open={detailsExpandedSections['casscf']}>▸</span>
            </button>
            {#if detailsExpandedSections['casscf']}
              <div class="detail-section-body">
                <div class="detail-kv-list">
                  <div class="kv"><span class="k">Active space</span><span class="v">{detailsData.casscf.active_space_label}</span></div>
                  <div class="kv"><span class="k">Active orbitals (ncas)</span><span class="v">{detailsData.casscf.ncas}</span></div>
                  <div class="kv"><span class="k">Active electrons (nelecas)</span><span class="v">{detailsData.casscf.nelecas}</span></div>
                  <div class="kv"><span class="k">Total MOs</span><span class="v">{detailsData.casscf.num_mo}</span></div>
                  <div class="kv"><span class="k">Converged</span><span class="v">{detailsData.casscf.converged ? 'Yes' : 'No'}</span></div>
                </div>
              </div>
            {/if}

            <!-- Orbital Composition -->
            <button class="detail-section-header" on:click={() => toggleDetailSection('orbitals')}>
              <span>Orbital Composition</span>
              <span class="chevron" class:open={detailsExpandedSections['orbitals']}>▸</span>
            </button>
            {#if detailsExpandedSections['orbitals']}
              <div class="detail-section-body">
                {#each detailsData.orbitals as orb}
                  <div class="orbital-detail-card">
                    <div class="orbital-detail-header">
                      <span class="orbital-detail-label">{orb.label}</span>
                      <span class="orbital-detail-occ">occ = {orb.occupation.toFixed(4)}</span>
                    </div>
                    <div class="ao-bar-list">
                      {#each orb.ao_contributions as ao}
                        <div class="ao-bar-row">
                          <span class="ao-bar-label">{ao.ao_label}</span>
                          <div class="ao-bar-track">
                            <div class="ao-bar-fill" style="width: {ao.weight_percent}%"></div>
                          </div>
                          <span class="ao-bar-pct">{ao.weight_percent}%</span>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}

          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  /* ── App frame ── */
  .phone-frame {
    width: 100%;
    height: 100vh;
    height: 100dvh;
    display: flex;
    flex-direction: column;
    background: #0d0d0d;
    color: #e0e0e0;
    font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    position: relative;
    overflow: hidden;
  }

  /* ── Top bar ── */
  .top-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 1rem;
    padding-top: calc(0.6rem + env(safe-area-inset-top, 0px));
    padding-left: calc(1rem + env(safe-area-inset-left, 0px));
    padding-right: calc(1rem + env(safe-area-inset-right, 0px));
    background: #111;
    border-bottom: 1px solid #222;
    flex-shrink: 0;
    z-index: 10;
  }

  .top-bar h1 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    color: #fff;
    flex: 1;
  }

  .top-actions {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  .loading-status {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .loading-text {
    font-size: 0.7rem;
    color: #4a9eff;
    font-family: 'SF Mono', 'Menlo', monospace;
    white-space: nowrap;
  }

  .compute-btn {
    background: #4a9eff;
    border: none;
    border-radius: 8px;
    padding: 0.4rem 0.75rem;
    min-height: 36px;
    font-size: 0.75rem;
    color: #fff;
    font-family: inherit;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    line-height: 1;
    letter-spacing: 0.02em;
    -webkit-tap-highlight-color: transparent;
  }

  .compute-btn:active:not(:disabled) {
    background: #3a8eef;
    transform: scale(0.97);
  }

  .compute-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── Current molecule bar ── */
  .current-molecule-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.35rem 0.75rem;
    padding-left: calc(0.75rem + env(safe-area-inset-left, 0px));
    padding-right: calc(0.75rem + env(safe-area-inset-right, 0px));
    background: #111;
    border-bottom: 1px solid #1a1a1a;
    flex-shrink: 0;
    z-index: 10;
  }

  .current-mol-name {
    font-size: 0.82rem;
    color: #ccc;
    font-weight: 500;
  }

  .current-mol-meta {
    font-size: 0.68rem;
    color: #555;
    font-family: 'SF Mono', 'Menlo', monospace;
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

  /* ── Loading overlay ── */
  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.2s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .loading-card {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    min-width: 280px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    animation: slideUp 0.3s ease-out;
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid #333;
    border-top-color: #4a9eff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1.5rem;
  }

  .header-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid #333;
    border-top-color: #4a9eff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .loading-message {
    font-size: 1rem;
    color: #ddd;
    font-weight: 500;
    margin-bottom: 1.2rem;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background: #333;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 0.6rem;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4a9eff, #44cc88);
    border-radius: 4px;
    transition: width 0.3s ease-out;
  }

  .progress-text {
    font-size: 0.85rem;
    color: #888;
    font-family: 'SF Mono', 'Menlo', monospace;
  }

  .progress-fill-pulse {
    animation: pulse-fill 2s ease-in-out infinite;
  }

  @keyframes pulse-fill {
    0%, 100% { opacity: 0.7; }
    50% { opacity: 1; }
  }

  .init-error {
    color: #ff6644;
    font-size: 0.9rem;
    margin-top: 1rem;
  }

  /* ── Welcome / empty state overlay ── */
  .welcome-overlay {
    position: absolute;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
  .welcome-card {
    background: #1e1e1e;
    border: 1px solid #333;
    border-radius: 18px;
    padding: 2rem 1.5rem;
    max-width: 340px;
    width: 90%;
    text-align: center;
  }
  .welcome-card h2 {
    margin: 0 0 0.75rem;
    font-size: 1.3rem;
    color: #fff;
  }
  .welcome-card p {
    color: #aaa;
    font-size: 0.9rem;
    line-height: 1.5;
    margin: 0 0 1.25rem;
  }

  /* ── Compute panel molecule select ── */
  .molecule-select {
    width: 100%;
    padding: 0.6rem 0.75rem;
    min-height: 44px;
    background: #1a1a1a;
    color: #fff;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    font-size: 16px;
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
    padding: 0 0.75rem;
    padding-left: calc(0.75rem + env(safe-area-inset-left, 0px));
    padding-right: calc(0.75rem + env(safe-area-inset-right, 0px));
    padding-bottom: calc(0.5rem + env(safe-area-inset-bottom, 0px));
    transition: max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    max-height: 110px;
    overflow: hidden;
    z-index: 20;
  }

  .bottom-sheet.open {
    max-height: 60vh;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }

  .sheet-handle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 0.75rem 0 0.4rem;
    min-height: 44px;
    background: none;
    border: none;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }

  .handle-bar {
    width: 36px;
    height: 4px;
    background: #444;
    border-radius: 2px;
    transition: background 0.2s;
  }

  .sheet-handle:active .handle-bar {
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
    padding: 0.5rem 0.75rem;
    min-height: 38px;
    background: transparent;
    color: #888;
    border: none;
    font-size: 0.8rem;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s;
    -webkit-tap-highlight-color: transparent;
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
    height: 6px;
    padding: 8px 0;
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

  .info-tip:active {
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

  .info-tip:active .tip-bubble,
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

  /* ── Orbitals header with select actions ── */
  .orbitals-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.3rem;
  }

  .orbitals-header h4 {
    margin: 0;
  }

  .select-actions {
    display: flex;
    gap: 0.3rem;
  }

  .select-btn {
    padding: 0.15rem 0.45rem;
    background: #1e1e1e;
    color: #888;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    font-size: 0.65rem;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .select-btn:active:not(:disabled) {
    border-color: #4a9eff;
    color: #4a9eff;
  }

  .select-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── Orbital groups ── */
  .orbital-group {
    margin-bottom: 0.5rem;
  }

  .group-header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    width: 100%;
    padding: 0.45rem 0.5rem;
    min-height: 40px;
    background: #1a1a1a;
    border: 1px solid #252525;
    border-radius: 8px;
    color: #bbb;
    cursor: pointer;
    margin-bottom: 0.35rem;
    transition: all 0.15s;
    font-family: inherit;
    font-size: 0.78rem;
    -webkit-tap-highlight-color: transparent;
  }

  .group-header:active:not(:disabled) {
    border-color: #3a3a3a;
    background: #1e1e1e;
  }

  .group-header:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }


  .group-name {
    font-weight: 500;
    flex: 1;
    text-align: left;
  }

  .group-count {
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 0.65rem;
    color: #666;
    background: #222;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
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
    padding: 0.4rem 0.6rem;
    min-height: 36px;
    background: #1e1e1e;
    color: #999;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    font-size: 0.75rem;
    font-family: 'SF Mono', 'Menlo', monospace;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
    -webkit-tap-highlight-color: transparent;
  }

  .chip:active:not(:disabled) {
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
    padding: 0.45rem;
    min-height: 40px;
    background: #1e1e1e;
    color: #999;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    font-size: 0.8rem;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s;
    -webkit-tap-highlight-color: transparent;
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

  /* ── Details button ── */
  .details-btn {
    background: none;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 0.4rem 0.65rem;
    min-height: 36px;
    font-size: 0.72rem;
    color: #888;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s;
    line-height: 1;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    -webkit-tap-highlight-color: transparent;
  }

  .details-btn:active {
    border-color: #4a9eff;
    background: #4a9eff18;
  }

  /* ── Modal overlay ── */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    z-index: 100;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    padding: 0;
  }

  .modal-panel {
    width: 100%;
    max-height: 92vh;
    max-height: 92dvh;
    background: #151515;
    border: none;
    border-top: 1px solid #2a2a2a;
    border-radius: 16px 16px 0 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 -8px 40px rgba(0,0,0,0.6);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 1rem;
    padding-left: calc(1rem + env(safe-area-inset-left, 0px));
    padding-right: calc(1rem + env(safe-area-inset-right, 0px));
    border-bottom: 1px solid #222;
    flex-shrink: 0;
  }

  .modal-header h2 {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #fff;
  }

  .modal-close {
    background: none;
    border: none;
    color: #666;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0.5rem;
    min-width: 44px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
    transition: color 0.15s;
    -webkit-tap-highlight-color: transparent;
  }

  .modal-close:active {
    color: #fff;
  }

  .modal-loading {
    padding: 2rem;
    text-align: center;
    color: #666;
    font-size: 0.85rem;
  }

  .modal-body {
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    padding: 0.5rem;
    padding-left: calc(0.5rem + env(safe-area-inset-left, 0px));
    padding-right: calc(0.5rem + env(safe-area-inset-right, 0px));
    padding-bottom: calc(0.5rem + env(safe-area-inset-bottom, 0px));
    flex: 1;
    overscroll-behavior: contain;
  }

  .modal-body::-webkit-scrollbar {
    width: 3px;
  }

  .modal-body::-webkit-scrollbar-thumb {
    background: #333;
    border-radius: 2px;
  }

  /* ── Detail sections ── */
  .detail-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 0.65rem 0.7rem;
    min-height: 44px;
    background: #1a1a1a;
    border: 1px solid #222;
    border-radius: 8px;
    color: #ddd;
    cursor: pointer;
    font-family: inherit;
    font-size: 0.85rem;
    font-weight: 500;
    margin-bottom: 0.3rem;
    transition: all 0.15s;
    -webkit-tap-highlight-color: transparent;
  }

  .detail-section-header:active {
    background: #1e1e1e;
    border-color: #3a3a3a;
  }

  .chevron {
    font-size: 0.75rem;
    color: #555;
    transition: transform 0.2s;
    display: inline-block;
  }

  .chevron.open {
    transform: rotate(90deg);
  }

  .detail-section-body {
    padding: 0.4rem 0.5rem 0.6rem;
    margin-bottom: 0.3rem;
  }

  .detail-section-body h5 {
    margin: 0.6rem 0 0.3rem;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #555;
    font-weight: 500;
  }

  /* ── Key-value lists ── */
  .detail-kv-list {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .kv {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.3rem 0.35rem;
    border-radius: 4px;
    font-size: 0.78rem;
    gap: 0.5rem;
  }

  .kv:nth-child(odd) {
    background: #1a1a1a;
  }

  .kv .k {
    color: #888;
    flex-shrink: 0;
  }

  .kv .v {
    color: #ccc;
    text-align: right;
    word-break: break-all;
  }

  .mono {
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 0.73rem;
  }

  /* ── Detail table ── */
  .detail-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.72rem;
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .detail-table thead,
  .detail-table tbody,
  .detail-table tr {
    display: table;
    width: 100%;
    table-layout: fixed;
  }

  .detail-table thead {
    display: table;
    width: 100%;
  }

  .detail-table th {
    padding: 0.25rem 0.3rem;
    text-align: left;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #555;
    font-weight: 500;
    border-bottom: 1px solid #222;
  }

  .detail-table td {
    padding: 0.25rem 0.3rem;
    color: #bbb;
  }

  .detail-table tr:nth-child(even) td {
    background: #1a1a1a;
  }

  /* ── AO labels grid ── */
  .ao-labels-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .ao-tag {
    padding: 0.15rem 0.4rem;
    background: #1e1e1e;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 0.65rem;
    color: #999;
    white-space: nowrap;
  }

  /* ── Orbital detail cards ── */
  .orbital-detail-card {
    padding: 0.4rem 0.5rem;
    background: #1a1a1a;
    border: 1px solid #222;
    border-radius: 8px;
    margin-bottom: 0.35rem;
  }

  .orbital-detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.35rem;
  }

  .orbital-detail-label {
    font-weight: 600;
    font-size: 0.8rem;
    color: #ddd;
  }

  .orbital-detail-occ {
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 0.7rem;
    color: #4a9eff;
  }

  .ao-bar-list {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .ao-bar-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.7rem;
  }

  .ao-bar-label {
    flex-shrink: 0;
    width: 70px;
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 0.65rem;
    color: #888;
    text-align: right;
  }

  .ao-bar-track {
    flex: 1;
    height: 6px;
    background: #222;
    border-radius: 3px;
    overflow: hidden;
  }

  .ao-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #4a9eff, #44cc88);
    border-radius: 3px;
    transition: width 0.3s;
  }

  .ao-bar-pct {
    flex-shrink: 0;
    width: 36px;
    font-family: 'SF Mono', 'Menlo', monospace;
    font-size: 0.65rem;
    color: #666;
    text-align: right;
  }

  /* ── Compute panel ── */
  .compute-panel {
    max-height: 95vh;
    max-height: 95dvh;
  }

  .compute-section {
    margin-bottom: 1rem;
  }

  .compute-section h4 {
    margin: 0 0 0.5rem;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #888;
    font-weight: 500;
  }

  .pending-count {
    color: #4a9eff;
    font-weight: 400;
    text-transform: none;
    letter-spacing: normal;
  }

  .res-sub {
    display: block;
    font-size: 0.6rem;
    color: #555;
    font-weight: 400;
    margin-top: 0.15rem;
  }

  .run-compute-btn {
    width: 100%;
    padding: 0.8rem 1rem;
    min-height: 48px;
    background: #4a9eff;
    color: #fff;
    border: none;
    border-radius: 12px;
    font-size: 0.9rem;
    font-family: inherit;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 0.5rem;
    -webkit-tap-highlight-color: transparent;
  }

  .run-compute-btn:active:not(:disabled) {
    background: #3a8eef;
    transform: scale(0.98);
  }

  .run-compute-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

</style>
