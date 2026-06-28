# Phase 4: Tags, Collections, Full-Text Search — Research

**Researched:** 2026-06-28
**Domain:** MySQL many-to-many relationships, FULLTEXT search configuration, async SQLAlchemy 2 query patterns
**Confidence:** HIGH (core patterns verified against installed packages + official MySQL docs + SQLAlchemy source)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tags (ORG-01, ORG-02)**
- **D-01:** Auto-create-on-attach (find-or-create by name). No separate `POST /tags` ceremony — tagging a note with a name finds the user's existing tag or creates it, then attaches.
- **D-02:** Tags are per-user. The `tags` table carries a `user_id` FK; each user has a private tag namespace. `GET /tags` returns only the caller's tags.
- **D-03:** Tag names are normalized on the way in — trimmed + lowercased — so "Python", "python", and " python " collapse to the same tag. Uniqueness enforced per user on the normalized name (`UNIQUE(user_id, name)`); find-or-create keys off the normalized value.
- **D-04:** Many-to-many via a `note_tags` join table.
- **D-05:** Multi-tag filter is AND (intersection). `GET /notes?tag=python&tag=docker` returns only notes carrying BOTH tags. Tag filter lives on the existing `GET /notes` list endpoint, composing with pagination/sort/filter. Use `selectinload` to avoid N+1.

**Collections (ORG-03, ORG-04)**
- **D-06:** Collections are many-to-many with notes via a `note_collections` join table.
- **D-07:** Collections are per-user, `user_id` FK; 403/404 ownership contract from Phase 3.
- **D-08:** REST surface: create collection, add note (`POST /collections/{id}/notes`), remove note, list notes (`GET /collections/{id}/notes`) with `NoteListResponse` envelope.

**Full-Text Search (SRCH-01)**
- **D-09:** Standalone `GET /search?q=` endpoint returning `NoteListResponse`, user-scoped, does NOT compose with tag/collection filters this phase.
- **D-10:** `MATCH(title, content) AGAINST(:q IN BOOLEAN MODE)` — reuses the existing `ft_notes_content(title, content)` FULLTEXT index.
- **D-11:** `innodb_ft_min_token_size = 2` must be set on the MySQL service AND the testcontainers MySQL container so 2-char terms ("AI") are indexed and searchable.

### Claude's Discretion (sensible defaults — planner may refine)
- Exact REST shape for tag attach/detach (`POST /notes/{id}/tags` with `{name}` + `DELETE /notes/{id}/tags/{name|id}`)
- Whether detaching the last note from a tag auto-deletes orphan tags (default: persist)
- `ON DELETE CASCADE` behavior for join table rows (default: cascade)
- Collection name uniqueness per user (`UNIQUE(user_id, name)`) — recommended
- BOOLEAN MODE query sanitization for stray operator characters (planner must handle gracefully)
- How `innodb_ft_min_token_size=2` is delivered (compose `command:` arg vs mounted `my.cnf`) and how the index rebuild is sequenced relative to Alembic migrations
- Whether `GET /search` supports sort whitelist or defaults to FULLTEXT relevance score

### Deferred Ideas (OUT OF SCOPE)
- Hybrid full-text + semantic rank fusion (SRCH-02, v2)
- Search composing with tag/collection filters
- Tag rename endpoint, tag/collection descriptions, colors, icons
- Bulk tagging / bulk collection assignment
- Search result highlighting / snippets / facets
- Auto-tagging via LLM (Phase 5)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORG-01 | User can create tags and attach/detach them to notes (many-to-many) | D-01..D-04: `tags` + `note_tags` tables; find-or-create pattern; `POST /notes/{id}/tags`, `DELETE /notes/{id}/tags/{name}` |
| ORG-02 | User can filter notes by one or more tags | D-05: AND-intersection via GROUP BY HAVING COUNT subquery; `selectinload(Note.tags)` for N+1-free serialization; `?tag=` query param on `GET /notes` |
| ORG-03 | User can create collections and add/remove notes from them | D-06..D-08: `collections` + `note_collections` tables; `POST /collections`, `POST /collections/{id}/notes`, `DELETE /collections/{id}/notes/{note_id}` |
| ORG-04 | User can list the notes contained in a collection | D-08: `GET /collections/{id}/notes` returns `NoteListResponse` envelope with ownership check |
| SRCH-01 | User can full-text search their notes by keyword (MySQL FULLTEXT) | D-09..D-11: `sqlalchemy.dialects.mysql.match()` in BOOLEAN MODE; `innodb_ft_min_token_size=2` in compose + testcontainers; FULLTEXT index rebuild in Phase-4 migration |
</phase_requirements>

---

## Summary

Phase 4 extends the note store with two organizational layers (tags, collections) and keyword search. All three are fundamentally well-trodden CRUD patterns on top of the existing async SQLAlchemy 2 / asyncmy / MySQL 8.4 stack — except for five genuinely tricky areas documented in detail below.

The phase adds three new domain packages (`app/tags/`, `app/collections/`, `app/search/`) mirroring the established `app/notes/` Router → Service → Repository pattern. One new Alembic migration creates four tables (`tags`, `note_tags`, `collections`, `note_collections`) and rebuilds the FULLTEXT index. Docker Compose and the testcontainers fixture both need a one-line startup argument change for `innodb_ft_min_token_size=2`. No new Python dependencies are required.

**The five genuinely tricky parts:**
1. `innodb_ft_min_token_size` is a startup-only variable — the MySQL container must receive it at launch, and the existing FULLTEXT index must be rebuilt in the Alembic migration.
2. `sqlalchemy.dialects.mysql.match()` is the correct SQLAlchemy 2 expression for `MATCH ... AGAINST ... IN BOOLEAN MODE` — not `text()`, not `func.match()`.
3. The AND-tag-intersection filter requires a GROUP BY / HAVING COUNT(DISTINCT) subquery, then `Note.id.in_(subquery)` on the outer paginated query + `selectinload(Note.tags)`.
4. The find-or-create tag pattern must use `session.begin_nested()` (savepoint) — not bare `session.rollback()` — to handle the race-condition `IntegrityError` without destroying the outer test transaction.
5. `NoteRead` needs a `tags: list[TagRead]` field, and `list_paginated()` / `get_by_id()` must add `selectinload(Note.tags)` — otherwise async lazy-load raises `MissingGreenlet`.

**Primary recommendation:** Follow the patterns below exactly; the non-tricky CRUD (tag list, collection CRUD, add/remove note-collection membership) is a direct copy of the Phase-2/3 patterns.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tag find-or-create + normalize | API / Backend (TagRepository) | — | Normalization is a server-side invariant; client never owns it |
| Tag attach/detach (many-to-many) | API / Backend (TagService) | MySQL (FK cascade) | ORM manages join-table rows; DB handles CASCADE on delete |
| Tag AND-filter on note list | API / Backend (NoteRepository) | MySQL (GROUP BY HAVING) | Query logic in repo; MySQL executes the GROUP BY/HAVING subquery |
| Collection CRUD + ownership | API / Backend (CollectionService) | — | Same 404-vs-403 pattern as notes |
| Collection note membership | API / Backend (CollectionRepository) | MySQL (FK cascade) | ORM manages join rows |
| FULLTEXT keyword search | API / Backend (SearchRepository) | MySQL (InnoDB FULLTEXT) | `match().in_boolean_mode()` issued from repo; index lives in MySQL |
| FULLTEXT index rebuild | MySQL (Alembic migration) | — | DDL runs in migration; can't be done at runtime via ORM |
| `innodb_ft_min_token_size` config | MySQL (Docker/testcontainers startup) | — | Read-only at runtime; must be set before mysqld starts |

---

## Standard Stack

No new dependencies are required for this phase. All patterns use libraries already in `pyproject.toml`.

### Core (existing — no new installs)

| Library | Version (installed) | Purpose in Phase 4 |
|---------|--------------------|--------------------|
| SQLAlchemy | 2.0.51 | `Table()` association tables, `relationship(secondary=...)`, `selectinload`, `match()` dialect expr |
| asyncmy | 0.2.x | MySQL async driver (unchanged) |
| Alembic | 1.18.4 | Migration adding tags/collections/join tables + FULLTEXT rebuild |
| FastAPI | 0.115.x | Three new routers: `/notes/{id}/tags`, `/collections`, `/search` |
| Pydantic v2 | 2.x | `TagRead`, `CollectionRead`, `NoteRead` extension with `tags` field |

[VERIFIED: npm registry] — not applicable; stack is Python/pyproject.toml verified above.

### Key dialect expression

```python
from sqlalchemy.dialects.mysql import match
# NOT: func.match() — that is the generic SQL MATCH which does not support .in_boolean_mode()
# NOT: text() — works but bypasses ORM column refs; match() is safer and idiomatic
```

[VERIFIED: SQLAlchemy 2.0.51 installed package `sqlalchemy/dialects/mysql/expression.py`]

### No new packages to add

This phase is purely application logic on the existing stack. `uv add` is NOT needed.

---

## Package Legitimacy Audit

> No new packages are installed in this phase. The standard stack from Phases 1–3 handles all requirements.

**Packages removed due to slopcheck [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time; however since no new packages are introduced, this section is vacuous.*

---

## Architecture Patterns

### System Architecture Diagram

```
Client (Swagger / curl)
    │
    │  POST /notes/{id}/tags  {"name": "python"}
    │  GET  /notes?tag=python&tag=docker
    │  POST /collections/{id}/notes  {"note_id": 5}
    │  GET  /collections/{id}/notes
    │  GET  /search?q=python
    ▼
FastAPI Router (tags/router.py | collections/router.py | search/router.py)
    │  parse request, call service, return response
    ▼
Service Layer (TagService | CollectionService | SearchService)
    │  business rules: 404/403 ownership; find-or-create; normalize; sanitize
    ▼
Repository Layer (TagRepository | CollectionRepository | SearchRepository)
    │  all SQL here: GROUP BY HAVING COUNT; match().in_boolean_mode(); selectinload
    ▼
MySQL 8.4 (InnoDB, FULLTEXT, utf8mb4)
    ├── tags  [UNIQUE(user_id, name)]
    ├── note_tags  [composite PK (note_id, tag_id)]
    ├── collections  [optional UNIQUE(user_id, name)]
    ├── note_collections  [composite PK (note_id, collection_id)]
    └── notes.ft_notes_content FULLTEXT (title, content)  [rebuilt with min_token_size=2]
```

### Recommended Project Structure Changes

```
app/
├── notes/
│   ├── models.py          # Add: tags/collections relationships + note_tags/note_collections Table()
│   ├── repository.py      # Extend: list_paginated() gains ?tag= filter + selectinload(Note.tags)
│   │                      #        get_by_id() gains selectinload(Note.tags)
│   └── schemas.py         # Extend: NoteRead gains `tags: list[TagRead]`
│
├── tags/                  # NEW domain package
│   ├── __init__.py
│   ├── models.py          # Tag ORM model
│   ├── schemas.py         # TagCreate, TagRead
│   ├── repository.py      # find_or_create_tag, list_by_user, attach_to_note, detach_from_note
│   └── service.py         # TagService: orchestrate repo, normalize, ownership
│   └── router.py          # GET /tags, POST /notes/{id}/tags, DELETE /notes/{id}/tags/{name}
│
├── collections/           # NEW domain package
│   ├── __init__.py
│   ├── models.py          # Collection ORM model
│   ├── schemas.py         # CollectionCreate, CollectionRead
│   ├── repository.py      # CRUD + add_note / remove_note / list_notes
│   └── service.py         # get_or_404_owned (mirrors NoteService pattern)
│   └── router.py          # POST /collections, GET /collections, GET|DELETE /collections/{id}/notes
│
├── search/                # NEW (or extend notes router with search route)
│   ├── __init__.py
│   ├── router.py          # GET /search?q=
│   ├── schemas.py         # SearchQuery (q: str, page, size)
│   └── repository.py      # search_fulltext() using mysql.match().in_boolean_mode()
│   └── service.py         # SearchService: sanitize q, call repo, paginate
│
└── core/
    └── dependencies.py    # Add: get_tag_service, get_collection_service, get_search_service

alembic/versions/
└── 0004_add_tags_collections.py  # down_revision = "0003_add_user_id_to_notes"
```

### Pattern 1: Many-to-Many Tables (SQLAlchemy 2 style)

**What:** Core Table objects defined at module level in the domain that owns them. ORM models use `relationship(secondary=...)`.

**Where to define:** `app/notes/models.py` is the right place for both join tables (since Note is the central entity and the join tables reference `notes.id`). The `Tag` and `Collection` ORM models live in their own domains.

**Example:**

```python
# app/notes/models.py  (additions)
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.dialects.mysql import INTEGER as MUINT
from sqlalchemy.orm import relationship
from app.database import Base

# --- Association tables (module-level, not ORM classes) ---
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", MUINT(unsigned=True), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",  MUINT(unsigned=True), ForeignKey("tags.id",  ondelete="CASCADE"), primary_key=True),
    mysql_engine="InnoDB",
)

note_collections = Table(
    "note_collections",
    Base.metadata,
    Column("note_id",       MUINT(unsigned=True), ForeignKey("notes.id",       ondelete="CASCADE"), primary_key=True),
    Column("collection_id", MUINT(unsigned=True), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    mysql_engine="InnoDB",
)

class Note(Base):
    # ... existing columns ...
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=note_tags, lazy="select"
    )
    collections_rel: Mapped[list["Collection"]] = relationship(
        "Collection", secondary=note_collections, lazy="select"
    )
```

[VERIFIED: SQLAlchemy 2.0.51 docs + installed package inspection]

**Critical:** use `lazy="select"` (default) on the relationship — do NOT use `lazy="selectin"` here (that conflicts with explicit `selectinload()` options in queries). Instead, add `selectinload(Note.tags)` explicitly in every async query.

### Pattern 2: selectinload for Eager Loading (No N+1)

**What:** Always use `selectinload(Note.tags)` in `list_paginated()` and `get_by_id()`. Never access `note.tags` on an instance from an async session without this — it will raise `MissingGreenlet`.

**Why selectin over joinedload:** For collections (many records each having multiple tags), `selectinload` is superior to `joinedload` because it avoids Cartesian-product result explosion and is the SQLAlchemy team's recommendation for one-to-many/many-to-many in async contexts.

```python
# app/notes/repository.py — extend list_paginated()
from sqlalchemy.orm import selectinload

# In the base query (ALWAYS, not just when tags filter is active):
query = (
    select(Note)
    .where(Note.user_id == user_id)
    .options(selectinload(Note.tags))   # ADD THIS
)
```

[VERIFIED: SQLAlchemy 2.0.51 docs + python execution above]

### Pattern 3: AND-Intersection Tag Filter

**What:** `GET /notes?tag=python&tag=docker` must return only notes that have BOTH tags. This requires a two-level subquery: first find note_ids that have all requested tags, then use those IDs in the main paginated query.

**Method: GROUP BY / HAVING COUNT(DISTINCT)** — most efficient for MySQL, clean SQL.

```python
# app/notes/repository.py — extend list_paginated() (imports: func, select, note_tags, Tag)

from sqlalchemy import select, func
from app.notes.models import note_tags  # the Table() object
from app.tags.models import Tag

async def list_paginated(
    self,
    page: int,
    size: int,
    sort: str = "-created_at",
    filter: str | None = None,
    tags: list[str] | None = None,   # NEW parameter
    *,
    user_id: int,
) -> tuple[list[Note], int]:

    # ... existing sort parsing ...

    # --- Build base query (owner-scoped) ---
    query = select(Note).where(Note.user_id == user_id)

    # --- Optional tag AND-filter (D-05) ---
    if tags:
        # Step 1: find tag IDs matching ALL requested normalized names for this user
        tag_id_subq = (
            select(Tag.id)
            .where(Tag.name.in_([t.strip().lower() for t in tags]))
            .where(Tag.user_id == user_id)
            .scalar_subquery()
        )
        # Step 2: find note_ids that have ALL N tags (HAVING COUNT(DISTINCT) = N)
        matching_note_ids = (
            select(note_tags.c.note_id)
            .where(note_tags.c.tag_id.in_(tag_id_subq))
            .group_by(note_tags.c.note_id)
            .having(func.count(note_tags.c.tag_id.distinct()) == len(tags))
            .scalar_subquery()
        )
        query = query.where(Note.id.in_(matching_note_ids))

    # --- Optional content filter (existing) ---
    if filter:
        query = query.where(Note.content.ilike(f"%{filter}%"))

    # --- Always eager-load tags (no N+1) ---
    query = query.options(selectinload(Note.tags))

    # --- Count (scoped to owner + tag filter) ---
    count_q = select(func.count()).select_from(query.subquery())
    total: int = (await self._session.execute(count_q)).scalar_one()

    # --- Sort + paginate ---
    query = query.order_by(order_fn(order_col)).offset((page - 1) * size).limit(size)
    result = await self._session.execute(query)
    return list(result.scalars().all()), total
```

**Generated SQL (verified via `stmt.compile(dialect=mysql.dialect())`):**
```sql
SELECT notes.id, notes.user_id, ...
FROM notes
WHERE notes.user_id = %s
  AND notes.id IN (
      SELECT note_tags.note_id FROM note_tags
      WHERE note_tags.tag_id IN (
          SELECT tags.id FROM tags
          WHERE tags.name IN (%s, %s) AND tags.user_id = %s
      )
      GROUP BY note_tags.note_id
      HAVING count(DISTINCT note_tags.tag_id) = %s
  )
LIMIT %s, %s
```

[VERIFIED: executed via SQLAlchemy 2.0.51 installed package above]

**Why not repeated EXISTS subqueries:** Each `EXISTS` subquery per tag scales as O(N × query_cost). The GROUP BY/HAVING approach is a single JOIN regardless of how many tags. On MySQL with InnoDB, the optimizer handles this well.

**Why not INTERSECT:** MySQL 8.4 supports `INTERSECT` but SQLAlchemy's `intersect()` produces a compound SELECT that is harder to compose with pagination and `selectinload`. Stick with the subquery.

### Pattern 4: FULLTEXT BOOLEAN MODE with sqlalchemy.dialects.mysql.match()

**What:** Use the MySQL-dialect-specific `match()` function, NOT `text()` and NOT `func.match()`. The dialect `match()` supports `.in_boolean_mode()` and parameterizes the search term automatically.

```python
# app/search/repository.py
from sqlalchemy import select, func
from sqlalchemy.dialects.mysql import match
from sqlalchemy.orm import selectinload
from app.notes.models import Note

class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_fulltext(
        self,
        q: str,
        user_id: int,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Note], int]:
        """MATCH(title, content) AGAINST(:q IN BOOLEAN MODE), user-scoped + paginated."""
        match_expr = match(Note.title, Note.content, against=q).in_boolean_mode()

        base = (
            select(Note)
            .where(match_expr)
            .where(Note.user_id == user_id)
            .options(selectinload(Note.tags))
        )

        total: int = (
            await self._session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()

        result = await self._session.execute(
            base.offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total
```

**Generated SQL (verified):**
```sql
SELECT notes.id, notes.user_id, notes.title, notes.content, ...
FROM notes
WHERE MATCH (notes.title, notes.content) AGAINST (%s IN BOOLEAN MODE)
  AND notes.user_id = %s
LIMIT %s, %s
```

[VERIFIED: SQLAlchemy 2.0.51 installed `sqlalchemy.dialects.mysql.match` + compiled above]

**Sort decision for search:** Default to FULLTEXT relevance score (no explicit ORDER BY — MySQL returns highest-scoring rows first). Do not add a sort whitelist to the `/search` endpoint this phase. The score is implicit in BOOLEAN MODE.

**BOOLEAN MODE stopword behavior (from official MySQL 8.4 docs):**
- 50% threshold does NOT apply in BOOLEAN MODE — predictable results [CITED: dev.mysql.com/doc/refman/8.4/en/fulltext-boolean.html]
- Stopwords DO still apply by default — common words like "the", "is" may be excluded
- `innodb_ft_min_token_size=2` makes 2-char tokens like "AI", "Go", "ML" searchable
- The `*` wildcard is a suffix wildcard (no leading wildcard)

### Pattern 5: BOOLEAN MODE Input Sanitization

**What:** The `against=` value is sent as a bound parameter (no SQL injection risk). However, InnoDB will raise an error for certain invalid operator combinations. Sanitize before passing.

**InnoDB BOOLEAN MODE error-causing patterns [CITED: dev.mysql.com/doc/refman/8.4/en/fulltext-boolean.html]:**
- `++word` or `+-word` — multiple operators
- `word+` — trailing operator
- `+*` — plus with bare wildcard
- `@` — reserved for `@distance` proximity operator (complex, skip this phase)

```python
# app/search/service.py
import re

def sanitize_boolean_query(q: str) -> str | None:
    """Sanitize user input for MATCH ... AGAINST ... IN BOOLEAN MODE.

    Returns None if the sanitized query is empty (caller skips DB query, returns empty list).
    """
    q = q.strip()
    if not q:
        return None
    # Remove @ (reserved for @distance proximity, unsupported this phase)
    q = q.replace("@", " ")
    # Remove consecutive operators: ++, +-, -+, --
    q = re.sub(r"[+\-]{2,}", "", q)
    # Remove trailing operators at end of any token
    q = re.sub(r"([a-zA-Z0-9*])[+\-]+(?=\s|$)", r"\1", q)
    # Collapse whitespace
    q = re.sub(r"\s+", " ", q).strip()
    return q or None
```

[VERIFIED: sanitization function tested via Python exec above; operator rules from official MySQL 8.4 docs]

### Pattern 6: find-or-create Tag with SAVEPOINT (race-condition safe)

**What:** D-01 requires find-or-create by name. Two concurrent requests may hit the window between SELECT and INSERT — the second insert violates the `UNIQUE(user_id, name)` constraint. Handle with `session.begin_nested()` (a SQL SAVEPOINT), NOT bare `session.rollback()`.

**Why savepoint, not rollback:** The tests use a transaction-per-test rollback strategy (see `conftest.py`). A bare `session.rollback()` inside find-or-create would roll back the entire test transaction, destroying all prior test data. A savepoint rolls back only the failed INSERT, leaving the outer transaction intact.

```python
# app/tags/repository.py
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.tags.models import Tag

class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create(self, user_id: int, raw_name: str) -> Tag:
        """Find-or-create a Tag for this user, normalized (D-01, D-03).

        Uses a SAVEPOINT to handle the race-condition window between
        the initial SELECT (not found) and the INSERT (concurrent request wins).
        A SAVEPOINT (begin_nested) rolls back only the failed insert,
        NOT the outer test transaction.
        """
        name = raw_name.strip().lower()  # D-03: normalize

        # Optimistic path — common case, no contention
        existing = (await self._session.execute(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        )).scalar_one_or_none()
        if existing is not None:
            return existing

        tag = Tag(user_id=user_id, name=name)
        try:
            async with self._session.begin_nested():  # SAVEPOINT
                self._session.add(tag)
            return tag
        except IntegrityError:
            # Concurrent request won the race; savepoint rolled back, outer tx intact
            return (await self._session.execute(
                select(Tag).where(Tag.user_id == user_id, Tag.name == name)
            )).scalar_one()
```

[VERIFIED: SQLAlchemy 2.0.51 supports `AsyncSession.begin_nested()` returning `AsyncSessionTransaction` as an async context manager; IntegrityError raised on UNIQUE violation is from `sqlalchemy.exc`]

### Pattern 7: Alembic Migration for Phase 4 Tables + FULLTEXT Rebuild

**What:** One migration chained from `0003_add_user_id_to_notes`, creating four tables AND rebuilding the FULLTEXT index so it uses `innodb_ft_min_token_size=2`.

**Critical sequencing:** The FULLTEXT index rebuild MUST happen in the migration (not in application code) because:
- The index was created by migration `d51191e92276` before `innodb_ft_min_token_size=2` was configured
- On fresh installs where the MySQL container already has `min_token_size=2` at startup, the DROP+ADD is harmless (idempotent on an empty table)
- On existing installs (upgrading from Phase 3), the DROP+ADD ensures the index uses the new token size

```python
# alembic/versions/0004_add_tags_collections.py
"""Add tags, note_tags, collections, note_collections tables; rebuild FULLTEXT index.

Revision ID: 0004_add_tags_collections
Revises: 0003_add_user_id_to_notes
"""
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from alembic import op

revision: str = "0004_add_tags_collections"
down_revision: str | Sequence[str] | None = "0003_add_user_id_to_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. tags table — per-user, normalized name, unique per user
    op.create_table(
        "tags",
        sa.Column("id", mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", mysql.INTEGER(unsigned=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tag"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # 2. note_tags join table — composite PK, CASCADE on both FKs
    op.create_table(
        "note_tags",
        sa.Column("note_id", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("tag_id",  mysql.INTEGER(unsigned=True), nullable=False),
        sa.PrimaryKeyConstraint("note_id", "tag_id", name="pk_note_tags"),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"],  ["tags.id"],  ondelete="CASCADE"),
        mysql_engine="InnoDB",
    )

    # 3. collections table — per-user
    op.create_table(
        "collections",
        sa.Column("id", mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", mysql.INTEGER(unsigned=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_collection"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # 4. note_collections join table — composite PK, CASCADE on both FKs
    op.create_table(
        "note_collections",
        sa.Column("note_id",       mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("collection_id", mysql.INTEGER(unsigned=True), nullable=False),
        sa.PrimaryKeyConstraint("note_id", "collection_id", name="pk_note_collections"),
        sa.ForeignKeyConstraint(["note_id"],       ["notes.id"],       ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        mysql_engine="InnoDB",
    )

    # 5. Rebuild FULLTEXT index with innodb_ft_min_token_size=2
    # The old index was created by migration d51191e92276 before min_token_size was configured.
    # DROP + ADD ensures the new index uses the server's current min_token_size=2 setting.
    # Safe on fresh installs (empty notes table) and correct on existing DBs.
    op.execute("ALTER TABLE notes DROP INDEX ft_notes_content")
    op.execute("ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)")


def downgrade() -> None:
    # Restore original FULLTEXT index (with default min_token_size)
    op.execute("ALTER TABLE notes DROP INDEX ft_notes_content")
    op.execute("ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)")
    op.drop_table("note_collections")
    op.drop_table("collections")
    op.drop_table("note_tags")
    op.drop_table("tags")
```

[VERIFIED: Alembic 1.18.4; `sa.PrimaryKeyConstraint` for composite PKs; `sa.UniqueConstraint` for named unique constraints; raw DDL `op.execute()` for FULLTEXT (Alembic has limited FULLTEXT support); pattern mirrors `d51191e92276` which also uses `op.execute()` for FULLTEXT]

### Pattern 8: innodb_ft_min_token_size Configuration

**What:** A startup-only MySQL variable (non-dynamic — cannot be changed via `SET GLOBAL`). Must be set before mysqld starts in both docker-compose and testcontainers.

**Verified fact:** Default value is 3. Setting to 2 makes 2-character tokens ("AI", "Go", "ML") indexable. After changing, ALL FULLTEXT indexes must be rebuilt. [CITED: dev.mysql.com/doc/refman/8.4/en/fulltext-fine-tuning.html]

#### docker-compose.yml change

```yaml
# docker-compose.yml — mysql service: add command line arg
mysql:
  image: mysql:8.4
  command: --innodb-ft-min-token-size=2    # ADD THIS LINE
  env_file:
    - .env
  # ... rest unchanged ...
```

Note: `command:` overrides the Docker CMD (arguments to mysqld). The mysql:8.4 entrypoint (`docker-entrypoint.sh`) passes these as mysqld flags. No custom `my.cnf` needed. [CITED: hub.docker.com/_/mysql — "Passing options to the server" section]

**Why not my.cnf mount:** The `command:` approach requires zero new files. Both approaches are valid; `command:` is simpler for a single variable.

#### tests/conftest.py change

```python
# tests/conftest.py — extend mysql_container fixture
@pytest.fixture(scope="session")
def mysql_container():
    """Spin up mysql:8.4 with innodb_ft_min_token_size=2 for 2-char FULLTEXT tests (D-11)."""
    container = (
        MySqlContainer("mysql:8.4")
        .with_command("--innodb-ft-min-token-size=2")
    )
    with container:
        yield container
```

`with_command()` is on `DockerContainer` (parent of `MySqlContainer`) and sets `_command`, which Docker passes as the container CMD. [VERIFIED: installed testcontainers 4.14.2 source inspection above]

**Startup-variable sequencing:**
1. `innodb_ft_min_token_size=2` is set at MySQL container start (via `command:` / `.with_command()`)
2. `alembic upgrade head` runs after MySQL is ready (via `depends_on: condition: service_healthy` in compose, or in `run_migrations` fixture)
3. Migration `0004` runs: creates tables AND DROP/ADD the FULLTEXT index — at this point MySQL is already using `min_token_size=2`, so the new index is built correctly
4. 2-char tokens are now searchable in all notes (including existing data)

### Anti-Patterns to Avoid

- **`lazy="selectin"` on the ORM relationship + explicit `selectinload()`:** Redundant — use `lazy="select"` (default) on the relationship and always add `selectinload()` explicitly in async queries.
- **`session.rollback()` in find-or-create:** Destroys the outer test transaction in the per-test rollback harness. Use `session.begin_nested()` (SAVEPOINT).
- **`func.match()` for MySQL FULLTEXT:** The generic `func.match()` doesn't know about `.in_boolean_mode()`. Use `from sqlalchemy.dialects.mysql import match`.
- **`text("MATCH ... AGAINST ...")` with f-string interpolation:** Direct SQL injection path. The `match()` dialect function parameterizes automatically.
- **`OPTIMIZE TABLE` for FULLTEXT rebuild in migration:** `OPTIMIZE TABLE` with `innodb_optimize_fulltext_only=ON` requires a global SET and multiple calls for large tables. For this phase's small dataset, `ALTER TABLE ... DROP INDEX ... ADD FULLTEXT KEY ...` is simpler and deterministic.
- **`SET GLOBAL innodb_ft_min_token_size=2` at runtime:** ERROR — this variable is read-only at runtime. MySQL returns `ERROR 1238 (HY000): Variable 'innodb_ft_min_token_size' is a read only variable`.
- **Attaching a tag in two concurrent requests without savepoint:** The UNIQUE constraint enforces correctness, but without savepoint the `IntegrityError` corrupts the session state in the async context.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MATCH AGAINST in BOOLEAN MODE | Raw `text()` f-strings | `sqlalchemy.dialects.mysql.match().in_boolean_mode()` | Parameterization, ORM column refs, composable |
| Many-to-many relationship management | Manual join-table INSERT/DELETE | `relationship(secondary=...)` + ORM collection append/remove | SQLAlchemy flushes join rows on commit; cascade-deletes join rows when parent is deleted |
| 50% threshold exclusion in FULLTEXT | Custom relevance scoring | BOOLEAN MODE natively avoids the 50% threshold | It's already the decision (D-10) |
| Eager loading for async | Accessing `note.tags` attribute post-query | `selectinload(Note.tags)` in the SELECT | Lazy load in async raises `MissingGreenlet`; `selectinload` batches into one extra query |
| N-exists tag-AND filter | N repeated `EXISTS` subqueries | GROUP BY / HAVING COUNT(DISTINCT) subquery | N separate EXISTS queries each hit the full `note_tags` table; GROUP BY is a single pass |

**Key insight:** SQLAlchemy's `relationship(secondary=...)` with `selectinload` solves the two hardest problems (N+1 and join-table management) without any custom code. Trust the ORM for the join-table write path; hand-roll only the GROUP BY/HAVING filter because the ORM's relationship filter helpers (`has()`, `any()`) don't support AND-all-of-N semantics natively.

---

## Common Pitfalls

### Pitfall 1: `innodb_ft_min_token_size` is Read-Only at Runtime

**What goes wrong:** Developer tries `SET GLOBAL innodb_ft_min_token_size=2;` to fix 2-char search without restarting — MySQL returns `ERROR 1238: Variable 'innodb_ft_min_token_size' is a read only variable`.

**Why it happens:** InnoDB builds its tokenization data structures at startup; the variable cannot change after that.

**How to avoid:** Set via `command:` in docker-compose.yml (or `--innodb-ft-min-token-size=2` mysqld flag) before the container starts. Rebuild the FULLTEXT index in the migration after startup.

**Warning signs:** `SHOW VARIABLES LIKE 'innodb_ft_min_token_size'` returns `3` (default). 2-char searches return empty results even for notes containing "AI".

### Pitfall 2: FULLTEXT Index Created Before `innodb_ft_min_token_size=2` Takes Effect

**What goes wrong:** The FULLTEXT index `ft_notes_content` was created by migration `d51191e92276` with the default `min_token_size=3`. Even after you restart MySQL with `min_token_size=2`, the old index data still ignores 2-char tokens — the index must be rebuilt.

**Why it happens:** The token size is baked into the index at creation time. The server variable controls new tokens being inserted, but the old indexed data is already stored with the old size.

**How to avoid:** Migration `0004` must DROP + ADD the FULLTEXT index. For fresh installs (container configured with `min_token_size=2` before `alembic upgrade head`), the drop+add in the migration is harmless. For any existing DB, it's mandatory.

**Warning signs:** `GET /search?q=AI` returns 0 results even though notes contain "AI"; `GET /search?q=artificial` returns results correctly. Running `SHOW INDEX FROM notes WHERE Key_name = 'ft_notes_content'` doesn't reveal the issue — you need to actually test the 2-char search.

### Pitfall 3: MissingGreenlet on `note.tags` in Async Context

**What goes wrong:** `NoteRead.model_validate(note)` (or accessing `note.tags` on a Note returned from an async query without `selectinload`) raises `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`.

**Why it happens:** In async SQLAlchemy, all lazy loads that would hit the database are prohibited outside the async execution context. Accessing a `lazy="select"` relationship attribute after the session has returned the object triggers an implicit database load, which fails.

**How to avoid:** Every query that returns a `Note` and whose results will be serialized into `NoteRead` (which now has `tags: list[TagRead]`) MUST include `.options(selectinload(Note.tags))`. This means updating `get_by_id()` in `NoteRepository` and adding `selectinload` to all paths in `list_paginated()`.

**Warning signs:** Tests pass when tags list is empty (no load attempted), fail when a note actually has tags attached.

### Pitfall 4: session.rollback() Destroys Test Transaction

**What goes wrong:** The find-or-create tag catch block calls `await session.rollback()` when `IntegrityError` is raised. In the test harness, this rolls back the entire per-test transaction (the one the `session` fixture opened), destroying all data created earlier in the test.

**Why it happens:** The test `session` fixture uses a single outer transaction + rollback strategy (see `conftest.py`). `session.rollback()` rolls back ALL uncommitted work on that session.

**How to avoid:** Use `async with session.begin_nested()` (SAVEPOINT) around the INSERT. When `IntegrityError` is raised, only the savepoint rolls back, not the outer transaction.

**Warning signs:** Test that creates a user, creates a note, then tags it — the tag creation raises IntegrityError on second attempt (concurrent simulation), and subsequent assertions fail because the user or note no longer exists in the DB.

### Pitfall 5: GROUP BY Result Set Ordering and Pagination

**What goes wrong:** The GROUP BY subquery used for AND-tag-filter doesn't guarantee any specific row order. Combined with OFFSET/LIMIT pagination, page 2 may overlap with page 1 or skip rows if not ordered consistently.

**Why it happens:** The subquery returns note_ids in arbitrary order; the outer query applies ORDER BY on the full Note result set AFTER the IN filter.

**How to avoid:** The ORDER BY and LIMIT/OFFSET are applied on the OUTER query (the main `select(Note)` that filters by `Note.id.in_(matching_note_ids)`), not inside the subquery. The subquery only returns IDs — ordering is controlled by the outer query's existing `order_fn(order_col)`. This is the correct pattern and is how the code above is structured.

**Warning signs:** Pagination tests show items appearing on multiple pages or items being skipped entirely.

### Pitfall 6: Normalization Inconsistency Between attach and filter

**What goes wrong:** Tags are stored normalized (lowercase-trimmed) at creation time (D-03), but the `?tag=` filter query doesn't normalize the input before comparing. `GET /notes?tag=Python` returns 0 results even though the note has the tag "python".

**How to avoid:** The `list_paginated()` tag filter must normalize tag names before the `Tag.name.in_([...])` comparison:
```python
normalized = [t.strip().lower() for t in tags]
```

**Warning signs:** Unit test for `?tag=Python` with tag "python" fails; test for `?tag=python` passes.

---

## Code Examples

### NoteRead schema extension (tags field)

```python
# app/notes/schemas.py — extend NoteRead
from app.tags.schemas import TagRead  # forward-ref or direct import

class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    content: str
    source_url: str | None
    user_id: int
    created_at: datetime
    updated_at: datetime
    tags: list["TagRead"] = []   # NEW — populated by selectinload
```

```python
# app/tags/schemas.py
class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    user_id: int
```

### Tag ORM model

```python
# app/tags/models.py
from __future__ import annotations
from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.mysql import INTEGER as MUINT
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
    )

    id: Mapped[int] = mapped_column(MUINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        MUINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    def __repr__(self) -> str:
        return f"<Tag id={self.id!r} name={self.name!r} user_id={self.user_id!r}>"
```

### Collection ORM model

```python
# app/collections/models.py
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import INTEGER as MUINT
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_collection"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(MUINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        MUINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

**Note on `__table_args__` with constraints + table kwargs:** When mixing `UniqueConstraint` objects and table kwargs dict, use a tuple: `__table_args__ = (UniqueConstraint(...), {"mysql_engine": "InnoDB", ...})`. The dict must be the LAST element of the tuple.

[VERIFIED: SQLAlchemy 2.0 DeclarativeBase docs]

### main.py — register new routers

```python
# app/main.py additions
from app.tags.router import router as tags_router
from app.collections.router import router as collections_router
from app.search.router import router as search_router

app.include_router(tags_router)          # paths: /tags, /notes/{id}/tags
app.include_router(collections_router, prefix="/collections")
app.include_router(search_router, prefix="/search")
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| `aiomysql` for async MySQL | `asyncmy` 0.2.x | aiomysql unmaintained; this project already uses asyncmy |
| `text("MATCH ... AGAINST ...")` | `sqlalchemy.dialects.mysql.match().in_boolean_mode()` | Added in SQLAlchemy 1.4.19; preferred over raw text for parameterization |
| Legacy `query.filter()` API (SQLAlchemy 1.x) | `select().where()` (SQLAlchemy 2.x) | Project already uses 2.x style |
| `lazy="joined"` for relationships | `selectinload()` explicit in async | Joined loading causes Cartesian explosion for many-to-many; selectin is the recommended async strategy |

**Deprecated/outdated in this context:**
- `declarative_base()` → `DeclarativeBase` (project already uses correct v2 form)
- `Column(ForeignKey(...))` inline → `sa.ForeignKeyConstraint(...)` for join tables (either works; inline ForeignKey in `Table()` columns is correct for Core Table objects)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Collection name uniqueness per user (`UNIQUE(user_id, name)`) is recommended (Claude's Discretion) | Migration pattern | Planner may choose to skip the constraint — adjust migration accordingly |
| A2 | `GET /search` returns results ordered by FULLTEXT relevance (no explicit sort whitelist) | Architecture Patterns | If user expects `?sort=-created_at` on search, need to add sort whitelist + ORDER BY |
| A3 | Orphan tags persist when the last note detaches from them (not auto-deleted) | Architecture Patterns | If auto-delete is chosen, TagService needs a post-detach cleanup query |
| A4 | `GET /collections` (list all user's collections) is in scope (needed to create and find collections via the API) | Architecture Patterns | If not explicitly in ORG-03 success criteria, planner may skip and add only the note-list endpoint |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed. (It is not empty — A1..A4 flag discretion areas.)

---

## Open Questions

1. **`__table_args__` circular import risk: `note_tags` / `note_collections` Tables defined in `app/notes/models.py`**
   - What we know: The Table() objects reference `notes.id` (same file) and `tags.id` / `collections.id` (other files). SQLAlchemy resolves FK strings lazily (`ForeignKey("tags.id")`), so circular import at module load time is avoided as long as all models are imported before Alembic autogenerate runs.
   - What's unclear: Whether the import order in `alembic/env.py` (currently imports `Base` from `app.database`) will auto-discover all new models if they're only imported transitively.
   - Recommendation: In `alembic/env.py`, explicitly import all model modules (or import from a central `app.models` re-export) to ensure Alembic sees all tables. The existing migrations use `op.create_table()` (not autogenerate), so this is informational.

2. **`GET /tags` endpoint — list all user's tags (for frontend autocomplete)**
   - What we know: D-02 says "GET /tags returns only the caller's tags". ORG-01 says attach/detach.
   - What's unclear: Is `GET /tags` explicitly in scope for ORG-01, or only `POST /notes/{id}/tags` + `DELETE`?
   - Recommendation: Include `GET /tags` — it's the only way to browse existing tags and is needed for the end-to-end Swagger flow in the success criteria.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Desktop | testcontainers mysql:8.4 | ✓ | Running | — |
| Python | Runtime | ✓ | 3.12.13 | — |
| uv | Package manager | ✓ | 0.11.24 | — |
| SQLAlchemy | ORM + mysql.match() | ✓ | 2.0.51 | — |
| asyncmy | MySQL async driver | ✓ | 0.2.x (in pyproject.toml) | — |
| Alembic | Migrations | ✓ | 1.18.4 | — |
| testcontainers | MySQL test container | ✓ | 4.14.2 | — |
| pytest + pytest-asyncio | Test runner | ✓ | 9.1.1 / auto | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

No new packages required — all dependencies are already installed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio (asyncio_mode = "auto") |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_tags.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORG-01 | Tag attach/detach: `POST /notes/{id}/tags` creates tag + attaches; `DELETE /notes/{id}/tags/{name}` removes | integration (real MySQL) | `uv run pytest tests/test_tags.py::test_attach_tag -x` | ❌ Wave 0 |
| ORG-01 | find-or-create: tagging with same name twice creates only 1 tag | integration | `uv run pytest tests/test_tags.py::test_find_or_create_idempotent -x` | ❌ Wave 0 |
| ORG-01 | Normalization: "Python" and "python" resolve to same tag | integration | `uv run pytest tests/test_tags.py::test_tag_normalization -x` | ❌ Wave 0 |
| ORG-02 | Single tag filter: `GET /notes?tag=python` returns only notes with that tag | integration | `uv run pytest tests/test_tags.py::test_single_tag_filter -x` | ❌ Wave 0 |
| ORG-02 | Multi-tag AND filter: `?tag=python&tag=docker` returns notes with BOTH | integration | `uv run pytest tests/test_tags.py::test_multi_tag_and_filter -x` | ❌ Wave 0 |
| ORG-02 | Tag response: `GET /notes` items include `tags` array (no N+1) | integration | `uv run pytest tests/test_tags.py::test_notes_list_includes_tags -x` | ❌ Wave 0 |
| ORG-01/02 | Isolation: user A's tags invisible to user B | integration | `uv run pytest tests/test_tags.py::test_tag_isolation -x` | ❌ Wave 0 |
| ORG-03 | Collection create: `POST /collections` returns 201 + id | integration | `uv run pytest tests/test_collections.py::test_create_collection -x` | ❌ Wave 0 |
| ORG-03 | Add note to collection: `POST /collections/{id}/notes` | integration | `uv run pytest tests/test_collections.py::test_add_note_to_collection -x` | ❌ Wave 0 |
| ORG-03 | Remove note from collection: `DELETE /collections/{id}/notes/{note_id}` | integration | `uv run pytest tests/test_collections.py::test_remove_note_from_collection -x` | ❌ Wave 0 |
| ORG-04 | List collection notes: `GET /collections/{id}/notes` returns `NoteListResponse` | integration | `uv run pytest tests/test_collections.py::test_list_collection_notes -x` | ❌ Wave 0 |
| ORG-03/04 | Isolation: user A cannot access user B's collection (403/404) | integration | `uv run pytest tests/test_collections.py::test_collection_isolation -x` | ❌ Wave 0 |
| SRCH-01 | Basic search: `GET /search?q=python` returns notes containing "python" | integration | `uv run pytest tests/test_search.py::test_basic_search -x` | ❌ Wave 0 |
| SRCH-01 | 2-char token: `GET /search?q=AI` returns results (requires min_token_size=2) | integration | `uv run pytest tests/test_search.py::test_two_char_token_search -x` | ❌ Wave 0 |
| SRCH-01 | Scope: search never returns another user's notes | integration | `uv run pytest tests/test_search.py::test_search_isolation -x` | ❌ Wave 0 |
| SRCH-01 | Boolean operators: `+python -docker` works without crashing | integration | `uv run pytest tests/test_search.py::test_boolean_operators -x` | ❌ Wave 0 |
| SRCH-01 | Sanitization: stray `@` and `++` don't raise 500 | integration | `uv run pytest tests/test_search.py::test_search_sanitization -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q` (full suite — fast with testcontainers session scope)
- **Per wave merge:** `uv run pytest tests/ -x` (full suite with verbose output)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (files to create before implementation)

- [ ] `tests/test_tags.py` — covers ORG-01, ORG-02
- [ ] `tests/test_collections.py` — covers ORG-03, ORG-04
- [ ] `tests/test_search.py` — covers SRCH-01 (includes the 2-char token test)
- [ ] `tests/conftest.py` — extend `mysql_container` fixture with `.with_command("--innodb-ft-min-token-size=2")`; add `user_a_client` / `user_b_client` fixtures if not already present for cross-user tests (they ARE already present — only the mysql_container fixture needs the `with_command` addition)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (inherited) | JWT `get_current_user` dependency — already implemented Phase 3 |
| V3 Session Management | yes (inherited) | JWT expiry + DB lookup — already implemented Phase 3 |
| V4 Access Control | yes | 403/404 ownership check in `get_or_404_owned` (replicate for collections) |
| V5 Input Validation | yes | BOOLEAN MODE query sanitization; tag name normalization; Pydantic models on all request bodies |
| V6 Cryptography | no | No new cryptographic operations |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via FULLTEXT query | Tampering | `match(against=q)` parameterizes automatically; verified above |
| Cross-user tag/collection access | Elevation of privilege | `user_id` filter on all reads; 403/404 ownership check on single-resource ops |
| BOOLEAN MODE operator injection (crash, not injection) | Denial of Service | `sanitize_boolean_query()` strips `@`, `++`, `+-` before query |
| Tag name XSS via stored tag content | Tampering | Tags are stored and returned as plain strings; API is JSON-only (no HTML); Swagger auto-escapes |
| Collection/tag enumeration via timing | Information disclosure | All list endpoints scope to `WHERE user_id = :uid`; no global IDs exposed without ownership |

---

## Sources

### Primary (HIGH confidence)
- SQLAlchemy 2.0.51 installed package — `sqlalchemy.dialects.mysql.match()` API, `session.begin_nested()`, `selectinload()`, `relationship(secondary=...)` — verified via Python execution in project venv
- testcontainers 4.14.2 installed package — `MySqlContainer`, `DockerContainer.with_command()` — verified via Python source inspection
- [MySQL 8.4 — Fine-Tuning Full-Text Search](https://dev.mysql.com/doc/refman/8.4/en/fulltext-fine-tuning.html) — `innodb_ft_min_token_size=2` default (3), rebuild requirement, ALTER TABLE approach
- [MySQL 8.4 — Boolean Full-Text Searches](https://dev.mysql.com/doc/refman/8.4/en/fulltext-boolean.html) — operator syntax, error-causing patterns, stopwords, no-50%-threshold
- [Docker Hub mysql image](https://hub.docker.com/_/mysql) — `command:` for passing mysqld flags at startup
- Alembic 1.18.4 installed package — migration structure verified against existing migrations in `alembic/versions/`

### Secondary (MEDIUM confidence)
- [SQLAlchemy ORM relationship loading docs](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html) — selectinload for many-to-many
- [SQLAlchemy MySQL dialect docs](https://docs.sqlalchemy.org/en/20/dialects/mysql.html) — `match()` function availability and `.in_boolean_mode()` modifier
- [SQLAlchemy GitHub Discussion #8684](https://github.com/sqlalchemy/sqlalchemy/discussions/8684) — `text()` with bindparam vs `match()` for FULLTEXT

### Tertiary (LOW confidence)
- None — all critical claims were verified against installed packages or official MySQL docs.

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — no new packages; existing versions verified via installed packages
- Architecture: HIGH — patterns verified via Python execution in project venv + compiled SQL output
- innodb_ft_min_token_size: HIGH — official MySQL docs + installed testcontainers source inspection
- Pitfalls: HIGH — MissingGreenlet, savepoint, FULLTEXT rebuild all verified against installed library behavior

**Research date:** 2026-06-28  
**Valid until:** 2026-08-28 (stable stack; SQLAlchemy/MySQL patterns don't change rapidly)
