/** Atlas API client – all calls go to the same origin. */
import type {
  ExtractOptions,
  ExtractResult,
  HealthResponse,
  IndexOptions,
  IndexResult,
  ListChatResponse,
  ListVideosResponse,
  QueueListResponse,
  SearchResponse,
  StatsResponse,
  Task,
  TranscribeOptions,
  TranscribeResult,
  Video,
} from "./types.ts";

const BASE = "";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = (await res
      .json()
      .catch(() => ({ detail: res.statusText }))) as { detail?: unknown };
    throw new Error(err.detail ? JSON.stringify(err.detail) : res.statusText);
  }
  return res.json() as Promise<T>;
}

async function postForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(BASE + path, { method: "POST", body: formData });
  if (!res.ok) {
    const err = (await res
      .json()
      .catch(() => ({ detail: res.statusText }))) as { detail?: unknown };
    throw new Error(err.detail ? JSON.stringify(err.detail) : res.statusText);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) {
    const err = (await res
      .json()
      .catch(() => ({ detail: res.statusText }))) as { detail?: unknown };
    throw new Error(err.detail ? JSON.stringify(err.detail) : res.statusText);
  }
  return res.json() as Promise<T>;
}

// ── Mutating endpoints ────────────────────────────────────────────────────────

export function transcribe(
  file: File,
  opts: TranscribeOptions = {},
): Promise<TranscribeResult> {
  const fd = new FormData();
  fd.append("video", file);
  fd.append("format", opts.format ?? "text");
  fd.append("benchmark", String(opts.benchmark ?? false));
  fd.append("no_queue", String(opts.no_queue ?? true));
  fd.append("no_streaming", String(opts.no_streaming ?? true));
  if (opts.output) fd.append("output", opts.output);
  return postForm<TranscribeResult>("/transcribe", fd);
}

export function extract(
  file: File,
  opts: ExtractOptions = {},
): Promise<ExtractResult> {
  const fd = new FormData();
  fd.append("video", file);
  fd.append("chunk_duration", opts.chunk_duration ?? "15s");
  fd.append("overlap", opts.overlap ?? "1s");
  fd.append("format", opts.format ?? "json");
  fd.append("include_summary", String(opts.include_summary ?? true));
  fd.append("benchmark", String(opts.benchmark ?? false));
  fd.append("no_queue", String(opts.no_queue ?? true));
  fd.append("no_streaming", String(opts.no_streaming ?? true));
  if (opts.attrs) fd.append("attrs", opts.attrs);
  if (opts.output) fd.append("output", opts.output);
  return postForm<ExtractResult>("/extract", fd);
}

export function indexVideo(
  file: File,
  opts: IndexOptions = {},
): Promise<IndexResult> {
  const fd = new FormData();
  fd.append("video", file);
  fd.append("chunk_duration", opts.chunk_duration ?? "15s");
  fd.append("overlap", opts.overlap ?? "1s");
  fd.append("include_summary", String(opts.include_summary ?? true));
  fd.append("benchmark", String(opts.benchmark ?? false));
  fd.append("no_queue", String(opts.no_queue ?? true));
  fd.append("no_streaming", String(opts.no_streaming ?? true));
  if (opts.attrs) fd.append("attrs", opts.attrs);
  return postForm<IndexResult>("/index", fd);
}

// ── Read-only endpoints ───────────────────────────────────────────────────────

export const search = (
  query: string,
  video_id: string | null = null,
  top_k = 10,
): Promise<SearchResponse> =>
  post<SearchResponse>("/search", { query, video_id, top_k });

export const listVideos = (): Promise<ListVideosResponse> =>
  get<ListVideosResponse>("/list-videos");
export const getVideo = (id: string): Promise<{ data?: Video } & Video> =>
  get<{ data?: Video } & Video>(`/get-video/${id}`);
export const listChat = (id: string, last_n = 50): Promise<ListChatResponse> =>
  get<ListChatResponse>(`/list-chat/${id}?last_n=${last_n}`);
export const stats = (): Promise<StatsResponse> => get<StatsResponse>("/stats");
export const health = (): Promise<HealthResponse> =>
  get<HealthResponse>("/health");
export const queueList = (
  status: string | null = null,
): Promise<QueueListResponse> =>
  get<QueueListResponse>("/queue/list" + (status ? `?status=${status}` : ""));
export const queueStatus = (id: string): Promise<Task> =>
  get<Task>(`/queue/status/${id}`);

// ── SSE chat stream ───────────────────────────────────────────────────────────

export function chatStream(
  videoId: string,
  query: string,
  onChunk: (chunk: string) => void,
  onDone: () => void,
): AbortController {
  const ctrl = new AbortController();
  fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_id: videoId, query }),
    signal: ctrl.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(await res.text());
      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (line.startsWith("data: ")) onChunk(line.slice(6));
        }
      }
      onDone();
    })
    .catch((err: unknown) => {
      if (err instanceof Error && err.name !== "AbortError")
        onChunk(`\n[Error: ${err.message}]`);
      onDone();
    });
  return ctrl;
}
