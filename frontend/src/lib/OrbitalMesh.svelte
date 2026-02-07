<script>
  import { T } from '@threlte/core';
  import { onMount } from 'svelte';
  import * as THREE from 'three';
  import MarchingCubesWorker from '../workers/marchingCubes.worker.js?worker';
  
  export let gridData;
  export let gridSize;
  export let bounds;
  export let isovalue;
  
  let geometry = null;
  let worker = null;
  
  onMount(() => {
    worker = new MarchingCubesWorker();
    worker.onmessage = (e) => {
      if (e.data.success) {
        updateGeometry(e.data.vertices, e.data.normals);
      } else {
        console.error('Worker error:', e.data.error);
      }
    };
    
    return () => {
      if (worker) worker.terminate();
      if (geometry) geometry.dispose();
    };
  });
  
  function updateGeometry(vertices, normals) {
    if (geometry) {
      geometry.dispose();
    }
    
    geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
    geometry.computeBoundingSphere();
  }
  
  $: if (worker && gridData && gridSize && bounds && isovalue !== undefined) {
    worker.postMessage({ gridData, gridSize, bounds, isovalue });
  }
</script>

{#if geometry}
  <!-- Positive isovalue surface (blue) -->
  <T.Mesh {geometry}>
    <T.MeshPhongMaterial
      color="#4a9eff"
      transparent
      opacity={0.8}
      side={THREE.DoubleSide}
      shininess={100}
      specular="#ffffff"
    />
  </T.Mesh>
{/if}
