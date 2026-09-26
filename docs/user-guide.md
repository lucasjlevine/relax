# User guide

Things to know when using **relax** as a RelAlg / SQL learning calculator.

## Modes

| Mode | What it does |
|------|----------------|
| **RelAlg** | Relational algebra over the selected dataset. Unicode symbols and plaintext keywords both work. |
| **SQL** | `SELECT` subset validated by sqlglot, executed in DuckDB. |

Switching modes loads that dataset’s example query (when present).

### RelAlg notation

- Classical subscripts: `π_{name}(σ_{dept = 'Engineering'}(Employee))`
- Prefix / RelaX style: `pi name (sigma dept = 'Engineering' (Employee))`
- **Assignments:** `A = π_{…}(R)` then reuse `A` (last assignment is the result if there is no trailing expression)
- **Format** converts prefix → classical subscripts (with indentation for nesting)
- Toolbar inserts common operators; the cursor badge shows line:column and whether you are in π/σ/… subscripts (or on a relation / attribute / function)
- Autocomplete suggests relations, attributes, and helper functions
- **Functions** in the calculator header lists helpers (`rownum()`, `length()`, `CASE WHEN …`, …)
- Shortcut: **Ctrl/Cmd + Enter** to execute; **Ctrl/Cmd + /** to toggle `--` comments
- Full in-app reference: open **Guide** in the calculator header (or `/guide`)

Helper functions: [functions.md](./functions.md)  
Full operator table: [relalg-syntax.md](./relalg-syntax.md)  
User-facing guide page: `/guide` in the app

## Built-in datasets

| Id | Focus | Relations |
|----|--------|-----------|
| `basics` | Selection / projection | `Employee` |
| `joins` | Natural / theta joins | `Project`, `Assign` |
| `setops` | ∪ ∩ − | `RedTeam`, `BlueTeam` |
| `aggregates` | Grouping (`γ`) | `Sale` |
| `library` | Multi-table joins | `Author`, `Book`, `Loan` |

Each group ships a formatted RelAlg example and a matching SQL example.

## Managing data

In the calculator left panel:

1. **Schema** — relation names, columns, row counts  
2. **Manage** — rename/delete dataset, relations, and columns; change column types (currency like `$50` coerces to numbers; bad values become null); add columns; edit rows; add another relation (empty or CSV) to the same dataset  
3. **Upload** — `.csv` / `.db` / `.sqlite` as a new dataset  
4. **Build** — define columns and cells without writing a file  
5. **Group** — RelaX-compatible Group Editor: edit `local_groups` text, Preview / Use, Load current, Download (see [group-editor.md](./group-editor.md))

**Sidebar tip:** Opening **Manage** or **Group** auto-expands the left panel; drag its right edge to resize. Width is remembered in the browser. Wide tables scroll horizontally.

Edits to built-in datasets apply for the current API process (in-memory). Uploaded/built/group-installed datasets behave the same until the backend restarts.

## Results

After **Execute**:

- Scrollable result table  
- Compact operator tree (narrow column on the right)  
- **CSV** download of the current result page  
- Entry added to **History** (browser-local) for reuse  

Dataset selection and the editor query are restored after a page reload.

## Scope boundaries

**In scope:** RelAlg + SQL teaching workflow above, including the RelaX-compatible [Group Editor](./group-editor.md).  
**Out of scope (for now):** BagAlg, TRC, intermediate-node result drill-down.

## Docs map

| Doc | Audience |
|-----|----------|
| [user-guide.md](./user-guide.md) (this file) | Using the calculator |
| [group-editor.md](./group-editor.md) | RelaX-compatible Group Editor |
| [functions.md](./functions.md) | Expression helper functions |
| [relalg-syntax.md](./relalg-syntax.md) | Operator / syntax reference |
| [api.md](./api.md) | HTTP API |
| [architecture.md](./architecture.md) | How the engine is wired |
| [development.md](./development.md) | Local setup & tests |
