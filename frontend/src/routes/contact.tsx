import { createFileRoute } from "@tanstack/react-router";
import { Nav } from "@/components/site/Nav";
import { Footer } from "@/components/site/Footer";
import { Background } from "@/components/site/Background";
import { SectionHeader } from "@/components/site/Evidence";

export const Route = createFileRoute("/contact")({
  head: () => ({
    meta: [
      { title: "Contact — LatAm Alpha Agent" },
      { name: "description", content: "Request a sample grounded memo on a Brazil ticker of your choice. Typically back within 24 hours." },
      { property: "og:title", content: "Contact — LatAm Alpha Agent" },
      { property: "og:description", content: "Request access, an API key, or a sample memo." },
    ],
  }),
  component: ContactPage,
});

function ContactPage() {
  return (
    <div className="relative min-h-screen">
      <Background />
      <Nav />
      <main className="pt-36 pb-24">
        <div className="mx-auto max-w-3xl px-6">
          <SectionHeader
            align="left"
            eyebrow="Request access"
            title={<>Talk to the <span className="italic text-gradient-emerald">research team.</span></>}
            desc="Tell us your firm and what you'd like to see. We'll usually run a sample memo on a Brazil ticker of your choice within 24 hours."
          />

          <form className="mt-12 glass-strong rounded-3xl p-8 space-y-5" onSubmit={(e) => { e.preventDefault(); alert("Thanks — we'll be in touch."); }}>
            <div className="grid md:grid-cols-2 gap-5">
              <Field label="Name" name="name" />
              <Field label="Work email" name="email" type="email" />
              <Field label="Firm" name="firm" />
              <Field label="Role" name="role" />
            </div>
            <div>
              <label className="block font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Sample ticker / thesis</label>
              <textarea rows={4} className="w-full bg-white/[0.04] border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-primary/50 transition" placeholder="e.g. SUZB3 — pulp export thesis into Q3" />
            </div>
            <div className="flex items-center justify-between pt-2">
              <div className="text-xs text-muted-foreground">We respond within 24h.</div>
              <button type="submit" className="bg-primary text-primary-foreground rounded-full px-6 py-2.5 text-sm font-medium hover:opacity-90 transition">
                Request sample memo →
              </button>
            </div>
          </form>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function Field({ label, name, type = "text" }: { label: string; name: string; type?: string }) {
  return (
    <div>
      <label className="block font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-2">{label}</label>
      <input type={type} name={name} className="w-full bg-white/[0.04] border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-primary/50 transition" />
    </div>
  );
}
