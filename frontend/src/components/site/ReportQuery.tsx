import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  createReportJob,
  downloadReportPdf,
  FAST_ANALYZE_DEMO_QUERY,
  FAST_ANALYZE_DURATION_MS,
  fastAnalyzeStatusForProgress,
  fetchExampleSeeds,
  fetchReportJobStatus,
  listFastAnalyzeSupportedQueries,
  MIN_REPORT_QUERY_LENGTH,
  progressForStatus,
  REPORT_POLL_INTERVAL_MS,
  resolveFastAnalyzeReport,
  type ReportJobStatusResponse,
} from "@/lib/research-api";

type Phase =
  | "idle"
  | "submitting"
  | "polling"
  | "completed"
  | "failed"
  | "fast_loading"
  | "fast";

const DEFAULT_PLACEHOLDER =
  "What were total export revenues by year for coffee exporters in LatAm?";

export function ReportQuery() {
  const [query, setQuery] = useState(FAST_ANALYZE_DEMO_QUERY);
  const [examples, setExamples] = useState<string[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<ReportJobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fastProgress, setFastProgress] = useState(0);
  const [activeFastReport, setActiveFastReport] = useState<{
    pdfPath: string;
    fileName: string;
  } | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fastAnalyzeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fastAnalyzeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopFastAnalyzeSimulation = useCallback(() => {
    if (fastAnalyzeTimerRef.current !== null) {
      clearTimeout(fastAnalyzeTimerRef.current);
      fastAnalyzeTimerRef.current = null;
    }
    if (fastAnalyzeIntervalRef.current !== null) {
      clearInterval(fastAnalyzeIntervalRef.current);
      fastAnalyzeIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    fetchExampleSeeds()
      .then((data) => setExamples(data.queries.slice(0, 3)))
      .catch(() => {
        /* examples are optional */
      });
  }, []);

  useEffect(() => () => stopFastAnalyzeSimulation(), [stopFastAnalyzeSimulation]);

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
  const isReportJobBusy = phase === "submitting" || phase === "polling";
  const isBusy = isReportJobBusy || phase === "fast_loading";
  const canSubmit = trimmed.length >= MIN_REPORT_QUERY_LENGTH && !isBusy;
  const fastAnalyzeReport = resolveFastAnalyzeReport(trimmed);
  const fastAnalyzeSupportedQueries = listFastAnalyzeSupportedQueries();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    stopFastAnalyzeSimulation();
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

  function handleFastAnalyze() {
    const resolvedReport = resolveFastAnalyzeReport(trimmed);
    if (!resolvedReport) {
      setError(
        "Fast analyze is available only for supported demo questions. Try the Brazil coffee exporters query.",
      );
      return;
    }

    stopPolling();
    stopFastAnalyzeSimulation();
    setError(null);
    setJobId(null);
    setJobStatus(null);
    setActiveFastReport(resolvedReport);
    setFastProgress(8);
    setPhase("fast_loading");

    const startedAt = Date.now();
    fastAnalyzeIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const progressRatio = Math.min(1, elapsed / FAST_ANALYZE_DURATION_MS);
      setFastProgress(8 + progressRatio * 87);
    }, 400);

    fastAnalyzeTimerRef.current = setTimeout(() => {
      stopFastAnalyzeSimulation();
      setFastProgress(100);
      setPhase("fast");
    }, FAST_ANALYZE_DURATION_MS);
  }

  function handleReset() {
    stopPolling();
    stopFastAnalyzeSimulation();
    setPhase("idle");
    setJobId(null);
    setJobStatus(null);
    setError(null);
    setFastProgress(0);
    setActiveFastReport(null);
  }

  const progress =
    phase === "fast_loading"
      ? fastProgress
      : jobStatus !== null
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

        {phase === "idle" && (
          <div className="mt-3 flex flex-wrap gap-2">
            {fastAnalyzeSupportedQueries.map((supportedQuery) => (
              <button
                key={`fast-${supportedQuery}`}
                type="button"
                onClick={() => setQuery(supportedQuery)}
                className="glass rounded-full px-3 py-1 text-left text-xs text-primary/90 hover:bg-white/5 transition"
              >
                {supportedQuery.length > 72 ? `${supportedQuery.slice(0, 72)}…` : supportedQuery}
              </button>
            ))}
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
            {isReportJobBusy ? (
              <>
                <Loader2 className="animate-spin" />
                {phase === "submitting" ? "Starting…" : "Generating…"}
              </>
            ) : (
              "Generate report"
            )}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="rounded-full px-6"
            disabled={
              phase === "fast_loading" || phase === "fast" || fastAnalyzeReport === null
            }
            onClick={handleFastAnalyze}
          >
            {phase === "fast_loading" ? (
              <>
                <Loader2 className="animate-spin" />
                Analyzing…
              </>
            ) : (
              "Fast analyze"
            )}
          </Button>
          {(phase === "completed" ||
            phase === "failed" ||
            phase === "fast" ||
            phase === "fast_loading") && (
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

        {phase === "fast" && activeFastReport && (
          <div className="mt-6 space-y-4 border-t border-border/60 pt-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="font-mono text-xs uppercase tracking-wider text-primary/90">
                Analyst report ready
              </p>
              <a
                href={activeFastReport.pdfPath}
                download={activeFastReport.fileName}
                className="text-xs text-muted-foreground underline-offset-4 hover:underline"
              >
                Download PDF
              </a>
            </div>
            <iframe
              src={activeFastReport.pdfPath}
              title="Amigo analyst report"
              className="h-[min(80vh,900px)] w-full rounded-2xl border border-border/60 bg-background/40"
            />
          </div>
        )}

        {(isBusy || phase === "completed" || phase === "failed") && (
          <div className="mt-6 space-y-3 border-t border-border/60 pt-6">
            <Progress value={progress} className="h-1.5" />
            {phase === "fast_loading" ? (
              <p className="font-mono text-xs text-muted-foreground">
                <span className="text-primary/90 uppercase">running</span>
                {" · "}
                {fastAnalyzeStatusForProgress(fastProgress)}
              </p>
            ) : (
              jobStatus && (
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
              )
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
            {phase === "idle" && !error.startsWith("Fast analyze") && (
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
