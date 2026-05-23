import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  createReportJob,
  downloadReportPdf,
  fetchExampleSeeds,
  fetchReportJobStatus,
  MIN_REPORT_QUERY_LENGTH,
  progressForStatus,
  REPORT_POLL_INTERVAL_MS,
  type ReportJobStatusResponse,
} from "@/lib/research-api";

type Phase = "idle" | "submitting" | "polling" | "completed" | "failed";

const DEFAULT_PLACEHOLDER =
  "What were total export revenues by year for coffee exporters in LatAm?";

export function ReportQuery() {
  const [query, setQuery] = useState("");
  const [examples, setExamples] = useState<string[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<ReportJobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchExampleSeeds()
      .then((data) => setExamples(data.queries.slice(0, 3)))
      .catch(() => {
        /* examples are optional */
      });
  }, []);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const pollOnce = useCallback(
    async (id: string) => {
      const status = await fetchReportJobStatus(id);
      setJobStatus(status);
      if (status.status === "completed") {
        stopPolling();
        setPhase("completed");
      } else if (status.status === "failed") {
        stopPolling();
        setPhase("failed");
        setError(status.error ?? "Report generation failed.");
      }
    },
    [stopPolling],
  );

  useEffect(() => {
    if (phase !== "polling" || !jobId) return;

    void pollOnce(jobId);
    pollTimerRef.current = setInterval(() => {
      void pollOnce(jobId).catch((pollError: unknown) => {
        stopPolling();
        setPhase("failed");
        setError(pollError instanceof Error ? pollError.message : "Could not reach the API.");
      });
    }, REPORT_POLL_INTERVAL_MS);

    return () => stopPolling();
  }, [phase, jobId, pollOnce, stopPolling]);

  const trimmed = query.trim();
  const canSubmit =
    trimmed.length >= MIN_REPORT_QUERY_LENGTH && phase !== "submitting" && phase !== "polling";

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setError(null);
    setJobStatus(null);
    setJobId(null);
    setPhase("submitting");

    try {
      const created = await createReportJob(trimmed);
      setJobId(created.job_id);
      setJobStatus({
        job_id: created.job_id,
        status: created.status,
        query: created.query,
        error: null,
        documents_ingested: 0,
        clickhouse_rows: 0,
        senso_chunks: 0,
      });
      setPhase("polling");
    } catch (submitError: unknown) {
      setPhase("idle");
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Could not start the report. Is the API running?",
      );
    }
  }

  async function handleDownload() {
    if (!jobId) return;
    try {
      const blob = await downloadReportPdf(jobId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `amigo-report-${jobId.slice(0, 8)}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (downloadError: unknown) {
      setError(
        downloadError instanceof Error ? downloadError.message : "Could not download the PDF.",
      );
    }
  }

  function handleReset() {
    stopPolling();
    setPhase("idle");
    setJobId(null);
    setJobStatus(null);
    setError(null);
  }

  const isBusy = phase === "submitting" || phase === "polling";
  const progress =
    jobStatus !== null
      ? progressForStatus(jobStatus.status, jobStatus)
      : phase === "submitting"
        ? 6
        : 0;

  return (
    <div id="report" className="mx-auto mt-12 max-w-2xl">
      <form onSubmit={(e) => void handleSubmit(e)} className="glass-strong rounded-3xl p-6 md:p-8">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-wider text-primary/90">
              Try it now
            </p>
            <h2 className="mt-1 font-display text-2xl tracking-tight">
              Generate a grounded report
            </h2>
          </div>
          <span className="hidden sm:inline glass rounded-full px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            No sign-in
          </span>
        </div>

        <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
          Ask a research question. We crawl sources, ingest metrics, and deliver a PDF analyst memo
          — same flow as{" "}
          <code className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-xs">
            generate_report.py
          </code>
          .
        </p>

        <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={examples[0] ?? DEFAULT_PLACEHOLDER}
          rows={3}
          disabled={isBusy}
          className="mt-5 min-h-[88px] resize-y rounded-2xl border-border/60 bg-background/40 text-base"
          aria-label="Research question"
        />

        {examples.length > 0 && phase === "idle" && (
          <div className="mt-3 flex flex-wrap gap-2">
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuery(example)}
                className="glass rounded-full px-3 py-1 text-left text-xs text-muted-foreground hover:bg-white/5 hover:text-foreground transition"
              >
                {example.length > 72 ? `${example.slice(0, 72)}…` : example}
              </button>
            ))}
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={!canSubmit} className="rounded-full px-6 glow-emerald">
            {isBusy ? (
              <>
                <Loader2 className="animate-spin" />
                {phase === "submitting" ? "Starting…" : "Generating…"}
              </>
            ) : (
              "Generate report"
            )}
          </Button>
          {(phase === "completed" || phase === "failed") && (
            <Button type="button" variant="ghost" className="rounded-full" onClick={handleReset}>
              New question
            </Button>
          )}
          {trimmed.length > 0 && trimmed.length < MIN_REPORT_QUERY_LENGTH && (
            <span className="text-xs text-muted-foreground">
              At least {MIN_REPORT_QUERY_LENGTH} characters
            </span>
          )}
        </div>

        {(isBusy || phase === "completed" || phase === "failed") && (
          <div className="mt-6 space-y-3 border-t border-border/60 pt-6">
            <Progress value={progress} className="h-1.5" />
            {jobStatus && (
              <p className="font-mono text-xs text-muted-foreground">
                <span className="text-primary/90 uppercase">{jobStatus.status}</span>
                {jobId && (
                  <>
                    {" "}
                    · job {jobId.slice(0, 8)}… · docs {jobStatus.documents_ingested} · rows{" "}
                    {jobStatus.clickhouse_rows}
                  </>
                )}
              </p>
            )}
            {phase === "completed" && (
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                onClick={() => void handleDownload()}
              >
                Download PDF
              </Button>
            )}
          </div>
        )}

        {error && (
          <p className="mt-4 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
            {phase === "idle" && (
              <span className="mt-1 block text-muted-foreground">
                Start the API with <code className="font-mono text-xs">uv run latam-api</code> (port
                8000).
              </span>
            )}
          </p>
        )}
      </form>
    </div>
  );
}
