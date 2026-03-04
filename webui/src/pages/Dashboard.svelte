<script>
  import { onMount } from "svelte";
  import { stats, health, queueList, listVideos } from "../lib/api.js";

  let statsData = null;
  let healthData = null;
  let queueData = null;
  let videosData = null;
  let loading = true;
  let error = null;

  onMount(async () => {
    try {
      [statsData, healthData, queueData, videosData] = await Promise.all([
        stats(),
        health(),
        queueList(),
        listVideos(),
      ]);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  /** @type {{ pending: number, running: number, completed: number, failed: number, timeout: number }} */
  $: queueBreakdown = (() => {
    const counts = {
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0,
      timeout: 0,
    };
    if (!queueData?.tasks) return counts;
    for (const t of queueData.tasks) {
      if (t.status in counts) counts[t.status]++;
    }
    return counts;
  })();

  $: videoCount = videosData?.count ?? statsData?.videos_indexed ?? 0;
  $: totalTasks = queueData?.tasks?.length ?? 0;

  function badgeClass(status) {
    return `badge badge-${status}`;
  }
</script>

<div class="page">
  <div class="page-header">
    <h2>Dashboard</h2>
    <p class="desc">System health, usage metrics, and storage overview.</p>
  </div>

  {#if loading}
    <p><span class="spinner"></span> Loading…</p>
  {:else if error}
    <div class="error-box">{error}</div>
  {:else}
    <!-- KPI row -->
    <div class="kpi-grid">
      <div class="card kpi">
        <span class="kpi-label">Status</span>
        <span
          class="kpi-value"
          class:online={healthData?.status === "ok"}
          class:offline={healthData?.status !== "ok"}
        >
          {healthData?.status === "ok" ? "Online" : "Offline"}
        </span>
      </div>
      <div class="card kpi">
        <span class="kpi-label">Videos</span>
        <span class="kpi-value num">{videoCount}</span>
      </div>
      <div class="card kpi">
        <span class="kpi-label">Total Tasks</span>
        <span class="kpi-value num">{totalTasks}</span>
      </div>
      <div class="card kpi">
        <span class="kpi-label">Active</span>
        <span class="kpi-value num accent"
          >{(queueBreakdown.pending ?? 0) + (queueBreakdown.running ?? 0)}</span
        >
      </div>
    </div>

    <!-- Queue breakdown -->
    <div class="card section">
      <h3>Queue by Status</h3>
      {#if totalTasks === 0}
        <p class="muted">No tasks in queue.</p>
      {:else}
        <div class="queue-bars">
          {#each [["pending", "Pending"], ["running", "Running"], ["completed", "Completed"], ["failed", "Failed"], ["timeout", "Timeout"]] as [key, label]}
            {@const count = queueBreakdown[key] ?? 0}
            {#if count > 0}
              <div class="bar-row">
                <span class={badgeClass(key)}>{label}</span>
                <div class="bar-track">
                  <div
                    class="bar-fill bar-{key}"
                    style="width:{Math.max((count / totalTasks) * 100, 4)}%"
                  ></div>
                </div>
                <span class="bar-count">{count}</span>
              </div>
            {/if}
          {/each}
        </div>
      {/if}
    </div>

    <!-- Videos list preview -->
    {#if videosData?.videos?.length}
      <div class="card section">
        <div class="section-header">
          <h3>Indexed Videos</h3>
          <a href="#/videos" class="link-sm">View all →</a>
        </div>
        <div class="video-list">
          {#each videosData.videos.slice(0, 8) as v}
            <a href={`#/videos/${v.video_id}`} class="video-row">
              <code class="vid-id">{v.video_id}</code>
              <span class="vid-date muted"
                >{v.indexed_at
                  ? new Date(v.indexed_at).toLocaleDateString()
                  : "—"}</span
              >
            </a>
          {/each}
          {#if videosData.videos.length > 8}
            <p class="muted" style="margin:0.5rem 0 0;font-size:0.8rem;">
              +{videosData.videos.length - 8} more
            </p>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Storage & Index details -->
    <div class="card section">
      <h3>Storage</h3>
      <div class="meta-grid">
        <div class="meta-row">
          <span class="key">Video index</span>
          <code>{statsData?.video_col_path ?? "—"}</code>
        </div>
        <div class="meta-row">
          <span class="key">Chat store</span>
          <code>{statsData?.chat_col_path ?? "—"}</code>
        </div>
      </div>
    </div>

    <div class="two-col">
      <div class="card section">
        <h3>Index Stats</h3>
        {#if statsData?.video_index_stats}
          <pre>{statsData.video_index_stats}</pre>
        {:else}
          <p class="muted">No index stats available.</p>
        {/if}
      </div>
      <div class="card section">
        <h3>Chat Stats</h3>
        {#if statsData?.chat_index_stats}
          <pre>{statsData.chat_index_stats}</pre>
        {:else}
          <p class="muted">No chat stats available.</p>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .page {
    padding: 2rem;
    max-width: 900px;
  }
  .page-header {
    margin-bottom: 1.5rem;
  }
  .page-header h2 {
    font-size: 1.5rem;
    margin-bottom: 0.25rem;
  }
  .desc {
    color: var(--text-muted);
    margin: 0;
    font-size: 0.9rem;
  }
  .muted {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  /* KPI grid */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin-bottom: 1rem;
  }
  .kpi {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 1rem 1.25rem;
  }
  .kpi-label {
    font-size: 0.72rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  .kpi-value {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1;
  }
  .kpi-value.num {
    color: var(--primary);
    font-family: var(--font-mono);
  }
  .kpi-value.accent {
    color: var(--warning);
  }
  .kpi-value.online {
    color: var(--success);
  }
  .kpi-value.offline {
    color: var(--danger);
  }

  /* Sections */
  .section {
    margin-bottom: 1rem;
  }
  .section h3 {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: 0.75rem;
  }
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }
  .section-header h3 {
    margin-bottom: 0;
  }
  .link-sm {
    font-size: 0.8rem;
    font-weight: 600;
  }

  /* Queue breakdown bars */
  .queue-bars {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .bar-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .bar-track {
    flex: 1;
    height: 6px;
    background: var(--bg3);
    border-radius: 1px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    border-radius: 1px;
    transition: width 0.3s;
  }
  .bar-pending {
    background: #6b7280;
  }
  .bar-running {
    background: var(--info);
  }
  .bar-completed {
    background: var(--success);
  }
  .bar-failed {
    background: var(--danger);
  }
  .bar-timeout {
    background: var(--warning);
  }
  .bar-count {
    font-size: 0.8rem;
    font-family: var(--font-mono);
    color: var(--text-muted);
    min-width: 2ch;
    text-align: right;
  }

  /* Video list */
  .video-list {
    display: flex;
    flex-direction: column;
  }
  .video-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.45rem 0;
    border-bottom: 1px solid var(--border);
    color: var(--text);
    font-size: 0.85rem;
  }
  .video-row:last-child {
    border-bottom: none;
  }
  .video-row:hover {
    color: var(--primary);
  }
  .vid-id {
    font-size: 0.8rem;
    background: var(--bg3);
    padding: 0.1em 0.4em;
    border-radius: var(--radius);
    word-break: break-all;
  }
  .vid-date {
    font-size: 0.78rem;
  }

  /* Storage */
  .meta-grid {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .meta-row {
    display: flex;
    gap: 1rem;
    font-size: 0.85rem;
    align-items: flex-start;
  }
  .key {
    color: var(--text-muted);
    min-width: 100px;
    flex-shrink: 0;
  }
  code {
    font-size: 0.78rem;
    font-family: var(--font-mono);
    background: var(--bg3);
    padding: 0.15em 0.4em;
    border-radius: var(--radius);
    word-break: break-all;
  }

  /* Two-col stats */
  .two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .two-col pre {
    font-size: 0.75rem;
    margin: 0;
  }

  @media (max-width: 700px) {
    .kpi-grid {
      grid-template-columns: repeat(2, 1fr);
    }
    .two-col {
      grid-template-columns: 1fr;
    }
  }
</style>
