import { createFileRoute } from "@tanstack/react-router";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";
import { Background } from "@/components/site/Background";
import { Hero } from "@/components/site/Hero";
import { Evidence } from "@/components/site/Evidence";
import { Examples } from "@/components/site/Examples";
import { Coverage } from "@/components/site/Coverage";
import { ApiSection } from "@/components/site/ApiSection";
import { Stats, WhoFor, CTA } from "@/components/site/Sections";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Amigo.ai — Underfollowed LatAm signals, grounded." },
      { name: "description", content: "Autonomous AI research analyst for emerging-market alpha. Discovers, classifies and grounds LatAm investment signals — every claim traceable to source." },
      { property: "og:title", content: "Amigo.ai — Underfollowed LatAm signals, grounded." },
      { property: "og:description", content: "Autonomous AI research analyst for emerging-market alpha. Evidence-first, agent-native, API-ready." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="relative min-h-screen">
      <Background />
      <Nav />
      <main>
        <Hero />
        <Stats />
        <Evidence />
        <Examples />
        <Coverage />
        <ApiSection />
        <WhoFor />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
