const stages = [
  {
    n: "01",
    title: "Discover",
    desc: "Autonomous web crawl across filings, news, reports, regulator portals, port data, and Portuguese-language sources.",
    metric: "12.4k sources / day",
  },
  {
    n: "02",
    title: "Clean & extract",
    desc: "Documents are deduplicated, parsed, and structured. Entities, tickers, metrics, dates and geographies are pulled out.",
    metric: "94% extraction precision",
  },
  {
    n: "03",
    title: "Classify",
    desc: "Each signal gets a routing tag — market-moving, structural, noise — plus a confidence score and conviction band.",
    metric: "8 classifications · 0–1.0 confidence",
  },
  {
    n: "04",
    title: "Ground & ship",
    desc: "Memos cite the exact evidence object: URL, snippet, extracted metric, classification, model used. Nothing un-sourced.",
    metric: "100% source-linked claims",
  },
];

export function Evidence() {
  return (
    <section id="evidence" className="relative py-32">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          eyebrow="Evidence pipeline"
          title={<>From noisy web to <span className="text-gradient-warm italic">grounded signal.</span></>}
          desc="Every memo is built on a structured evidence object — not vibes, not summaries. You can audit any claim back to its primary source in one click."
        />

        <div className="mt-16 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {stages.map((s, i) => (
            <div key={s.n} className="glass rounded-2xl p-6 relative overflow-hidden group hover:bg-white/[0.06] transition">
              <div className="font-mono text-xs text-muted-foreground">{s.n}</div>
              <h3 className="mt-3 font-display text-2xl">{s.title}</h3>
              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
              <div className="mt-6 pt-4 border-t border-border/60 font-mono text-xs text-primary/90">
                {s.metric}
              </div>
              {i < stages.length - 1 && (
                <div className="hidden lg:block absolute top-1/2 -right-2 h-px w-4 bg-gradient-to-r from-border to-transparent" />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  desc,
  align = "center",
}: {
  eyebrow?: string;
  title: React.ReactNode;
  desc?: string;
  align?: "center" | "left";
}) {
  const a = align === "center" ? "text-center mx-auto" : "text-left";
  return (
    <div className={`max-w-3xl ${a}`}>
      {eyebrow && (
        <div className={`inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-primary/80 ${align === "center" ? "" : ""}`}>
          <span className="h-px w-6 bg-primary/50" />
          {eyebrow}
        </div>
      )}
      <h2 className="mt-4 font-display text-[clamp(2rem,4.5vw,3.75rem)] leading-[1] tracking-tight">{title}</h2>
      {desc && <p className="mt-5 text-lg text-muted-foreground leading-relaxed">{desc}</p>}
    </div>
  );
}
