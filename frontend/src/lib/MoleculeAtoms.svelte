<script>
  import { T } from '@threlte/core';
  
  export let atoms = [];
  
  const atomColors = {
    'H': '#ffffff',
    'C': '#909090',
    'N': '#3050f8',
    'O': '#ff0d0d',
    'F': '#90e050',
    'P': '#ff8000',
    'S': '#ffff30',
    'Cl': '#1ff01f',
  };
  
  const atomSizes = {
    'H': 0.31,
    'C': 0.76,
    'N': 0.71,
    'O': 0.66,
    'F': 0.57,
    'P': 1.07,
    'S': 1.05,
    'Cl': 1.02,
  };
  
  function getAtomColor(element) {
    return atomColors[element] || '#cccccc';
  }
  
  function getAtomSize(element) {
    return atomSizes[element] || 0.7;
  }
</script>

{#each atoms as atom}
  <T.Mesh position={atom.coords}>
    <T.SphereGeometry args={[getAtomSize(atom.element) * 0.3, 16, 16]} />
    <T.MeshPhongMaterial color={getAtomColor(atom.element)} />
  </T.Mesh>
{/each}
