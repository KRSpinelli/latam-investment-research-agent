import { SectionHeader } from "./Evidence";
import agri from "@/assets/ex-agri.jpg";
import logistics from "@/assets/ex-logistics.jpg";
import energy from "@/assets/ex-energy.jpg";
import memo from "@/assets/ex-memo.jpg";
import signals from "@/assets/ex-signals.jpg";
import api from "@/assets/ex-api.jpg";

const examples = [
  {
    img: memo,
    tag: "Research memo",
    title: "LatAm soy export thesis Q3",
    desc: "Full grounded memo with 14 evidence objects, confidence 0.82, ready to drop into the IC deck.",
    accent: "emerald",
  },
  {
    img: signals,
    tag: "Live signal feed",
    title: "Underfollowed LatAm tickers",
    desc: "Real-time signal stream with classification, conviction band, and one-click drill into the source evidence.",
    accent: "amber",
  },
  {
    img: agri,
    tag: "Sector cluster",
    title: "Agriculture intelligence",
    desc: "Yield, planting pace, FX exposure, port congestion — assembled across CONAB, USDA and satellite providers.",
    accent: "emerald",
  },
  {
    img: logistics,
    tag: "Sector cluster",
    title: "Logistics & ports",
    desc: "Santos, Paranaguá, Itaqui throughput plus inland rail and trucking pace. Surfaces backlogs before consensus.",
    accent: "amber",
  },
  {
    img: energy,
    tag: "Sector cluster",
    title: "Energy & infrastructure",
    desc: "Pre-salt production, ethanol crush spreads, hydro reservoir levels, and ANEEL filings synthesized weekly.",
    accent: "emerald",
  },
  {
    img: api,
    tag: "Developer workflow",
    title: "Agent-native API",
    desc: "Pull structured evidence objects into your own agent or quant pipeline. Pay-per-call, observable, typed.",
    accent: "amber",
  },
];

export function Examples() {
  return (
    <section id="examples" className="relative py-32">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex items-end justify-between gap-8 flex-wrap">
          <SectionHeader
            align="left"
            eyebrow="Workflow examples"
            title={<>Built for the way <span className="italic text-gradient-emerald">analysts actually work.</span></>}
            desc="Six concrete workflows the agent ships day-one. Each one is a real surface — memos, signals, sector hubs, API."
          />
          <a href="#" className="hidden md:inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition">
            View all workflows <span aria-hidden>→</span>
          </a>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {examples.map((e) => (
            <article
              key={e.title}
              className="group glass rounded-3xl overflow-hidden hover:bg-white/[0.06] transition flex flex-col"
            >
              <div className="relative aspect-[4/3] overflow-hidden m-3 rounded-2xl bg-card">
                <img
                  src={e.img}
                  alt={e.title}
                  loading="lazy"
                  className="absolute inset-0 h-full w-full object-cover transition duration-700 group-hover:scale-[1.04]"
                />
                <div className="absolute top-3 left-3 glass-strong rounded-full px-3 py-1 text-[10px] font-mono uppercase tracking-wider">
                  {e.tag}
                </div>
              </div>
              <div className="px-6 pb-6 pt-2">
                <h3 className="font-display text-2xl leading-tight">{e.title}</h3>
                <p className="mt-2.5 text-sm text-muted-foreground leading-relaxed">{e.desc}</p>
                <div className="mt-5 flex items-center justify-between">
                  <span className={`text-xs font-mono uppercase tracking-wider ${e.accent === "emerald" ? "text-primary/80" : "text-accent/90"}`}>
                    Open workflow
                  </span>
                  <span className="h-7 w-7 rounded-full glass flex items-center justify-center text-xs group-hover:translate-x-0.5 transition">→</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
