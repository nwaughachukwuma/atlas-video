<script>
  import { MessageSquareIcon, XIcon } from "lucide-svelte";
  import { createEventDispatcher, onDestroy } from "svelte";
  import { chatStream, listChat } from "../lib/api.js";

  export let videoId;

  const dispatch = createEventDispatcher();

  let messages = [];
  let query = "";
  let streaming = false;
  let ctrl = null;
  let listEl;

  async function loadHistory() {
    try {
      const data = await listChat(videoId);
      messages = (data.messages || []).map((m) => ({
        role: m.role ?? (m.query ? "user" : "assistant"),
        text: m.content ?? m.query ?? m.answer ?? JSON.stringify(m),
      }));
    } catch (_) {
      /* ignore */
    }
  }

  loadHistory();

  function scrollBottom() {
    if (listEl)
      setTimeout(() => {
        listEl.scrollTop = listEl.scrollHeight;
      }, 50);
  }

  async function send() {
    const q = query.trim();
    if (!q || streaming) return;
    query = "";
    messages = [...messages, { role: "user", text: q }];
    messages = [...messages, { role: "assistant", text: "" }];
    streaming = true;
    scrollBottom();

    ctrl = chatStream(
      videoId,
      q,
      (chunk) => {
        messages[messages.length - 1].text += chunk;
        messages = messages;
        scrollBottom();
      },
      () => {
        streaming = false;
        ctrl = null;
      },
    );
  }

  function cancel() {
    ctrl?.abort();
    streaming = false;
  }

  onDestroy(() => ctrl?.abort());

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }
</script>

<div
  class="fixed bottom-6 right-6 w-96 max-h-[520px] bg-surface border border-line rounded-xl flex flex-col z-[1000]"
>
  <div
    class="flex items-center justify-between px-4 py-3 border-b border-line font-semibold text-[0.9rem]"
  >
    <span
      ><MessageSquareIcon
        size={16}
        strokeWidth={2}
        style="display:inline;vertical-align:middle;"
      /> Chat with Video</span
    >
    <button
      class="btn-secondary px-[0.6em] py-[0.2em]"
      on:click={() => dispatch("close")}
      ><XIcon size={14} strokeWidth={2} /></button
    >
  </div>
  <div
    class="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-2"
    bind:this={listEl}
  >
    {#if messages.length === 0}
      <p class="text-muted text-[0.85rem] text-center m-auto">
        Ask a question about this video…
      </p>
    {/if}
    {#each messages as m}
      <div class={`flex ${m.role === "user" ? "justify-end" : ""}`}>
        <span
          class={`max-w-[80%] px-[0.8em] py-[0.5em] rounded-[10px] text-[0.88rem] whitespace-pre-wrap wrap-break-word ${
            m.role === "user"
              ? "bg-cobalt text-white"
              : "bg-surface-alt text-ink"
          }`}>{m.text || (streaming && m.role === "assistant" ? "…" : "")}</span
        >
      </div>
    {/each}
  </div>
  <div class="flex gap-2 px-4 py-3 border-t border-line">
    <textarea
      bind:value={query}
      on:keydown={handleKey}
      placeholder="Ask something… (Enter to send)"
      rows="2"
      disabled={streaming}
      class="flex-1 resize-none text-[0.85rem]"
    ></textarea>
    {#if streaming}
      <button class="btn-danger self-end whitespace-nowrap" on:click={cancel}
        >Stop</button
      >
    {:else}
      <button
        class="btn-primary self-end whitespace-nowrap"
        on:click={send}
        disabled={!query.trim()}>Send</button
      >
    {/if}
  </div>
</div>
