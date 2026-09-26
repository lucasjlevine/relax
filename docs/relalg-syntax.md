# RelAlg syntax (RelaX-compatible)

Both **unicode symbols** and **plaintext** keywords are accepted. Keywords are case-insensitive.

## Unary operators

| Symbol | Plaintext | Subscript form | Example |
|--------|-----------|----------------|---------|
| σ | `sigma` | `σ_{cond}(R)` | `σ_{dept = 'Engineering'}(Employee)` or `sigma dept = 'Engineering' (Employee)` |
| π | `pi` | `π_{cols}(R)` | `π_{name}(Employee)` |
| ρ | `rho` | `ρ_{renames}(R)` | `ρ_{name→n}(Employee)` |
| τ | `tau` / `order by` | `τ_{keys}(R)` | `τ_{salary desc}(Employee)` |
| γ | `gamma` / `group by` | `γ_{cols; aggs}(R)` | `γ_{region; sum(amount)→total}(Sale)` |
| δ | `delta` / `distinct` | `δ(R)` | `delta (Employee)` |

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

## Assignments

Name intermediate results and reuse them (compiled as SQL `WITH` / CTEs). Blank lines between steps are fine. If the query is only assignments, the **last** assigned name is the result:

```text
EngineerNames = π_{name}(
  σ_{dept = 'Engineering'}(Employee)
)

SalesNames = π_{name}(
  σ_{dept = 'Sales'}(Employee)
)

SalesAndEngineerNames = EngineerNames ∪ SalesNames
```

You can also end with a bare expression after the assignments:

```text
A = σ_{dept = 'Sales'}(Employee)
π_{name}(A)
```

## Comments

SQL-style comments: `-- line` and `/* block */`.

## SQL mode

Standard SELECT subset executed by DuckDB after sqlglot validation:

```sql
SELECT a, b FROM R WHERE a > 1
SELECT * FROM R JOIN S ON R.b = S.b
SELECT * FROM R UNION SELECT * FROM S
```
