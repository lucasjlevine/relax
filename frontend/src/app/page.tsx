import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(ellipse_at_top_left,_#d9efe9_0%,_#f3f7fb_45%,_#eef2f6_100%)]">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(15,70,90,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(15,70,90,0.06) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
        }}
      />

      <header className="relative z-10 mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <span className="font-[family-name:var(--font-display)] text-2xl tracking-tight text-primary">
          relax
        </span>
        <Button asChild variant="outline">
          <Link href="/calc">Open calculator</Link>
        </Button>
      </header>

      <main className="relative z-10 mx-auto flex min-h-[70vh] w-full max-w-5xl flex-col justify-center px-6 pb-24 pt-8">
        <p className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-primary/80">
          Relational learning lab
        </p>
        <h1 className="max-w-3xl font-[family-name:var(--font-display)] text-5xl leading-tight tracking-tight text-foreground md:text-6xl">
          relax
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          Write relational algebra or SQL against curated datasets. Execute instantly,
          inspect the result table, and follow the operator tree — inspired by RelaX.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/calc">Get started</Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <a
              href="https://dbis-uibk.github.io/relax/landing"
              target="_blank"
              rel="noreferrer"
            >
              View inspiration
            </a>
          </Button>
        </div>

        <div className="mt-16 max-w-2xl rounded-lg border bg-card/80 p-5 shadow-sm backdrop-blur">
          <p className="font-mono text-sm text-primary">
            π a (σ a &gt; 1 (R))
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Core RelAlg and SQL modes for teaching. Expand operators and datasets as you learn.
          </p>
        </div>
      </main>
    </div>
  );
}
