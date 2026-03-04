<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { FilmIcon } from "lucide-svelte";
  import { onMount } from "svelte";
  import { listVideos, search } from "../lib/api.ts";
  import type { Video, SearchResult } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";

  let videos: Video[] = [];
  let loading: boolean = true;
  let error: string | null = null;
  let searchQuery: string = "";
  let searchResults: SearchResult[] | null = null;
  let searching: boolean = false;

  onMount(async () => {
    try {
      const data = await listVideos();
      videos = data.videos ?? [];
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  });

  async function doSearch(): Promise<void> {
    if (!searchQuery.trim()) {
      searchResults = null;
      return;
    }
    searching = true;
    try {
      const data = await search(searchQuery.trim(), null, 20);
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

  <div class="flex gap-2 mb-6">
    <input
      type="search"
      bind:value={searchQuery}
      placeholder="Search across all videos…"
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

  {#if error}<div class="error-box">{error}</div>{/if}

  {#if searchResults !== null}
    <section>
      <h3 class="mb-3">
        Search results <span class="text-muted text-[0.85rem]"
          >({searchResults.length})</span
        >
      </h3>
      {#if searchResults.length === 0}
        <p class="text-muted text-[0.85rem]">No results found.</p>
      {:else}
        {#each searchResults as r}
          <div class="card mb-3">
            <div class="flex justify-between mb-[0.4rem]">
              <a
                href={toPath(`/videos/${r.video_id}`)}
                use:route
                class="font-mono text-[0.85rem] text-cobalt">{r.video_id}</a
              >
              <span class="text-[0.78rem] text-muted"
                >score: {r.score?.toFixed(3) ?? "—"}</span
              >
            </div>
            {#if r.description}<p class="text-[0.85rem] text-muted mt-1 mb-0">
                {r.description}
              </p>{/if}
            {#if r.transcript}<p class="text-[0.85rem] text-muted mt-1 mb-0">
                {r.transcript}
              </p>{/if}
          </div>
        {/each}
      {/if}
    </section>
  {:else if loading}
    <p><span class="spinner"></span> Loading videos…</p>
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
          href={toPath(`/videos/${v.video_id}`)}
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
