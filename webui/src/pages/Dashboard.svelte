<script>
  import { onMount } from "svelte";
  import { stats, health, queueList, listVideos } from "../lib/api.js";
  import { LayoutDashboardIcon } from "lucide-svelte";

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

<div class="p-8 max-w-[900px]">
  <div class="mb-6">
    <h2 class="text-[1.5rem] mb-1 flex items-center gap-1.5">
      <LayoutDashboardIcon
        size={20}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      />
      Dashboard
    </h2>
    <p class="text-muted text-[0.9rem] mb-0">
      System health, usage metrics, and storage overview.
    </p>
  </div>

  {#if loading}
    <p><span class="spinner"></span> Loading…</p>
  {:else if error}
    <div class="error-box">{error}</div>
  {:else}
    <!-- KPI row -->
    <div class="grid grid-cols-4 gap-3 mb-4 max-sm:grid-cols-2">
      <div class="card flex flex-col gap-[0.35rem] px-5 py-4">
        <span
          class="text-[0.72rem] text-muted uppercase tracking-[0.06em] font-semibold"
          >Status</span
        >
        <span
          class={`text-[1.5rem] font-bold leading-none ${healthData?.status === "ok" ? "text-success" : "text-danger"}`}
        >
          {healthData?.status === "ok" ? "Online" : "Offline"}
        </span>
      </div>
      <div class="card flex flex-col gap-[0.35rem] px-5 py-4">
        <span
          class="text-[0.72rem] text-muted uppercase tracking-[0.06em] font-semibold"
          >Videos</span
        >
        <span class="text-[1.5rem] font-bold leading-none text-cobalt font-mono"
          >{videoCount}</span
        >
      </div>
      <div class="card flex flex-col gap-[0.35rem] px-5 py-4">
        <span
          class="text-[0.72rem] text-muted uppercase tracking-[0.06em] font-semibold"
          >Total Tasks</span
        >
        <span class="text-[1.5rem] font-bold leading-none text-cobalt font-mono"
          >{totalTasks}</span
        >
      </div>
      <div class="card flex flex-col gap-[0.35rem] px-5 py-4">
        <span
          class="text-[0.72rem] text-muted uppercase tracking-[0.06em] font-semibold"
          >Active</span
        >
        <span
          class="text-[1.5rem] font-bold leading-none text-warning font-mono"
          >{(queueBreakdown.pending ?? 0) + (queueBreakdown.running ?? 0)}</span
        >
      </div>
    </div>

    <!-- Queue breakdown -->
    <div class="card mb-4">
      <h3 class="text-[0.85rem] uppercase tracking-[0.05em] text-muted mb-3">
        Queue by Status
      </h3>
      {#if totalTasks === 0}
        <p class="text-muted text-[0.85rem]">No tasks in queue.</p>
      {:else}
        <div class="flex flex-col gap-2">
          {#each [["pending", "Pending"], ["running", "Running"], ["completed", "Completed"], ["failed", "Failed"], ["timeout", "Timeout"]] as [key, label]}
            {@const count = queueBreakdown[key] ?? 0}
            {#if count > 0}
              <div class="flex items-center gap-3">
                <span class={badgeClass(key)}>{label}</span>
                <div class="flex-1 h-1.5 bg-surface-alt overflow-hidden">
                  <div
                    class={`h-full transition-[width] duration-300 ${
                      key === "pending"
                        ? "bg-[#6b7280]"
                        : key === "running"
                          ? "bg-cobalt"
                          : key === "completed"
                            ? "bg-success"
                            : key === "failed"
                              ? "bg-danger"
                              : "bg-warning"
                    }`}
                    style="width:{Math.max((count / totalTasks) * 100, 4)}%"
                  ></div>
                </div>
                <span
                  class="text-[0.8rem] font-mono text-muted min-w-[2ch] text-right"
                  >{count}</span
                >
              </div>
            {/if}
          {/each}
        </div>
      {/if}
    </div>

    <!-- Videos list preview -->
    {#if videosData?.videos?.length}
      <div class="card mb-4">
        <div class="flex justify-between items-center mb-3">
          <h3
            class="text-[0.85rem] uppercase tracking-[0.05em] text-muted mb-0"
          >
            Indexed Videos
          </h3>
          <a href="#/videos" class="text-[0.8rem] font-semibold">View all →</a>
        </div>
        <div class="flex flex-col">
          {#each videosData.videos.slice(0, 8) as v}
            <a
              href={`#/videos/${v.video_id}`}
              class="flex justify-between items-center py-[0.45rem] border-b border-line text-ink text-[0.85rem] hover:text-cobalt last:border-b-0"
            >
              <code
                class="text-[0.8rem] bg-surface-alt px-[0.4em] py-[0.1em] font-mono break-all"
                >{v.video_id}</code
              >
              <span class="text-muted text-[0.78rem]"
                >{v.indexed_at
                  ? new Date(v.indexed_at).toLocaleDateString()
                  : "—"}</span
              >
            </a>
          {/each}
          {#if videosData.videos.length > 8}
            <p class="text-muted mt-2 mb-0 text-[0.8rem]">
              +{videosData.videos.length - 8} more
            </p>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Storage & Index details -->
    <div class="card mb-4">
      <h3 class="text-[0.85rem] uppercase tracking-[0.05em] text-muted mb-3">
        Storage
      </h3>
      <div class="flex flex-col gap-2">
        <div class="flex gap-4 text-[0.85rem] items-start">
          <span class="text-muted min-w-24 shrink-0">Video index</span>
          <code
            class="text-[0.78rem] font-mono bg-surface-alt px-[0.4em] py-[0.15em] break-all"
            >{statsData?.video_col_path ?? "—"}</code
          >
        </div>
        <div class="flex gap-4 text-[0.85rem] items-start">
          <span class="text-muted min-w-24 shrink-0">Chat store</span>
          <code
            class="text-[0.78rem] font-mono bg-surface-alt px-[0.4em] py-[0.15em] break-all"
            >{statsData?.chat_col_path ?? "—"}</code
          >
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
      <div class="card">
        <h3 class="text-[0.85rem] uppercase tracking-[0.05em] text-muted mb-3">
          Index Stats
        </h3>
        {#if statsData?.video_index_stats}
          <pre class="m-0 text-[0.75rem]">{statsData.video_index_stats}</pre>
        {:else}
          <p class="text-muted text-[0.85rem] mb-0">
            No index stats available.
          </p>
        {/if}
      </div>
      <div class="card">
        <h3 class="text-[0.85rem] uppercase tracking-[0.05em] text-muted mb-3">
          Chat Stats
        </h3>
        {#if statsData?.chat_index_stats}
          <pre class="m-0 text-[0.75rem]">{statsData.chat_index_stats}</pre>
        {:else}
          <p class="text-muted text-[0.85rem] mb-0">No chat stats available.</p>
        {/if}
      </div>
    </div>
  {/if}
</div>
