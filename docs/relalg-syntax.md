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

Use **Format → Pretty** for classical subscripts with indentation, or **Format → Dense** for a compact single-line form that drops implied parentheses.

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

- Comparisons: `=`, `!=`, `<>`, `<`, `<=`, `>`, `>=` (and unicode `≠`, `≤`, `≥`)
- Null tests: `col = null` / `null = col` → is null; `col != null` / `col ≠ null` → is not null (any type)
- Logic: `and` / `∧`, `or` / `∨`, `not` / `¬`
- Column refs: `a` or `R.a` (qualified names stay distinct through joins when several relations share an attribute, e.g. `Actor.fname` vs `Director.fname`; colliding join columns are aliased as `Relation_attr`)

## Automatic type coercion

If a string column is used as a number (or date), the calculator converts and **persists** the column type on the dataset (built-ins are forked first). Examples:

- Comparisons: `σ_{Movie.year < 1960}(Movie)` → `year` becomes number  
- Aggregates: `avg` / `sum` / `min` / `max` on a string column → number  
- Arithmetic / helpers: `a + 1`, `abs(a)`, `round(a)`, …  
- Date helpers: `date(…)`, `adddate` / `subdate`

## Multiple statements

Separate independent RelAlg queries with **semicolons**. Each statement is executed in order and returns its own result table (and operator tree). A leading `--` comment becomes the result label:

```text
-- Kate Winslet titles
π_{Movie.title}(
  Movie ⋈_{Movie.mov_id = Cast.mov_id} Cast
  ⋈_{Cast.act_id = Actor.act_id}
  σ_{Actor.fname = 'Kate' ∧ Actor.lname = 'Winslet'}(Actor)
);

-- Years before 1960 or after 1990
π_{Movie.title, Movie.year}(
  σ_{Movie.year < 1960}(Movie)
   ∪
  σ_{Movie.year > 1990}(Movie)
);
```

Assignments (`A = …`) within a single statement still share one result (the last assignment / trailing expression). Use `;` only between fully separate queries.

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

Standard SELECT subset executed by DuckDB after sqlglot validation.

Teaching-friendly rewrites (accepted and normalized):

- Multiple consecutive `WITH` blocks → one `WITH` with comma-separated CTEs  
- Bare `Engineering UNION ALL Sales` → `SELECT * FROM Engineering UNION ALL SELECT * FROM Sales`

```sql
WITH Engineering AS (
  SELECT * FROM Employee WHERE dept = 'Engineering'
)
WITH Sales AS (
  SELECT * FROM Employee WHERE dept = 'Sales'
)
Engineering UNION ALL Sales
```

```sql
SELECT a, b FROM R WHERE a > 1
SELECT * FROM R JOIN S ON R.b = S.b
SELECT * FROM R UNION SELECT * FROM S
```
