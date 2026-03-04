<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { search } from "../lib/api.ts";
  import type { SearchResult } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";

  let query: string = "";
  let videoId: string = "";
  let topK: number = 10;
  let loading: boolean = false;
  let results: SearchResult[] | null = null;
  let count: number = 0;
  let error: string | null = null;

  async function doSearch(): Promise<void> {
    if (!query.trim()) return;
    loading = true;
    error = null;
    results = null;
    try {
      const data = await search(query.trim(), videoId.trim() || null, topK);
      results = data.results ?? [];
      count = data.count ?? results.length;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  function clear(): void {
    results = null;
    query = "";
    videoId = "";
    error = null;
  }

  function handleSubmit(e: SubmitEvent): void {
    e.preventDefault();
    void doSearch();
  }
</script>

<div class="page">
  <h2>🔎 Search</h2>
  <p class="desc">
    Run natural-language semantic queries against all indexed videos, or narrow
    to a specific video.
  </p>

  <form class="search-form card" onsubmit={handleSubmit}>
    <div class="form-row">
      <input
        class="query-input"
        bind:value={query}
        placeholder="e.g. people discussing climate change"
        required
        aria-label="Search query"
      />
      <input
        bind:value={videoId}
        placeholder="Video ID (optional)"
        aria-label="Video ID filter"
      />
      <div class="topk-group">
        <label for="topk">Top K</label>
        <input id="topk" type="number" min="1" max="100" bind:value={topK} />
      </div>
    </div>
    <div class="btn-row">
      <button
        type="submit"
        class="btn-primary"
        disabled={loading || !query.trim()}
      >
        {#if loading}<span class="spinner"></span>{/if}
        Search
      </button>
      {#if results !== null || error}
        <button type="button" class="btn-secondary" onclick={clear}
          >Clear</button
        >
      {/if}
    </div>
  </form>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}

  {#if results !== null}
    <div class="results-section">
      <h3>
        {count} result{count !== 1 ? "s" : ""}{videoId
          ? ` in video ${videoId}`
          : ""}
      </h3>
      {#if results.length === 0}
        <div class="empty card">
          No matching results found. Try a different query.
        </div>
      {:else}
        <div class="results-list">
          {#each results as r, i}
            <div class="result-card card">
              <div class="result-header">
                <span class="result-num">#{i + 1}</span>
                <a
                  href={toPath(`/videos/${r.video_id}`)}
                  use:route
                  class="vid-link">{r.video_id}</a
                >
                {#if r.score !== undefined}
                  <span class="score">score: {r.score.toFixed(4)}</span>
                {/if}
              </div>
              {#if r.description}<p class="excerpt">{r.description}</p>{/if}
              {#if r.transcript}<p class="transcript muted">
                  {r.transcript}
                </p>{/if}
              {#if r.start_time !== undefined && r.end_time !== undefined}
                <div class="timestamp muted">
                  ⏱ {r.start_time}s – {r.end_time}s
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .page {
    padding: 2rem;
    max-width: 900px;
  }
  .desc {
    color: var(--text-muted);
    margin-bottom: 1.5rem;
  }
  .search-form {
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .form-row {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .query-input {
    flex: 2;
    min-width: 200px;
  }
  .form-row input:not(.query-input) {
    flex: 1;
    min-width: 140px;
  }
  .topk-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .topk-group label {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
  }
  .topk-group input {
    width: 80px;
  }
  .btn-row {
    display: flex;
    gap: 0.5rem;
  }
  .results-section {
    margin-top: 1.5rem;
  }
  h3 {
    margin-bottom: 0.75rem;
    font-size: 1rem;
    color: var(--text-muted);
    font-weight: 600;
  }
  .results-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .result-card {
    padding: 1rem 1.25rem;
  }
  .result-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }
  .result-num {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 700;
  }
  .vid-link {
    font-family: monospace;
    font-size: 0.85rem;
    color: var(--primary);
  }
  .score {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-left: auto;
  }
  .excerpt {
    font-size: 0.9rem;
    margin: 0.25rem 0 0;
  }
  .transcript {
    font-size: 0.85rem;
    margin-top: 0.25rem;
    font-style: italic;
  }
  .timestamp {
    font-size: 0.8rem;
    margin-top: 0.4rem;
  }
  .muted {
    color: var(--text-muted);
  }
  .empty {
    padding: 1.5rem;
    text-align: center;
    color: var(--text-muted);
  }
  .error-box {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--danger);
    border-radius: var(--radius);
    color: var(--danger);
  }
</style>
