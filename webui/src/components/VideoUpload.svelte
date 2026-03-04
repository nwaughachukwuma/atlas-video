<script lang="ts" module>
  type Prop = {
    accept?: string;
    file?: File | null;
    onChange?: (value: File | null) => void;
  };
</script>

<script lang="ts">
  import { FilmIcon, UploadIcon, XIcon } from "lucide-svelte";
  let {
    accept = "video/*",
    file = $bindable<File | null>(null),
    onChange = () => {},
  }: Prop = $props();

  let dragging: boolean = $state(false);
  let input: HTMLInputElement | null = $state(null);

  function handleDragOver(e: DragEvent): void {
    e.preventDefault();
    dragging = true;
  }

  function handleDragLeave(): void {
    dragging = false;
  }

  function handleDrop(e: DragEvent): void {
    e.preventDefault();
    dragging = false;
    const f = e.dataTransfer?.files[0];
    if (f) setFile(f);
  }

  function setFile(f: File): void {
    file = f;
    onChange(f);
  }

  function handleInput(e: Event): void {
    const target = e.target as HTMLInputElement;
    const f = target.files?.[0];
    if (f) setFile(f);
  }

  function clear(): void {
    file = null;
    if (input) input.value = "";
    onChange(null);
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }
</script>

<div
  class={`border-2 border-dashed p-8 text-center transition-all duration-[0.15s] bg-surface-alt cursor-pointer ${
    dragging
      ? "border-cobalt bg-[rgba(19,81,170,0.07)]"
      : file
        ? "border-solid border-success p-4"
        : "border-line"
  }`}
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  ondrop={handleDrop}
  role="region"
  aria-label="Video file upload"
>
  {#if file}
    <div class="flex items-center gap-3 text-left">
      <span class="text-cobalt flex"
        ><FilmIcon size={20} strokeWidth={1.5} /></span
      >
      <div class="flex-1">
        <span class="block text-[0.9rem] font-medium">{file.name}</span>
        <span class="block text-[0.78rem] text-muted"
          >{formatSize(file.size)}</span
        >
      </div>
      <button
        type="button"
        class="bg-transparent border-none text-muted p-1 leading-none hover:text-danger"
        onclick={clear}
        title="Remove file"><XIcon size={16} strokeWidth={2} /></button
      >
    </div>
  {:else}
    <div>
      <span class="text-cobalt flex justify-center mb-2"
        ><UploadIcon size={28} strokeWidth={1.5} /></span
      >
      <p class="text-muted my-1 mb-3 text-[0.9rem]">
        Drag &amp; drop a video file here
      </p>
      <span class="text-muted text-[0.8rem] block mb-2">or</span>
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <label class="btn-secondary cursor-pointer">
        Browse files
        <input
          bind:this={input}
          type="file"
          {accept}
          onchange={handleInput}
          hidden
        />
      </label>
    </div>
  {/if}
</div>
