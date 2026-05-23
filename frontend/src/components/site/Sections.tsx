import { SectionHeader } from "./Evidence";

export function Stats() {
  return (
    <section className="relative py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="glass-strong rounded-3xl p-10 md:p-14 relative overflow-hidden noise">
          <div className="absolute -top-32 -right-32 h-72 w-72 rounded-full bg-primary/20 blur-3xl" />
          <div className="grid md:grid-cols-4 gap-10 relative">
            {[
              ["12.4k", "sources crawled daily"],
              ["4", "sectors live across LatAm"],
              ["0.94", "average extraction precision"],
              ["100%", "claims linked to evidence"],
            ].map(([n, l]) => (
              <div key={l}>
                <div className="font-display text-5xl md:text-6xl text-gradient-emerald">{n}</div>
                <div className="mt-3 text-sm text-muted-foreground max-w-[14ch]">{l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export function WhoFor() {
  const personas = [
    { who: "Hedge funds", desc: "Underfollowed LatAm signals before they hit Bloomberg." },
    { who: "PE & VC", desc: "Diligence on LatAm targets with sourced evidence packets." },
    { who: "Commodity desks", desc: "Soy, sugar, pulp, iron ore — port to processor." },
    { who: "Macro teams", desc: "Country-level structural reads with citations." },
    { who: "Quant teams", desc: "Typed evidence objects piped into your factor stack." },
    { who: "AI agents", desc: "Machine-payment ready API for autonomous research." },
  ];
  return (
    <section className="relative py-32">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          eyebrow="Built for"
          title={<>Institutional research workflows, <span className="italic text-gradient-warm">not vibes.</span></>}
        />
        <div className="mt-14 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {personas.map((p) => (
            <div key={p.who} className="glass rounded-2xl p-6 hover:bg-white/[0.06] transition">
              <div className="font-display text-2xl">{p.who}</div>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{p.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function CTA() {
  return (
    <section className="relative py-24">
      <div className="mx-auto max-w-5xl px-6">
        <div className="glass-strong rounded-3xl p-12 md:p-16 text-center relative overflow-hidden">
          <div className="absolute inset-0 -z-10 aurora-bg opacity-60" />
          <div className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-primary/90">
            <span className="h-1.5 w-1.5 rounded-full bg-primary pulse-dot" /> Closed preview · 18 firms onboarded
          </div>
          <h2 className="mt-5 font-display text-[clamp(2.25rem,5vw,4.5rem)] leading-[0.98]">
            See the agent run on a <span className="italic text-gradient-emerald">real thesis.</span>
          </h2>
          <p className="mt-5 max-w-xl mx-auto text-muted-foreground">
            We'll generate a full grounded memo on a LatAm ticker of your choice — usually back within 24 hours.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <a href="/contact" className="bg-primary text-primary-foreground rounded-full px-6 py-3 text-sm font-medium hover:opacity-90 transition glow-emerald">
              Request a sample memo
            </a>
            <a href="/methodology" className="glass rounded-full px-6 py-3 text-sm font-medium hover:bg-white/5 transition">
              Read methodology
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
