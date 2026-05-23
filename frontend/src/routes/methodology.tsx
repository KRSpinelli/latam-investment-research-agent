import { createFileRoute } from "@tanstack/react-router";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";
import { Background } from "@/components/site/Background";
import { SectionHeader } from "@/components/site/Evidence";
import pipeline from "@/assets/ex-pipeline.jpg";

export const Route = createFileRoute("/methodology")({
  head: () => ({
    meta: [
      { title: "Methodology — Amigo.ai" },
      { name: "description", content: "How the agent discovers, extracts, classifies and grounds LatAm market intelligence. Evidence-first by design." },
      { property: "og:title", content: "Methodology — Amigo.ai" },
      { property: "og:description", content: "Evidence-first AI research analyst for emerging markets. Here's how it works." },
    ],
  }),
  component: MethodologyPage,
});

function MethodologyPage() {
  return (
    <div className="relative min-h-screen">
      <Background />
      <Nav />
      <main className="pt-36 pb-24">
        <div className="mx-auto max-w-5xl px-6">
          <SectionHeader
            align="left"
            eyebrow="Methodology"
            title={<>How we turn the open web into <span className="italic text-gradient-emerald">grounded signal.</span></>}
            desc="The agent is a pipeline, not a chatbot. Six stages, each observable, each leaving a structured evidence trail."
          />

          <div className="mt-12 relative glass-strong rounded-3xl overflow-hidden aspect-[16/9]">
            <img src={pipeline} alt="Evidence pipeline" className="absolute inset-0 h-full w-full object-cover opacity-80" />
          </div>

          <div className="mt-16 space-y-12">
            {[
              { n: "01", t: "Source discovery", b: "Curated source registry across Portuguese and English: regulator portals (ANP, ANTAQ, ANEEL, ANATEL, BNDES), exchanges (B3), agencies (CONAB, IBGE), top financial press, sell-side research, and machine-readable filings. Plus autonomous link-following on emerging sources." },
              { n: "02", t: "Crawl & normalize", b: "Polite, deduplicating crawler. PDFs, HTML, structured filings all normalized into a canonical document object with provenance, timestamps and hashes preserved." },
              { n: "03", t: "Entity & metric extraction", b: "LLM-based extraction with schema validation. Tickers, companies, geographies, metrics with units, dates and event types are pulled into typed fields. Failed parses are flagged, not silently dropped." },
              { n: "04", t: "Classification & routing", b: "Each candidate signal is classified across 8 axes (market-moving, structural, regulatory, noise, etc.) and assigned a conviction band. Confidence is calibrated against held-out historical outcomes." },
              { n: "05", t: "Evidence packaging", b: "Every claim that downstream systems will surface gets packaged as an evidence object: source URL, exact snippet, extracted metric, classification, confidence, model used, timestamp. Nothing un-sourced ships." },
              { n: "06", t: "Memo synthesis", b: "Analysis agents compose memos by retrieving evidence packets, not by hallucinating. Every assertion in the memo is rendered with an inline citation back to the evidence object." },
            ].map((s) => (
              <div key={s.n} className="grid md:grid-cols-[120px_1fr] gap-6 md:gap-12 pb-12 border-b border-border/60 last:border-0">
                <div className="font-mono text-sm text-primary/80">{s.n}</div>
                <div>
                  <h3 className="font-display text-3xl">{s.t}</h3>
                  <p className="mt-3 text-muted-foreground leading-relaxed">{s.b}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
