# Phase 4: Tags, Collections, Full-Text Search — Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 22 new/modified files
**Analogs found:** 22 / 22

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/tags/models.py` | model | CRUD | `app/auth/models.py` (User) | exact |
| `app/tags/schemas.py` | schema | request-response | `app/notes/schemas.py` | exact |
| `app/tags/repository.py` | repository | CRUD | `app/notes/repository.py` | exact |
| `app/tags/service.py` | service | CRUD | `app/notes/service.py` | exact |
| `app/tags/router.py` | router | request-response | `app/notes/router.py` | exact |
| `app/collections/models.py` | model | CRUD | `app/auth/models.py` (User) + `app/notes/models.py` | exact |
| `app/collections/schemas.py` | schema | request-response | `app/notes/schemas.py` | exact |
| `app/collections/repository.py` | repository | CRUD | `app/notes/repository.py` | exact |
| `app/collections/service.py` | service | CRUD | `app/notes/service.py` | exact |
| `app/collections/router.py` | router | request-response | `app/notes/router.py` | exact |
| `app/search/schemas.py` | schema | request-response | `app/notes/schemas.py` | role-match |
| `app/search/repository.py` | repository | CRUD | `app/notes/repository.py` | role-match |
| `app/search/service.py` | service | request-response | `app/notes/service.py` | role-match |
| `app/search/router.py` | router | request-response | `app/notes/router.py` | role-match |
| `app/notes/models.py` | model (modify) | CRUD | self (extend) | exact |
| `app/notes/repository.py` | repository (modify) | CRUD | self (extend) | exact |
| `app/notes/schemas.py` | schema (modify) | request-response | self (extend) | exact |
| `app/core/dependencies.py` | config (modify) | request-response | self (extend) | exact |
| `app/main.py` | config (modify) | request-response | self (extend) | exact |
| `docker-compose.yml` | config (modify) | — | self (extend) | exact |
| `tests/conftest.py` | test (modify) | — | self (extend) | exact |
| `alembic/versions/0004_add_tags_collections.py` | migration | batch | `alembic/versions/0003_add_user_id_to_notes.py` + `alembic/versions/d51191e92276_create_notes_table.py` | exact |
| `tests/test_tags.py` | test | CRUD | `tests/test_notes_crud.py` + `tests/test_notes_isolation.py` | exact |
| `tests/test_notes_tag_filter.py` | test | CRUD | `tests/test_notes_list.py` | role-match |
| `tests/test_collections.py` | test | CRUD | `tests/test_notes_crud.py` + `tests/test_notes_isolation.py` | exact |
| `tests/test_search.py` | test | request-response | `tests/test_notes_list.py` | role-match |
| `tests/test_phase4_isolation.py` | test | request-response | `tests/test_notes_isolation.py` | exact |

---

## Pattern Assignments

### `app/tags/models.py` (model, CRUD)

**Analog:** `app/auth/models.py` lines 33-74 (User model — same per-user-owned entity with unsigned INT PK + utf8mb4 table args)

**Imports pattern** (analog: `app/auth/models.py` lines 1-30):
```python
from __future__ import annotations

from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
```

**Model pattern** — simple model with no UniqueConstraint in `__table_args__` (analog: `app/auth/models.py` lines 33-58 for plain dict table args, but Tag needs a tuple because of the constraint). Critical: when mixing `UniqueConstraint` objects and table kwargs, `__table_args__` MUST be a tuple with the dict as the last element:
```python
class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
```

Contrast with the plain-dict form in `app/notes/models.py` lines 40-44 (no UniqueConstraint — just the dict):
```python
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
```

**`__repr__` pattern** (analog: `app/notes/models.py` line 81, `app/auth/models.py` line 73):
```python
    def __repr__(self) -> str:
        return f"<Tag id={self.id!r} name={self.name!r} user_id={self.user_id!r}>"
```

---

### `app/tags/schemas.py` (schema, request-response)

**Analog:** `app/notes/schemas.py` (complete file, 91 lines)

**Imports pattern** (analog: `app/notes/schemas.py` lines 1-17):
```python
from pydantic import BaseModel, ConfigDict, Field
```

**Three-schema pattern + from_attributes** (analog: `app/notes/schemas.py` lines 61-77):
```python
class TagCreate(BaseModel):
    """Request body for tagging a note — just the name."""
    name: str = Field(min_length=1, max_length=128)

class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    user_id: int
```

No `TagUpdate` needed — D-03 (rename is deferred). No `TagListResponse` needed — `GET /tags` returns a plain `list[TagRead]` (not paginated).

---

### `app/tags/repository.py` (repository, CRUD)

**Analog:** `app/notes/repository.py` (complete file, 143 lines)

**Imports pattern** (analog: `app/notes/repository.py` lines 1-20):
```python
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.tags.models import Tag
```

**Constructor pattern** (analog: `app/notes/repository.py` lines 30-33):
```python
class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```

**find-or-create with SAVEPOINT** — unique to tags (no analog in current codebase, but required by D-01 and RESEARCH.md Pattern 6). The SAVEPOINT (`begin_nested`) pattern is critical because the per-test transaction in `tests/conftest.py` lines 87-92 uses an outer transaction that a bare `session.rollback()` would destroy:
```python
async def find_or_create(self, user_id: int, raw_name: str) -> Tag:
    name = raw_name.strip().lower()  # D-03: normalize
    existing = (await self._session.execute(
        select(Tag).where(Tag.user_id == user_id, Tag.name == name)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    tag = Tag(user_id=user_id, name=name)
    try:
        async with self._session.begin_nested():  # SAVEPOINT — not rollback()
            self._session.add(tag)
        return tag
    except IntegrityError:
        return (await self._session.execute(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        )).scalar_one()
```

**list_by_user pattern** (analog: `app/notes/repository.py` lines 54-61 get_by_id pattern, adapted):
```python
async def list_by_user(self, user_id: int) -> list[Tag]:
    result = await self._session.execute(
        select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    )
    return list(result.scalars().all())
```

**attach/detach via ORM relationship append/remove** — uses `note.tags.append(tag)` / `note.tags.remove(tag)` with `session.flush()`. The join-table row is managed by SQLAlchemy `relationship(secondary=note_tags)` — no manual INSERT/DELETE into `note_tags`.

---

### `app/tags/service.py` (service, CRUD)

**Analog:** `app/notes/service.py` (complete file, 130 lines)

**Constructor + ownership check pattern** (analog: `app/notes/service.py` lines 30-67):
```python
class TagService:
    def __init__(self, repo: TagRepository, note_repo: NoteRepository) -> None:
        self._repo = repo
        self._note_repo = note_repo
```

The tag service must also resolve notes by ownership before attaching tags — so it takes `NoteRepository` as a second dependency (or calls `NoteService.get_or_404_owned`). Copy the 404/403 sequence from `app/notes/service.py` lines 44-67:
```python
    async def get_or_404_owned(self, note_id: int, current_user: User) -> Note:
        note = await self._note_repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")
        if note.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access forbidden")
        return note
```

**ValueError → 422 translation pattern** (analog: `app/notes/service.py` lines 94-104):
```python
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
```

---

### `app/tags/router.py` (router, request-response)

**Analog:** `app/notes/router.py` (complete file, 151 lines)

**Router declaration pattern** (analog: `app/notes/router.py` lines 29-43):
```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.auth.models import User

router = APIRouter(tags=["tags"])
```

**Endpoint pattern — Depends wiring** (analog: `app/notes/router.py` lines 58-69):
```python
@router.get("/tags", response_model=list[TagRead])
async def list_tags(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TagRead]:
    svc = TagService(TagRepository(session), NoteRepository(session))
    return await svc.list_tags(user_id=current_user.id)
```

**Sub-resource endpoint pattern** (analog: `app/notes/router.py` POST pattern lines 72-90):
```python
@router.post("/notes/{note_id}/tags", response_model=NoteRead, status_code=201)
async def attach_tag(
    note_id: int,
    data: TagCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    ...

@router.delete("/notes/{note_id}/tags/{name}", status_code=204)
async def detach_tag(
    note_id: int,
    name: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ...
```

**Response serialization pattern** (analog: `app/notes/router.py` line 90):
```python
    return NoteRead.model_validate(note)
```

---

### `app/collections/models.py` (model, CRUD)

**Analog:** `app/auth/models.py` lines 33-74 (User model — same per-user entity with UNIQUE constraint)

**Model pattern** — same tuple-form `__table_args__` as Tag because `Collection` also has a `UniqueConstraint`:
```python
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_collection"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

---

### `app/collections/schemas.py` (schema, request-response)

**Analog:** `app/notes/schemas.py` lines 61-91 (NoteRead + NoteListResponse — the collection note list reuses `NoteListResponse` directly)

```python
from pydantic import BaseModel, ConfigDict, Field

class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)

class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    user_id: int
```

`GET /collections/{id}/notes` returns `NoteListResponse` from `app/notes/schemas.py` — import and reuse, do not duplicate.

---

### `app/collections/repository.py` (repository, CRUD)

**Analog:** `app/notes/repository.py` (complete file, 143 lines)

**Constructor + select pattern** (analog: `app/notes/repository.py` lines 30-61):
```python
class CollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, collection_id: int) -> Collection | None:
        result = await self._session.execute(
            select(Collection).where(Collection.id == collection_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, name: str) -> Collection:
        coll = Collection(user_id=user_id, name=name)
        self._session.add(coll)
        await self._session.commit()
        await self._session.refresh(coll)
        return coll
```

**list_notes_for_collection pattern** — uses `selectinload` to avoid N+1, returns `(list[Note], int)` tuple matching `list_paginated` contract (analog: `app/notes/repository.py` lines 63-122):
```python
async def list_notes(
    self,
    collection_id: int,
    page: int,
    size: int,
    *,
    user_id: int,
) -> tuple[list[Note], int]:
    # join via note_collections association table
    query = (
        select(Note)
        .join(note_collections, Note.id == note_collections.c.note_id)
        .where(note_collections.c.collection_id == collection_id)
        .where(Note.user_id == user_id)
        .options(selectinload(Note.tags))
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await self._session.execute(count_q)).scalar_one()
    result = await self._session.execute(query.offset((page - 1) * size).limit(size))
    return list(result.scalars().all()), total
```

**add_note / remove_note via ORM collection** (analog: same pattern as tag attach/detach using `relationship(secondary=...)`):
```python
async def add_note(self, collection: Collection, note: Note) -> None:
    collection.notes.append(note)
    await self._session.commit()

async def remove_note(self, collection: Collection, note: Note) -> None:
    collection.notes.remove(note)
    await self._session.commit()
```

---

### `app/collections/service.py` (service, CRUD)

**Analog:** `app/notes/service.py` (complete file, 130 lines)

**get_or_404_owned ownership pattern** (analog: `app/notes/service.py` lines 44-67 — copy exactly, substituting `Collection` for `Note` and detail strings):
```python
async def get_or_404_owned(self, collection_id: int, current_user: User) -> Collection:
    coll = await self._repo.get_by_id(collection_id)
    if coll is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    if coll.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return coll
```

**list_notes → NoteListResponse envelope** (analog: `app/notes/service.py` lines 69-112):
```python
    pages = (total + size - 1) // size if total > 0 else 0
    return NoteListResponse(
        items=[NoteRead.model_validate(n) for n in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
```

---

### `app/collections/router.py` (router, request-response)

**Analog:** `app/notes/router.py` (complete file, 151 lines)

**Router + Depends pattern** (analog: `app/notes/router.py` lines 29-43 and 58-69):
```python
router = APIRouter(tags=["collections"])

@router.post("/", response_model=CollectionRead, status_code=201)
async def create_collection(
    data: CollectionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectionRead:
    svc = CollectionService(CollectionRepository(session), NoteRepository(session))
    coll = await svc.create(data, user_id=current_user.id)
    return CollectionRead.model_validate(coll)

@router.get("/{collection_id}/notes", response_model=NoteListResponse)
async def list_collection_notes(
    collection_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListResponse:
    ...

@router.post("/{collection_id}/notes", status_code=204)
async def add_note_to_collection(
    collection_id: int,
    data: ...,   # {"note_id": int}
    ...
) -> None:
    ...

@router.delete("/{collection_id}/notes/{note_id}", status_code=204)
async def remove_note_from_collection(
    collection_id: int,
    note_id: int,
    ...
) -> None:
    ...
```

**204 No Content pattern** (analog: `app/notes/router.py` lines 134-150):
```python
@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(...) -> None:
    await _make_service(session).delete(note_id, current_user)
```

---

### `app/search/schemas.py` (schema, request-response)

**Analog:** `app/notes/schemas.py` lines 79-91 (NoteListResponse — search response reuses this envelope)

No new schema class needed for the response. Only a query parameter schema (can be inline in the router as `Query(...)` params). `NoteListResponse` from `app/notes/schemas.py` is the return type.

---

### `app/search/repository.py` (repository, request-response)

**Analog:** `app/notes/repository.py` lines 63-122 (`list_paginated` structure — count + page query pattern)

**No existing analog for `match().in_boolean_mode()`** — this is the only fully novel pattern. RESEARCH.md Pattern 4 provides the complete excerpt. Key import:

```python
from sqlalchemy.dialects.mysql import match   # NOT func.match() — that lacks .in_boolean_mode()
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.notes.models import Note
```

**Core search pattern** — mirrors `list_paginated` count-then-fetch structure (analog: `app/notes/repository.py` lines 112-122):
```python
class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_fulltext(
        self, q: str, user_id: int, page: int = 1, size: int = 20
    ) -> tuple[list[Note], int]:
        match_expr = match(Note.title, Note.content, against=q).in_boolean_mode()
        base = (
            select(Note)
            .where(match_expr)
            .where(Note.user_id == user_id)
            .options(selectinload(Note.tags))
        )
        total = (await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        result = await self._session.execute(
            base.offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total
```

---

### `app/search/service.py` (service, request-response)

**Analog:** `app/notes/service.py` lines 69-112 (`list_notes` — paginate + NoteListResponse envelope)

**Sanitize + call repo + build envelope**:
```python
import re

def sanitize_boolean_query(q: str) -> str | None:
    q = q.strip()
    if not q:
        return None
    q = q.replace("@", " ")
    q = re.sub(r"[+\-]{2,}", "", q)
    q = re.sub(r"([a-zA-Z0-9*])[+\-]+(?=\s|$)", r"\1", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q or None

class SearchService:
    def __init__(self, repo: SearchRepository) -> None:
        self._repo = repo

    async def search(self, q: str, page: int, size: int, user_id: int) -> NoteListResponse:
        clean_q = sanitize_boolean_query(q)
        if clean_q is None:
            return NoteListResponse(items=[], total=0, page=page, size=size, pages=0)
        items, total = await self._repo.search_fulltext(clean_q, user_id, page, size)
        pages = (total + size - 1) // size if total > 0 else 0
        return NoteListResponse(
            items=[NoteRead.model_validate(n) for n in items],
            total=total, page=page, size=size, pages=pages,
        )
```

NoteListResponse envelope pattern (analog: `app/notes/service.py` lines 105-112):
```python
        pages = (total + size - 1) // size if total > 0 else 0
        return NoteListResponse(
            items=[NoteRead.model_validate(n) for n in items],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )
```

---

### `app/search/router.py` (router, request-response)

**Analog:** `app/notes/router.py` lines 46-69 (list endpoint with Query params)

```python
router = APIRouter(tags=["search"])

@router.get("/", response_model=NoteListResponse)
async def search_notes(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListResponse:
    svc = SearchService(SearchRepository(session))
    return await svc.search(q=q, page=page, size=size, user_id=current_user.id)
```

---

### `app/notes/models.py` — MODIFY (add join tables + relationships)

**Analog:** self — extend existing file at `F:\My-home-lab\app\notes\models.py`

**Current imports** (lines 26-28) need two additions:
```python
from sqlalchemy import DateTime, ForeignKey, String, Table, Column, Text, func   # add Table, Column
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship
```

**Add association Table objects at module level** (before the `Note` class, after imports) — pattern from RESEARCH.md Pattern 1. The Table objects use string FK references (`"tags.id"`, `"collections.id"`) to avoid circular imports:
```python
from app.database import Base

note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", INTEGER(unsigned=True), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",  INTEGER(unsigned=True), ForeignKey("tags.id",  ondelete="CASCADE"), primary_key=True),
    mysql_engine="InnoDB",
)

note_collections = Table(
    "note_collections",
    Base.metadata,
    Column("note_id",       INTEGER(unsigned=True), ForeignKey("notes.id",       ondelete="CASCADE"), primary_key=True),
    Column("collection_id", INTEGER(unsigned=True), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    mysql_engine="InnoDB",
)
```

**Add relationships inside `Note` class** (after existing `owner` relationship, line 67):
```python
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=note_tags, lazy="select"
    )
    collections_rel: Mapped[list["Collection"]] = relationship(
        "Collection", secondary=note_collections, lazy="select"
    )
```

Use `lazy="select"` (NOT `lazy="selectin"`) — `selectinload` is added explicitly in each query. Mixing both causes a double-load.

---

### `app/notes/repository.py` — MODIFY (add tag filter + selectinload)

**Analog:** self — extend existing file at `F:\My-home-lab\app\notes\repository.py`

**New imports to add** (after line 15):
```python
from sqlalchemy.orm import selectinload
from app.notes.models import note_tags   # the Table() object — added to models.py above
# Tag is imported lazily via string in the subquery to avoid circular import at module load
```

**Extend `list_paginated` signature** (current: line 63-70, add `tags` parameter):
```python
    async def list_paginated(
        self,
        page: int,
        size: int,
        sort: str = "-created_at",
        filter: str | None = None,
        tags: list[str] | None = None,   # NEW — AND-intersection filter (D-05)
        *,
        user_id: int,
    ) -> tuple[list[Note], int]:
```

**Add tag AND-filter block** (after the existing `filter` block, analog: lines 105-116, INSERT after line 110):
```python
        # --- Optional tag AND-intersection filter (D-05) ---
        if tags:
            from sqlalchemy import func as sa_func
            from app.tags.models import Tag   # local import avoids circular at module level

            normalized_tags = [t.strip().lower() for t in tags]  # D-03: normalize input too (Pitfall 6)
            tag_id_subq = (
                select(Tag.id)
                .where(Tag.name.in_(normalized_tags))
                .where(Tag.user_id == user_id)
                .scalar_subquery()
            )
            matching_note_ids = (
                select(note_tags.c.note_id)
                .where(note_tags.c.tag_id.in_(tag_id_subq))
                .group_by(note_tags.c.note_id)
                .having(sa_func.count(note_tags.c.tag_id.distinct()) == len(normalized_tags))
                .scalar_subquery()
            )
            query = query.where(Note.id.in_(matching_note_ids))
```

**Add selectinload on every query path** — the `query` after all filters is extended (analog: query building lines 105-121, ADD before count):
```python
        query = query.options(selectinload(Note.tags))   # ALWAYS — MissingGreenlet if omitted
```

**Extend `get_by_id`** (current: lines 54-61) — add `selectinload` so single-note endpoints also serialize tags:
```python
    async def get_by_id(self, note_id: int) -> Note | None:
        result = await self._session.execute(
            select(Note).where(Note.id == note_id).options(selectinload(Note.tags))
        )
        return result.scalar_one_or_none()
```

---

### `app/notes/schemas.py` — MODIFY (add `tags` field to NoteRead)

**Analog:** self — extend existing file at `F:\My-home-lab\app\notes\schemas.py`

**New import** (add after line 16):
```python
from __future__ import annotations   # for forward references

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.tags.schemas import TagRead
```

Or use a string annotation / direct import. Direct import works if there is no circular dependency. If a circular import arises (tags.schemas imports notes.schemas), use `from __future__ import annotations` + `"TagRead"` string annotation.

**Extend NoteRead** (current: lines 61-77, add `tags` field after `updated_at`):
```python
class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    content: str
    source_url: str | None
    user_id: int
    created_at: datetime
    updated_at: datetime
    tags: list["TagRead"] = []   # NEW — populated by selectinload(Note.tags)
```

`NoteListResponse` is unchanged — reused verbatim for `/search` and `/collections/{id}/notes`.

---

### `app/core/dependencies.py` — MODIFY (add service providers)

**Analog:** self — extend existing file at `F:\My-home-lab\app\core\dependencies.py`

**Existing pattern to replicate** (lines 50-54):
```python
async def get_note_service(
    db: AsyncSession = Depends(get_db),
) -> NoteService:
    """Construct NoteService with its repository for the current request."""
    return NoteService(NoteRepository(db))
```

**Add analogous providers** following the same structure:
```python
async def get_tag_service(
    db: AsyncSession = Depends(get_db),
) -> TagService:
    return TagService(TagRepository(db), NoteRepository(db))

async def get_collection_service(
    db: AsyncSession = Depends(get_db),
) -> CollectionService:
    return CollectionService(CollectionRepository(db), NoteRepository(db))

async def get_search_service(
    db: AsyncSession = Depends(get_db),
) -> SearchService:
    return SearchService(SearchRepository(db))
```

Note: routers in this phase inline `_make_service()` locally (following the notes router pattern at line 41-43) instead of using `get_*_service` from dependencies. Either approach is valid — pick one and be consistent.

---

### `app/main.py` — MODIFY (register new routers)

**Analog:** self — extend existing file at `F:\My-home-lab\app\main.py`

**Existing router registration pattern** (lines 23-26 + 54-56):
```python
from app.api.health import router as health_router
from app.auth.router import router as auth_router
from app.notes.router import router as notes_router

app.include_router(health_router)
app.include_router(auth_router, prefix="/auth")
app.include_router(notes_router, prefix="/notes")
```

**Add three new registrations** in the same pattern:
```python
from app.tags.router import router as tags_router
from app.collections.router import router as collections_router
from app.search.router import router as search_router

app.include_router(tags_router)               # paths at /tags and /notes/{id}/tags — no prefix
app.include_router(collections_router, prefix="/collections")
app.include_router(search_router, prefix="/search")
```

Tags router gets no prefix because it owns paths on both `/tags` and `/notes/{id}/tags`.

---

### `alembic/versions/0004_add_tags_collections.py` (migration)

**Analog 1:** `alembic/versions/d51191e92276_create_notes_table.py` (complete, 79 lines) — shows `op.create_table` + `op.execute` for FULLTEXT DDL (lines 40-73)

**FULLTEXT raw DDL pattern** (analog: `d51191e92276` lines 70-73):
```python
# op.create_index doesn't support FULLTEXT — use raw DDL.
op.execute("ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)")
```

Phase 4 rebuilds by DROP + ADD (analog: same pattern, two `op.execute` calls):
```python
op.execute("ALTER TABLE notes DROP INDEX ft_notes_content")
op.execute("ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)")
```

**Analog 2:** `alembic/versions/0003_add_user_id_to_notes.py` (complete, 70 lines) — shows `down_revision` chaining (line 28) and `op.create_foreign_key` / `op.create_index` pattern (lines 53-63)

**Chain declaration pattern** (analog: `0003` lines 27-30):
```python
revision: str = "0004_add_tags_collections"
down_revision: str | Sequence[str] | None = "0003_add_user_id_to_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Table creation with UniqueConstraint + ForeignKeyConstraint** (no direct analog in codebase — this phase introduces them; RESEARCH.md Pattern 7 is authoritative):
```python
op.create_table(
    "tags",
    sa.Column("id", mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True),
    sa.Column("user_id", mysql.INTEGER(unsigned=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("name", sa.String(128), nullable=False),
    sa.UniqueConstraint("user_id", "name", name="uq_user_tag"),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
    mysql_collate="utf8mb4_unicode_ci",
)
```

Join tables use `sa.PrimaryKeyConstraint` + `sa.ForeignKeyConstraint`:
```python
op.create_table(
    "note_tags",
    sa.Column("note_id", mysql.INTEGER(unsigned=True), nullable=False),
    sa.Column("tag_id",  mysql.INTEGER(unsigned=True), nullable=False),
    sa.PrimaryKeyConstraint("note_id", "tag_id", name="pk_note_tags"),
    sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["tag_id"],  ["tags.id"],  ondelete="CASCADE"),
    mysql_engine="InnoDB",
)
```

---

### `docker-compose.yml` — MODIFY (add `innodb_ft_min_token_size`)

**Analog:** self (no existing `command:` on mysql service — this is a new addition)

**Pattern from RESEARCH.md Pattern 8** — add a single `command:` key to the mysql service:
```yaml
mysql:
  image: mysql:8.4
  command: --innodb-ft-min-token-size=2    # ADD — startup-only variable; cannot SET GLOBAL
  env_file:
    - .env
  # ... rest unchanged ...
```

The `command:` overrides the Docker CMD and passes the flag to `mysqld` at startup. This is the simplest approach (no custom `my.cnf` file needed).

---

### `tests/conftest.py` — MODIFY (add `with_command` to mysql fixture)

**Analog:** self — extend existing fixture at `F:\My-home-lab\tests\conftest.py`

**Current fixture** (lines 37-40):
```python
@pytest.fixture(scope="session")
def mysql_container():
    """Spin up a real mysql:8.4 container once per test session (D-16)."""
    with MySqlContainer("mysql:8.4") as container:
        yield container
```

**Replace with** (adds `.with_command()` before the context manager — `DockerContainer.with_command()` sets `_command` which Docker passes as CMD):
```python
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

**Existing fixtures to reuse** — `user_a_client` (lines 143-175) and `user_b_client` (lines 178-213) are already present and ready for Phase 4 isolation tests. No new two-user fixtures needed.

---

### `tests/test_tags.py` (test, CRUD)

**Analog 1:** `tests/test_notes_crud.py` (complete, 167 lines) — fixture usage + assertion pattern

**Analog 2:** `tests/test_notes_isolation.py` (complete, 167 lines) — `user_a_client` / `user_b_client` fixture pattern for cross-user isolation

**Test function signature pattern** (analog: `test_notes_crud.py` line 27):
```python
async def test_attach_tag_returns_200(auth_client: httpx.AsyncClient) -> None:
    ...
```

**Setup-action-assert structure** (analog: `test_notes_crud.py` lines 54-64):
```python
async def test_attach_tag_returns_200(auth_client: httpx.AsyncClient) -> None:
    # Setup: create a note
    create_resp = await auth_client.post("/notes/", json={"content": "tagging test"})
    note_id = create_resp.json()["id"]

    # Action: attach tag
    resp = await auth_client.post(f"/notes/{note_id}/tags", json={"name": "python"})
    assert resp.status_code == 200   # or 201 — TBD by planner

    # Assert: tags field populated
    data = resp.json()
    assert any(t["name"] == "python" for t in data["tags"])
```

**Cross-user isolation pattern** (analog: `test_notes_isolation.py` lines 48-61):
```python
async def test_tag_isolation(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    # A creates note + tags it
    a_note = (await user_a_client.post("/notes/", json={"content": "A note"})).json()
    await user_a_client.post(f"/notes/{a_note['id']}/tags", json={"name": "secret"})

    # B's tag list must not include A's "secret" tag
    b_tags = (await user_b_client.get("/tags")).json()
    assert not any(t["name"] == "secret" for t in b_tags)
```

---

### `tests/test_notes_tag_filter.py` (test, CRUD)

**Analog:** `tests/test_notes_list.py` (complete, 294 lines) — filter + pagination assertion pattern

**Filter assertion pattern** (analog: `test_notes_list.py` lines 216-233):
```python
async def test_single_tag_filter(auth_client: httpx.AsyncClient) -> None:
    # Seed notes
    n1 = (await auth_client.post("/notes/", json={"content": "python note"})).json()
    n2 = (await auth_client.post("/notes/", json={"content": "docker note"})).json()
    await auth_client.post(f"/notes/{n1['id']}/tags", json={"name": "python"})

    # Filter
    resp = await auth_client.get("/notes/?tag=python")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert n1["id"] in ids
    assert n2["id"] not in ids
```

**Multi-tag AND filter** — unique to Phase 4, no analog. Must assert strict intersection:
```python
async def test_multi_tag_and_filter(auth_client: httpx.AsyncClient) -> None:
    n_both = (await auth_client.post("/notes/", json={"content": "both"})).json()
    n_one  = (await auth_client.post("/notes/", json={"content": "one only"})).json()
    await auth_client.post(f"/notes/{n_both['id']}/tags", json={"name": "python"})
    await auth_client.post(f"/notes/{n_both['id']}/tags", json={"name": "docker"})
    await auth_client.post(f"/notes/{n_one['id']}/tags",  json={"name": "python"})

    resp = await auth_client.get("/notes/?tag=python&tag=docker")
    ids = [i["id"] for i in resp.json()["items"]]
    assert n_both["id"] in ids
    assert n_one["id"] not in ids    # has python but NOT docker
```

---

### `tests/test_collections.py` (test, CRUD)

**Analog:** `tests/test_notes_crud.py` lines 27-167 + `tests/test_notes_isolation.py` lines 48-135

**Collection create pattern** (analog: `test_notes_crud.py` lines 27-34):
```python
async def test_create_collection_returns_201(auth_client: httpx.AsyncClient) -> None:
    resp = await auth_client.post("/collections/", json={"name": "Work"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Work"
    assert "id" in data
```

**Add note + list notes pattern** (analog: `test_notes_crud.py` lines 54-64):
```python
async def test_list_collection_notes_returns_envelope(auth_client: httpx.AsyncClient) -> None:
    coll = (await auth_client.post("/collections/", json={"name": "Reading"})).json()
    note = (await auth_client.post("/notes/", json={"content": "for collection"})).json()
    await auth_client.post(f"/collections/{coll['id']}/notes", json={"note_id": note["id"]})

    resp = await auth_client.get(f"/collections/{coll['id']}/notes")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data and "total" in data and "pages" in data
    assert any(i["id"] == note["id"] for i in data["items"])
```

---

### `tests/test_search.py` (test, request-response)

**Analog:** `tests/test_notes_list.py` lines 27-50 (envelope + default params pattern)

**Basic search pattern**:
```python
async def test_basic_search(auth_client: httpx.AsyncClient) -> None:
    await auth_client.post("/notes/", json={"content": "Learning Python programming"})
    resp = await auth_client.get("/search/?q=python")
    assert resp.status_code == 200
    data = resp.json()
    assert any("python" in i["content"].lower() for i in data["items"])

async def test_two_char_token_search(auth_client: httpx.AsyncClient) -> None:
    """innodb_ft_min_token_size=2 must be active — 'AI' is 2 chars."""
    await auth_client.post("/notes/", json={"content": "Artificial Intelligence AI tools"})
    resp = await auth_client.get("/search/?q=AI")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
```

**Isolation pattern** (analog: `test_notes_isolation.py` lines 106-134):
```python
async def test_search_isolation(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    await user_a_client.post("/notes/", json={"content": "A's private research"})
    resp = await user_b_client.get("/search/?q=private")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
```

---

### `tests/test_phase4_isolation.py` (test, request-response)

**Analog:** `tests/test_notes_isolation.py` (complete, 167 lines) — all cross-user test patterns

**Key isolation assertions to cover** (analog: lines 48-134):
- User B cannot see / modify user A's tags (`GET /tags`, `DELETE /notes/{id}/tags/{name}`)
- User B cannot see / modify user A's collections (`GET /collections`, `GET /collections/{id}/notes`)
- User B cannot add notes to user A's collection (`POST /collections/{id}/notes` → 403)
- `GET /search?q=` never returns another user's notes

Pattern mirrors `test_cross_user_get_returns_403` from `test_notes_isolation.py` lines 48-61.

---

## Shared Patterns

### Authentication (apply to all new routers)

**Source:** `app/core/dependencies.py` lines 41-110  
**Apply to:** `app/tags/router.py`, `app/collections/router.py`, `app/search/router.py`

All endpoints require `current_user: User = Depends(get_current_user)`. The `get_current_user` dependency validates the Bearer JWT, fetches the User from DB, and raises 401 for any failure — no per-router auth code needed.

```python
from app.core.dependencies import get_current_user, get_db
from app.auth.models import User

@router.get("/...")
async def endpoint(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),   # 401 if missing/invalid
) -> ...:
```

### 404 / 403 Ownership Check (apply to all single-resource endpoints)

**Source:** `app/notes/service.py` lines 44-67  
**Apply to:** All `CollectionService`, `TagService` single-resource endpoints

```python
resource = await self._repo.get_by_id(resource_id)
if resource is None:
    raise HTTPException(status_code=404, detail="<Resource> not found")
if resource.user_id != current_user.id:
    raise HTTPException(status_code=403, detail="Access forbidden")
return resource
```

### `NoteListResponse` envelope (apply to all list-of-notes endpoints)

**Source:** `app/notes/schemas.py` lines 79-91  
**Apply to:** `GET /collections/{id}/notes`, `GET /search`

```python
pages = (total + size - 1) // size if total > 0 else 0
return NoteListResponse(
    items=[NoteRead.model_validate(n) for n in items],
    total=total, page=page, size=size, pages=pages,
)
```

### `selectinload(Note.tags)` on every Note query (apply to all Note-returning queries)

**Source:** RESEARCH.md Pattern 2 (no existing codebase analog — this is new to Phase 4)  
**Apply to:** `NoteRepository.get_by_id`, `NoteRepository.list_paginated`, `SearchRepository.search_fulltext`, `CollectionRepository.list_notes`

```python
.options(selectinload(Note.tags))   # Omit → MissingGreenlet on note.tags access
```

### `model_validate` serialization (apply to all ORM → schema conversions)

**Source:** `app/notes/router.py` line 90  
**Apply to:** All router endpoints returning ORM instances

```python
return NoteRead.model_validate(note)           # single note
return TagRead.model_validate(tag)             # single tag
return CollectionRead.model_validate(coll)     # single collection
```

### utf8mb4 / InnoDB `__table_args__` (apply to all new ORM models)

**Source:** `app/notes/models.py` lines 40-44 (plain dict form) or tuple form when `UniqueConstraint` is present  
**Apply to:** `app/tags/models.py`, `app/collections/models.py`

Plain dict (no constraints):
```python
__table_args__ = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}
```

Tuple form (with constraints — dict MUST be last):
```python
__table_args__ = (
    UniqueConstraint("user_id", "name", name="uq_<table>"),
    {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
)
```

### Tag name normalization (apply everywhere tags are created or filtered)

**Source:** RESEARCH.md D-03 / Pitfall 6  
**Apply to:** `TagRepository.find_or_create`, `NoteRepository.list_paginated` tag filter block

```python
name = raw_name.strip().lower()   # normalize at create time
normalized_tags = [t.strip().lower() for t in tags]   # normalize at filter time
```

---

## No Analog Found

All Phase 4 files have a close analog in the codebase. The following patterns have no existing codebase implementation and must be built from RESEARCH.md excerpts:

| Pattern | Where Used | RESEARCH.md Section |
|---------|-----------|---------------------|
| `match().in_boolean_mode()` FULLTEXT query | `app/search/repository.py` | Pattern 4 |
| `session.begin_nested()` SAVEPOINT in find-or-create | `app/tags/repository.py` | Pattern 6 |
| `Table()` association object + `relationship(secondary=...)` | `app/notes/models.py` | Pattern 1 |
| GROUP BY / HAVING COUNT(DISTINCT) AND-tag-filter subquery | `app/notes/repository.py` | Pattern 3 |
| `sanitize_boolean_query()` BOOLEAN MODE sanitization | `app/search/service.py` | Pattern 5 |

---

## Metadata

**Analog search scope:** `app/`, `tests/`, `alembic/versions/`  
**Files scanned:** 20 existing files read  
**Pattern extraction date:** 2026-06-28
