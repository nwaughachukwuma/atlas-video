<script>
  import Router from 'svelte-spa-router';
  import NavBar from './components/NavBar.svelte';
  import Home from './pages/Home.svelte';
  import Transcribe from './pages/Transcribe.svelte';
  import Extract from './pages/Extract.svelte';
  import Index from './pages/Index.svelte';
  import Search from './pages/Search.svelte';
  import Videos from './pages/Videos.svelte';
  import VideoDetail from './pages/VideoDetail.svelte';
  import Queue from './pages/Queue.svelte';
  import Stats from './pages/Stats.svelte';

  const routes = {
    '/': Home,
    '/transcribe': Transcribe,
    '/extract': Extract,
    '/index': Index,
    '/search': Search,
    '/videos': Videos,
    '/videos/:id': VideoDetail,
    '/queue': Queue,
    '/queue/:id': Queue,
    '/stats': Stats,
  };

  let currentPath = '/';

  import { location } from 'svelte-spa-router';
  $: currentPath = $location;
</script>

<NavBar {currentPath} />
<main>
  <Router {routes} />
</main>

<style>
  main {
    flex: 1;
    overflow-y: auto;
    min-height: 100vh;
  }
</style>

