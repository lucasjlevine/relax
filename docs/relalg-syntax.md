# RelAlg syntax (RelaX-compatible)

Both **unicode symbols** and **plaintext** keywords are accepted. Keywords are case-insensitive.

## Unary operators

| Symbol | Plaintext | Subscript form | Example |
|--------|-----------|----------------|---------|
| σ | `sigma` | `σ_{cond}(R)` | `σ_{a > 1}(R)` or `sigma a > 1 (R)` |
| π | `pi` | `π_{cols}(R)` | `π_{a, b}(R)` |
| ρ | `rho` | `ρ_{renames}(R)` | `ρ_{a→x}(R)` |
| τ | `tau` / `order by` | `τ_{keys}(R)` | `τ_{a asc}(R)` |
| γ | `gamma` / `group by` | `γ_{cols; aggs}(R)` | `γ_{a; count(*)→n}(R)` |
| δ | `delta` / `distinct` | `δ(R)` | `delta (R)` |

Use **Format** in the calculator to rewrite prefix-style queries into classical subscript notation with indentation for nested expressions.

Bracket form `π[a](R)` / `σ[a > 1](R)` is also accepted.

## Binary / set operators

| Symbol | Plaintext | Example |
|--------|-----------|---------|
| ∪ | `union` | `R union S` |
| ∩ | `intersect` | `R intersect S` |
| − | `-` / `except` | `R except S` |
| × | `cross` | `R cross S` |
| ÷ | `division` | `R division S` |
| ⋈ | `join` | `R join S` / `R ⋈_{a=b} S` |
| ⟕ | `left join` | `R left join S on …` |
| ⟖ | `right join` | `R right join S on …` |
| ⟗ | `full join` | `R full join S on …` |
| ⋉ | `semi join` | `R semi join S` |
| ▷ | `anti join` | `R anti join S` |

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
