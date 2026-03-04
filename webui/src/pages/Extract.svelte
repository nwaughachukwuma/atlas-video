<script>
  import { FlaskConicalIcon, CircleCheckIcon } from "lucide-svelte";
  import VideoUpload from "../components/VideoUpload.svelte";
  import { extract } from "../lib/api.js";

  let file = null;
  let chunk_duration = "15s";
  let overlap = "1s";
  let format = "json";
  let include_summary = true;
  let benchmark = false;
  let no_queue = true;
  let loading = false;
  let result = null;
  let error = null;
  let taskInfo = null;

  async function submit() {
    if (!file) return;
    loading = true;
    result = null;
    error = null;
    taskInfo = null;
    try {
      const data = await extract(file, {
        chunk_duration,
        overlap,
        format,
        include_summary,
        benchmark,
        no_queue,
        no_streaming: true,
      });
      if (data.ok === false) {
        error = data.error || "Unknown error";
      } else if (
        data.task_id ||
        (typeof data === "object" && "id" in data && !("chunks" in data))
      ) {
        taskInfo = data;
      } else {
        result = data;
      }
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="p-8 max-w-[760px]">
  <h2>
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
      on:change={() => {
        result = null;
        error = null;
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
        <select id="fmt" bind:value={format} class="w-[100px]">
          <option value="json">JSON</option>
          <option value="text">Text</option>
        </select>
      </div>
    </div>
    <div class="flex flex-col gap-2 mt-3">
      <label
        class="flex items-center gap-2 cursor-pointer text-[0.88rem] !text-ink !mb-0"
      >
        <input
          type="checkbox"
          bind:checked={include_summary}
          class="accent-cobalt"
        />
        <span>Include summary</span>
      </label>
      <label
        class="flex items-center gap-2 cursor-pointer text-[0.88rem] !text-ink !mb-0"
      >
        <input type="checkbox" bind:checked={benchmark} class="accent-cobalt" />
        <span>Benchmark timing</span>
      </label>
      <label
        class="flex items-center gap-2 cursor-pointer text-[0.88rem] !text-ink !mb-0"
      >
        <input type="checkbox" bind:checked={no_queue} class="accent-cobalt" />
        <span>Run immediately (no queue)</span>
      </label>
    </div>
  </div>

  <button
    class="btn-primary mb-3 text-base px-[1.6em] py-[0.6em]"
    on:click={submit}
    disabled={!file || loading}
  >
    {#if loading}<span class="spinner"></span> Extracting…{:else}Extract
      Insights{/if}
  </button>

  {#if error}<div class="error-box">{error}</div>{/if}

  {#if taskInfo}
    <div class="success-box">
      <CircleCheckIcon
        size={16}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Task queued! <strong>Task ID:</strong>
      {taskInfo.task_id ?? taskInfo.id ?? JSON.stringify(taskInfo)}
      <br /><a href="#/queue">View Queue →</a>
    </div>
  {/if}

  {#if result}
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
            <pre>{JSON.stringify(chunk, null, 2)}</pre>
          </details>
        {/each}
        {#if result.summary}
          <div class="mt-4 pt-4 border-t border-line">
            <h4 class="mb-[0.4rem]">Summary</h4>
            <p>{result.summary}</p>
          </div>
        {/if}
      {:else}
        <pre>{JSON.stringify(result, null, 2)}</pre>
      {/if}
    </div>
  {/if}
</div>
