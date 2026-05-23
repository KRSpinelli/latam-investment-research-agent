import { Link } from "@tanstack/react-router";

export function Footer() {
  return (
    <footer className="relative mt-32 border-t border-border/60">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-[1.5fr_repeat(4,1fr)]">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-md bg-gradient-to-br from-primary to-accent" />
              <span className="font-display text-lg">LatAm Alpha Agent</span>
            </div>
            <p className="mt-4 text-sm text-muted-foreground max-w-sm">
              Autonomous emerging-market intelligence infrastructure. Evidence-grounded
              research for institutional investors, starting with Brazil.
            </p>
            <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-primary pulse-dot" />
              <span className="font-mono uppercase tracking-wider">Live signals · São Paulo</span>
            </div>
          </div>

          <FooterCol title="Product" links={[
            ["Research hub", "/research"],
            ["Methodology", "/methodology"],
            ["API", "/api"],
            ["Examples", "/#examples"],
          ]} />
          <FooterCol title="Coverage" links={[
            ["Agriculture", "/research"],
            ["Logistics", "/research"],
            ["Energy", "/research"],
            ["Infrastructure", "/research"],
          ]} />
          <FooterCol title="Company" links={[
            ["About", "/contact"],
            ["Careers", "/contact"],
            ["Security", "/contact"],
            ["Contact", "/contact"],
          ]} />
          <FooterCol title="Resources" links={[
            ["Data sources", "/methodology"],
            ["Docs", "/api"],
            ["llms.txt", "/api"],
            ["Status", "/api"],
          ]} />
        </div>

        <div className="mt-14 pt-6 border-t border-border/60 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between text-xs text-muted-foreground">
          <div>© 2026 LatAm Alpha Agent. Not investment advice.</div>
          <div className="font-mono">v0.4.2 · evidence schema 2026-05</div>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{title}</div>
      <ul className="mt-4 space-y-2.5 text-sm">
        {links.map(([label, href]) => (
          <li key={label}>
            {href.startsWith("/#") ? (
              <a href={href} className="text-foreground/80 hover:text-foreground transition">{label}</a>
            ) : (
              <Link to={href} className="text-foreground/80 hover:text-foreground transition">{label}</Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
