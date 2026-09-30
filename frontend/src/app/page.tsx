import Link from "next/link";
import { Button } from "@/components/ui/button";

const DATASETS = [
  { name: "Basics", focus: "σ π ρ", blurb: "Employee — selection & projection" },
  { name: "Joins", focus: "⋈", blurb: "Project × Assign" },
  { name: "SetOps", focus: "∪ ∩ −", blurb: "Overlapping teams" },
  { name: "Aggregates", focus: "γ", blurb: "Sale — group by" },
  { name: "Library", focus: "joins", blurb: "Author, Book, Loan" },
] as const;

export default function HomePage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[radial-gradient(ellipse_at_top_left,_#d9efe9_0%,_#f3f7fb_45%,_#eef2f6_100%)]">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(15,70,90,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(15,70,90,0.06) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage:
            "radial-gradient(ellipse at center, black 30%, transparent 75%)",
        }}
      />

      <header className="relative z-10 mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <span className="font-[family-name:var(--font-display)] text-xl tracking-tight text-primary sm:text-2xl">
          Relational Playground
        </span>
        <nav className="flex items-center gap-4">
          <Link
            href="/guide"
            className="hidden text-sm text-muted-foreground hover:text-foreground sm:inline"
          >
            Guide
          </Link>
          <a
            href="#about"
            className="hidden text-sm text-muted-foreground hover:text-foreground sm:inline"
          >
            About
          </a>
          <Button asChild variant="outline">
            <Link href="/calc">Open calculator</Link>
          </Button>
        </nav>
      </header>

      <main className="relative z-10">
        <section className="mx-auto flex min-h-[72vh] w-full max-w-5xl flex-col justify-center px-6 pb-16 pt-6">
          <h1 className="font-[family-name:var(--font-display)] text-4xl leading-[1.05] tracking-tight text-foreground sm:text-5xl md:text-6xl">
            Relational Playground
          </h1>
          <p className="mt-5 max-w-lg text-lg text-muted-foreground md:text-xl">
            A browser calculator for relational algebra and SQL. Write a query,
            run it on teaching data, and inspect the result table and operator
            tree.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/calc">Open calculator</Link>
            </Button>
            <Button asChild size="lg" variant="secondary">
              <Link href="/guide">Read the guide</Link>
            </Button>
          </div>
          <pre className="mt-14 max-w-xl overflow-x-auto font-mono text-sm leading-relaxed text-primary/90">
{`π_{name}(
  σ_{dept = 'Engineering'}(Employee)
)`}
          </pre>
        </section>

        <section
          id="about"
          className="border-t border-primary/10 bg-background/60 py-20 backdrop-blur-sm"
        >
          <div className="mx-auto w-full max-w-5xl px-6">
            <h2 className="font-[family-name:var(--font-display)] text-3xl tracking-tight text-foreground">
              About
            </h2>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Type RelAlg with classical subscripts or plaintext keywords, or
              switch to SQL. Queries run against small built-in datasets, or ones
              you upload or build.
            </p>

            <div className="mt-12 grid gap-10 md:grid-cols-2">
              <div>
                <h3 className="text-lg font-medium text-foreground">In the calculator</h3>
                <ul className="mt-3 space-y-2 text-muted-foreground">
                  <li>
                    RelAlg operators (σ π ⋈ γ ∪ …) and a SQL SELECT mode
                  </li>
                  <li>
                    Named steps with assignments (
                    <code className="text-foreground/80">A = π_…(R)</code>
                    ), then reuse <code className="text-foreground/80">A</code>
                  </li>
                  <li>
                    Helper functions (
                    <code className="text-foreground/80">rownum</code>,{" "}
                    <code className="text-foreground/80">length</code>,{" "}
                    <code className="text-foreground/80">CASE WHEN</code>
                    , …)
                  </li>
                  <li>Result table, operator tree, Format, History, CSV export</li>
                </ul>
              </div>
              <div>
                <h3 className="text-lg font-medium text-foreground">Built-in datasets</h3>
                <ul className="mt-3 space-y-2 text-sm">
                  {DATASETS.map((ds) => (
                    <li
                      key={ds.name}
                      className="flex flex-wrap items-baseline gap-x-3 gap-y-1"
                    >
                      <span className="min-w-[5.5rem] font-medium text-foreground">
                        {ds.name}
                      </span>
                      <span className="font-mono text-xs text-primary">{ds.focus}</span>
                      <span className="text-muted-foreground">{ds.blurb}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-14 border-t border-primary/10 pt-10">
              <h3 className="text-lg font-medium text-foreground">Inspiration</h3>
              <p className="mt-3 max-w-2xl text-muted-foreground">
                Inspired by{" "}
                <a
                  href="https://dbis-uibk.github.io/relax/landing"
                  className="font-medium text-foreground/80 underline-offset-2 hover:underline"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  RelaX
                </a>
                , the relational algebra calculator from the Databases and
                Information Systems group at the University of Innsbruck. This
                project is a separate RelAlg + SQL learning tool; it is not
                affiliated with RelaX.
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                Citation:{" "}
                <a
                  href="https://dbis-uibk.github.io/relax/landing"
                  className="font-mono text-xs text-foreground/80 underline-offset-2 hover:underline"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  https://dbis-uibk.github.io/relax/landing
                </a>
              </p>
            </div>

            <div className="mt-14 flex flex-wrap items-center gap-4 border-t border-primary/10 pt-10">
              <Button asChild>
                <Link href="/calc">Try the calculator</Link>
              </Button>
              <p className="max-w-md text-sm text-muted-foreground">
                Scope is RelAlg + SQL only (no BagAlg or TRC). See the{" "}
                <Link href="/guide" className="font-medium text-foreground/80 underline-offset-2 hover:underline">
                  Guide
                </Link>{" "}
                for syntax, helpers, and shortcuts.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
