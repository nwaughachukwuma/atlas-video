<script lang="ts">
  import { route } from "@mateothegreat/svelte5-router";
  import {
    DatabaseIcon,
    CircleCheckIcon,
    LoaderCircleIcon,
  } from "lucide-svelte";
  import VideoUpload from "../components/VideoUpload.svelte";
  import { indexVideo } from "../lib/api.ts";
  import type { IndexResult, TaskQueuedResult } from "../lib/types.ts";
  import { toPath } from "../lib/routing.ts";
  import { toast } from "svelte-sonner";

  let file: File | null = null;
  let chunk_duration: string = "15s";
  let overlap: string = "1s";
  let include_summary: boolean = true;
  let benchmark: boolean = false;
  let no_queue: boolean = true;

  let loading: boolean = false;
  let result: IndexResult | null = null;
  let taskInfo: TaskQueuedResult | null = null;

  async function submit() {
    if (loading || !file) return;
    loading = true;
    result = null;
    taskInfo = null;

    return indexVideo(file, {
      chunk_duration,
      overlap,
      include_summary,
      benchmark,
      no_queue,
      no_streaming: true,
    })
      .then((d) => {
        if (d.task_id) taskInfo = d;
        else if (d.video_id) result = d;
        else if ("id" in d && !("video_id" in d)) taskInfo = d;
        else result = d;
      })
      .catch((e) =>
        toast.error("Error while indexing video", {
          description: e.message,
        }),
      )
      .finally(() => (loading = false));
  }
</script>

<div class="p-8 max-w-[760px]">
  <h2 class="flex items-center gap-1.5">
    <DatabaseIcon
      size={20}
      strokeWidth={2}
      style="display:inline;vertical-align:middle;"
    /> Index Video
  </h2>
  <p class="text-muted mb-5">
    Index your video for semantic search and conversational chat. Chunks are
    stored locally in a vector store for instant retrieval.
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
    class="btn-primary mb-3 flex items-center gap-x-2 text-base px-6 py-2.5"
    onclick={submit}
    disabled={!file || loading}
  >
    {#if loading}
      <LoaderCircleIcon
        class="w-5 h-5 animate-spin"
        style="animation-duration: 0.3s"
      />
      Indexing…
    {:else}
      Index Video
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
      <br /><a href={toPath("/queue")} use:route>View Queue →</a>
    </div>
  {/if}

  {#if result}
    <div class="card mt-2">
      <h3>
        <CircleCheckIcon
          size={18}
          strokeWidth={2}
          style="display:inline;vertical-align:middle;"
        /> Indexed Successfully
      </h3>
      <p>
        <strong>Video ID:</strong>
        <code
          class="bg-surface-alt px-[0.4em] py-[0.15em] text-[0.85em] font-mono"
          >{result.video_id}</code
        >
      </p>
      <p><strong>Indexed chunks:</strong> {result.indexed_count}</p>
      <a
        href={toPath(`/video/${result.video_id}`)}
        use:route
        class="btn-primary inline-block mt-2 px-6 py-2.5"
      >
        View Video →
      </a>
      {#if result.result}
        <details class="mt-4 border border-line p-2">
          <summary class="cursor-pointer text-[0.88rem] text-muted">
            Full result JSON
          </summary>
          <pre class="max-h-96 overflow-y-auto m-0">{JSON.stringify(
              result.result,
              null,
              2,
            )}</pre>
        </details>
      {/if}
    </div>
  {/if}
</div>
