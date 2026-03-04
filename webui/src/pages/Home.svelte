<script>
  let showHelp = false;

  const features = [
    {
      path: "/transcribe",
      icon: "🎙️",
      title: "Transcribe",
      desc: "Convert video audio to text in plain text, VTT, or SRT format.",
    },
    {
      path: "/extract",
      icon: "🔬",
      title: "Extract Insights",
      desc: "Derive rich multimodal understanding from your video — scenes, descriptions, and summaries.",
    },
    {
      path: "/index",
      icon: "📦",
      title: "Index Video",
      desc: "Index a video for semantic search and chat. Stored locally for instant retrieval.",
    },
    {
      path: "/videos",
      icon: "🎬",
      title: "Browse Videos",
      desc: "View all indexed videos, search across them, and chat with any video.",
    },
    {
      path: "/queue",
      icon: "📋",
      title: "Task Queue",
      desc: "Monitor and manage background tasks for long-running video operations.",
    },
    {
      path: "/dashboard",
      icon: "📊",
      title: "Dashboard",
      desc: "System health, video & chat counts, queue status, and storage overview.",
    },
  ];
</script>

<div class="home">
  <header>
    <h1>⚡ Atlas <span class="accent">Video</span></h1>
    <p class="subtitle">
      Multimodal AI engine for video insights — transcription, semantic
      extraction, semantic search, and conversational chat. All running locally.
    </p>
  </header>

  <section class="features">
    {#each features as f}
      <a href={`#${f.path}`} class="feature-card card">
        <span class="feat-icon">{f.icon}</span>
        <h3>{f.title}</h3>
        <p>{f.desc}</p>
        <span class="go-btn">Explore →</span>
      </a>
    {/each}
  </section>

  <button
    class="help-trigger"
    on:click={() => (showHelp = true)}
    title="How it works"
  >
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none"
      ><circle
        cx="10"
        cy="10"
        r="9"
        stroke="currentColor"
        stroke-width="1.5"
      /><text
        x="10"
        y="14.5"
        text-anchor="middle"
        fill="currentColor"
        font-size="12"
        font-weight="600">?</text
      ></svg
    >
    How it works
  </button>

  {#if showHelp}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal-backdrop" on:click={() => (showHelp = false)}>
      <div class="modal card" on:click|stopPropagation>
        <div class="modal-header">
          <h2>How it works</h2>
          <button class="modal-close" on:click={() => (showHelp = false)}
            >✕</button
          >
        </div>
        <ol>
          <li><strong>Upload</strong> a video file (any common format).</li>
          <li>
            <strong>Choose</strong> an operation: transcribe, extract, or index.
          </li>
          <li>
            <strong>Configure</strong> options like chunk duration, output format,
            and queuing.
          </li>
          <li>
            <strong>Submit</strong> and watch results stream in — or queue for later.
          </li>
          <li>
            <strong>Chat</strong> with indexed videos to ask questions in natural
            language.
          </li>
        </ol>
      </div>
    </div>
  {/if}
</div>

<style>
  .home {
    padding: 2rem;
    max-width: 960px;
  }
  header {
    margin-bottom: 2.5rem;
  }
  h1 {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
  }
  .accent {
    color: var(--primary);
  }
  .subtitle {
    color: var(--text-muted);
    font-size: 1.05rem;
    max-width: 580px;
  }
  .features {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }
  .feature-card {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    color: var(--text);
    transition:
      border-color 0.15s,
      transform 0.15s;
  }
  .feature-card:hover {
    border-color: var(--primary);
    transform: translateY(-2px);
  }
  .feat-icon {
    font-size: 1.8rem;
  }
  .feature-card h3 {
    margin: 0;
    font-size: 1rem;
  }
  .feature-card p {
    color: var(--text-muted);
    font-size: 0.85rem;
    flex: 1;
    margin: 0;
  }
  .go-btn {
    color: var(--primary);
    font-size: 0.85rem;
    font-weight: 600;
  }

  /* Help trigger button */
  .help-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.82rem;
    padding: 0.35em 0.8em;
    border-radius: var(--radius);
    cursor: pointer;
    transition: all 0.15s;
  }
  .help-trigger:hover {
    color: var(--primary);
    border-color: var(--primary);
  }

  /* Modal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .modal {
    width: 480px;
    max-width: 90vw;
    max-height: 85vh;
    overflow-y: auto;
    padding: 1.5rem;
  }
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  .modal-header h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  .modal-close {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 1.1rem;
    cursor: pointer;
    padding: 0.2em;
  }
  .modal-close:hover {
    color: var(--text);
  }
  .modal ol {
    margin: 0;
    padding-left: 1.4em;
    color: var(--text-muted);
  }
  .modal li {
    margin-bottom: 0.5em;
    font-size: 0.9rem;
    line-height: 1.5;
  }
  .modal li strong {
    color: var(--text);
  }
</style>
