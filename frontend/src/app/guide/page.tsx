import Link from "next/link";
import type { Metadata } from "next";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Guide — relax",
  description:
    "How to use the relax RelAlg and SQL calculator: syntax, assignments, helpers, shortcuts, and datasets.",
};

const TOC = [
  { id: "start", label: "Getting started" },
  { id: "relalg", label: "Relational algebra" },
  { id: "assignments", label: "Assignments" },
  { id: "functions", label: "Helper functions" },
  { id: "sql", label: "SQL mode" },
  { id: "editor", label: "Editor & shortcuts" },
  { id: "data", label: "Datasets" },
  { id: "results", label: "Results" },
] as const;

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em] text-foreground">
      {children}
    </code>
  );
}

function Pre({ children }: { children: string }) {
  return (
    <pre className="mt-3 overflow-x-auto rounded-md border bg-card px-4 py-3 font-mono text-sm leading-relaxed text-foreground/90">
      {children}
    </pre>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-primary/10 pt-12">
      <h2 className="font-[family-name:var(--font-display)] text-2xl tracking-tight text-foreground">
        {title}
      </h2>
      <div className="mt-4 space-y-4 text-muted-foreground">{children}</div>
    </section>
  );
}

export default function GuidePage() {
  return (
    <div className="relative min-h-screen bg-[radial-gradient(ellipse_at_top_left,_#d9efe9_0%,_#f3f7fb_45%,_#eef2f6_100%)]">
      <header className="sticky top-0 z-20 border-b bg-card/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="font-[family-name:var(--font-display)] text-xl tracking-tight text-primary"
            >
              relax
            </Link>
            <span className="text-sm text-muted-foreground">Guide</span>
          </div>
          <Button asChild>
            <Link href="/calc">Open calculator</Link>
          </Button>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-5xl gap-10 px-6 py-10 lg:grid-cols-[200px_minmax(0,1fr)]">
        <aside className="hidden lg:block">
          <nav className="sticky top-24 space-y-1 text-sm">
            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              On this page
            </p>
            {TOC.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="block rounded px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </aside>

        <article className="min-w-0 pb-20">
          <h1 className="font-[family-name:var(--font-display)] text-4xl tracking-tight text-foreground">
            Calculator guide
          </h1>
          <p className="mt-3 max-w-2xl text-lg text-muted-foreground">
            How to write RelAlg and SQL in relax, use helpers and assignments, and
            work with teaching datasets.
          </p>

          <Section id="start" title="Getting started">
            <p>
              Open the <Link href="/calc" className="text-primary underline-offset-2 hover:underline">calculator</Link>,
              pick a dataset on the left, and write a query in the editor. Switch
              between <strong className="font-medium text-foreground">RelAlg</strong> and{" "}
              <strong className="font-medium text-foreground">SQL</strong> with the tabs.
              Press <strong className="font-medium text-foreground">Execute</strong> (or{" "}
              <Code>⌘/Ctrl + Enter</Code>) to run.
            </p>
            <p>
              RelAlg is the default learning path: classical subscripts like{" "}
              <Code>π_&#123;…&#125;(R)</Code>, plaintext keywords like{" "}
              <Code>pi</Code> / <Code>sigma</Code>, and an operator tree of the
              executed expression. SQL mode accepts a read-only{" "}
              <Code>SELECT</Code> subset.
            </p>
          </Section>

          <Section id="relalg" title="Relational algebra">
            <p>
              Both unicode symbols and plaintext keywords work. Keywords are
              case-insensitive. Prefer classical subscripts;{" "}
              <strong className="font-medium text-foreground">Format</strong> rewrites
              prefix style into subscript form.
            </p>

            <h3 className="pt-2 text-base font-medium text-foreground">Unary operators</h3>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[32rem] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b text-foreground">
                    <th className="py-2 pr-3 font-medium">Symbol</th>
                    <th className="py-2 pr-3 font-medium">Plaintext</th>
                    <th className="py-2 font-medium">Example</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  {[
                    ["σ", "sigma", "σ_{dept = 'Engineering'}(Employee)"],
                    ["π", "pi", "π_{name}(Employee)"],
                    ["ρ", "rho", "ρ_{name→n}(Employee)"],
                    ["τ", "tau / order by", "τ_{salary desc}(Employee)"],
                    ["γ", "gamma / group by", "γ_{region; sum(amount)→total}(Sale)"],
                    ["δ", "delta / distinct", "δ(Employee)"],
                  ].map(([sym, plain, ex]) => (
                    <tr key={sym} className="border-b border-border/70">
                      <td className="py-2 pr-3 font-mono text-foreground">{sym}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{plain}</td>
                      <td className="py-2 font-mono text-xs text-foreground/80">{ex}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3 className="pt-4 text-base font-medium text-foreground">Binary / set operators</h3>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[28rem] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b text-foreground">
                    <th className="py-2 pr-3 font-medium">Symbol</th>
                    <th className="py-2 pr-3 font-medium">Plaintext</th>
                    <th className="py-2 font-medium">Notes</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  {[
                    ["∪", "union", "Schemas must match"],
                    ["∩", "intersect", "Schemas must match"],
                    ["−", "except / minus", "Schemas must match"],
                    ["×", "cross", "Cartesian product"],
                    ["÷", "division", "Right schema ⊆ left"],
                    ["⋈", "join", "Natural or θ with _{…} / on"],
                    ["⟕ ⟖ ⟗", "left / right / full join", "Outer joins"],
                    ["⋉ ▷", "semi join / anti join", "Existence filters"],
                  ].map(([sym, plain, note]) => (
                    <tr key={sym} className="border-b border-border/70">
                      <td className="py-2 pr-3 font-mono text-foreground">{sym}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{plain}</td>
                      <td className="py-2 text-sm">{note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3 className="pt-4 text-base font-medium text-foreground">Conditions</h3>
            <p>
              Comparisons <Code>= != &lt;&gt; &lt; &lt;= &gt; &gt;=</Code>, logic{" "}
              <Code>and / or / xor / not</Code> (or ∧ ∨ ¬), pattern match{" "}
              <Code>like</Code> / <Code>ilike</Code>, and qualified columns{" "}
              <Code>Relation.attr</Code>.
            </p>
            <Pre>{`π_{name}(
  σ_{dept = 'Engineering' ∧ salary > 80000}(Employee)
)`}</Pre>
          </Section>

          <Section id="assignments" title="Assignments">
            <p>
              Name intermediate results and reuse them — same idea as SQL{" "}
              <Code>WITH</Code>. Blank lines between steps are fine. If the query is
              only assignments, the <strong className="font-medium text-foreground">last</strong>{" "}
              assigned name is the result shown in the table.
            </p>
            <Pre>{`EngineerNames = π_{name}(
  σ_{dept = 'Engineering'}(Employee)
)

SalesNames = π_{name}(
  σ_{dept = 'Sales'}(Employee)
)

SalesAndEngineerNames = EngineerNames ∪ SalesNames`}</Pre>
            <p>
              You can also end with a bare expression after the assignments:
            </p>
            <Pre>{`A = σ_{dept = 'Sales'}(Employee)
π_{name}(A)`}</Pre>
          </Section>

          <Section id="functions" title="Helper functions">
            <p>
              Scalar helpers work inside projections, selections, and join conditions —
              SQL-style names, case-insensitive. Open{" "}
              <strong className="font-medium text-foreground">Functions</strong> in the
              calculator for a quick panel, or use autocomplete while typing.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[30rem] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b text-foreground">
                    <th className="py-2 pr-3 font-medium">Category</th>
                    <th className="py-2 font-medium">Functions</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border/70">
                    <td className="py-2 pr-3 text-foreground">Row</td>
                    <td className="py-2 font-mono text-xs">
                      rownum() · rand()
                    </td>
                  </tr>
                  <tr className="border-b border-border/70">
                    <td className="py-2 pr-3 text-foreground">Strings</td>
                    <td className="py-2 font-mono text-xs">
                      length · upper · lower · concat
                    </td>
                  </tr>
                  <tr className="border-b border-border/70">
                    <td className="py-2 pr-3 text-foreground">Dates</td>
                    <td className="py-2 font-mono text-xs">
                      date · adddate · subdate · year · month (1–12) · day · now
                    </td>
                  </tr>
                  <tr className="border-b border-border/70">
                    <td className="py-2 pr-3 text-foreground">Numbers</td>
                    <td className="py-2 font-mono text-xs">
                      + − * / % · abs · round · floor · ceil
                    </td>
                  </tr>
                  <tr className="border-b border-border/70">
                    <td className="py-2 pr-3 text-foreground">Logic</td>
                    <td className="py-2 font-mono text-xs">
                      coalesce · xor · CASE WHEN … THEN … ELSE … END
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-3 text-foreground">Aggregates (γ)</td>
                    <td className="py-2 font-mono text-xs">
                      count · sum · avg · min · max
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <Pre>{`π_{name, CASE WHEN salary > 80000 THEN 'high' ELSE 'ok' END→band}(
  σ_{rownum() < 5}(τ_{salary desc}(Employee))
)`}</Pre>
            <p className="text-sm">
              <Code>rownum()</Code> is 0-based. In a selection it is rewritten with a
              window filter; in a join condition it refers to the{" "}
              <strong className="font-medium text-foreground">left</strong> input.
            </p>
          </Section>

          <Section id="sql" title="SQL mode">
            <p>
              SQL mode validates a read-only <Code>SELECT</Code> (including{" "}
              <Code>UNION</Code> / <Code>INTERSECT</Code> / <Code>EXCEPT</Code>) and
              runs it in DuckDB. Inserts, updates, deletes, and DDL are rejected.
            </p>
            <p>
              Teaching shortcuts: consecutive <Code>WITH</Code> blocks are merged into
              one CTE list, and bare <Code>A UNION ALL B</Code> is rewritten to{" "}
              <Code>SELECT * FROM A UNION ALL SELECT * FROM B</Code>.
            </p>
            <Pre>{`WITH Engineering AS (
  SELECT * FROM Employee WHERE dept = 'Engineering'
)
WITH Sales AS (
  SELECT * FROM Employee WHERE dept = 'Sales'
)
Engineering UNION ALL Sales`}</Pre>
            <p>Equivalent standard form:</p>
            <Pre>{`WITH Engineering AS (
  SELECT * FROM Employee WHERE dept = 'Engineering'
),
Sales AS (
  SELECT * FROM Employee WHERE dept = 'Sales'
)
SELECT * FROM Engineering
UNION ALL
SELECT * FROM Sales`}</Pre>
          </Section>

          <Section id="editor" title="Editor & shortcuts">
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <Code>⌘/Ctrl + Enter</Code> — Execute
              </li>
              <li>
                <Code>⌘/Ctrl + /</Code> — Toggle line comment (<Code>--</Code>)
              </li>
              <li>
                <Code>⌘/Ctrl + Space</Code> — Autocomplete (relations, attributes,
                helpers)
              </li>
              <li>
                After <Code>Relation.</Code>, completions list that relation’s
                attributes only
              </li>
              <li>
                RelAlg cursor badge shows line:column and whether you are in a π/σ/…
                subscript
              </li>
              <li>
                Operator toolbar inserts unicode symbols at the cursor
              </li>
              <li>
                Comments: <Code>-- line</Code> and <Code>/* block */</Code>
              </li>
            </ul>
          </Section>

          <Section id="data" title="Datasets">
            <p>
              Built-in groups: <Code>basics</Code>, <Code>joins</Code>,{" "}
              <Code>setops</Code>, <Code>aggregates</Code>, <Code>library</Code>. Each
              loads an example RelAlg and SQL query when selected.
            </p>
            <p>Left panel tabs:</p>
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <strong className="font-medium text-foreground">Schema</strong> —
                relation names, columns, row counts
              </li>
              <li>
                <strong className="font-medium text-foreground">Manage</strong> —
                rename/delete, edit types and rows, add relations (auto-widens the
                panel)
              </li>
              <li>
                <strong className="font-medium text-foreground">Upload</strong> — CSV /
                SQLite as a new dataset
              </li>
              <li>
                <strong className="font-medium text-foreground">Build</strong> — define
                columns and cells in the UI
              </li>
              <li>
                <strong className="font-medium text-foreground">Group</strong> —
                RelaX-compatible Group Editor (<code className="font-mono text-xs">local_groups</code>{" "}
                text): Preview, Use, Load current, Download
              </li>
            </ul>
            <p className="text-sm">
              Your uploads and edits are saved on the server for this browser
              (cookie ownership). Dataset choice and the editor query are restored
              after a browser reload.
            </p>
          </Section>

          <Section id="results" title="Results">
            <p>
              After Execute you get a scrollable result table, a compact operator tree,
              optional CSV download of the current page, and an entry in{" "}
              <strong className="font-medium text-foreground">History</strong> for reuse.
            </p>
            <p>
              Scope is RelAlg + SQL only — no BagAlg or TRC. Intermediate-node result
              drill-down is not available yet.
            </p>
            <div className="flex flex-wrap gap-3 pt-4">
              <Button asChild>
                <Link href="/calc">Open calculator</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/">Home</Link>
              </Button>
            </div>
          </Section>
        </article>
      </div>
    </div>
  );
}
