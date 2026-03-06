<script lang="ts">
  import { Router, type RouteConfig } from "@mateothegreat/svelte5-router";
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
  import { BASE_PATH } from "./lib/routing.ts";
  import { Toaster } from "svelte-sonner";

  const routes: RouteConfig[] = [
    { path: "/", component: Home },
    { path: "/transcribe", component: Transcribe },
    { path: "/extract", component: Extract },
    { path: "/index", component: Index },
    { path: "/video/(?<id>[^/]+)", component: VideoDetail },
    { path: "/videos", component: Videos },
    { path: "/queue/(?<id>[^/]+)", component: Queue },
    { path: "/queue", component: Queue },
    { path: "/dashboard", component: Dashboard },
  ];
</script>

<NavBar />

<main class="flex-1 overflow-y-auto min-h-screen">
  <Router {routes} basePath={BASE_PATH} />
</main>

<div class="fixed top-4 right-5 z-100">
  <HowItWorks />
</div>

<Toaster duration={5000} position="bottom-right" />
