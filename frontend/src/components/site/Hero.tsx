import heroImg from "@/assets/hero-ambient.jpg";
import { ReportQuery } from "@/components/site/ReportQuery";

export function Hero() {
  return (
    <section className="relative pt-36 pb-24 overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <img
          src={heroImg}
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-50 [mask-image:radial-gradient(ellipse_at_center,black_40%,transparent_75%)]"
        />
      </div>

      <div className="mx-auto max-w-7xl px-6">
        <div className="flex justify-center mb-8">
          <div className="glass rounded-full pl-1.5 pr-4 py-1 flex items-center gap-2.5 text-xs">
            <span className="bg-primary/15 text-primary rounded-full px-2.5 py-0.5 font-mono uppercase tracking-wider">v0.4 · live</span>
            <span className="text-muted-foreground">Now indexing LatAm agriculture, logistics, energy</span>
          </div>
        </div>

        <h1 className="font-display text-center text-[clamp(2.75rem,7vw,6.5rem)] leading-[0.95] tracking-tight">
          Find underfollowed{" "}
          <span className="text-gradient-emerald italic">LatAm signals</span>
          <br />
          before consensus catches up.
        </h1>

        <p className="mx-auto mt-8 max-w-2xl text-center text-lg text-muted-foreground leading-relaxed">
          An autonomous research analyst that crawls filings, news and reports, extracts
          structured metrics, and generates grounded investment theses — every claim
          traceable to a source.
        </p>

        <ReportQuery />

        <div className="mt-10 flex flex-wrap justify-center items-center gap-3">
          <a href="#examples" className="group inline-flex items-center gap-2 bg-primary text-primary-foreground rounded-full px-6 py-3 text-sm font-medium hover:opacity-90 transition glow-emerald">
            See workflow examples
            <span className="transition group-hover:translate-x-0.5">→</span>
          </a>
          <a href="#evidence" className="glass inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium hover:bg-white/5 transition">
            How evidence works
          </a>
        </div>

        <div className="mt-16 flex flex-wrap justify-center items-center gap-x-10 gap-y-4 text-xs font-mono uppercase tracking-wider text-muted-foreground">
          <span>Built for hedge funds</span>
          <span className="h-1 w-1 rounded-full bg-border" />
          <span>PE / VC research</span>
          <span className="h-1 w-1 rounded-full bg-border" />
          <span>Commodity desks</span>
          <span className="h-1 w-1 rounded-full bg-border" />
          <span>Macro teams</span>
        </div>

        <HeroTicker />
      </div>
    </section>
  );
}

const tickerItems = [
  { ticker: "SOY", label: "Soy export pace", val: "+12.4%", trend: "up" },
  { ticker: "BRL", label: "USD/BRL forward", val: "5.18", trend: "down" },
  { ticker: "VALE", label: "Iron ore shipment", val: "31.2 Mt", trend: "up" },
  { ticker: "PETR", label: "Pre-salt output", val: "2.84 mbd", trend: "up" },
  { ticker: "RAIL", label: "Rumo grain rail", val: "8.1 Mt", trend: "up" },
  { ticker: "ETH", label: "Ethanol crush", val: "62.1%", trend: "down" },
  { ticker: "SAN", label: "Santos throughput", val: "14.3 Mt", trend: "up" },
  { ticker: "CRUDE", label: "Brent diff", val: "+1.85", trend: "up" },
];

function HeroTicker() {
  const items = [...tickerItems, ...tickerItems];
  return (
    <div className="relative mt-20 glass rounded-2xl overflow-hidden">
      <div className="absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-background to-transparent z-10" />
      <div className="absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-background to-transparent z-10" />
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border/60 text-xs font-mono uppercase tracking-wider text-muted-foreground">
        <span className="h-1.5 w-1.5 rounded-full bg-primary pulse-dot" />
        Live evidence feed — LatAm
        <span className="ml-auto opacity-60">SHA · {new Date().toISOString().slice(0, 10)}</span>
      </div>
      <div className="flex animate-ticker py-3 whitespace-nowrap">
        {items.map((i, idx) => (
          <div key={idx} className="flex items-center gap-3 px-6 border-r border-border/40">
            <span className="font-mono text-xs text-muted-foreground">{i.ticker}</span>
            <span className="text-sm">{i.label}</span>
            <span className={`font-mono text-sm ${i.trend === "up" ? "text-primary" : "text-accent"}`}>
              {i.trend === "up" ? "▲" : "▼"} {i.val}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
