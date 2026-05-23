import { createFileRoute, Link } from "@tanstack/react-router";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";
import { Background } from "@/components/site/Background";
import { SectionHeader } from "@/components/site/Evidence";
import agri from "@/assets/ex-agri.jpg";
import logistics from "@/assets/ex-logistics.jpg";
import energy from "@/assets/ex-energy.jpg";

export const Route = createFileRoute("/research")({
  head: () => ({
    meta: [
      { title: "Research Hub — LatAm Alpha Agent" },
      { name: "description", content: "Brazil sector intelligence — agriculture, logistics, energy, infrastructure. Grounded, sourced, updated weekly." },
      { property: "og:title", content: "Research Hub — LatAm Alpha Agent" },
      { property: "og:description", content: "Brazil sector intelligence — agriculture, logistics, energy, infrastructure." },
    ],
  }),
  component: ResearchPage,
});

const memos = [
  { sector: "Agriculture", title: "Soy export pace running 12% above 5y average — port congestion forming at Santos", date: "May 22, 2026", conf: 0.84, img: agri },
  { sector: "Logistics", title: "Rumo grain rail throughput hits decade high; FX pass-through still favorable", date: "May 18, 2026", conf: 0.79, img: logistics },
  { sector: "Energy", title: "Hydro reservoirs at 67% — ethanol crush spread tightening into Q3", date: "May 14, 2026", conf: 0.71, img: energy },
  { sector: "Agriculture", title: "CONAB revises corn estimate +3.4 Mt; implications for global feed balance", date: "May 9, 2026", conf: 0.81, img: agri },
  { sector: "Logistics", title: "ANTAQ port stats: Paranaguá throughput up 18% YoY on soy complex", date: "May 5, 2026", conf: 0.76, img: logistics },
  { sector: "Energy", title: "Pre-salt production crosses 3 mbd; ANP filings confirm Búzios ramp", date: "May 1, 2026", conf: 0.88, img: energy },
];

function ResearchPage() {
  return (
    <div className="relative min-h-screen">
      <Background />
      <Nav />
      <main className="pt-36 pb-24">
        <div className="mx-auto max-w-7xl px-6">
          <SectionHeader
            align="left"
            eyebrow="Research hub"
            title={<>Brazil intelligence, <span className="italic text-gradient-emerald">published openly.</span></>}
            desc="A growing library of grounded memos across our four coverage sectors. Every claim is source-linked."
          />

          <div className="mt-10 flex flex-wrap gap-2">
            {["All", "Agriculture", "Logistics", "Energy", "Infrastructure", "Macro"].map((t, i) => (
              <button key={t} className={`text-xs font-mono uppercase tracking-wider px-3.5 py-1.5 rounded-full transition ${i === 0 ? "bg-primary text-primary-foreground" : "glass hover:bg-white/5"}`}>
                {t}
              </button>
            ))}
          </div>

          <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {memos.map((m, i) => (
              <Link to="/research" key={i} className="group glass rounded-3xl overflow-hidden hover:bg-white/[0.06] transition">
                <div className="relative aspect-[16/10] overflow-hidden m-3 rounded-2xl">
                  <img src={m.img} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition duration-700 group-hover:scale-[1.04]" />
                  <div className="absolute top-3 left-3 glass-strong rounded-full px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider">{m.sector}</div>
                  <div className="absolute bottom-3 right-3 glass-strong rounded-full px-2.5 py-1 text-[10px] font-mono text-primary/90">conf {m.conf}</div>
                </div>
                <div className="px-6 pb-6 pt-1">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{m.date}</div>
                  <h3 className="mt-2 font-display text-xl leading-tight">{m.title}</h3>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
