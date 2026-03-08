<script module>
  export const POLL_INTERVAL = 3000;
</script>

<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { ClipboardListIcon, LoaderCircleIcon } from "lucide-svelte";
  import type { Task } from "../lib/types";
  import { toPath } from "../lib/routing";
  import { onMount } from "svelte";
  import { queueStatus } from "../lib/api";
  import { toast } from "svelte-sonner";

  let { taskId, loading }: { taskId: string; loading: boolean } = $props();

  let task = $state<Task | null>(null);

  function badgeClass(status: Task["status"]) {
    return `badge badge-${status ?? "pending"}`;
  }

  function formatDate(iso: string | undefined) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }

  async function fetchTaskStatus() {
    return queueStatus(taskId)
      .then((d) => (task = d))
      .catch((e) =>
        toast.error(`Error getting queue status for taskId: ${taskId}`, {
          description: e.message,
        }),
      );
  }

  onMount(() => {
    fetchTaskStatus();

    const pollInterval = setInterval(async () => {
      const hasActive =
        task && (task.status === "pending" || task.status === "running");
      if (hasActive) await fetchTaskStatus();
    }, POLL_INTERVAL);

    return () => {
      clearInterval(pollInterval);
    };
  });
</script>

<!-- Single task view -->
<div class="mb-4 text-[0.85rem]">
  <a href={toPath("/queue")} use:route>← All Tasks</a>
</div>
<h2>
  <ClipboardListIcon
    size={20}
    strokeWidth={2}
    style="display:inline;vertical-align:middle;"
  /> Task Detail
</h2>
{#if loading}
  <p class="flex items-center gap-x-2">
    <LoaderCircleIcon
      class="w-5 h-5 animate-spin"
      style="animation-duration: 0.3s"
    />
    Loading…
  </p>
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
        <span class="text-muted min-w-24">Command</span><span class="text-ink"
          >{task.command}</span
        >
      </div>
      {#if task.run_type}
        <div class="flex gap-4 text-[0.88rem]">
          <span class="text-muted min-w-24">Run type</span><span class="text-ink"
            >{task.run_type}</span
          >
        </div>
      {/if}
      <div class="flex gap-4 text-[0.88rem]">
        <span class="text-muted min-w-24">Label</span><span class="text-ink"
          >{task.label}</span
        >
      </div>
      <div class="flex gap-4 text-[0.88rem]">
        <span class="text-muted min-w-24">Created</span><span class="text-ink"
          >{formatDate(task.created_at)}</span
        >
      </div>
      <div class="flex gap-4 text-[0.88rem]">
        <span class="text-muted min-w-24">Started</span><span class="text-ink"
          >{formatDate(task.started_at)}</span
        >
      </div>
      <div class="flex gap-4 text-[0.88rem]">
        <span class="text-muted min-w-24">Finished</span><span class="text-ink"
          >{formatDate(task.finished_at)}</span
        >
      </div>
      {#if task.duration}<div class="flex gap-4 text-[0.88rem]">
          <span class="text-muted min-w-24">Duration</span><span
            class="text-ink">{task.duration}</span
          >
        </div>{/if}
    </div>

    {#if task.output_path}
      <div class="success-box mt-4">
        Output: <code class="font-mono text-[0.78rem]">{task.output_path}</code>
        {#if task.requested_output_path}
          <div class="mt-2">
            Also written to:
            <code class="font-mono text-[0.78rem]">{task.requested_output_path}</code>
          </div>
        {/if}
        {#if task.benchmark_path}
          <div class="mt-2">
            Benchmark:
            <code class="font-mono text-[0.78rem]">{task.benchmark_path}</code>
          </div>
        {/if}
      </div>
    {/if}

    {#if task.result}
      <details class="card mt-4">
        <summary class="cursor-pointer text-[0.88rem] text-muted">
          Persisted result
        </summary>
        <pre class="max-h-96 overflow-y-auto m-0 mt-3 text-sm">{typeof task.result ===
        "string"
          ? task.result
          : JSON.stringify(task.result, null, 2)}</pre>
      </details>
    {/if}

    {#if task.benchmark_text}
      <details class="card mt-4">
        <summary class="cursor-pointer text-[0.88rem] text-muted">
          Benchmark summary
        </summary>
        <pre class="max-h-80 overflow-y-auto m-0 mt-3 text-sm">{task.benchmark_text}</pre>
      </details>
    {/if}

    {#if task.status === "pending" || task.status === "running"}
      <p class="text-muted flex items-center gap-x-2 text-[0.85rem] mt-4">
        <LoaderCircleIcon
          class="w-5 h-5 animate-spin"
          style="animation-duration: 0.3s"
        />
        Refreshing every 5s…
      </p>
    {/if}
  </div>
{/if}
