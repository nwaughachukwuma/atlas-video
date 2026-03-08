<script lang="ts">
  import { route, type RouteResult } from "@mateothegreat/svelte5-router";
  import { ClipboardListIcon, LoaderCircleIcon } from "lucide-svelte";
  import { onMount } from "svelte";
  import { queueList } from "../lib/api.ts";
  import type { Task, TaskStatus } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";
  import QueueTaskId, { POLL_INTERVAL } from "./QueueTaskId.svelte";

  let { route: routeResult }: { route: RouteResult } = $props();
  const taskId: string | null = $derived.by(
    () =>
      // @ts-expect-error
      routeResult.result.path.params?.id ??
      routeResult.result.path.original.match(/^\/queue\/([^/]+)$/)?.[1] ??
      null,
  );

  let tasks = $state<Task[]>([]);
  let loading = $state(false);
  let statusFilter = $state<TaskStatus | null>(null);
  let commandFilter = $state<string | null>(null);
  let runTypeFilter = $state<"queued" | "direct" | null>(null);

  const statusOptions: (TaskStatus | null)[] = [
    null,
    "pending",
    "running",
    "completed",
    "failed",
    "timeout",
  ];
  const commandOptions: (string | null)[] = [
    null,
    "transcribe",
    "extract",
    "index",
  ];
  const runTypeOptions: (("queued" | "direct") | null)[] = [
    null,
    "queued",
    "direct",
  ];

  async function fetchTasks() {
    if (loading) return;

    loading = true;
    return queueList(statusFilter, commandFilter, runTypeFilter)
      .then((d) => (tasks = d.tasks))
      .catch((e) =>
        toast.error("Error while fetching Queue data", {
          description: e.message,
        }),
      )
      .finally(() => (loading = false));
  }

  onMount(() => {
    fetchTasks();

    const pollInterval = setInterval(async () => {
      const hasActive = tasks.some(
        (t) => t.status === "pending" || t.status === "running",
      );
      if (hasActive) await fetchTasks();
    }, POLL_INTERVAL);

    return () => {
      clearInterval(pollInterval);
    };
  });

  function badgeClass(status: string) {
    return `badge badge-${status ?? "pending"}`;
  }

  function formatDate(iso: string | undefined) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }
</script>

<div class="p-8 max-w-[860px]">
  {#if taskId}
    <!-- Single task view -->
    <QueueTaskId {taskId} {loading} />
  {:else}
    <!-- Task list view -->
      <h2 class="flex items-center gap-1.5">
        <ClipboardListIcon
          size={20}
          strokeWidth={2}
          style="display:inline;vertical-align:middle;"
        /> Run History
      </h2>
      <p class="text-muted mb-5">
        Monitor queued work and inspect persisted direct-run results.
      </p>

      <div class="flex flex-wrap gap-[0.4rem] mb-3">
        {#each statusOptions as s}
          <button
            class={statusFilter === s ? "btn-primary" : "btn-secondary"}
          onclick={() => {
            statusFilter = s;
            fetchTasks();
          }}
          >
            {s ?? "All"}
          </button>
        {/each}
      </div>

      <div class="flex flex-wrap gap-[0.4rem] mb-3">
        {#each commandOptions as c}
          <button
            class={commandFilter === c ? "btn-primary" : "btn-secondary"}
            onclick={() => {
              commandFilter = c;
              fetchTasks();
            }}
          >
            {c ?? "All commands"}
          </button>
        {/each}
      </div>

      <div class="flex flex-wrap gap-[0.4rem] mb-5">
        {#each runTypeOptions as mode}
          <button
            class={runTypeFilter === mode ? "btn-primary" : "btn-secondary"}
            onclick={() => {
              runTypeFilter = mode;
              fetchTasks();
            }}
          >
            {mode ?? "All runs"}
          </button>
        {/each}
        <button class="btn-secondary" onclick={fetchTasks} title="Refresh"
        >↻ Refresh</button
        >
      </div>

    {#if loading}
      <p class="flex gap-x-2 items-center">
        <LoaderCircleIcon
          class="w-5 h-5 animate-spin"
          style="animation-duration: 0.3s"
        />
        Loading…
      </p>
    {:else if tasks.length === 0}
      <div class="card text-center py-8"><p>No tasks found.</p></div>
    {:else}
      <div class="flex flex-col gap-2">
        {#each tasks as t}
          <a
            href={toPath(`/queue/${t.id}`)}
            use:route
            class="card flex flex-col gap-[0.3rem] text-ink transition-[border-color] duration-150 hover:border-cobalt"
          >
            <div class="flex items-center gap-2">
              <span class={badgeClass(t.status)}>{t.status}</span>
              {#if t.run_type}
                <span class="tag text-[0.78rem]">{t.run_type}</span>
              {/if}
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
