<script>
  import { ClipboardListIcon } from "lucide-svelte";
  import { onMount, onDestroy } from "svelte";
  import { queueList, queueStatus } from "../lib/api.js";

  export let params = {};
  const taskId = params.id ?? null;

  let tasks = [];
  let task = null;
  let loading = true;
  let error = null;
  let statusFilter = null;
  let pollInterval = null;

  const statusOptions = [
    null,
    "pending",
    "running",
    "completed",
    "failed",
    "timeout",
  ];

  async function load() {
    try {
      if (taskId) {
        task = await queueStatus(taskId);
      } else {
        const data = await queueList(statusFilter);
        tasks = data.tasks ?? [];
      }
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    await load();
    // Auto-refresh when there are active tasks
    pollInterval = setInterval(async () => {
      const hasActive =
        tasks.some((t) => t.status === "pending" || t.status === "running") ||
        (task && (task.status === "pending" || task.status === "running"));
      if (hasActive) await load();
    }, 5000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  function badgeClass(status) {
    return `badge badge-${status ?? "pending"}`;
  }

  function formatDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }
</script>

<div class="p-8 max-w-[860px]">
  {#if taskId}
    <!-- Single task view -->
    <div class="mb-4 text-[0.85rem]"><a href="#/queue">← All Tasks</a></div>
    <h2>
      <ClipboardListIcon
        size={20}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Task Detail
    </h2>
    {#if loading}
      <p><span class="spinner"></span> Loading…</p>
    {:else if error}
      <div class="error-box">{error}</div>
    {:else if task}
      <div class="card">
        <div class="flex items-center gap-3 mb-4">
          <span
            class={`w-2 h-2 rounded-full ${
              task.status === "running"
                ? "bg-cobalt shadow-[0_0_0_3px_rgba(59,130,246,0.3)] animate-pulse"
                : "bg-muted"
            }`}
          ></span>
          <code class="text-[0.82rem]">{task.id}</code>
          <span class={badgeClass(task.status)}>{task.status}</span>
        </div>
        <div class="flex flex-col gap-[0.4rem]">
          <div class="flex gap-4 text-[0.88rem]">
            <span class="text-muted min-w-[100px]">Command</span><span
              class="text-ink">{task.command}</span
            >
          </div>
          <div class="flex gap-4 text-[0.88rem]">
            <span class="text-muted min-w-[100px]">Label</span><span
              class="text-ink">{task.label}</span
            >
          </div>
          <div class="flex gap-4 text-[0.88rem]">
            <span class="text-muted min-w-[100px]">Created</span><span
              class="text-ink">{formatDate(task.created_at)}</span
            >
          </div>
          <div class="flex gap-4 text-[0.88rem]">
            <span class="text-muted min-w-[100px]">Started</span><span
              class="text-ink">{formatDate(task.started_at)}</span
            >
          </div>
          <div class="flex gap-4 text-[0.88rem]">
            <span class="text-muted min-w-[100px]">Finished</span><span
              class="text-ink">{formatDate(task.finished_at)}</span
            >
          </div>
          {#if task.duration}<div class="flex gap-4 text-[0.88rem]">
              <span class="text-muted min-w-[100px]">Duration</span><span
                class="text-ink">{task.duration}</span
              >
            </div>{/if}
        </div>
        {#if task.error}
          <div class="error-box mt-4">{task.error}</div>
        {/if}
        {#if task.output_path}
          <div class="success-box mt-4">
            Output: <code class="font-mono text-[0.78rem]"
              >{task.output_path}</code
            >
          </div>
        {/if}
        {#if task.status === "pending" || task.status === "running"}
          <p class="text-muted text-[0.85rem] mt-4">
            <span class="spinner"></span> Refreshing every 5s…
          </p>
        {/if}
      </div>
    {/if}
  {:else}
    <!-- Task list view -->
    <h2 class="flex items-center gap-1.5">
      <ClipboardListIcon
        size={20}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Task Queue
    </h2>
    <p class="text-muted mb-5">Monitor and inspect background tasks.</p>

    <div class="flex flex-wrap gap-[0.4rem] mb-5">
      {#each statusOptions as s}
        <button
          class={statusFilter === s ? "btn-primary" : "btn-secondary"}
          on:click={() => {
            statusFilter = s;
            load();
          }}
        >
          {s ?? "All"}
        </button>
      {/each}
      <button class="btn-secondary" on:click={load} title="Refresh"
        >↻ Refresh</button
      >
    </div>

    {#if loading}
      <p><span class="spinner"></span> Loading…</p>
    {:else if error}
      <div class="error-box">{error}</div>
    {:else if tasks.length === 0}
      <div class="card text-center py-8"><p>No tasks found.</p></div>
    {:else}
      <div class="flex flex-col gap-2">
        {#each tasks as t}
          <a
            href={`#/queue/${t.id}`}
            class="card flex flex-col gap-[0.3rem] text-ink transition-[border-color] duration-[0.15s] hover:border-cobalt"
          >
            <div class="flex items-center gap-2">
              <span class={badgeClass(t.status)}>{t.status}</span>
              <span class="tag text-[0.78rem]">{t.command}</span>
              <span class="text-[0.88rem] flex-1">{t.label}</span>
            </div>
            <div class="flex gap-4 items-center">
              <code class="text-[0.75rem] font-mono text-muted">{t.id}</code>
              <span class="text-muted text-[0.85rem]"
                >{formatDate(t.created_at)}</span
              >
            </div>
          </a>
        {/each}
      </div>
    {/if}
  {/if}
</div>
