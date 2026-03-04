<script>
  import {
    CircleAlertIcon,
    CircleCheckIcon,
    InfoIcon,
    XIcon,
  } from "lucide-svelte";

  /** @type {'error' | 'success' | 'info'} */
  export let type = "error";
  export let message = "";
  export let dismissible = false;

  let visible = true;

  $: if (message) visible = true;
</script>

{#if visible && message}
  <div
    class={`flex items-start gap-[0.6rem] px-[0.9rem] py-[0.65rem] my-3 text-[0.83rem] font-mono border leading-[1.4] ${
      type === "error"
        ? "bg-[#18070a] border-[#7f1d1d] text-[#fca5a5]"
        : type === "success"
          ? "bg-[#011a11] border-[#065f46] text-[#6ee7b7]"
          : "bg-[#0c1a2e] border-[#1e3a5f] text-[#93c5fd]"
    }`}
    role="alert"
  >
    <div class="shrink-0 mt-[0.05em] flex">
      {#if type === "error"}<CircleAlertIcon size={15} />{/if}
      {#if type === "success"}<CircleCheckIcon size={15} />{/if}
      {#if type === "info"}<InfoIcon size={15} />{/if}
    </div>
    <span class="flex-1 wrap-break-word">{message}</span>
    {#if dismissible}
      <button
        class="shrink-0 bg-transparent border-none p-0 text-inherit opacity-60 cursor-pointer flex mt-[0.1em] hover:opacity-100"
        on:click={() => (visible = false)}
        aria-label="Dismiss"
      >
        <XIcon size={13} />
      </button>
    {/if}
  </div>
{/if}
