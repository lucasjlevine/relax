# Helper functions (RelAlg expressions)

These work inside projections, selections, join conditions, and other value expressions — similar to SQL scalar functions. Names are case-insensitive.

In the calculator, open **Functions** (header) for a quick reference. Autocomplete also suggests these helpers.

## Row & randomness

| Function | Returns | Notes |
|----------|---------|--------|
| `rownum()` | number | 0-based index of the current row. In a selection it is applied with DuckDB `QUALIFY`. In a join condition it refers to the **left** input’s row index. |
| `rand()` | number | Uniform random value in `[0, 1]`. |

Example:

```text
π_{name}(σ_{rownum() < 3}(τ_{salary desc}(Employee)))
```

## Strings

| Function | Returns | Notes |
|----------|---------|--------|
| `length(s)` / `strlen(s)` | number | Character length |
| `upper(s)` / `ucase(s)` | string | Uppercase |
| `lower(s)` / `lcase(s)` | string | Lowercase |
| `concat(s1, s2, …)` | string | Concatenate |

Example:

```text
π_{upper(name)→n, length(name)→len}(Employee)
```

## Dates & time

Store dates as `date` columns or parse strings with `date('YYYY-MM-DD')`.

| Function | Returns | Notes |
|----------|---------|--------|
| `date(s)` | date | Parse `YYYY-MM-DD` |
| `adddate(d, n)` | date | Add `n` days |
| `subdate(d, n)` | date | Subtract `n` days |
| `year(d)` | number | Year |
| `month(d)` | number | Month **1–12** (SQL-style) |
| `day(d)` / `dayofmonth(d)` | number | Day of month 1–31 |
| `hour(d)` / `minute(d)` / `second(d)` | number | Time parts |
| `now()` | timestamp | Query start time |
| `clock_timestamp()` | timestamp | Same as `now()` here |
| `transaction_timestamp()` / `statement_timestamp()` | timestamp | Same as `now()` here |

Example:

```text
π_{title, year(date('1987-01-01'))→y}(Book)
```

## Numbers

| Function / op | Returns | Notes |
|---------------|---------|--------|
| `a + b`, `a - b`, `a * b`, `a / b`, `a % b` | number | Arithmetic / modulo |
| `add` / `sub` / `mul` / `div` / `mod` | number | Function forms of the same ops |
| `abs(n)` | number | Absolute value |
| `round(n)` / `round(n, d)` | number | Round |
| `floor(n)` / `ceil(n)` | number | Floor / ceiling |

## Null, logic & conditionals

| Function / op | Returns | Notes |
|---------------|---------|--------|
| `coalesce(a, b, …)` | type of args | First non-null |
| `a xor b` | boolean | Exclusive or |
| `CASE WHEN cond THEN result [WHEN …] [ELSE result] END` | type of results | SQL-style conditional; all branches should share a type |

Example:

```text
π_{name, CASE WHEN salary > 80000 THEN 'high' ELSE 'ok' END→band}(Employee)
```

Aggregates for `γ` remain: `count`, `sum`, `avg`, `min`, `max`.

## Autocomplete

In the calculator editor, type a relation or attribute name (or Ctrl/Cmd-Space) to complete from the current dataset schema and these helpers. After `Relation.`, only that relation’s attributes are suggested.
