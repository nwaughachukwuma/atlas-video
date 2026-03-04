<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { FilmIcon, MessageSquareIcon } from "lucide-svelte";
  import { onMount, onDestroy } from "svelte";
  import { getVideo, search } from "../lib/api.ts";
  import type { Video, SearchResult } from "../lib/types.ts";
  import ChatPanel from "../components/ChatPanel.svelte";
  import { toPath } from "../lib/routing.ts";

  let { route: routeResult } = $props();

  const videoId: string = $derived(
    ((routeResult?.result?.path?.params?.id as string | undefined) ??
      "") as string,
  );

  let videoData: Video | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);
  let chatOpen: boolean = $state(false);
  let searchQuery: string = $state("");
  let searchResults: SearchResult[] | null = $state(null);
  let searching: boolean = $state(false);
  let pollInterval: ReturnType<typeof setInterval> | null = $state(null);
  let taskStatus: string | null = $state(null);

  async function loadVideo(): Promise<void> {
    try {
      const data = await getVideo(videoId);
      videoData = data.data ?? data;
      loading = false;
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("404") || msg.includes("No data")) {
        // may still be indexing via queue — poll
        loading = false;
        taskStatus = "pending";
      } else {
        error = msg;
        loading = false;
      }
    }
  }

  async function doSearch(): Promise<void> {
    if (!searchQuery.trim()) {
      searchResults = null;
      return;
    }
    searching = true;
    try {
      const data = await search(searchQuery.trim(), videoId, 20);
      searchResults = data.results ?? [];
    } catch (e) {
      error = (e as Error).message;
    } finally {
      searching = false;
    }
  }

  function clearSearch(): void {
    searchQuery = "";
    searchResults = null;
  }

  onMount(async () => {
    await loadVideo();
    if (!videoData) {
      // Poll until video is available (queued indexing)
      pollInterval = setInterval(async () => {
        await loadVideo();
        if (videoData) clearInterval(pollInterval!);
      }, 4000);
    }
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  function formatDate(iso: string | undefined): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }
</script>

<div class="p-8 max-w-[860px]">
  <div class="mb-4 text-[0.85rem]">
    <a href={toPath("/videos")} use:route>← All Videos</a>
  </div>
  <h2>
    <FilmIcon
      size={20}
      strokeWidth={2}
      style="display:inline;vertical-align:middle;"
    /> Video Detail
  </h2>
  <code
    class="block text-[0.8rem] bg-surface-alt px-[0.5em] py-[0.25em] font-mono mt-1 mb-5 w-fit"
    >{videoId}</code
  >

  {#if loading}
    <div class="card text-center py-8">
      <span class="spinner"></span>
      <p class="mt-2 mb-0">Loading video data…</p>
    </div>
  {:else if error}
    <div class="error-box">{error}</div>
  {:else if !videoData}
    <div class="card text-center py-8">
      <span class="spinner"></span>
      <p class="mt-2 mb-0">
        Video is still being indexed… Checking every 4 seconds.
      </p>
      <p class="text-muted text-[0.85rem] mb-0">
        This page will update automatically when ready.
      </p>
    </div>
  {:else}
    <div class="flex gap-2 mb-5">
      <input
        type="search"
        bind:value={searchQuery}
        placeholder="Search within this video…"
        class="flex-1"
        onkeydown={(e) => e.key === "Enter" && doSearch()}
      />
      <button
        class="btn-primary"
        onclick={doSearch}
        disabled={searching || !searchQuery.trim()}
      >
        {#if searching}<span class="spinner"></span>{:else}Search{/if}
      </button>
      {#if searchResults !== null}
        <button class="btn-secondary" onclick={clearSearch}>Clear</button>
      {/if}
    </div>

    {#if searchResults !== null}
      <section class="card">
        <h3 class="mb-3">
          Search results <span class="text-muted text-[0.85rem]"
            >({searchResults.length})</span
          >
        </h3>
        {#if searchResults.length === 0}
          <p class="text-muted text-[0.85rem]">No results.</p>
        {:else}
          {#each searchResults as r}
            <div class="border-b border-line py-3 last:border-b-0">
              <span class="text-[0.75rem] text-muted"
                >score: {r.score?.toFixed(3) ?? "—"}</span
              >
              {#if r.description}<p class="text-[0.88rem] mt-1 mb-0">
                  {r.description}
                </p>{/if}
              {#if r.transcript}<p class="text-[0.85rem] text-muted mb-0">
                  {r.transcript}
                </p>{/if}
            </div>
          {/each}
        {/if}
      </section>
    {:else}
      <div class="card mb-4">
        <h3 class="mb-3">Video Info</h3>
        <div class="flex flex-col gap-[0.4rem]">
          {#each Object.entries(videoData) as [k, v]}
            {#if typeof v !== "object" || v === null}
              <div class="flex gap-4 text-[0.88rem]">
                <span class="text-muted min-w-32">{k}</span>
                <span class="text-ink">{v ?? "—"}</span>
              </div>
            {/if}
          {/each}
        </div>
        {#if videoData.chunks}
          <h4 class="mt-4">Segments ({videoData.chunks.length})</h4>
          {#each videoData.chunks as chunk, i}
            <details class="border border-line mb-[0.4rem] p-[0.4rem]">
              <summary
                class="cursor-pointer text-[0.85rem] text-muted hover:text-cobalt"
                >Segment {i + 1}</summary
              >
              <pre>{JSON.stringify(chunk, null, 2)}</pre>
            </details>
          {/each}
        {/if}
      </div>
    {/if}

    <button
      class="btn-primary mt-6 text-base px-[1.6em] py-[0.6em]"
      onclick={() => (chatOpen = true)}
    >
      <MessageSquareIcon
        size={16}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Chat with this video
    </button>
  {/if}
</div>

{#if chatOpen}
  <ChatPanel {videoId} onClose={() => (chatOpen = false)} />
{/if}
