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
