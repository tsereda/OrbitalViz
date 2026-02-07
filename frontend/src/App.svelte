<script>
  import MultiOrbitalViewer from './lib/MultiOrbitalViewer.svelte'
  
  // Configure API URL (can be overridden via environment variables)
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
</script>

<MultiOrbitalViewer {apiUrl} />

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    overflow: hidden;
  }
</style>
