export type Level = 'L0' | 'L1' | 'L2' | 'L3';
export type Severity = 'error' | 'warning';

export interface Issue {
  rule: string;
  level: Level;
  severity: Severity;
  target?: string;
  message: string;
  measured?: number | string | null;
  required?: number | string | null;
  hint?: string;
  /** mm, script frame (Z-up, same as part.glb before its root rotation) */
  location?: [number, number, number];
  location2?: [number, number, number];
}

export interface Round {
  n: number;
  seconds: number;
  exec_ok?: boolean;
  issues: Issue[];
  code?: string;
  /** e.g. rounds/r1.glb; absent if the round failed to execute */
  glb?: string;
  /** true when the round was reconstructed rather than recorded */
  reconstructed?: boolean;
}

export interface Feature {
  id: string;
  type: string;
  dims: Record<string, number>;
  note?: string;
}

export interface PartSpec {
  part_type?: string;
  material?: string;
  process?: string;
  features?: Feature[];
  assertions?: Record<string, unknown> & { bbox?: { x: number; y: number; z: number; tol?: number } };
  defaults_used?: string[];
  missing?: string[];
}

export interface Usage { calls?: number; prompt_tokens?: number; completion_tokens?: number }

export interface RunJson {
  status: string;
  spec?: PartSpec;
  rounds: Round[];
  final_issues?: Issue[];
  usage?: Usage;
}

export interface VersionInfo {
  version: number;
  status?: string;
  change?: string;
  /** examples: version produced by a scripted parameter edit, not by the LLM (description) */
  synthetic?: string;
  /** bytes per file name (file_sizes) */
  sizes?: Record<string, number>;
  run: RunJson | null;
  files: string[];
}

export type RunStatus = 'queued' | 'running' | 'success' | 'need_info' | 'failed' | 'error';

export interface RunSummary {
  id: string;
  title: string;
  status: RunStatus;
  created_at?: string;
  versions: number[];
  /** examples only (welcome cards) */
  request?: string;
  rounds?: number;
  thumb?: string;
  thumbFallback?: string;
}

export interface RunDetail {
  id: string;
  title: string;
  request: string;
  material?: string;
  process?: string;
  status: RunStatus;
  created_at?: string;
  readOnly: boolean;
  /** examples: which of several real runs was picked, and why (picked is 0-based) */
  selection?: { runs: number; picked: number; reason: string; reason_zh?: string; summary: Record<string, [string, number]>[] };
  versions: VersionInfo[];
}

export interface Health { ok: boolean; llm_configured: boolean; auth_required?: boolean; authenticated?: boolean }

/** SSE events, see docs/web-app.md */
export type LiveEvent =
  | { type: 'parsing' }
  | { type: 'spec'; data: PartSpec }
  | { type: 'generating' }
  | { type: 'round'; data: { n: number; seconds: number; exec_ok?: boolean; issues: Issue[]; glb?: string } }
  | { type: 'fixing'; data: { n: number } }
  | { type: 'artifact'; data: { name: string } }
  | { type: 'artifact_failed'; data: { name: string; message: string } }
  | { type: 'done'; data: { status: string; version?: number; usage?: Usage } }
  | { type: 'error'; data: { message: string } };

export const EVENT_NAMES = ['parsing', 'spec', 'generating', 'round', 'fixing', 'artifact', 'artifact_failed', 'done', 'error'] as const;
