import { Link } from "@tanstack/react-router";

export function Nav() {
  return (
    <header className="fixed top-0 inset-x-0 z-50">
      <div className="mx-auto max-w-7xl px-6 pt-5">
        <div className="glass rounded-full px-5 py-2.5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="relative h-7 w-7">
              <div className="absolute inset-0 rounded-md bg-gradient-to-br from-primary to-accent opacity-90 group-hover:opacity-100 transition" />
              <div className="absolute inset-[3px] rounded-[5px] bg-background flex items-center justify-center">
                <span className="font-display text-[13px] leading-none text-primary">L</span>
              </div>
            </div>
            <span className="font-display text-lg tracking-tight">
              LatAm Alpha <span className="text-muted-foreground">Agent</span>
            </span>
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-sm text-muted-foreground">
            <Link to="/research" className="hover:text-foreground transition">Research</Link>
            <Link to="/methodology" className="hover:text-foreground transition">Methodology</Link>
            <Link to="/api" className="hover:text-foreground transition">API</Link>
            <a href="/#examples" className="hover:text-foreground transition">Examples</a>
            <Link to="/contact" className="hover:text-foreground transition">Contact</Link>
          </nav>

          <div className="flex items-center gap-2">
            <Link
              to="/contact"
              className="hidden sm:inline-flex text-sm text-muted-foreground hover:text-foreground transition px-3 py-1.5"
            >
              Sign in
            </Link>
            <Link
              to="/contact"
              className="inline-flex items-center gap-1.5 text-sm font-medium bg-primary text-primary-foreground rounded-full px-4 py-1.5 hover:opacity-90 transition"
            >
              Request access
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}
