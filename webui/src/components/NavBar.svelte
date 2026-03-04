<script>
  export let currentPath = "/";

  const links = [
    { path: "/", label: "🏠 Home", title: "Atlas Video" },
    { path: "/transcribe", label: "🎙️ Transcribe", title: "Transcribe" },
    { path: "/extract", label: "🔬 Extract", title: "Extract Insights" },
    { path: "/index", label: "📦 Index", title: "Index Video" },
    { path: "/videos", label: "🎬 Videos", title: "Indexed Videos" },
    { path: "/queue", label: "📋 Queue", title: "Task Queue" },
    { path: "/dashboard", label: "📊 Dashboard", title: "Dashboard" },
  ];

  function isActive(path) {
    if (path === "/") return currentPath === "/";
    return currentPath.startsWith(path);
  }
</script>

<nav>
  <div class="logo">
    <a href="#/">⚡ Atlas</a>
    <span class="version">Multimodal AI</span>
  </div>
  <ul>
    {#each links as l}
      <li class:active={isActive(l.path)}>
        <a href={`#${l.path}`}>{l.label}</a>
      </li>
    {/each}
  </ul>
  <div class="nav-footer">
    <span class="muted">Atlas Multimodal Engine</span>
    <a
      href="https://github.com/nwaughachukwuma/atlas-video"
      target="_blank"
      class="gh-link">GitHub ↗</a
    >
  </div>
</nav>

<style>
  nav {
    width: 210px;
    min-height: 100vh;
    background: var(--bg2);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 1.25rem 0;
    position: sticky;
    top: 0;
    flex-shrink: 0;
  }
  .logo {
    padding: 0 1.1rem 1.25rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.75rem;
  }
  .logo a {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--primary);
    display: block;
  }
  .version {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    flex: 1;
  }
  li a {
    display: block;
    padding: 0.55em 1.1rem;
    color: var(--text-muted);
    font-size: 0.9rem;
    border-left: 2px solid transparent;
    transition: all 0.15s;
  }
  li a:hover {
    color: var(--text);
    background: var(--bg3);
  }
  li.active a {
    color: var(--primary);
    border-left-color: var(--primary);
    background: rgba(99, 102, 241, 0.1);
  }
  .nav-footer {
    padding: 1rem 1.1rem 0;
    border-top: 1px solid var(--border);
    font-size: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.3em;
  }
  .muted {
    color: var(--text-muted);
  }
  .gh-link {
    color: var(--text-muted);
  }
  .gh-link:hover {
    color: var(--primary);
  }
</style>
