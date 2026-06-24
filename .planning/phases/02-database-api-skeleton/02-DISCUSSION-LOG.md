# Phase 2: Database + API Skeleton - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 2-Database + API Skeleton
**Areas discussed:** Note data model, List endpoint contract, Code layout reconcile, Test DB strategy

---

## Note Data Model

### Primary key type
| Option | Description | Selected |
|--------|-------------|----------|
| BIGINT autoincrement | Standard MySQL integer PK; simplest, fastest, ideal for learning; easy to reference later | ✓ |
| UUID (CHAR(36)/BINARY(16)) | Non-guessable, merge-friendly; more complexity than this phase needs | |

### Title field
| Option | Description | Selected |
|--------|-------------|----------|
| Content + optional source_url only | Match roadmap scope exactly; minimal model | ✓ |
| Add optional title field | Nicer listing UX but beyond stated scope | |

### Timestamps
| Option | Description | Selected |
|--------|-------------|----------|
| created_at + updated_at | Both, server-managed; enables sort-by-modified; good MySQL learning | ✓ |
| created_at only | Simpler; loses sort-by-modified and ON UPDATE learning | |

### Delete semantics
| Option | Description | Selected |
|--------|-------------|----------|
| Hard delete | Row removed, returns 204; simplest, matches "delete a note" | ✓ |
| Soft delete (deleted_at) | Enables undo/trash; adds filter complexity to every query | |

**User's choice:** BIGINT autoincrement · content + optional source_url (no title) · created_at + updated_at · hard delete.
**Notes:** All four were the recommended options — keeping the data model minimal and scope-aligned for the MVP slice.

---

## List Endpoint Contract (GET /notes)

### Pagination params
| Option | Description | Selected |
|--------|-------------|----------|
| ?page= & ?size= | 1-based page + size; matches roadmap ?page= criterion; default 20, max 100 (over→422) | ✓ |
| ?limit= & ?offset= | SQL-style; more flexible, less friendly, doesn't match success criteria wording | |

### Response shape
| Option | Description | Selected |
|--------|-------------|----------|
| {items, total, page, size, pages} | Envelope with pagination metadata; standard, Swagger-friendly | ✓ |
| Bare array + headers | Leaner body; metadata in X-Total-Count etc., easy to miss | |

### Sorting
| Option | Description | Selected |
|--------|-------------|----------|
| Default -created_at; created_at/updated_at with signed prefix | Newest-first default; leading '-' = desc; unknown field→422 | ✓ |
| Default newest; sort=field & order=asc\|desc | Two explicit params; more verbose | |

### Filtering
| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive substring of content | LIKE %term% on content; simple keyword narrowing | ✓ |
| Substring of content OR source_url | Broader match; marginally more query complexity | |

**User's choice:** ?page=/?size= (default 20, max 100) · {items,total,page,size,pages} envelope · default -created_at, signed-prefix sort on created_at/updated_at · ?filter= substring of content.
**Notes:** Real FULLTEXT search deferred to Phase 4 (SRCH-01); this ?filter= is deliberately a simpler LIKE match.

---

## Code Layout Reconcile

### Structure
| Option | Description | Selected |
|--------|-------------|----------|
| Domain-per-folder | app/notes/{router,schemas,models,service,repository}.py per ARCHITECTURE.md | ✓ |
| Layer-folders (keep Phase 1 seed) | app/api/notes.py + app/services/notes.py + app/repositories/notes.py | |

### Cleanup of Phase-1 empty folders
| Option | Description | Selected |
|--------|-------------|----------|
| Remove empty layer folders, keep health where it is | Delete empty app/services + app/repositories; leave app/api/health.py | ✓ |
| Remove empty folders AND move health | Same + standardize health placement; more churn | |
| Leave everything, just add app/notes/ | No churn but leaves dead empty packages | |

### Service layer for CRUD
| Option | Description | Selected |
|--------|-------------|----------|
| Keep thin NoteService | Router→Service→Repository; establishes pattern for Phase 3+ | ✓ |
| Router → Repository directly | Less boilerplate now; inconsistency to refactor later | |

**User's choice:** Domain-per-folder · remove empty app/services & app/repositories, keep app/api/health.py · keep thin NoteService.
**Notes:** Resolves the tension between Phase 1's seeded layer folders and ARCHITECTURE.md's domain-per-folder prescription, in favor of the research convention.

---

## Test DB Strategy

### MySQL provisioning
| Option | Description | Selected |
|--------|-------------|----------|
| testcontainers (ephemeral per run) | Throwaway mysql:8.4 per session; same code local + CI; needs Docker + 1 dev dep | ✓ |
| Dedicated compose test service | Transparent; must start manually; CI wires separately | |
| GHA service container + local compose | Two slightly different setups | |

### Schema setup
| Option | Description | Selected |
|--------|-------------|----------|
| alembic upgrade head against test DB | Tests real migrations; matches production; success criterion 4 | ✓ |
| Create tables from metadata | Faster; bypasses Alembic, won't catch broken migrations | |

### Isolation
| Option | Description | Selected |
|--------|-------------|----------|
| Transaction per test, rolled back | Fast, isolated, clean; standard pattern | ✓ |
| Truncate tables between tests | Simpler to reason about; slower | |

### Error response shape
| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI defaults | {"detail": ...} + default 422; zero custom code | ✓ |
| Custom error envelope | {error:{code,message}} via handlers; premature for this phase | |

**User's choice:** testcontainers (ephemeral mysql:8.4) · alembic upgrade head for schema · transaction-per-test rollback · FastAPI default error bodies.
**Notes:** testcontainers chosen partly so the same setup drops cleanly into Phase 7 GitHub Actions CI.

---

## Claude's Discretion

- Alembic first-migration approach (autogenerate vs hand-write) as long as it yields the utf8mb4 notes table and no create_all.
- DB session dependency wiring and lifespan implementation details.
- mysql healthcheck command/interval specifics.
- Lower-bound query validation (page<1, size<1) handling.
- Test fixture organization (conftest.py, fixture scopes).
- Index on created_at for sort performance.

## Deferred Ideas

- Auth / per-user note scoping → Phase 3
- Tags, collections, FULLTEXT search → Phase 4
- title field on notes → later if listing UX needs it
- Soft delete / trash / undo → only if a need appears
- Custom error envelope → deferred (FastAPI defaults this phase)
- CI pipeline / prod compose override → Phase 7
