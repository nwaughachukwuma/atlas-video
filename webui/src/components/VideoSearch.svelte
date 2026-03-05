<script lang="ts" module>
  type Props = {
    videoId?: string | null;
    disabled?: boolean;
    placeholder?: string;
  };
</script>

<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { LoaderCircleIcon, SearchIcon, XIcon } from "lucide-svelte";
  import { search } from "../lib/api.ts";
  import type { SearchResult } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";

  let { videoId = null, disabled, placeholder }: Props = $props();

  let query = $state("");
  let results = $state<SearchResult[] | null>(null);
  let searching = $state(false);

  const isScoped = $derived(!!videoId);
  const _placeholder = $derived.by(() =>
    placeholder
      ? placeholder
      : isScoped
        ? "Search within this video..."
        : "Search across all video...",
  );
  const topK = $derived(isScoped ? 10 : 20);

  async function doSearch(): Promise<void> {
    if (searching || !query.trim()) {
      results = null;
      return;
    }
    searching = true;
    search(query.trim(), videoId ?? null, topK)
      .then((d) => (results = d.results))
      .catch((e) => toast.error("Search failed", { description: e.message }))
      .finally(() => (searching = false));
  }

  function clear(): void {
    query = "";
    results = null;
  }

  function handleKey(e: KeyboardEvent): void {
    if (e.key === "Enter") doSearch();
  }
</script>

<div>
  <!-- Search bar -->
  <div class="flex gap-2 mb-5">
    <input
      type="search"
      bind:value={query}
      placeholder={_placeholder}
      class="flex-1"
      onkeydown={handleKey}
      {disabled}
    />
    <button
      class="btn-primary flex items-center gap-x-2"
      onclick={doSearch}
      disabled={searching || !query.trim()}
    >
      {#if searching}
        <LoaderCircleIcon
          class="w-4 h-4 animate-spin"
          style="animation-duration: 0.3s"
        />
      {:else}
        <SearchIcon size={15} strokeWidth={2} />
        Search
      {/if}
    </button>
    {#if results !== null}
      <button class="btn-secondary flex items-center gap-1" onclick={clear}>
        <XIcon size={14} strokeWidth={2} />
        Clear
      </button>
    {/if}
  </div>

  <!-- Results -->
  {#if results !== null}
    <section class="card">
      <h3 class="mb-3">
        Search results
        <span class="text-muted text-[0.85rem]">({results.length})</span>
      </h3>

      {#if results.length === 0}
        <p class="text-muted text-[0.85rem] mb-0">No results found.</p>
      {:else}
        {#each results as r}
          <div class="border-b border-line py-3 last:border-b-0">
            {#if !isScoped}
              <div class="flex justify-between mb-1">
                <a
                  href={toPath(`/video/${r.video_id}`)}
                  use:route
                  class="font-mono text-[0.85rem] text-cobalt"
                >
                  {r.video_id}
                </a>
                <span class="text-[0.78rem] text-muted">
                  score: {r.score?.toFixed(3) ?? "—"}
                </span>
              </div>
            {:else}
              <span class="text-[0.75rem] text-muted block mb-1">
                score: {r.score?.toFixed(3) ?? "—"}
              </span>
            {/if}

            {#if r.description}
              <p class="text-[0.88rem] mt-1 mb-0">{r.description}</p>
            {/if}
            {#if r.transcript}
              <p class="text-[0.85rem] text-muted mt-1 mb-0">{r.transcript}</p>
            {/if}
          </div>
        {/each}
      {/if}
    </section>
  {/if}
</div>
