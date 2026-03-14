<script module>
  export const POLL_INTERVAL = 3000;
</script>

<script lang="ts">
  import { route, type RouteResult } from "@mateothegreat/svelte5-router";
  import {
    FileTextIcon,
    GaugeIcon,
    HistoryIcon,
    LoaderCircleIcon,
  } from "lucide-svelte";
  import { onMount } from "svelte";
  import { runBenchmark, runDetail, runOutput, runsList } from "../lib/api.ts";
  import type {
    Run,
    RunBenchmarkResponse,
    RunMode,
    RunOutputResponse,
    TaskStatus,
  } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";

  let { route: routeResult }: { route: RouteResult } = $props();
  const originalPath = $derived(routeResult.result.path.original);
  const scopedCommand = $derived.by((): Run["command"] | "" => {
    if (originalPath.startsWith("/transcribe/runs")) return "transcribe";
    if (originalPath.startsWith("/extract/runs")) return "extract";
    return "";
  });
  const runsBasePath = $derived.by(() => {
    if (scopedCommand === "transcribe") return "/transcribe/runs";
    if (scopedCommand === "extract") return "/extract/runs";
    return "/runs";
  });
  const listHeading = $derived.by(() => {
    if (scopedCommand === "transcribe") return "Transcribe Runs";
    if (scopedCommand === "extract") return "Extract Runs";
    return "Runs";
  });
  const listDescription = $derived.by(() => {
    if (scopedCommand === "transcribe") {
      return "Persisted history for transcribe runs across queued and direct execution.";
    }
    if (scopedCommand === "extract") {
      return "Persisted history for extract runs across queued and direct execution.";
    }
    return "Persisted history for queued and direct transcribe, extract, and index runs.";
  });
  const detailHeading = $derived.by(() => {
    if (scopedCommand === "transcribe") return "Transcribe Run Detail";
    if (scopedCommand === "extract") return "Extract Run Detail";
    return "Run Detail";
  });
  const runId: string | null = $derived.by(
    () =>
      routeResult.result.path.params?.id ??
      originalPath.match(/^\/(?:transcribe|extract)\/runs\/([^/]+)$/)?.[1] ??
      originalPath.match(/^\/runs\/([^/]+)$/)?.[1] ??
      null,
  );

  let runs = $state<Run[]>([]);
  let loading = $state(false);
  let selectedStatus = $state("");
  let selectedCommand = $state("");
  let selectedMode = $state("");

  let currentRun = $state<Run | null>(null);
  let outputData = $state<RunOutputResponse | null>(null);
  let benchmarkData = $state<RunBenchmarkResponse | null>(null);

  const statusOptions: (TaskStatus | "")[] = [
    "",
    "pending",
    "running",
    "completed",
    "failed",
    "timeout",
  ];
  const commandOptions: (Run["command"] | "")[] = [
    "",
    "transcribe",
    "extract",
    "index",
  ];
  const modeOptions: (RunMode | "")[] = ["", "direct", "queued"];

  function setStatusFilter(status: TaskStatus | "") {
    selectedStatus = status;
    fetchRuns();
  }

  function setCommandFilter(command: Run["command"] | "") {
    selectedCommand = command;
    fetchRuns();
  }

  function setModeFilter(mode: RunMode | "") {
    selectedMode = mode;
    fetchRuns();
  }

  async function fetchRuns() {
    loading = true;
    return runsList(
      selectedStatus || null,
      scopedCommand || selectedCommand || null,
      (selectedMode || null) as RunMode | null,
      100,
    )
      .then((data) => {
        runs = data.runs;
      })
      .catch((e) =>
        toast.error("Error while fetching runs", {
          description: e.message,
        }),
      )
      .finally(() => (loading = false));
  }

  async function fetchRun() {
    if (!runId) return;
    loading = true;
    return runDetail(runId)
      .then(async (data) => {
        currentRun = data;
        outputData = null;
        benchmarkData = null;

        if (data.output_path) {
          outputData = await runOutput(runId).catch(() => null);
        }
        if (data.benchmark_path) {
          benchmarkData = await runBenchmark(runId).catch(() => null);
        }
      })
      .catch((e) =>
        toast.error(`Error getting run ${runId}`, {
          description: e.message,
        }),
      )
      .finally(() => (loading = false));
  }

  function badgeClass(status: string) {
    return `badge badge-${status ?? "pending"}`;
  }

  function formatDate(iso: string | undefined | null) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }

  onMount(() => {
    if (scopedCommand) {
      selectedCommand = scopedCommand;
    }
    if (runId) fetchRun();
    else fetchRuns();

    const interval = setInterval(async () => {
      if (runId) {
        const hasActive =
          currentRun &&
          (currentRun.status === "pending" || currentRun.status === "running");
        if (hasActive) await fetchRun();
      } else {
        const hasActive = runs.some(
          (run) => run.status === "pending" || run.status === "running",
        );
        if (hasActive) await fetchRuns();
      }
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  });
</script>

<div class="p-8 max-w-[920px]">
  {#if runId}
    <div class="mb-4 text-[0.85rem]">
      <a href={toPath(runsBasePath)} use:route>← All Runs</a>
    </div>

    <h2 class="flex items-center gap-1.5 mb-1">
      <HistoryIcon
        size={20}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      />
      {detailHeading}
    </h2>
    <p class="text-muted mb-5">Inspect persisted output and benchmark data.</p>

    {#if loading && !currentRun}
      <p class="flex items-center gap-x-2">
        <LoaderCircleIcon class="w-5 h-5 animate-spin" /> Loading…
      </p>
    {:else if currentRun}
      <div class="card mb-4">
        <div class="flex items-center gap-2 mb-4 flex-wrap">
          <code class="text-[0.8rem] font-mono">{currentRun.id}</code>
          <span class={badgeClass(currentRun.status)}>{currentRun.status}</span>
          <span class="tag text-[0.78rem]">{currentRun.command}</span>
          <span class="tag text-[0.78rem]">{currentRun.mode}</span>
          {#if currentRun.task_id}
            <a
              href={toPath(`/queue/${currentRun.task_id}`)}
              use:route
              class="text-[0.82rem] font-semibold"
            >
              Queue task →
            </a>
          {/if}
        </div>

        <div class="grid grid-cols-2 gap-3 max-sm:grid-cols-1 text-[0.88rem]">
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Label</span><span
              >{currentRun.label}</span
            >
          </div>
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Created</span><span
              >{formatDate(currentRun.created_at)}</span
            >
          </div>
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Started</span><span
              >{formatDate(currentRun.started_at)}</span
            >
          </div>
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Finished</span><span
              >{formatDate(currentRun.finished_at)}</span
            >
          </div>
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Input</span><span
              class="break-all">{currentRun.input_path ?? "—"}</span
            >
          </div>
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Format</span><span
              >{currentRun.format ?? "—"}</span
            >
          </div>
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Output</span><span
              class="break-all">{currentRun.output_path ?? "—"}</span
            >
          </div>
          <div class="flex gap-4">
            <span class="text-muted min-w-24">Benchmark</span><span
              class="break-all">{currentRun.benchmark_path ?? "—"}</span
            >
          </div>
        </div>

        {#if currentRun.error}
          <div
            class="mt-4 border border-danger/20 bg-danger/5 text-danger px-3 py-2 text-[0.88rem]"
          >
            {currentRun.error}
          </div>
        {/if}
      </div>

      <div class="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
        <div class="card">
          <h3 class="mb-3 flex items-center gap-2">
            <FileTextIcon size={16} strokeWidth={2} /> Output
          </h3>
          {#if outputData}
            <pre
              class="max-h-96 overflow-y-auto m-0 text-[0.78rem]">{outputData.kind ===
              "json"
                ? JSON.stringify(outputData.content, null, 2)
                : String(outputData.content)}</pre>
          {:else}
            <p class="text-muted mb-0 text-[0.85rem]">
              No stored output available.
            </p>
          {/if}
        </div>

        <div class="card">
          <h3 class="mb-3 flex items-center gap-2">
            <GaugeIcon size={16} strokeWidth={2} /> Benchmark
          </h3>
          {#if benchmarkData}
            <pre
              class="max-h-96 overflow-y-auto m-0 text-[0.78rem]">{benchmarkData.content}</pre>
          {:else}
            <p class="text-muted mb-0 text-[0.85rem]">
              No stored benchmark available.
            </p>
          {/if}
        </div>
      </div>
    {/if}
  {:else}
    <h2 class="flex items-center gap-1.5">
      <HistoryIcon
        size={20}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      />
      {listHeading}
    </h2>
    <p class="text-muted mb-5">{listDescription}</p>

    <div class="card mb-4">
      <div class="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h3 class="mb-0 text-[0.9rem]">Filters</h3>
        <button class="btn-secondary" onclick={fetchRuns} title="Refresh">
          ↻ Refresh
        </button>
      </div>

      <div class="grid gap-3">
        <div class="grid grid-cols-6 gap-[0.4rem] max-sm:grid-cols-2">
          {#each statusOptions as option}
            <button
              class={selectedStatus === option
                ? "btn-primary"
                : "btn-secondary"}
              onclick={() => setStatusFilter(option)}
            >
              {option || "All"}
            </button>
          {/each}
        </div>

        {#if !scopedCommand}
          <div class="grid grid-cols-4 gap-[0.4rem] max-sm:grid-cols-2">
            {#each commandOptions as option}
              <button
                class={selectedCommand === option
                  ? "btn-primary"
                  : "btn-secondary"}
                onclick={() => setCommandFilter(option)}
              >
                {option || "All commands"}
              </button>
            {/each}
          </div>
        {/if}

        <div class="grid grid-cols-3 gap-[0.4rem] max-sm:grid-cols-1">
          {#each modeOptions as option}
            <button
              class={selectedMode === option ? "btn-primary" : "btn-secondary"}
              onclick={() => setModeFilter(option)}
            >
              {option === ""
                ? "All runs"
                : option === "queued"
                  ? "Queued"
                  : "Direct"}
            </button>
          {/each}
        </div>
      </div>
    </div>

    {#if loading}
      <p class="flex items-center gap-x-2">
        <LoaderCircleIcon class="w-5 h-5 animate-spin" /> Loading…
      </p>
    {:else if runs.length === 0}
      <div class="card text-center py-8"><p>No runs found.</p></div>
    {:else}
      <div class="flex flex-col gap-2">
        {#each runs as run}
          <a
            href={toPath(`${runsBasePath}/${run.id}`)}
            use:route
            class="card flex flex-col gap-[0.35rem] text-ink transition-[border-color] duration-150 hover:border-cobalt"
          >
            <div class="flex items-center gap-2 flex-wrap">
              <span class={badgeClass(run.status)}>{run.status}</span>
              <span class="tag text-[0.78rem]">{run.command}</span>
              <span class="tag text-[0.78rem]">{run.mode}</span>
              <span class="text-[0.88rem] flex-1">{run.label}</span>
            </div>
            <div class="flex gap-4 items-center flex-wrap">
              <code class="text-[0.75rem] font-mono text-muted">{run.id}</code>
              <span class="text-muted text-[0.85rem]"
                >{formatDate(run.created_at)}</span
              >
              {#if run.benchmark_path}
                <span class="text-muted text-[0.82rem]">benchmark</span>
              {/if}
            </div>
          </a>
        {/each}
      </div>
    {/if}
  {/if}
</div>
