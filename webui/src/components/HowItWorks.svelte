<script lang="ts" module>
  import type { Step } from "../lib/types.ts";
  const steps: Step[] = [
    {
      num: "01",
      action: "Upload",
      detail: "Drop or browse a video file — any common format accepted.",
    },
    {
      num: "02",
      action: "Choose",
      detail:
        "Pick an operation: Transcribe, Extract Insights, or Index for chat.",
    },
    {
      num: "03",
      action: "Configure",
      detail: "Set chunk duration, output format, queuing preferences.",
    },
    {
      num: "04",
      action: "Submit",
      detail: "Results stream in immediately, or tasks are queued for later.",
    },
    {
      num: "05",
      action: "Chat",
      detail: "Ask questions in natural language about any indexed video.",
    },
  ];
</script>

<script lang="ts">
  import { CircleQuestionMarkIcon, XIcon } from "lucide-svelte";
  let open: boolean = false;
</script>

<button
  class="inline-flex items-center gap-[0.35rem] bg-transparent border border-line text-muted font-sans text-[0.8rem] font-semibold px-3 py-[0.38em] tracking-[0.01em] cursor-pointer transition-all duration-300 ease-linear whitespace-nowrap hover:border-cobalt hover:text-cobalt"
  onclick={() => (open = true)}
  title="How it works"
>
  <CircleQuestionMarkIcon size={18} strokeWidth={1.5} />
  <span>How it works</span>
</button>

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-999"
    onclick={() => (open = false)}
  >
    <div
      class="bg-surface border border-line w-[480px] max-w-[92vw] max-h-[85vh] overflow-y-auto"
      onclick={(e) => e.stopPropagation()}
      role="dialog"
      tabindex="0"
      aria-modal="true"
      aria-label="How it works"
    >
      <div
        class="flex justify-between items-center px-5 py-4 border-b border-line"
      >
        <span
          class="font-sans text-[0.95rem] font-bold tracking-[-0.01em] uppercase text-ink"
        >
          How it works
        </span>
        <button
          class="bg-transparent border-none text-muted cursor-pointer p-[0.2em] flex items-center hover:text-ink"
          onclick={() => (open = false)}
          aria-label="Close"
        >
          <XIcon size={16} />
        </button>
      </div>
      <ol class="list-none m-0 py-5 px-5 flex flex-col gap-3">
        {#each steps as s, i}
          <li class="flex gap-3 items-start">
            <div
              class="shrink-0 w-7 h-7 rounded-full bg-cobalt/10 border border-cobalt/20 flex items-center justify-center"
            >
              <span class="font-mono text-[0.65rem] font-bold text-cobalt">
                {i + 1}
              </span>
            </div>
            <div class="flex flex-col gap-[0.15rem]">
              <strong
                class="font-sans text-[0.88rem] font-bold text-ink tracking-[-0.005em]"
                >{s.action}</strong
              >
              <span class="text-[0.82rem] text-muted leading-[1.45]"
                >{s.detail}</span
              >
            </div>
          </li>
          {#if i < steps.length - 1}
            <li class="flex gap-3 items-center" aria-hidden="true">
              <div class="w-7 flex justify-center">
                <div class="w-px h-4 bg-line"></div>
              </div>
            </li>
          {/if}
        {/each}
      </ol>
    </div>
  </div>
{/if}
