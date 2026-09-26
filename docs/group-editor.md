# Group Editor

The **Group** tab in the calculator is a RelaX-compatible Group Editor (GE). It edits the same `local_groups` text format RelaX uses, so you can paste groups from RelaX (or export ours into RelaX) without conversion.

## Open the editor

1. Open the calculator.
2. In the left panel, click **Group**.
3. Edit the text, then **Preview** (parse only) or **Use** (install into this session).

Draft text is kept in browser `localStorage` under `relax.groupEditorText`.

## Actions

| Button | Effect |
|--------|--------|
| **Preview** | Parse text; show group names, columns, and row counts. Does not install. |
| **Use** | Parse and install every `group:` block as a user dataset; select the last one and load its example query when present. |
| **Load current** | Replace the editor with a RelaX-format export of the selected dataset. |
| **Download** | Save the editor text as a `.txt` file. |
| **Insert relation** | Insert a starter `R = { … }` block at the cursor. |

## Format (RelaX-compatible)

Headers (any of these styles):

```text
group: My group
description: Short description
category: practice

exampleRelAlg - {
  σ_{a = 1}(A)
}

exampleSql - {
  SELECT * FROM A WHERE a = 1
}
```

Multiline headers also work (`group[[…]]`, `exampleRelAlg[[…]]`, …) — same as the built-in `backend/data/local_groups` file.

### Inline relations

```text
A = {
a:number, b:string
1, hello
2, 'world'
}
```

- Header row lists columns; optional `:type` (`number`, `string`, `boolean`, `date`).
- Untyped columns default to `string` (and may be inferred from the first data rows).
- `null`, quotes, and `;` as a cell delimiter are accepted (RelaX-style).

### Derived relations (RelAlg)

Assign a RelAlg expression instead of `{ … }` to materialize a table from earlier relations in the same group:

```text
A = { a:number
1
2
}
B = { a:number
1
}
C = A - B
```

Derived relations are evaluated when you Preview / Use (and when the server loads a file).

### Comments

`--` line comments and `/* … */` block comments are skipped (same spirit as RelaX).

## API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/datasets/group/preview` | `{ "text": "…" }` → parsed group summaries |
| `POST` | `/api/datasets/group/install` | Parse and install all groups |
| `GET` | `/api/datasets/{id}/export` | `{ text, filename }` RelaX serialization |
| `GET` | `/api/datasets/{id}/export.txt` | Plain-text download |

## Not included (yet)

RelaX also ships a Handsontable spreadsheet mode and GitHub Gist load/save. This editor is text-first and format-compatible; use **Manage** for cell editing after **Use**.
