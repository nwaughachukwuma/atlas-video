<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import {
    FlaskConicalIcon,
    CircleCheckIcon,
    LoaderCircleIcon,
  } from "lucide-svelte";
  import VideoUpload from "../components/VideoUpload.svelte";
  import { extract } from "../lib/api.ts";
  import type { ExtractResult, TaskQueuedResult } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";

  let file: File | null = null;
  let chunk_duration: string = "15s";
  let overlap: string = "1s";
  let format: string = "json";
  let include_summary: boolean = true;
  let benchmark: boolean = false;
  let no_queue: boolean = true;
  let loading: boolean = false;
  let result: ExtractResult | null = null;
  let taskInfo: TaskQueuedResult | null = null;

  async function submit() {
    if (loading || !file) return;

    loading = true;
    result = null;
    taskInfo = null;

    return extract(file, {
      chunk_duration,
      overlap,
      format,
      include_summary,
      benchmark,
      no_queue,
      no_streaming: true,
    })
      .then((d) => {
        if (
          d.task_id ||
          (typeof d === "object" && "id" in d && !("chunks" in d))
        ) {
          taskInfo = d;
        } else result = d;
      })
      .catch((e) =>
        toast.error("Error while extracting multimodal insight", {
          description: e.message,
        }),
      )
      .finally(() => (loading = false));
  }
</script>

<div class="p-8 max-w-[760px]">
  <h2 class="flex items-center gap-1.5">
    <FlaskConicalIcon
      size={20}
      strokeWidth={2}
      style="display:inline;vertical-align:middle;"
    /> Extract Video Insights
  </h2>
  <p class="text-muted mb-5">
    Derive rich multimodal understanding — scene descriptions, visual context,
    and summaries.
  </p>

  <div class="card mb-4">
    <VideoUpload
      bind:file
      onChange={() => {
        result = null;
      }}
    />
  </div>

  <div class="card mb-4">
    <h3 class="mb-3">Options</h3>
    <div class="flex gap-4 flex-wrap">
      <div class="mb-4">
        <label for="cd">Chunk duration</label>
        <input
          id="cd"
          type="text"
          bind:value={chunk_duration}
          style="width:90px"
        />
      </div>
      <div class="mb-4">
        <label for="ov">Overlap</label>
        <input id="ov" type="text" bind:value={overlap} style="width:90px" />
      </div>
      <div class="mb-4">
        <label for="fmt">Format</label>
        <select id="fmt" bind:value={format} class="w-24">
          <option value="json">JSON</option>
          <option value="text">Text</option>
        </select>
      </div>
    </div>
    <div class="flex flex-col gap-2 mt-3">
      <label
        class="flex items-center gap-2 cursor-pointer text-[0.88rem] text-ink mb-0"
      >
        <input
          type="checkbox"
          bind:checked={include_summary}
          class="accent-cobalt"
        />
        <span>Include summary</span>
      </label>
      <label
        class="flex items-center gap-2 cursor-pointer text-[0.88rem] text-ink mb-0"
      >
        <input type="checkbox" bind:checked={benchmark} class="accent-cobalt" />
        <span>Benchmark timing</span>
      </label>
      <label
        class="flex items-center gap-2 cursor-pointer text-[0.88rem] text-ink mb-0"
      >
        <input type="checkbox" bind:checked={no_queue} class="accent-cobalt" />
        <span>Run immediately (no queue)</span>
      </label>
    </div>
  </div>

  <button
    class="btn-primary mb-3 flex items-center gap-x-2 text-base px-[1.6em] py-[0.6em]"
    onclick={submit}
    disabled={!file || loading}
  >
    {#if loading}
      <LoaderCircleIcon
        class="w-5 h-5 animate-spin"
        style="animation-duration: 0.3s"
      /> Extracting…
    {:else}
      Extract Insights
    {/if}
  </button>

  {#if taskInfo}
    <div class="success-box">
      <CircleCheckIcon
        size={16}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Task queued! <strong>Task ID:</strong>
      {taskInfo.task_id ?? taskInfo.id ?? JSON.stringify(taskInfo)}
      {#if taskInfo.output_path}
        <br /><strong>Stored output:</strong> {taskInfo.output_path}
      {/if}
      {#if taskInfo.benchmark_path}
        <br /><strong>Benchmark:</strong> {taskInfo.benchmark_path}
      {/if}
      <br /><a href={toPath("/queue")} use:route>View Queue →</a>
    </div>
  {/if}

  {#if result}
    <div class="success-box mt-2">
      <CircleCheckIcon
        size={16}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Saved run <strong>{result.id}</strong>
      {#if result.output_path}
        <br /><strong>Stored output:</strong> {result.output_path}
      {/if}
      {#if result.benchmark_path}
        <br /><strong>Benchmark:</strong> {result.benchmark_path}
      {/if}
      {#if result.id}
        <br /><a href={toPath(`/queue/${result.id}`)} use:route>Inspect saved run →</a>
      {/if}
    </div>
    <div class="card mt-2">
      <h3>Extracted Insights</h3>
      {#if result.chunks}
        <p class="text-muted text-[0.85rem]">
          {result.chunks.length} segments extracted
        </p>
        {#each result.chunks as chunk, i}
          <details class="border border-line mb-2 p-2">
            <summary
              class="cursor-pointer text-[0.88rem] text-muted hover:text-cobalt"
              >Segment {i + 1} — {chunk.start_time ?? ""}s – {chunk.end_time ??
                ""}s</summary
            >
            <pre class="text-sm">
              {JSON.stringify(chunk, null, 2)}
            </pre>
          </details>
        {/each}
        {#if result.summary}
          <div class="mt-4 pt-4 border-t border-line">
            <h4 class="mb-[0.4rem]">Summary</h4>
            <p>{result.summary}</p>
          </div>
        {/if}
      {:else}
        <pre class="text-sm">
          {JSON.stringify(result, null, 2)}
        </pre>
      {/if}
    </div>
  {/if}
</div>
