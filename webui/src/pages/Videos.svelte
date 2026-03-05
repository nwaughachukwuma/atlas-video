<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { FilmIcon, LoaderCircleIcon } from "lucide-svelte";
  import { onMount } from "svelte";
  import { listVideos } from "../lib/api.ts";
  import type { Video } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";
  import VideoSearch from "../components/VideoSearch.svelte";

  let videos = $state<Video[]>([]);
  let loading = $state(true);

  onMount(() => {
    listVideos()
      .then((d) => (videos = d.videos))
      .catch((e) =>
        toast.error("Error fetching videos", { description: e.message }),
      )
      .finally(() => (loading = false));
  });

  function formatDate(iso: string | undefined): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }
</script>

<div class="p-8 max-w-[900px]">
  <h2 class="flex items-center gap-1.5">
    <FilmIcon
      size={20}
      strokeWidth={2}
      style="display:inline;vertical-align:middle;"
    /> Indexed Videos
  </h2>
  <p class="text-muted mb-5">
    All videos currently in your local vector store. Click any video to explore
    or chat with it.
  </p>

  <VideoSearch
    disabled={!videos.length}
    placeholder={!videos.length ? "Upload videos to search" : ""}
  />

  {#if loading}
    <p class="flex gap-x-2 items-center">
      <LoaderCircleIcon
        class="w-5 h-5 animate-spin"
        style="animation-duration: 0.3s"
      />
      Loading videos…
    </p>
  {:else if videos.length === 0}
    <div class="card text-center py-10">
      <p class="mb-4">No videos indexed yet.</p>
      <a
        href={toPath("/index")}
        use:route
        class="btn-primary inline-block px-6 py-2.5 text-[0.95rem]"
        >Index your first video →</a
      >
    </div>
  {:else}
    <div class="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
      {#each videos as v}
        <a
          href={toPath(`/video/${v.video_id}`)}
          use:route
          class="card flex gap-3 items-start text-ink transition-[border-color] duration-150 hover:border-cobalt"
        >
          <div class="text-cobalt flex items-center">
            <FilmIcon size={20} strokeWidth={1.5} />
          </div>
          <div class="flex flex-col gap-1 min-w-0">
            <span
              class="text-[0.8rem] font-mono whitespace-nowrap overflow-hidden text-ellipsis max-w-36"
              title={v.video_id}>{v.video_id}</span
            >
            {#if v.indexed_at}<span class="text-muted text-[0.85rem]"
                >{formatDate(v.indexed_at)}</span
              >{/if}
            {#if v.chunk_count !== undefined}<span class="tag"
                >{v.chunk_count} chunks</span
              >{/if}
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div>
