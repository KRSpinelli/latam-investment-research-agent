export function Background() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      <div className="absolute inset-0 aurora-bg" />
      <div className="absolute inset-0 grid-bg opacity-40 [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" />
      <div className="absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-primary/20 blur-[120px] animate-float" />
      <div className="absolute top-1/3 -right-40 h-[600px] w-[600px] rounded-full bg-accent/15 blur-[140px] animate-float" style={{ animationDelay: "-6s" }} />
    </div>
  );
}
