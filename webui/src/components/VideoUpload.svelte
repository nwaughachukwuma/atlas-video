<script lang="ts" module>
  type Prop = {
    accept?: string;
    file?: File | null;
    onChange?: (value: File | null) => void;
  };
</script>

<script lang="ts">
  import { UploadIcon, XIcon } from "lucide-svelte";
  let {
    accept = "video/*",
    file = $bindable<File | null>(null),
    onChange = () => {},
  }: Prop = $props();

  let dragging = $state(false);
  let input = $state<HTMLInputElement | null>(null);
  let previewUrl = $state<string | null>(null);

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
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    file = f;
    previewUrl = URL.createObjectURL(f);
    onChange(f);
  }

  function handleInput(e: Event): void {
    const target = e.target as HTMLInputElement;
    const f = target.files?.[0];
    if (f) setFile(f);
  }

  function clear() {
    file = null;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
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
  role="region"
  aria-label="Video file upload"
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  ondrop={handleDrop}
  class={`border-2 border-dashed p-8 text-center transition-all duration-150 bg-surface-alt cursor-pointer ${
    dragging
      ? "border-cobalt bg-[rgba(19,81,170,0.07)]"
      : file
        ? "border-solid border-success p-4"
        : "border-line"
  }`}
>
  {#if file}
    <div class="flex gap-3 items-start">
      <div class="flex flex-1 flex-col gap-3 items-start text-left w-full">
        {#if previewUrl}
          <video
            src={previewUrl}
            class="max-w-44 aspect-video rounded object-cover grayscale"
          >
            <track kind="captions" />
          </video>
        {/if}
        <div>
          <span class="block text-[0.88rem] font-medium truncate">
            {file.name}
          </span>
          <span class="block text-[0.75rem] text-muted">
            {formatSize(file.size)}
          </span>
        </div>
      </div>
      <button
        type="button"
        class="bg-transparent border-none text-muted p-1 leading-none hover:text-danger shrink-0"
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
