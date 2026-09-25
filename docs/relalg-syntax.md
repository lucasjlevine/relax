# RelAlg syntax (RelaX-compatible)

Both **unicode symbols** and **plaintext** keywords are accepted. Keywords are case-insensitive.

## Unary operators

| Symbol | Plaintext | Example |
|--------|-----------|---------|
| σ | `sigma` | `sigma a > 1 (R)` |
| π | `pi` | `pi a, b (R)` |
| ρ | `rho` | `rho S (R)` or `rho a→x, b→y (R)` |

## Binary / set operators

| Symbol | Plaintext | Example |
|--------|-----------|---------|
| ∪ | `union` | `R union S` |
| ∩ | `intersect` | `R intersect S` |
| − | `-` / `except` | `R - S` |
| × | `x` / `cross join` | `R x S` |
| ⋈ | `join` | `R join S` |
| ⋈_θ | `join` with condition | `R join S on a = b` |

## Conditions

Boolean expressions in `sigma` and theta-join:

- Comparisons: `=`, `!=`, `<>`, `<`, `<=`, `>`, `>=`
- Logic: `and` / `∧`, `or` / `∨`, `not` / `¬`
- Column refs: `a` or `R.a`

## Comments

SQL-style comments: `-- line` and `/* block */`.

## Assignments (future / limited)

RelaX allows `A = expr` before a final query. MVP focuses on a single expression over named base relations from the loaded dataset.

## SQL mode

Standard SELECT subset executed by DuckDB after sqlglot validation:

```sql
SELECT a, b FROM R WHERE a > 1
SELECT * FROM R JOIN S ON R.b = S.b
SELECT * FROM R UNION SELECT * FROM S
```
