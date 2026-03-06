<script lang="ts" module>
  type Props = {
    videoId: string;
  };
</script>

<script lang="ts">
  import {
    MessageSquareIcon,
    XIcon,
    SendIcon,
    SquareIcon,
    LoaderCircleIcon,
    BotIcon,
    ChevronDownIcon,
  } from "lucide-svelte";
  import { onDestroy, onMount } from "svelte";
  import { marked } from "marked";
  import { chatStream, listChat } from "../lib/api.ts";
  import type { ChatMessage, RawChatMessage } from "../lib/types.ts";

  let { videoId }: Props = $props();

  let isOpen = $state(false);
  let messages = $state<ChatMessage[]>([]);
  let query = $state("");
  let streaming = $state(false);
  let streamingContent = $state("");

  let ctrl = $state<AbortController | null>(null);
  let listEl = $state<HTMLDivElement | null>(null);
  let textareaEl = $state<HTMLTextAreaElement | null>(null);
  let bottomRef = $state<HTMLDivElement | null>(null);

  const STORAGE_KEY = $derived(`atlas_chat_${videoId}`);

  // Load persisted messages from localStorage on mount
  function loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        messages = JSON.parse(stored) as ChatMessage[];
      }
    } catch {}
  }

  // Persist messages to localStorage
  function saveToStorage(): void {
    if (messages.length === 0) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {}
  }

  // Load chat history from server
  async function loadHistory(): Promise<void> {
    try {
      const data = await listChat(videoId);
      const serverMessages = (data.messages || []).map(
        (m: RawChatMessage): ChatMessage => ({
          role:
            m.role === "user" || m.role === "assistant"
              ? m.role
              : m.query
                ? "user"
                : "assistant",
          text: m.content ?? m.query ?? m.answer ?? JSON.stringify(m),
        }),
      );
      // Merge: prefer server messages if available, otherwise keep local
      if (serverMessages.length > 0) {
        messages = serverMessages;
      }
    } catch {}
  }

  onMount(() => {
    loadFromStorage();
    void loadHistory();
  });

  $effect(() => {
    if (videoId) {
      loadFromStorage();
      void loadHistory();
    }
  });

  // Save to storage when messages change
  $effect(() => {
    if (messages.length > 0) {
      saveToStorage();
    }
  });

  // Focus textarea when panel opens
  $effect(() => {
    if (isOpen) {
      setTimeout(() => textareaEl?.focus(), 100);
    }
  });

  $effect(() => {
    if (messages || streamingContent) {
      scrollBottom();
    }
  });

  function scrollBottom(): void {
    setTimeout(() => {
      bottomRef?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, 50);
  }

  async function send(): Promise<void> {
    const q = query.trim();
    if (!q || streaming) return;

    query = "";
    messages = [...messages, { role: "user", text: q }];
    streaming = true;
    streamingContent = "";
    scrollBottom();

    ctrl = chatStream(
      videoId,
      q,
      (chunk) => {
        streamingContent += chunk;
        scrollBottom();
      },
      () => {
        // Add the completed assistant message
        messages = [...messages, { role: "assistant", text: streamingContent }];
        streaming = false;
        streamingContent = "";
        ctrl = null;
      },
    );
  }

  function cancel(): void {
    ctrl?.abort();
    if (streamingContent) {
      messages = [...messages, { role: "assistant", text: streamingContent }];
    }
    streaming = false;
    streamingContent = "";
  }

  onDestroy(() => ctrl?.abort());

  function handleKey(e: KeyboardEvent): void {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function togglePanel(): void {
    isOpen = !isOpen;
  }
</script>

<!-- Floating Panel -->
<div
  class="fixed bottom-22 right-6 z-50 w-96 min-h-64 flex flex-col bg-surface border border-line rounded-2xl shadow-xl transition-all duration-200 origin-bottom-right {isOpen
    ? 'opacity-100 scale-100 pointer-events-auto'
    : 'opacity-0 scale-95 translate-y-2.5 pointer-events-none'}"
  style="max-height: min(32rem, calc(100vh - 8rem));"
>
  <!-- Header -->
  <div
    class="flex items-center justify-between px-4 py-3 border-b border-line shrink-0"
  >
    <div class="flex items-center gap-2 text-sm font-semibold text-ink">
      <BotIcon size={16} strokeWidth={2} class="text-cobalt" />
      <span>Chat with Video</span>
    </div>
    <button
      class="w-7 h-7 p-0 flex items-center justify-center bg-transparent border-none rounded-md text-muted cursor-pointer transition-all duration-150 hover:bg-surface-alt hover:text-ink"
      onclick={() => (isOpen = false)}
      aria-label="Minimize"
    >
      <ChevronDownIcon size={16} strokeWidth={2} />
    </button>
  </div>

  <!-- Messages -->
  <div
    bind:this={listEl}
    class="flex-1 overflow-y-auto p-4 flex flex-col gap-3 min-h-0"
  >
    {#if messages.length === 0 && !streaming}
      <p class="text-center text-muted text-xs py-8 px-4 m-auto">
        Ask anything about this video — topics, timestamps, or specific details.
      </p>
    {/if}

    {#each messages as m (m.text + m.role)}
      <div class="flex {m.role === 'user' ? 'justify-end' : 'justify-start'}">
        <div
          class="max-w-[85%] px-3.5 py-2.5 text-sm leading-snug rounded-2xl {m.role ===
          'user'
            ? 'bg-cobalt text-white rounded-br-sm whitespace-pre-wrap wrap-break-word'
            : 'bg-surface-alt text-ink border border-line rounded-bl-sm prose prose-sm max-w-none'}"
        >
          {#if m.role === "assistant"}
            {@html marked.parse(m.text)}
          {:else}
            {m.text}
          {/if}
        </div>
      </div>
    {/each}

    <!-- Streaming bubble -->
    {#if streaming && streamingContent}
      <div class="flex justify-start">
        <div
          class="max-w-[85%] px-3.5 py-2.5 text-sm leading-snug rounded-2xl bg-surface-alt text-ink border border-line rounded-bl-sm prose prose-sm max-w-none"
        >
          {@html marked.parse(streamingContent)}
        </div>
      </div>
    {/if}

    <!-- Typing indicator -->
    {#if streaming && !streamingContent}
      <div class="flex justify-start">
        <div
          class="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-2xl rounded-bl-sm bg-surface-alt text-muted border border-line"
        >
          <LoaderCircleIcon
            size={14}
            strokeWidth={2}
            class="animate-spin"
            style="animation-duration:0.6s"
          />
          <span class="text-sm">thinking…</span>
        </div>
      </div>
    {/if}

    <div bind:this={bottomRef}></div>
  </div>

  <!-- Input -->
  <div class="flex gap-2 p-3 border-t border-line shrink-0">
    <textarea
      bind:this={textareaEl}
      bind:value={query}
      onkeydown={handleKey}
      placeholder="Ask something…"
      rows={2}
      disabled={streaming}
      class="flex-1 resize-none px-3 py-2 text-sm border border-line rounded-lg bg-transparent min-h-9 max-h-24 font-sans focus:outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/15 disabled:opacity-60 disabled:cursor-not-allowed"
    ></textarea>
    {#if streaming}
      <button
        class="self-end w-9 h-9 p-0 flex items-center justify-center bg-danger text-white border-none rounded-lg cursor-pointer shrink-0 transition-all duration-150 hover:bg-red-800"
        onclick={cancel}
      >
        <SquareIcon size={14} strokeWidth={0} fill="currentColor" />
      </button>
    {:else}
      <button
        class="self-end w-9 h-9 p-0 flex items-center justify-center bg-cobalt text-white border-none rounded-lg cursor-pointer shrink-0 transition-all duration-150 hover:bg-cobalt-dark disabled:opacity-40 disabled:cursor-not-allowed"
        onclick={send}
        disabled={!query.trim()}
      >
        <SendIcon size={14} strokeWidth={2} />
      </button>
    {/if}
  </div>
</div>

<!-- FAB Button -->
<button
  class="fixed bottom-6 right-6 z-50 w-13 h-13 rounded-full bg-cobalt text-white border-none shadow-lg flex items-center justify-center cursor-pointer transition-all duration-200 hover:scale-105 hover:shadow-xl active:scale-95"
  onclick={togglePanel}
  aria-label="Toggle chat panel"
>
  {#if isOpen}
    <XIcon size={20} strokeWidth={2} />
  {:else}
    <MessageSquareIcon size={20} strokeWidth={2} />
  {/if}
</button>
