<script>
  import Router from "svelte-spa-router";
  import { location } from "svelte-spa-router";
  import NavBar from "./components/NavBar.svelte";
  import HowItWorks from "./components/HowItWorks.svelte";
  import Home from "./pages/Home.svelte";
  import Transcribe from "./pages/Transcribe.svelte";
  import Extract from "./pages/Extract.svelte";
  import Index from "./pages/Index.svelte";
  import Videos from "./pages/Videos.svelte";
  import VideoDetail from "./pages/VideoDetail.svelte";
  import Queue from "./pages/Queue.svelte";
  import Dashboard from "./pages/Dashboard.svelte";

  const routes = {
    "/": Home,
    "/transcribe": Transcribe,
    "/extract": Extract,
    "/index": Index,
    "/videos": Videos,
    "/videos/:id": VideoDetail,
    "/queue": Queue,
    "/queue/:id": Queue,
    "/dashboard": Dashboard,
  };

  let currentPath = "/";
  $: currentPath = $location;
</script>

<NavBar {currentPath} />
<main class="flex-1 overflow-y-auto min-h-screen">
  <Router {routes} />
</main>

<div class="fixed top-4 right-5 z-[100]">
  <HowItWorks />
</div>
