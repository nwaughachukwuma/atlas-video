<script lang="ts">
  import { route, type RouteResult } from "@mateothegreat/svelte5-router";
  import { FilmIcon, LoaderCircleIcon } from "lucide-svelte";
  import { onMount } from "svelte";
  import { getVideo } from "../lib/api.ts";
  import type { Video } from "../lib/types.ts";
  import ChatPanel from "../components/ChatPanel.svelte";
  import VideoSearch from "../components/VideoSearch.svelte";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";

  let { route: routeResult }: { route: RouteResult } = $props();

  // @ts-expect-error
  let videoId: string = $derived(routeResult.result.path.params?.id);
  let videoData = $state<Video | null>(null);
  let loading = $state(true);
  let pollInterval = $state<number | null>(null);
  let taskStatus = $state<string | null>(null);

  async function loadVideoData() {
    if (!videoId) throw new Error("videoId not found");
    return getVideo(videoId)
      .then((d) => {
        if (d.data) videoData = d.data;
        return d.data;
      })
      .catch((e) => {
        // may still be indexing via queue — poll
        if (e.message.includes("404") || e.message.includes("No data")) {
          taskStatus = "pending";
          return;
        }
        toast.error("Error fetching video data", { description: e.message });
      })
      .finally(() => (loading = false));
  }

  onMount(() => {
    loadVideoData();
    if (!videoData) {
      // Poll until video is available (queued indexing)
      pollInterval = setInterval(() => {
        loadVideoData().then(
          (d) => d && pollInterval && clearInterval(pollInterval),
        );
      }, 4000);
    }
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  });
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
    <div class="card flex items-center gap-x-2 text-center py-8">
      <LoaderCircleIcon
        class="w-5 h-5 animate-spin"
        style="animation-duration: 0.3s"
      />
      <span>Loading video data…</span>
    </div>
  {:else if !videoData}
    <div class="card py-8">
      <div class="flex items-center gap-x-2">
        <LoaderCircleIcon
          class="w-5 h-5 animate-spin"
          style="animation-duration: 0.3s"
        />
        <div>Video is being indexed...Checking every 4s.</div>
      </div>
      <p class="text-muted mt-4 text-[0.85rem] mb-0">
        This page will update automatically when ready.
      </p>
    </div>
  {:else}
    <VideoSearch {videoId} />

    <div class="card mb-4 mt-5">
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
        {#each videoData.chunks as chunk, i (`${i}:${chunk.start_time}`)}
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

    <ChatPanel {videoId} />
  {/if}
</div>
