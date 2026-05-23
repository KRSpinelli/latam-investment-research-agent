import { SectionHeader } from "./Evidence";

export function ApiSection() {
  return (
    <section className="relative py-32">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid lg:grid-cols-[1fr_1.2fr] gap-12 items-center">
          <div>
            <SectionHeader
              align="left"
              eyebrow="Agent-native API"
              title={<>Pipe structured LatAm evidence <span className="italic text-gradient-emerald">into your own stack.</span></>}
              desc="Typed evidence objects, conviction scores, citations, and routing metadata — exposed via a clean REST + streaming API. Pay-per-call, observable, agent-friendly."
            />
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#" className="bg-primary text-primary-foreground rounded-full px-5 py-2.5 text-sm font-medium hover:opacity-90 transition">
                Read API docs
              </a>
              <a href="#" className="glass rounded-full px-5 py-2.5 text-sm font-medium hover:bg-white/5 transition">
                Get an API key
              </a>
            </div>

            <ul className="mt-10 space-y-3.5 text-sm">
              {[
                "Streaming evidence objects with source-linked snippets",
                "OpenAPI 3.1 spec · TypeScript & Python clients",
                "Per-call usage metering · machine-payment ready",
                "Observability: traces, evals, drift, source coverage",
              ].map((f) => (
                <li key={f} className="flex items-start gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                  <span className="text-muted-foreground">{f}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="glass-strong rounded-3xl overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-border/60">
              <div className="flex gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
              </div>
              <div className="ml-3 font-mono text-xs text-muted-foreground">POST /v1/signals</div>
              <span className="ml-auto text-[10px] font-mono uppercase text-primary/80">200 · 184ms</span>
            </div>
            <pre className="font-mono text-[12.5px] leading-[1.7] p-6 overflow-x-auto text-foreground/90">
{`{
  "signal_id": "sig_01H7XQ...K2D",
  "ticker": "SUZB3",
  "sector": "pulp & paper",
  "country": "BR",
  `}<span className="text-primary">{`"classification"`}</span>{`: `}<span className="text-accent">{`"market_moving"`}</span>{`,
  `}<span className="text-primary">{`"conviction"`}</span>{`: 0.82,
  `}<span className="text-primary">{`"thesis"`}</span>{`: `}<span className="text-accent">{`"Eucalyptus harvest pace 11% ahead`}</span>{`
            `}<span className="text-accent">{`of 5y avg; ANTAQ confirms"`}</span>{`,
  `}<span className="text-primary">{`"evidence"`}</span>{`: [
    {
      `}<span className="text-primary">{`"source"`}</span>{`: `}<span className="text-accent">{`"antaq.gov.br/..."`}</span>{`,
      `}<span className="text-primary">{`"snippet"`}</span>{`: `}<span className="text-accent">{`"Pulp export tonnage..."`}</span>{`,
      `}<span className="text-primary">{`"metric"`}</span>{`: { "value": 4.21, "unit": "Mt" },
      `}<span className="text-primary">{`"published_at"`}</span>{`: `}<span className="text-accent">{`"2026-05-22T18:00Z"`}</span>{`,
      `}<span className="text-primary">{`"confidence"`}</span>{`: 0.91
    }
    /* + 7 more */
  ]
}`}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
