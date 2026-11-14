import type { SpawnOptions } from "node:child_process";

export interface ProcessOptions extends SpawnOptions {
  encoding?: BufferEncoding;
  maxBuffer?: number;
}

export interface ProcessResult<T = string | Buffer> {
  status: number | null;
  error?: NodeJS.ErrnoException | null;
  stdout?: T | null;
  stderr?: T | null;
}

export interface QualityTask {
  label: string;
  command: string;
  args: string[];
  layer?: string;
  testRunner?: string;
  resource?: string;
  requireEvidence?: boolean;
  specification?: string;
  requirements?: string[];
  reasons?: string[];
}

export interface Specification {
  task?: string;
  scopes: string[];
  tasks: QualityTask[];
}

export interface Evidence {
  passed: number;
  incomplete: boolean;
}

export interface Feedback {
  identity: string | null;
  diagnostics: string[];
  suggestion: string;
  docs: string;
  requirements: string[];
}

export interface ReportedQualityTask extends QualityTask {
  status: string;
  exitCode: number | null;
  durationMs: number;
  evidence?: Evidence;
  feedback?: Feedback | null;
}

export interface QualityReport {
  version: number;
  status: string;
  excludedLayers: string[];
  tasks: ReportedQualityTask[];
}

export type ExecutionResult = ProcessResult;
export type Executor = (
  command: string,
  args: string[],
  options: ProcessOptions,
) => ExecutionResult | Promise<ExecutionResult>;

export function processError(error: unknown): NodeJS.ErrnoException {
  return error instanceof Error ? error : new Error(String(error));
}
