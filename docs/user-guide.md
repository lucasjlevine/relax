# User guide

Things to know when using **Relational Playground** as a RelAlg / SQL learning calculator.

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
- **Format** — **Pretty** (balanced), **Dense** (compact, blank line between queries), or **Sparse** (fully expanded)
- Toolbar inserts common operators (stays pinned above the editor); the cursor badge shows line:column and whether you are in π/σ/… subscripts (or on a relation / attribute / function)
- Autocomplete suggests relations, attributes, helper functions, and RelAlg keywords (`pi` / `project` → `π_{}()`, `join` → `⋈`, …). Accept with **Tab** or **Enter**
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

## Workspaces

Each dataset is a **workspace**: RelAlg/SQL drafts and **History** are stored per dataset in the browser (`localStorage`). Switching workspaces saves the current drafts and restores that dataset’s saved queries.

- **Left sidebar** — active workspace name + schema (relations / columns). Drag the edge to resize.
- **Workspaces** (header or sidebar) — sheet overlay to open Built-in / Mine / Public datasets; rename, delete, share, duplicate, or toggle public/private.
- **Manage data** — same sheet’s Data tab: Manage relations/rows, Upload, Build, Group Editor.

### Persistence & sharing

- Uploads, builds, Group installs, and edits to built-ins are saved on the server under `backend/data/user_datasets/` (JSON), keyed by an opaque browser cookie (`relax_owner`). Survives backend restarts.
- New uploads default to **private** (owner + share link only). **Make public** lists the dataset for everyone and allows them to open/query (not edit). Duplicate copies a public dataset into your private library.
- Editing a built-in (rename, rows, …) creates a **personal copy**; the calculator switches to it.
- **Copy share link** produces `/calc?share=…`. Recipients can preview and **Add to my datasets**.

Edits never rewrite the built-in `local_groups` file on disk.

## Results

After **Execute**:

- Scrollable result table  
- Compact operator tree (narrow column on the right)  
- **CSV** download of the current result page  
- Entry added to that workspace’s **History** (browser-local)  

Active workspace, drafts, and per-dataset history are restored after a page reload.

## Scope boundaries

**In scope:** RelAlg + SQL teaching workflow above, including the RelaX-compatible [Group Editor](./group-editor.md).  
**Out of scope (for now):** BagAlg, TRC, intermediate-node result drill-down.

## Security (short)

Built-in datasets are always available. Your uploads default to private (owner cookie + share link). Datasets you mark **public** are world-readable/queryable. See [security.md](./security.md).

## Docs map

| Doc | Audience |
|-----|----------|
| [user-guide.md](./user-guide.md) (this file) | Using the calculator |
| [group-editor.md](./group-editor.md) | RelaX-compatible Group Editor |
| [functions.md](./functions.md) | Expression helper functions |
| [relalg-syntax.md](./relalg-syntax.md) | Operator / syntax reference |
| [api.md](./api.md) | HTTP API |
| [security.md](./security.md) | Threat model & hardening |
| [architecture.md](./architecture.md) | How the engine is wired |
| [development.md](./development.md) | Local setup & tests |
