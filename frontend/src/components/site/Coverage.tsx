import { SectionHeader } from "./Evidence";

export function Coverage() {
  const clusters = [
    {
      name: "Agriculture",
      tag: "P0 wedge",
      sources: ["CONAB", "USDA Brazil desk", "B3 grain futures", "Santos port data", "Satellite NDVI"],
      kpis: [["Coverage", "78%"], ["Sources", "412"], ["Daily metrics", "8.2k"]],
    },
    {
      name: "Logistics",
      tag: "P0 wedge",
      sources: ["ANTAQ port stats", "Rumo / VLI rail", "ANTT trucking", "Customs filings", "AIS vessel data"],
      kpis: [["Coverage", "71%"], ["Sources", "286"], ["Daily metrics", "5.4k"]],
    },
    {
      name: "Energy",
      tag: "Live",
      sources: ["ANP filings", "ONS dispatch", "Petrobras reports", "Hydro reservoirs", "Ethanol UNICA"],
      kpis: [["Coverage", "64%"], ["Sources", "198"], ["Daily metrics", "3.1k"]],
    },
    {
      name: "Infrastructure",
      tag: "Roadmap",
      sources: ["BNDES disbursements", "PPP concessions", "ANEEL auctions", "ANATEL filings"],
      kpis: [["Coverage", "42%"], ["Sources", "104"], ["Daily metrics", "1.2k"]],
    },
  ];

  return (
    <section className="relative py-32">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          eyebrow="Coverage"
          title={<>Four sectors. <span className="italic text-gradient-warm">One Brazil.</span></>}
          desc="We start where the alpha lives — sectors where Brazil is structurally global, but coverage in English is structurally thin."
        />

        <div className="mt-14 grid gap-4 md:grid-cols-2">
          {clusters.map((c) => (
            <div key={c.name} className="glass rounded-3xl p-7 hover:bg-white/[0.06] transition">
              <div className="flex items-start justify-between">
                <h3 className="font-display text-3xl">{c.name}</h3>
                <span className="text-[10px] font-mono uppercase tracking-wider px-2.5 py-1 rounded-full glass-strong text-primary/90">
                  {c.tag}
                </span>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-3">
                {c.kpis.map(([k, v]) => (
                  <div key={k}>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{k}</div>
                    <div className="mt-1 font-display text-2xl">{v}</div>
                  </div>
                ))}
              </div>

              <div className="mt-6 pt-6 border-t border-border/60">
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-3">Sources include</div>
                <div className="flex flex-wrap gap-1.5">
                  {c.sources.map((s) => (
                    <span key={s} className="text-xs px-2.5 py-1 rounded-full bg-white/[0.04] border border-border/60">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
