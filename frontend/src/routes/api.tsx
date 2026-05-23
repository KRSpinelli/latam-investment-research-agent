import { createFileRoute } from "@tanstack/react-router";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";
import { Background } from "@/components/site/Background";
import { ApiSection } from "@/components/site/ApiSection";
import { SectionHeader } from "@/components/site/Evidence";

export const Route = createFileRoute("/api")({
  head: () => ({
    meta: [
      { title: "API — Amigo.ai" },
      { name: "description", content: "Agent-native market intelligence API. Typed evidence objects, streaming signals, pay-per-call. Built for institutional research stacks." },
      { property: "og:title", content: "API — Amigo.ai" },
      { property: "og:description", content: "Pipe structured LatAm evidence into your own agent or quant stack." },
    ],
  }),
  component: ApiPage,
});

function ApiPage() {
  return (
    <div className="relative min-h-screen">
      <Background />
      <Nav />
      <main className="pt-36 pb-12">
        <div className="mx-auto max-w-7xl px-6">
          <SectionHeader
            align="left"
            eyebrow="Developer API"
            title={<>Agent-native intelligence, <span className="italic text-gradient-emerald">composable.</span></>}
            desc="Three endpoints to start: signals, evidence, memos. Streaming and REST, typed clients in TypeScript and Python."
          />

          <div className="mt-14 grid md:grid-cols-3 gap-4">
            {[
              { m: "GET", p: "/v1/signals", d: "Stream classified signals across coverage sectors with conviction bands." },
              { m: "GET", p: "/v1/evidence/{id}", d: "Resolve any evidence object — source URL, snippet, metric, confidence." },
              { m: "POST", p: "/v1/memos", d: "Generate a grounded memo on a ticker or thesis. Returns inline citations." },
            ].map((e) => (
              <div key={e.p} className="glass rounded-2xl p-6">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-primary/15 text-primary uppercase">{e.m}</span>
                  <code className="font-mono text-sm">{e.p}</code>
                </div>
                <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{e.d}</p>
              </div>
            ))}
          </div>
        </div>

        <ApiSection />
      </main>
      <Footer />
    </div>
  );
}
