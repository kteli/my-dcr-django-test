# Engineering Notes — Design & Decisions

## 1) Project structure & modularity
**Goal:** keep responsibilities small, testable, and swappable.

- **App layout**
  - `countries/models.py` – data schema & invariants.
  - `countries/views.py` – thin HTTP layer only.
  - `countries/services/` – pure logic split by responsibility:
    - `region_stats.py` – aggregation query.
    - `api_client.py` – external I/O (HTTP fetch + retries).
    - `data_validator.py` – row-level validation/normalization.
    - `database_manager.py` – bulk write ops + caching helpers.
  - `countries/management/commands/update_country_listing.py` – orchestration for imports.
  - `countries/tests/` – unit/integration tests per surface (view, validator, command).

**Why:** isolates I/O boundaries, makes each piece unit-testable, and keeps the view logic tiny. Also makes it easy to evolve internals without changing API contracts.

---

## 2) Models — correctness & queryability
**Files:** `models.py`

- **`Region`**
  - `name` is `unique=True`, `db_index=True`.  
  - Rationale: Regions are a small cardinality lookup with direct matching by name; uniqueness avoids dupes, index speeds filters/joins.

- **`Country`**
  - `name`, `alpha2Code`, `alpha3Code` are `unique=True` + indexed.
  - `population` is a **`BigIntegerField`** to avoid overflow on large numbers.
  - `region` has `related_name="countries"` for straightforward reverse access.
  - `topLevelDomain` stored as **JSON string in `TextField`** (Django 2.2 portable).  
  - `capital` is nullable + indexed (common filter/search).
  - Uppercasing ISO codes enforced with validators + `save()` normalization to keep integrity even if bypassing forms.

---

## 3) Aggregations — no `prefetch_related` for pure aggregates
**File:** `services/region_stats.py`

- We **do not** use `prefetch_related("countries")`.  
  - **Why:** prefetch hydrates Python objects and adds extra queries, but **aggregate queries run entirely in SQL**. Prefetching doesn’t help and actually adds overhead.
- Use `annotate(Count("countries"), Sum("countries__population"))` with `Coalesce` to handle empty populations as 0.
- Order and filter applied at the DB level for efficiency.

---

## 4) Import pipeline — reliability & performance
**Files:** `api_client.py`, `data_validator.py`, `database_manager.py`, management command

- **APIClient**
  - Pulls from `COUNTRY_API_URL` (defaults to the assignment URL).
  - Retries on timeouts/5xx with exponential backoff; 10s timeout per call.
  - Optionally saves raw response for debugging.

- **DataValidator**
  - Centralizes row validation & normalization (alpha code casing, TLD cleanup, capital normalization).
  - Returns shapes matching models exactly (TLD → compact JSON string).
  - Logs non-fatal TLD weirdness instead of failing good rows.

- **DatabaseManager**
  - Preloads **countries/regions to dicts** (keyed by name) to avoid N+1 lookups.
  - Uses `bulk_create` / `bulk_update` with explicit `fields` lists.
  - Provides `reset_database()` and cache-friendly helpers.

- **Command (`update_country_listing`)**
  - Flags: `--dry-run`, `--reset`, `--batch-size`, `--no-progress`, `--save-response`.
  - Wraps writes in a single transaction (unless dry-run) for **all-or-nothing** consistency.
  - Batches creates/updates; compares existing vs desired in memory to avoid redundant writes.

---

## 5) View & API shape
**File:** `views.py`

- **Stats endpoint** returns:
  - `regions: [{name, number_countries, total_population}]`
  - `meta` with pagination details (page, total_pages, etc.) and a debug `execution_time_ms`.
- Validates user input via `StatsQueryForm` (page/per_page/name) to keep the view logic clean and safe.

**Extensibility:**  
- Filtering by `name` is implemented with `icontains`, trivial to extend with more filters/sorting later.

---

## 6) Caching — cache data, not whole responses
**Where:** `views.py` (low-level cache) + `update_country_listing` (cache clear)

- We **cache only the expensive data** (regions list + pagination meta) using a **stable cache key** derived from relevant query params.
- `execution_time_ms` is recalculated fresh on every request.
- After a successful import, we **clear the cache** (`cache.clear()`) to ensure stats refresh immediately.  

---

## 7) Validation strategy
- **Query params**: `StatsQueryForm` with strict numeric ranges & name validator (letters/spaces/hyphens), plus a `clean_name` that normalizes empty strings to `None`.
- **Import rows**: `CountryRowForm` owns field shapes (including permissive but safe TLD list handling and capitalization).  
- **Model-level validators** and DB constraints (uniques, indexes) backstop the forms to prevent drift.

---

## 8) Indexing & performance
- Indexes on:
  - `Region.name`
  - `Country.name`, `alpha2Code`, `alpha3Code` (unique + indexed)
  - `Country.region`, `population`, `capital`
- Aggregations leverage indexes indirectly (join & grouping), while filters on `name`/`region`/`capital` benefit directly.

---

## 9) Testing philosophy
- **Unit tests** for pure logic (`DataValidator`).
- **API tests** for the stats endpoint (shape, filters, pagination, aggregates).
- **Command tests** that patch the API client to avoid real network I/O and assert DB mutations + cache clearing behavior.
- Cache is reset in tests to avoid cross-test interference.



## 10) Alternatives considered (and why not now)
- **`prefetch_related` on aggregate view:** unnecessary; aggregates are SQL-native.
- **Full-page caching (`@cache_page`)**: simpler but freezes debug fields; switched to low-level cache.
- **Per-row DB updates in loop:** leads to N+1; replaced with preloaded dicts + bulk ops.
- **Eager validation at model only:** Form-level validation gives better error grouping and cleaner normalization; models enforce final integrity.
