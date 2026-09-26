import Link from "next/link";
import { Button } from "@/components/ui/button";

const DATASETS = [
  {
    name: "Basics",
    focus: "σ / π / ρ",
    blurb: "One Employee relation for selection and projection.",
  },
  {
    name: "Joins",
    focus: "⋈",
    blurb: "Project and Assign for natural and theta joins.",
  },
  {
    name: "SetOps",
    focus: "∪ ∩ −",
    blurb: "Overlapping teams for union, intersect, and difference.",
  },
  {
    name: "Aggregates",
    focus: "γ",
    blurb: "Sale rows for grouping and aggregates.",
  },
  {
    name: "Library",
    focus: "multi-table",
    blurb: "Author, Book, and Loan for chained joins.",
  },
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
        <span className="font-[family-name:var(--font-display)] text-2xl tracking-tight text-primary">
          relax
        </span>
        <nav className="flex items-center gap-4">
          <a
            href="#guide"
            className="hidden text-sm text-muted-foreground hover:text-foreground sm:inline"
          >
            Guide
          </a>
          <Button asChild variant="outline">
            <Link href="/calc">Open calculator</Link>
          </Button>
        </nav>
      </header>

      <main className="relative z-10">
        <section className="mx-auto flex min-h-[72vh] w-full max-w-5xl flex-col justify-center px-6 pb-16 pt-6">
          <h1 className="font-[family-name:var(--font-display)] text-5xl leading-[1.05] tracking-tight text-foreground md:text-7xl">
            relax
          </h1>
          <p className="mt-5 max-w-xl text-lg text-muted-foreground md:text-xl">
            Learn relational algebra and SQL by running queries against small teaching
            datasets — with classical subscripts, results, and an operator tree.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/calc">Open calculator</Link>
            </Button>
            <Button asChild size="lg" variant="secondary">
              <a href="#guide">
                How it works
              </a>
            </Button>
          </div>
          <pre className="mt-14 max-w-xl overflow-x-auto font-mono text-sm leading-relaxed text-primary/90">
{`π_{name}(
  σ_{dept = 'Engineering'}(Employee)
)`}
          </pre>
        </section>

        <section
          id="guide"
          className="border-t border-primary/10 bg-background/60 py-20 backdrop-blur-sm"
        >
          <div className="mx-auto w-full max-w-5xl px-6">
            <h2 className="font-[family-name:var(--font-display)] text-3xl tracking-tight text-foreground">
              What you can do
            </h2>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              The calculator is RelAlg + SQL only — no BagAlg or TRC. Everything below is
              available in the Teaching MVP.
            </p>

            <ol className="mt-12 space-y-10">
              <li className="grid gap-2 md:grid-cols-[140px_1fr] md:gap-8">
                <span className="font-mono text-sm text-primary">01 · modes</span>
                <div>
                  <h3 className="text-lg font-medium text-foreground">RelAlg and SQL</h3>
                  <p className="mt-1 text-muted-foreground">
                    Switch languages freely. RelAlg accepts unicode operators (
                    <code className="text-foreground/80">σ π ⋈ γ</code>
                    ) and plaintext keywords (
                    <code className="text-foreground/80">sigma</code>,{" "}
                    <code className="text-foreground/80">pi</code>,{" "}
                    <code className="text-foreground/80">join</code>
                    ). Format rewrites prefix style into classical subscripts.
                  </p>
                </div>
              </li>
              <li className="grid gap-2 md:grid-cols-[140px_1fr] md:gap-8">
                <span className="font-mono text-sm text-primary">02 · datasets</span>
                <div>
                  <h3 className="text-lg font-medium text-foreground">
                    Five built-in scopes — or bring your own
                  </h3>
                  <p className="mt-1 text-muted-foreground">
                    Start from curated examples, upload CSV/SQLite, build a relation in the
                    UI, or manage rows/names in the Manage tab (drag the left panel wider).
                  </p>
                  <ul className="mt-4 space-y-2">
                    {DATASETS.map((ds) => (
                      <li
                        key={ds.name}
                        className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm"
                      >
                        <span className="min-w-[6.5rem] font-medium text-foreground">
                          {ds.name}
                        </span>
                        <span className="font-mono text-xs text-primary">{ds.focus}</span>
                        <span className="text-muted-foreground">{ds.blurb}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </li>
              <li className="grid gap-2 md:grid-cols-[140px_1fr] md:gap-8">
                <span className="font-mono text-sm text-primary">03 · results</span>
                <div>
                  <h3 className="text-lg font-medium text-foreground">
                    Table, tree, and CSV export
                  </h3>
                  <p className="mt-1 text-muted-foreground">
                    Execute shows a scrollable result table and a compact operator tree.
                    Export the current result as CSV anytime.
                  </p>
                </div>
              </li>
            </ol>

            <div className="mt-16 flex flex-wrap items-center gap-4 border-t border-primary/10 pt-10">
              <Button asChild>
                <Link href="/calc">Try the calculator</Link>
              </Button>
              <p className="text-sm text-muted-foreground">
                Syntax reference and API notes live in the repo under{" "}
                <span className="font-mono text-foreground/80">docs/</span>
                — start with{" "}
                <span className="font-mono text-foreground/80">user-guide.md</span>.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
