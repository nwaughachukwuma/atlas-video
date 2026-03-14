<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { MicIcon, CircleCheckIcon, LoaderCircleIcon } from "lucide-svelte";
  import VideoUpload from "../components/VideoUpload.svelte";
  import { transcribe } from "../lib/api.ts";
  import type { TranscribeResult, TaskQueuedResult } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";

  let file: File | null = null;
  let format: string = "text";
  let benchmark: boolean = false;
  let no_queue: boolean = true;
  let loading: boolean = false;

  let result: TranscribeResult | null = null;
  let taskInfo: TaskQueuedResult | null = null;

  async function submit() {
    if (loading || !file) return;

    loading = true;
    result = null;
    taskInfo = null;

    return transcribe(file, {
      format,
      benchmark,
      no_queue,
      no_streaming: true,
    })
      .then((d) => {
        if (d.task_id) taskInfo = d;
        else result = d;
      })
      .catch((e) =>
        toast.error("Error in transcribe video", {
          description: e.message,
        }),
      )
      .finally(() => (loading = false));
  }
</script>

<div class="p-8 max-w-[760px]">
  <h2 class="flex items-center gap-1.5">
    <MicIcon
      size={20}
      strokeWidth={2}
      style="display:inline;vertical-align:middle;"
    /> Transcribe Video
  </h2>
  <p class="text-muted mb-5">
    Convert your video's audio to text. Supports plain text, WebVTT, and SRT
    formats.
  </p>

  <div class="mb-5 text-[0.9rem]">
    <a
      class="px-3 py-2 border-cobalt/40 border"
      href={toPath("/transcribe/runs")}
      use:route>View Previous Runs →</a
    >
  </div>

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
        <label for="fmt">Output format</label>
        <select id="fmt" bind:value={format} class="w-40">
          <option value="text">Plain text</option>
          <option value="vtt">WebVTT</option>
          <option value="srt">SRT</option>
        </select>
      </div>
    </div>
    <div class="flex flex-col gap-2 mt-3">
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
    class="btn-primary flex items-center gap-x-2 mb-3 text-base px-[1.6em] py-[0.6em]"
    onclick={submit}
    disabled={!file || loading}
  >
    {#if loading}
      <LoaderCircleIcon
        class="w-5 h-5 animate-spin"
        style="animation-duration: 0.3s"
      /> Transcribing…{:else}Transcribe{/if}
  </button>

  {#if taskInfo}
    <div class="success-box">
      <CircleCheckIcon
        size={16}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Task queued! <strong>Task ID:</strong>
      {taskInfo.task_id ?? taskInfo.id ?? JSON.stringify(taskInfo)}
      {#if taskInfo.run_id}
        <br /><strong>Run ID:</strong> {taskInfo.run_id}
      {/if}
      <br /><a href={toPath("/queue")} use:route>View Queue →</a>
      {#if taskInfo.run_id}
        <br /><a href={toPath(`/runs/${taskInfo.run_id}`)} use:route
          >View Persisted Run →</a
        >
      {/if}
    </div>
  {/if}

  {#if result}
    <div class="card mt-2">
      <h3 class="mb-3 flex items-center gap-x-2">
        Transcript <span class="tag">{format}</span>
      </h3>
      {#if result.run_id}
        <p class="text-muted text-[0.85rem] mb-3">
          Saved as run <code class="font-mono">{result.run_id}</code>.
          <a href={toPath(`/runs/${result.run_id}`)} use:route>View run →</a>
        </p>
      {/if}
      <p
        class="text-wrap bg-neutral-500/3 max-h-80 overflow-y-auto p-1.5 font-mono text-sm text-muted"
      >
        {#if result.transcript}
          {result.transcript}
        {:else}
          {JSON.stringify(result, null, 2)}
        {/if}
      </p>
    </div>
  {/if}
</div>
