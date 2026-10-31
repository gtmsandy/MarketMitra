# Milestone 7A query-performance baseline

## Scope and environment

This report records existing behavior; it does not optimize production queries.
Measurements were made on deterministic in-memory SQLite fixtures through the
real SQLAlchemy repositories and `PostgresMarketProvider`.

A local PostgreSQL URL exists for database `marketmitra`, but that name does not
identify a disposable environment. Docker and `psql` are unavailable. No
connection, seed, mutation, timing run, or `EXPLAIN ANALYZE` was performed
against that database. PostgreSQL timing and plan evidence therefore remain
pending rather than inferred from SQLite.

The existing `test_pre_production_gate.py` is destructive: it drops and creates
`marketmitra_test_gate` and truncates application tables. It was not run.

## Query inventory

| Priority | API or process | Source path | Current query pattern | Suspected complexity | Existing correctness coverage |
| --- | --- | --- | --- | --- | --- |
| P0 | `GET /api/v1/stocks`, `?q=` | `providers/postgres_market.py`: `get_stocks`, `search_stocks`; `repositories/price_repository.py`: `get_latest_by_symbol` | Instrument list + snapshot + latest price per instrument; search filters the complete collection in Python | SQL statements `N + 2`; response and application filtering `O(N)` | Provider/API listing and search tests; 7A adds normalization, ordering, and growth contracts |
| P0 | Gainers and losers | `providers/postgres_market.py`: `get_top_gainers`, `get_top_losers`, `_to_market_mover` | Common-session query + full session query + instrument lookup for every returned mover | SQL statements `N + 2`; unbounded result | Sign, sorting, shared-session tests; 7A adds deterministic ties and filtering contracts |
| P0 | Most active | `providers/postgres_market.py`: `get_most_active` | Common-session query + full session query + instrument lookup per row | SQL statements `N + 2`; unbounded result | Sorting/shape tests; 7A adds deterministic ties and growth contract |
| P1 | Stock detail | `providers/postgres_market.py`: `get_stock_detail` | Instrument + latest price + all valid history + latest snapshot; 52-week range calculated in Python | Four statements; history rows grow with retention | Detail, case, missing snapshot, and 52-week exclusion tests |
| P1 | History and intraday | `get_stock_history`, `get_stock_intraday`; repository symbol queries | All valid daily or all intraday observations loaded and returned | One existence query plus unbounded retrieval | Chronology, OHLC, unknown symbol, empty intraday, and live quote tests |
| P1 | Breadth, sectors, heatmap | `repositories/price_repository.py` aggregation methods | Each path independently discovers or embeds the latest common session and aggregates it | Constant statement count; execution cost depends on rows and PostgreSQL plan | Counts, methodology, sector count, ordering, equity filtering, common-session tests |
| P1 | Live sector calculation | `services/market_service.py`: `get_sector_analytics` | Calls historical sector analytics even though the value is unused, then calls heatmap | One unnecessary aggregation by source inspection | Live-state analytics tests; no SQL-count contract |
| P1 | Polling deduplication | `services/live_polling_worker.py`: `poll_cycle` | Loads every stored `(symbol, timestamp)` for symbols in the feed | Constant statements but rows grow with retained live history | Validation, duplicate, rollback, and persistence tests |
| P2 | Ingestion | `ingestion/service.py`; instrument and price repositories | Instrument existence query per symbol; price upsert loads all existing history separately per target instrument | Repeated per-instrument statements and history-sized reads | Ingestion validation, conflict, rollback, dry-run, and repository tests |

`PostgresMarketProvider._get_all_latest_prices` also contains an `N + 1`
pattern, but source search found no active caller.

## Confirmed SQLite measurements

Each result is deterministic across repeated test runs. SQL parameters are not
captured or logged. Listener removal has its own regression test.

| Path | 2 instruments | 5 instruments | 20 instruments | Observed model |
| --- | ---: | ---: | ---: | --- |
| Stock list | 4 | 7 | 22 | `N + 2` |
| Stock search matching all rows | 4 | 7 | 22 | `N + 2` |
| Gainers, all rows positive | 4 | 7 | 22 | `N + 2` |
| Losers, all rows negative | 4 | 7 | 22 | `N + 2` |
| Most active | 4 | 7 | 22 | `N + 2` |

## Milestone 7B result

Stock listing and search now use one set-based query joining every instrument
that has a price to its latest valid daily-price observation, followed by the
existing latest-snapshot lookup. The same deterministic SQLite fixtures measure:

| Path | 2 instruments | 5 instruments | 20 instruments | Result |
| --- | ---: | ---: | ---: | --- |
| Stock list | 2 | 2 | 2 | Kept |
| Stock search matching all rows | 2 | 2 | 2 | Kept |

This eliminates 2, 5, and 20 per-symbol latest-price statements respectively
at those fixture sizes. Correctness contracts preserve symbol ordering,
case-insensitive partial search, whitespace trimming, literal `%` and `_`
matching, inclusion of non-equities with valid prices, omission of instruments
without valid prices, latest-valid selection, and snapshot-derived timestamps.

PostgreSQL latency and plan improvement remain unmeasured until the isolated
benchmark environment described below is available. The change is retained on
the independently reproducible query-count reduction and green equivalence
contracts; it makes no claim about PostgreSQL wall-clock improvement.

## Milestone 7C result

The session-price query now uses its existing instrument join to populate the
`DailyPrice.instrument` relationship. Gainers, losers, and most-active consume
that already-loaded relationship instead of issuing one instrument lookup per
result. The common-session lookup remains separate and unchanged.

| Path | 2 instruments | 5 instruments | 20 instruments | 50 instruments | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Gainers, all rows positive | 2 | 2 | 2 | 2 | Kept |
| Losers, all rows negative | 2 | 2 | 2 | 2 | Kept |
| Most active | 2 | 2 | 2 | 2 | Kept |

This eliminates 2, 5, 20, and 50 per-result instrument statements at those
fixture sizes. Correctness contracts preserve the latest common valid equity
session, valid-OHLC and equity filtering, positive/negative/zero inclusion,
complete response fields, stable turnover/symbol tie-breaking, change ranking,
turnover ranking, and observation-date metadata.

The PostgreSQL dialect compiles the session query to one parameterized join
that selects both daily-price and instrument columns. No PostgreSQL connection,
timing run, or execution-plan measurement was performed, so PostgreSQL latency
improvement remains unmeasured.

Serialized provider-result sizes also grew linearly:

| Path | 2 rows | 5 rows | 20 rows |
| --- | ---: | ---: | ---: |
| Stock list/search | 630 B | 1,575 B | 6,300 B |
| Gainers | 280 B | 700 B | 2,800 B |
| Losers | 282 B | 705 B | 2,820 B |
| Most active | 278 B | 695 B | 2,780 B |

These are fixture payload sizes, not HTTP wire sizes or PostgreSQL timings.
Current integration contracts intentionally remain unbounded: the PostgreSQL API
tests expect more than 600 stock rows and more than 2,500 daily history rows for
NABIL. Milestone 7A introduces no limits or pagination.

## Correctness contracts

The new tests establish that future query changes must preserve:

- whitespace trimming, case-insensitive matching, and partial company search;
- symbol-ordered search results;
- stable mover ties using the current turnover-descending, symbol-ascending
  source order;
- the latest common valid equity session;
- exclusion of non-equities, missing observations, and invalid OHLC rows.

Existing tests additionally cover symbol search, detail lookup, chronological
history, 52-week boundaries, historical/live separation, sector methodology,
and unknown-symbol behavior.

## Safe PostgreSQL benchmark procedure

1. Create a new local database named `marketmitra_benchmark` with a dedicated
   least-privilege test user. Do not reuse `marketmitra`.
2. Verify the host is localhost, the database has no shared or production data,
   and the user can connect and transact only in this test database.
3. Apply the existing Alembic migrations to the empty database.
4. Set `MARKETMITRA_BENCHMARK_DATABASE_URL` to that database and set
   `MARKETMITRA_CONFIRM_DISPOSABLE=marketmitra_benchmark`.
5. Run `python -m tests.postgres_performance_benchmark` from `backend`.

The runner independently rejects remote hosts, ordinary database names,
unconfirmed names, missing schema, and populated application tables. It warms
each path once, records ten runs at 5, 20, and 100 instruments, reports median
and p95 application/database time, query count, and serialized response size,
then rolls the synthetic transaction back.

After `ANALYZE` on the isolated synthetic dataset, capture representative plans
with:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
SELECT ...;
```

Capture the latest-session query, session-price query, per-symbol latest-price
query, and each aggregation separately. Keep parameters and dataset constant;
record cold and warmed runs separately. Do not run `EXPLAIN ANALYZE` for writes
outside a transaction that will be rolled back.

## Proposed performance targets

These targets are for 7B verification, not assertions that the current baseline
is acceptable:

- Stock list and search: constant query count, target at most two statements,
  independent of instrument count.
- Gainers, losers, and most-active: constant query count, target at most two
  statements per request.
- Exact result equivalence for fields, filtering, ordering, ties, freshness
  timestamps, and missing-price behavior.
- At least 30% improvement in PostgreSQL median and p95 database time at the
  100-instrument fixture, and a delta larger than observed run-to-run variance.
- No regression greater than 5% on unaffected measured endpoints.
- No index or migration unless a before/after PostgreSQL plan proves it useful.

## Recommended Milestone 7B

Start only with stock listing and search, because their `N + 2` behavior is
confirmed and both share one low-risk data-access path.

- **Files:** `backend/app/repositories/price_repository.py`,
  `backend/app/providers/postgres_market.py`, repository/provider tests, and the
  7A performance contracts.
- **Design:** add one repository query that returns instruments joined to their
  latest valid daily price, with the latest snapshot fetched once. Apply the
  existing case-insensitive symbol/company predicate in SQL for search while
  preserving symbol ordering and complete unbounded results.
- **Equivalence:** compare complete serialized results from old and new paths for
  populated, missing-price, invalid-price, case/whitespace, and tie fixtures.
- **Expected benefit:** reduce confirmed `N + 2` statements to a constant one or
  two. Timing benefit remains a hypothesis until the isolated PostgreSQL run.
- **Migration:** none initially. Consider an index only after plan evidence.
- **Rollback:** revert the repository/provider commit; no data or schema rollback
  is needed.

Movers, history, aggregation, polling, and ingestion should remain separate
follow-up slices so each improvement can be measured and reverted independently.
