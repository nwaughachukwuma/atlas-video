// ── Domain models ─────────────────────────────────────────────────────────────

export interface VideoChunk {
  start_time?: string | number;
  end_time?: string | number;
  description?: string;
  transcript?: string;
  summary?: string;
  [key: string]: unknown;
}

export interface Video {
  video_id: string;
  indexed_at?: string;
  chunk_count?: number;
  chunks?: VideoChunk[];
  [key: string]: unknown;
}

export interface ListVideosResponse {
  videos: Video[];
  count: number;
}

// ── Queue / Tasks ─────────────────────────────────────────────────────────────

export type TaskStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "timeout";

export interface Task {
  id: string;
  command: string;
  label: string;
  status: TaskStatus;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  duration?: string | number;
  error?: string;
  output_path?: string;
  /** Present on some queue responses that mirror the task */
  task_id?: string;
}

export interface QueueListResponse {
  tasks: Task[];
}

// ── Search ────────────────────────────────────────────────────────────────────

export interface SearchResult {
  video_id: string;
  score?: number;
  content?: string;
  start_time?: number;
  end_time?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  count: number;
}

// ── System ────────────────────────────────────────────────────────────────────

export interface StatsResponse {
  videos_indexed?: number;
  video_col_path?: string;
  chat_col_path?: string;
  video_index_stats?: string;
  chat_index_stats?: string;
}

export interface HealthResponse {
  status: "ok" | "error";
  [key: string]: unknown;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

export interface RawChatMessage {
  role?: string;
  query?: string;
  content?: string;
  answer?: string;
}

export interface ListChatResponse {
  messages: RawChatMessage[];
}

// ── API options ───────────────────────────────────────────────────────────────

export interface TranscribeOptions {
  format?: string;
  benchmark?: boolean;
  no_queue?: boolean;
  no_streaming?: boolean;
  output?: string;
}

export interface ExtractOptions {
  chunk_duration?: string;
  overlap?: string;
  format?: string;
  include_summary?: boolean;
  benchmark?: boolean;
  no_queue?: boolean;
  no_streaming?: boolean;
  attrs?: string;
  output?: string;
}

export interface IndexOptions {
  chunk_duration?: string;
  overlap?: string;
  include_summary?: boolean;
  benchmark?: boolean;
  no_queue?: boolean;
  no_streaming?: boolean;
  attrs?: string;
}

// ── API result shapes ─────────────────────────────────────────────────────────

/** Returned when a task is enqueued instead of run immediately. */
export interface TaskQueuedResult {
  task_id?: string;
  id?: string;
  error?: string;
}

export interface TranscribeResult extends TaskQueuedResult {
  transcript?: string;
  [key: string]: unknown;
}

export interface ExtractResult extends TaskQueuedResult {
  chunks?: VideoChunk[];
  summary?: string;
  [key: string]: unknown;
}

export interface IndexResult extends TaskQueuedResult {
  video_id?: string;
  indexed_count?: number;
  result?: unknown;
}

// ── NavBar ────────────────────────────────────────────────────────────────────

import type { ComponentType } from "svelte";

export interface NavLink {
  path: string;
  icon: ComponentType;
  label: string;
  title: string;
}

export interface Feature {
  path: string;
  icon: ComponentType;
  title: string;
  desc: string;
}

export interface Step {
  num: string;
  action: string;
  detail: string;
}
