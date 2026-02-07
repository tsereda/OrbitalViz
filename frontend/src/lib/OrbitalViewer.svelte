<script>
  import { Canvas, T } from '@threlte/core';
  import { OrbitControls } from '@threlte/extras';
  import { onMount } from 'svelte';
  import OrbitalMesh from './OrbitalMesh.svelte';
  import MoleculeAtoms from './MoleculeAtoms.svelte';
  
  export let apiUrl = 'http://localhost:8000';
  
  let orbitalIndex = 0;
  let isovalue = 0.02;
  let gridSize = 64;
  let loading = false;
  let moleculeInfo = null;
  let orbitalData = null;
  let prevOrbitalIndex = -1;
  let prevGridSize = -1;
  
  onMount(() => {
    fetchMoleculeInfo();
    fetchOrbitalData();
  });
  
  async function fetchMoleculeInfo() {
    try {
      const response = await fetch(`${apiUrl}/api/molecule/info`);
      moleculeInfo = await response.json();
    } catch (error) {
      console.error('Failed to fetch molecule info:', error);
    }
  }
  
  async function fetchOrbitalData() {
    loading = true;
    try {
      const response = await fetch(
        `${apiUrl}/api/orbital/${orbitalIndex}?grid_size=${gridSize}&margin=3.0`
      );
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const arrayBuffer = await response.arrayBuffer();
      
      // Parse header (3 ints + 6 floats = 36 bytes)
      const headerView = new DataView(arrayBuffer, 0, 36);
      const gx = headerView.getInt32(0, true);
      const gy = headerView.getInt32(4, true);
      const gz = headerView.getInt32(8, true);
      const minX = headerView.getFloat32(12, true);
      const minY = headerView.getFloat32(16, true);
      const minZ = headerView.getFloat32(20, true);
      const maxX = headerView.getFloat32(24, true);
      const maxY = headerView.getFloat32(28, true);
      const maxZ = headerView.getFloat32(32, true);
      
      // Parse orbital data
      const dataView = new Float32Array(arrayBuffer, 36);
      
      orbitalData = {
        gridSize: gx,
        gridData: dataView,
        bounds: {
          min: [minX, minY, minZ],
          max: [maxX, maxY, maxZ]
        }
      };
      
      prevOrbitalIndex = orbitalIndex;
      prevGridSize = gridSize;
    } catch (error) {
      console.error('Failed to fetch orbital data:', error);
    } finally {
      loading = false;
    }
  }
  
  $: {
    if ((orbitalIndex !== prevOrbitalIndex || gridSize !== prevGridSize) && 
        moleculeInfo !== null) {
      fetchOrbitalData();
    }
  }
</script>

<div class="orbital-viewer">
  <div class="controls">
    <div class="control-group">
      <label>
        Orbital Index:
        <input
          type="range"
          bind:value={orbitalIndex}
          min="0"
          max={moleculeInfo?.num_orbitals - 1 || 0}
          disabled={loading || !moleculeInfo}
        />
        <span>{orbitalIndex}</span>
      </label>
    </div>
    
    <div class="control-group">
      <label>
        Isovalue:
        <input
          type="range"
          bind:value={isovalue}
          min="0.001"
          max="0.1"
          step="0.001"
          disabled={loading}
        />
        <span>{isovalue.toFixed(3)}</span>
      </label>
    </div>
    
    <div class="control-group">
      <label>
        Grid Resolution:
        <select bind:value={gridSize} disabled={loading}>
          <option value={32}>32 (Fast)</option>
          <option value={64}>64 (Balanced)</option>
          <option value={96}>96 (High)</option>
        </select>
      </label>
    </div>
    
    {#if loading}
      <div class="loading">Loading orbital data...</div>
    {/if}
  </div>
  
  <div class="canvas-container">
    <Canvas>
      <T.PerspectiveCamera makeDefault position={[10, 10, 10]} fov={50}>
        <OrbitControls enableDamping enablePan enableZoom />
      </T.PerspectiveCamera>
      
      <!-- Lighting -->
      <T.AmbientLight intensity={0.5} />
      <T.DirectionalLight position={[10, 10, 10]} intensity={1} />
      <T.DirectionalLight position={[-10, -10, -10]} intensity={0.5} />
      
      <!-- Molecule atoms -->
      {#if moleculeInfo}
        <MoleculeAtoms atoms={moleculeInfo.atoms} />
      {/if}
      
      <!-- Orbital isosurface -->
      {#if orbitalData && !loading}
        <OrbitalMesh
          gridData={orbitalData.gridData}
          gridSize={orbitalData.gridSize}
          bounds={orbitalData.bounds}
          {isovalue}
        />
      {/if}
    </Canvas>
  </div>
</div>

<style>
  .orbital-viewer {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: #1a1a1a;
    color: #fff;
  }
  
  .controls {
    padding: 1rem;
    background: #2a2a2a;
    border-bottom: 1px solid #3a3a3a;
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
    align-items: center;
  }
  
  .control-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .control-group label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
  }
  
  input[type="range"] {
    width: 150px;
  }
  
  select {
    padding: 0.25rem 0.5rem;
    background: #1a1a1a;
    color: #fff;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
  }
  
  .loading {
    color: #4a9eff;
    font-weight: 500;
  }
  
  .canvas-container {
    flex: 1;
    position: relative;
    touch-action: none;
  }
  
  span {
    min-width: 50px;
    text-align: right;
    font-family: monospace;
  }
  
  /* Mobile optimizations */
  @media (max-width: 768px) {
    .controls {
      flex-direction: column;
      gap: 1rem;
      align-items: stretch;
    }
    
    .control-group label {
      flex-direction: column;
      align-items: stretch;
    }
    
    input[type="range"] {
      width: 100%;
    }
  }
</style>
