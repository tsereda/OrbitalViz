<script>
  import { T } from '@threlte/core';
  import { onMount } from 'svelte';
  import * as THREE from 'three';
  import MarchingCubesWorker from '../workers/marchingCubes.worker.js?worker';
  
  export let gridData;
  export let gridSize;
  export let bounds;
  export let isovalue;
  export let positiveColor = '#4a9eff';
  export let negativeColor = '#ff4a4a';
  export let opacity = 0.7;
  
  let positiveGeometry = null;
  let negativeGeometry = null;
  let posWorker = null;
  let negWorker = null;
  
  onMount(() => {
    posWorker = new MarchingCubesWorker();
    negWorker = new MarchingCubesWorker();
    
    posWorker.onmessage = (e) => {
      if (e.data.success) {
        if (positiveGeometry) positiveGeometry.dispose();
        positiveGeometry = new THREE.BufferGeometry();
        positiveGeometry.setAttribute('position', new THREE.BufferAttribute(e.data.vertices, 3));
        positiveGeometry.setAttribute('normal', new THREE.BufferAttribute(e.data.normals, 3));
        positiveGeometry.computeBoundingSphere();
      }
    };
    
    negWorker.onmessage = (e) => {
      if (e.data.success) {
        if (negativeGeometry) negativeGeometry.dispose();
        negativeGeometry = new THREE.BufferGeometry();
        negativeGeometry.setAttribute('position', new THREE.BufferAttribute(e.data.vertices, 3));
        negativeGeometry.setAttribute('normal', new THREE.BufferAttribute(e.data.normals, 3));
        negativeGeometry.computeBoundingSphere();
      }
    };
    
    return () => {
      if (posWorker) posWorker.terminate();
      if (negWorker) negWorker.terminate();
      if (positiveGeometry) positiveGeometry.dispose();
      if (negativeGeometry) negativeGeometry.dispose();
    };
  });
  
  $: if (posWorker && negWorker && gridData && gridSize && bounds && isovalue !== undefined) {
    // Positive lobe
    posWorker.postMessage({ gridData, gridSize, bounds, isovalue: isovalue });
    // Negative lobe
    negWorker.postMessage({ gridData, gridSize, bounds, isovalue: -isovalue });
  }
</script>

{#if positiveGeometry}
  <T.Mesh geometry={positiveGeometry}>
    <T.MeshPhongMaterial
      color={positiveColor}
      transparent
      {opacity}
      side={THREE.DoubleSide}
      shininess={100}
      specular="#ffffff"
    />
  </T.Mesh>
{/if}

{#if negativeGeometry}
  <T.Mesh geometry={negativeGeometry}>
    <T.MeshPhongMaterial
      color={negativeColor}
      transparent
      {opacity}
      side={THREE.DoubleSide}
      shininess={100}
      specular="#ffffff"
    />
  </T.Mesh>
{/if}
