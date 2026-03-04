<script lang="ts" module>
  import {
    HouseIcon,
    MicIcon,
    FlaskConicalIcon,
    DatabaseIcon,
    FilmIcon,
    ClipboardListIcon,
    LayoutDashboardIcon,
    ZapIcon,
  } from "lucide-svelte";
  import type { NavLink } from "../lib/types.ts";

  type Props = { basePath?: string };

  const links: NavLink[] = [
    { path: "/", icon: HouseIcon, label: "Home", title: "Atlas Video" },
    {
      path: "/transcribe",
      icon: MicIcon,
      label: "Transcribe",
      title: "Transcribe",
    },
    {
      path: "/extract",
      icon: FlaskConicalIcon,
      label: "Extract",
      title: "Extract Insights",
    },
    {
      path: "/index",
      icon: DatabaseIcon,
      label: "Index",
      title: "Index Video",
    },
    {
      path: "/videos",
      icon: FilmIcon,
      label: "Videos",
      title: "Indexed Videos",
    },
    {
      path: "/queue",
      icon: ClipboardListIcon,
      label: "Queue",
      title: "Task Queue",
    },
    {
      path: "/dashboard",
      icon: LayoutDashboardIcon,
      label: "Dashboard",
      title: "Dashboard",
    },
  ];
</script>

<script lang="ts">
  import { active, route } from "@mateothegreat/svelte5-router";

  let { basePath = "/" }: Props = $props();

  function withBase(path: string): string {
    return basePath === "/" ? path : `${basePath}${path}`;
  }

  function activeOptions(path: string): {
    active: { class: string[]; absolute: boolean };
  } {
    return {
      active: {
        class: [
          "text-cobalt",
          "border-l-cobalt",
          "bg-[rgba(19,81,170,0.06)]",
          "font-bold",
        ],
        absolute: path === "/",
      },
    };
  }
</script>

<nav
  class="w-52 min-h-screen bg-surface border-r border-line flex flex-col py-5 sticky top-0 shrink-0"
>
  <div class="px-[1.1rem] pb-5 border-b border-line mb-3">
    <a
      href={withBase("/")}
      use:route
      class="font-sans text-[1.15rem] font-black text-cobalt flex items-center gap-[0.35rem] tracking-[-0.02em]"
    >
      <ZapIcon size={16} strokeWidth={2} />
      <span>Atlas</span>
    </a>
    <span class="text-[0.7rem] font-bold text-muted uppercase tracking-[0.2em]"
      >Multimodal AI</span
    >
  </div>
  <ul class="list-none m-0 p-0 flex-1">
    {#each links as l}
      <li>
        <a
          href={withBase(l.path)}
          use:route
          use:active={activeOptions(l.path)}
          class="flex items-center gap-2 py-[0.55em] px-[1.1rem] text-[0.88rem] font-medium border-l-2 transition-all duration-300 ease-linear text-muted border-l-transparent hover:text-ink hover:bg-surface-alt"
        >
          <l.icon size={15} strokeWidth={1.5} />
          <span>{l.label}</span>
        </a>
      </li>
    {/each}
  </ul>
  <div
    class="px-[1.1rem] pt-4 border-t border-line text-[0.75rem] flex flex-col gap-[0.3em]"
  >
    <span class="text-muted">Atlas Multimodal Engine</span>
    <a
      href="https://github.com/nwaughachukwuma/atlas-video"
      target="_blank"
      class="text-muted hover:text-cobalt">GitHub ↗</a
    >
  </div>
</nav>
