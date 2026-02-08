<script>
  import MultiOrbitalViewer from './lib/MultiOrbitalViewer.svelte'
  
  // Configure API URL (can be overridden via environment variables)
  // Use empty string in production to make relative requests to same host
  const apiUrl = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '' : 'http://localhost:8000');
</script>

<MultiOrbitalViewer {apiUrl} />

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    overflow: hidden;
  }
</style>
