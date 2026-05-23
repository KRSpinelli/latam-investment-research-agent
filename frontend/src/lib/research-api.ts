/** Client for the research report job API (see samples/generate_report.py). */

export type ReportJobStatus = "pending" | "running" | "completed" | "failed";

export interface ReportJobCreateResponse {
  job_id: string;
  status: ReportJobStatus;
  query: string;
}

export interface ReportJobStatusResponse {
  job_id: string;
  status: ReportJobStatus;
  query: string;
  error: string | null;
  documents_ingested: number;
  clickhouse_rows: number;
  senso_chunks: number;
}

export interface ExampleSeedsResponse {
  queries: string[];
  seed_urls: string[];
}

export const MIN_REPORT_QUERY_LENGTH = 8;
export const REPORT_POLL_INTERVAL_MS = 5000;

/** Demo question pre-mapped to a static analyst PDF for the fast-analyze flow. */
export const FAST_ANALYZE_DEMO_QUERY =
  "What are the most promising coffee exporters in brazil?";

/** Simulated analysis duration before the fast-analyze sample PDF is shown. */
export const FAST_ANALYZE_DURATION_MS = 20_000;

/** Normalize a research question for fast-analyze dictionary lookup. */
export function normalizeQueryForFastAnalyze(query: string): string {
  return query
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[?.!]+$/, "");
}

/**
 * Fast-analyze only: natural-language questions mapped to PDFs in ``frontend/public``.
 * Keys are normalized with ``normalizeQueryForFastAnalyze``.
 */
const FAST_ANALYZE_QUERY_REPORTS: Readonly<Record<string, string>> = {
  [normalizeQueryForFastAnalyze(FAST_ANALYZE_DEMO_QUERY)]: "amigo_report_full.pdf",
};

/** Resolve a static PDF for the fast-analyze flow, if the question is supported. */
export function resolveFastAnalyzeReport(
  query: string,
): { pdfPath: string; fileName: string } | null {
  const fileName = FAST_ANALYZE_QUERY_REPORTS[normalizeQueryForFastAnalyze(query)];
  if (!fileName) {
    return null;
  }
  return { pdfPath: `/${fileName}`, fileName };
}

/** Return supported fast-analyze demo questions (for UI hints). */
export function listFastAnalyzeSupportedQueries(): string[] {
  return Object.keys(FAST_ANALYZE_QUERY_REPORTS).map((normalized) => {
    if (normalized === normalizeQueryForFastAnalyze(FAST_ANALYZE_DEMO_QUERY)) {
      return FAST_ANALYZE_DEMO_QUERY;
    }
    return normalized;
  });
}

/** Progress label for the fast-analyze loading simulation. */
export function fastAnalyzeStatusForProgress(progressPercent: number): string {
  if (progressPercent < 20) return "Starting research pipeline…";
  if (progressPercent < 45) return "Crawling sources and ingesting metrics…";
  if (progressPercent < 70) return "Running ClickHouse analytics queries…";
  if (progressPercent < 88) return "Generating narrative and charts…";
  return "Rendering analyst PDF…";
}

/** API origin; empty string uses same origin (Vite dev proxy → latam-api). */
export function getApiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return (base ?? "").replace(/\/$/, "");
}

async function parseJsonError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      return body.detail.map((d) => d.msg).join("; ");
    }
  } catch {
    /* ignore */
  }
  return response.statusText || `Request failed (${response.status})`;
}

export async function fetchExampleSeeds(): Promise<ExampleSeedsResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/research/examples`);
  if (!response.ok) {
    throw new Error(await parseJsonError(response));
  }
  return response.json() as Promise<ExampleSeedsResponse>;
}

export async function createReportJob(query: string): Promise<ReportJobCreateResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/research/report/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error(await parseJsonError(response));
  }
  return response.json() as Promise<ReportJobCreateResponse>;
}

export async function fetchReportJobStatus(jobId: string): Promise<ReportJobStatusResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/research/report/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(await parseJsonError(response));
  }
  return response.json() as Promise<ReportJobStatusResponse>;
}

export async function downloadReportPdf(jobId: string): Promise<Blob> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/research/report/jobs/${jobId}/pdf`);
  if (!response.ok) {
    throw new Error(await parseJsonError(response));
  }
  return response.blob();
}

export function progressForStatus(
  status: ReportJobStatus,
  metrics: { documents_ingested: number; clickhouse_rows: number },
): number {
  switch (status) {
    case "pending":
      return 12;
    case "running":
      return Math.min(88, 28 + metrics.documents_ingested * 8 + metrics.clickhouse_rows * 2);
    case "completed":
      return 100;
    case "failed":
      return 0;
    default:
      return 0;
  }
}
