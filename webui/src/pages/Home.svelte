<script>
  import {
    MicIcon,
    FlaskConicalIcon,
    DatabaseIcon,
    FilmIcon,
    ClipboardListIcon,
    LayoutDashboardIcon,
    ZapIcon,
  } from "lucide-svelte";

  const features = [
    {
      path: "/transcribe",
      icon: MicIcon,
      title: "Transcribe",
      desc: "Convert video audio to text in plain text, VTT, or SRT format.",
    },
    {
      path: "/extract",
      icon: FlaskConicalIcon,
      title: "Extract Insights",
      desc: "Derive rich multimodal understanding from your video — scenes, descriptions, and summaries.",
    },
    {
      path: "/index",
      icon: DatabaseIcon,
      title: "Index Video",
      desc: "Index a video for semantic search and chat. Stored locally for instant retrieval.",
    },
    {
      path: "/videos",
      icon: FilmIcon,
      title: "Browse Videos",
      desc: "View all indexed videos, search across them, and chat with any video.",
    },
    {
      path: "/queue",
      icon: ClipboardListIcon,
      title: "Task Queue",
      desc: "Monitor and manage background tasks for long-running video operations.",
    },
    {
      path: "/dashboard",
      icon: LayoutDashboardIcon,
      title: "Dashboard",
      desc: "System health, video & chat counts, queue status, and storage overview.",
    },
  ];
</script>

<div class="p-8 max-w-[960px]">
  <header class="mb-10">
    <h1 class="text-[2.5rem] mb-2">
      <ZapIcon
        size={28}
        strokeWidth={2.5}
        style="display:inline;vertical-align:baseline;"
      /> Atlas <span class="text-cobalt">Video</span>
    </h1>
    <p class="text-muted text-[1.05rem] max-w-[580px] !mb-0">
      Multimodal AI engine for video insights — transcription, semantic
      extraction, semantic search, and conversational chat. All running locally.
    </p>
  </header>

  <section
    class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4 mb-8"
  >
    {#each features as f}
      <a
        href={`#${f.path}`}
        class="card flex flex-col gap-[0.4rem] text-ink transition-[border-color,transform] duration-[0.15s] hover:border-cobalt hover:-translate-y-0.5"
      >
        <span class="text-cobalt flex items-center"
          ><svelte:component this={f.icon} size={24} strokeWidth={1.5} /></span
        >
        <h3 class="!m-0 text-[1rem]">{f.title}</h3>
        <p class="text-muted text-[0.85rem] flex-1 !m-0">{f.desc}</p>
        <span class="text-cobalt text-[0.85rem] font-semibold">Explore →</span>
      </a>
    {/each}
  </section>
</div>
