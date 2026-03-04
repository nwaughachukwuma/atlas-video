<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import { MicIcon, CircleCheckIcon } from "lucide-svelte";
  import VideoUpload from "../components/VideoUpload.svelte";
  import { transcribe } from "../lib/api.ts";
  import type { TranscribeResult, TaskQueuedResult } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";

  let file: File | null = null;
  let format: string = "text";
  let benchmark: boolean = false;
  let no_queue: boolean = true;
  let loading: boolean = false;
  let result: TranscribeResult | null = null;
  let error: string | null = null;
  let taskInfo: TaskQueuedResult | null = null;

  async function submit(): Promise<void> {
    if (!file) return;
    loading = true;
    result = null;
    error = null;
    taskInfo = null;
    try {
      const data = await transcribe(file, {
        format,
        benchmark,
        no_queue,
        no_streaming: true,
      });
      if (data.ok === false) {
        error = data.error ?? "Unknown error";
      } else if (data.task_id) {
        taskInfo = data;
      } else {
        result = data;
      }
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
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

  <div class="card mb-4">
    <VideoUpload
      bind:file
      onChange={() => {
        result = null;
        error = null;
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
    class="btn-primary mb-3 text-base px-[1.6em] py-[0.6em]"
    onclick={submit}
    disabled={!file || loading}
  >
    {#if loading}<span class="spinner"></span> Transcribing…{:else}Transcribe{/if}
  </button>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}

  {#if taskInfo}
    <div class="success-box">
      <CircleCheckIcon
        size={16}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Task queued! <strong>Task ID:</strong>
      {taskInfo.task_id ?? taskInfo.id ?? JSON.stringify(taskInfo)}
      <br /><a href={toPath("/queue")} use:route>View Queue →</a>
    </div>
  {/if}

  {#if result}
    <div class="card mt-2">
      <h3 class="mb-3">Transcript <span class="tag">{format}</span></h3>
      {#if result.transcript}
        <pre>{result.transcript}</pre>
      {:else}
        <pre>{JSON.stringify(result, null, 2)}</pre>
      {/if}
    </div>
  {/if}
</div>
