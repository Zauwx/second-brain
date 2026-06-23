# Feature Research

**Domain:** Personal Knowledge Base / "Second Brain" API (API-first, learning project)
**Researched:** 2026-06-23
**Confidence:** HIGH (cross-validated across Obsidian, Notion, Logseq, Trilium, Mem, Readwise, and FastAPI ecosystem docs)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that any knowledge base must have. Missing any of these makes the product feel broken,
not incomplete. All competitors (Obsidian, Notion, Logseq, Trilium) share these unconditionally.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Note CRUD (create / read / update / delete) | Core primitive — without it, nothing else functions | LOW | title + body (markdown text) + optional source URL + timestamps; FastAPI + SQLAlchemy + MySQL |
| Tag management (many-to-many) | Every PKM tool since Evernote has tags; users rely on them for retrieval | MEDIUM | junction table `note_tags`; tags must be per-user; allow create-on-assign (no separate pre-create step) |
| Collection / folder grouping | Notes need a coarser container above tags; all tools offer this (Notion databases, Obsidian folders, Trilium tree) | MEDIUM | single-level collections for v1 (no nested trees — complexity not worth it yet) |
| Full-text search | Retrieval is the core value; without FTS the product is a write-only dump | MEDIUM | MySQL `FULLTEXT` index on `notes.title + notes.body`; `MATCH … AGAINST` in boolean mode; scoped per-user |
| User accounts + JWT auth | Multi-user is required; every request must be scoped to the authenticated user | MEDIUM | `users` table; `POST /auth/register` + `POST /auth/login` returning access token; `Authorization: Bearer` header; password hashing via bcrypt |
| Per-user data isolation | Without row-level ownership, auth is theater | LOW | Every query carries a `WHERE user_id = ?` filter; enforced at the service layer, not just the route layer |
| OpenAPI / Swagger auto-docs | API-first means the Swagger UI IS the UI for v1; it must be complete and accurate | LOW | FastAPI generates this for free from type annotations; just keep schemas clean |
| Proper HTTP status codes + error shapes | Consumers (tests, Swagger) need consistent, predictable error envelopes | LOW | 400 validation errors, 401 unauthenticated, 403 forbidden, 404 not found, 422 unprocessable — use a single `ErrorResponse` schema |
| Pagination on list endpoints | Without pagination, `GET /notes` becomes unusable at scale; standard REST expectation | LOW | Cursor-based (keyset on `created_at`) preferred over offset for MySQL performance; `limit` capped at 100 |
| Filtering + sorting on list endpoints | Users need to find notes by tag, collection, date range, sort by relevance or recency | LOW | Query params: `?tag=`, `?collection_id=`, `?sort=created_at\|updated_at`, `?order=asc\|desc` |

### Differentiators (Competitive Advantage)

These are the features that justify building a custom tool AND demonstrate real skills. They go beyond basic CRUD and are tied directly to the learning goals (LLM routing, vector search, REST design).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-summarization via Ollama (local LLM) | Removes manual effort; keeps data private (no cloud call); demonstrates local LLM routing | MEDIUM | `POST /notes/{id}/summarize` — sends note body to Ollama REST API at `localhost:11434`; stores summary in `notes.summary`; use `llama3` or `mistral` model; async task preferred (don't block HTTP response) |
| Auto-tagging / classification via Ollama | Suggests tags from note content; reduces taxonomy friction; same local-privacy benefit | MEDIUM | `POST /notes/{id}/suggest-tags` — prompt Ollama to return JSON array of tag strings; present as suggestions (user confirms); store accepted tags via normal tag endpoint |
| Semantic search (RAG retrieval layer) | Keyword FTS misses synonyms and concepts; semantic search is the core differentiator of modern PKM tools like Mem | HIGH | Generate embeddings at ingest time (via cloud embedding API or local `nomic-embed-text` via Ollama); store in ChromaDB (separate container); `GET /notes/search?q=&mode=semantic` queries ChromaDB with cosine similarity; filter by user metadata |
| RAG Q&A ("ask your notes") | The single most compelling demo for a second brain; directly demonstrates LLM + retrieval pipeline | HIGH | `POST /qa` — embeds the question, retrieves top-K relevant note chunks from ChromaDB (filtered by `user_id`), sends context + question to cloud LLM (Claude or OpenAI); returns answer with source note IDs cited; this is the "wow" feature |
| Related notes suggestions | Surfaces connections the user did not know existed; all serious PKM tools offer this (Obsidian graph, Mem AI) | MEDIUM | `GET /notes/{id}/related` — embed the note, query ChromaDB for nearest neighbours excluding self; return ranked list of note IDs + similarity scores; cheap to add once RAG infrastructure is in place |
| Source URL storage + metadata | Distinguishes saved articles/links from freeform notes; Readwise-style provenance tracking | LOW | `notes.source_url` column (nullable); enables "web clippings" workflow without a browser extension |
| Async AI job status endpoint | Background summarization/tagging needs a status surface so callers know when results are ready | MEDIUM | Simple `jobs` table with `pending / running / done / failed`; `GET /jobs/{id}` endpoint; no message queue needed for v1 — poll-based is fine |
| Rate limiting on AI endpoints | Prevents Ollama from being hammered; teaches HTTP 429 and backpressure patterns | LOW | Use `slowapi` (FastAPI-native rate limiting middleware); apply only to `/summarize`, `/suggest-tags`, `/qa` |

### Anti-Features (Deliberately NOT Building for v1)

These are features that seem natural to add but would derail the learning goals, explode scope, or require infrastructure not justified by v1.

| Feature | Why Requested | Why Problematic for This v1 | What to Do Instead |
|---------|---------------|-----------------------------|--------------------|
| Rich SPA / frontend UI | "Can I see my notes?" is a natural ask | Adds React/Vue/Next.js stack, state management, and design work — none of which is the learning goal; doubles the project scope | Swagger UI IS the v1 UI; build a minimal read-only HTML view in v2 if desired |
| Real-time collaboration / sharing | Multi-user suggests sharing between users | Requires WebSockets or SSE, permission matrices, invite flows — 3x the complexity; single-user isolation is the learning goal | Keep data strictly per-user; add public share links as a v2 stretch goal |
| Mobile app | Notes are useful on the go | React Native / Flutter is a separate learning track; the API itself is mobile-ready; just not prioritized | The REST API is already consumable by any client |
| Web clipper browser extension | Saving URLs with one click is convenient | Browser extension development is a separate platform (Chrome Extension Manifest V3); adds weeks with no MySQL/REST/AI learning | Accept URL as a plain `source_url` field in `POST /notes`; power users can use `curl` |
| Markdown import / export (bulk) | "I want to migrate from Obsidian" | Parsing arbitrary Markdown vaults, handling attachments, and preserving frontmatter metadata is a standalone feature project; not core to the learning objective | Provide `GET /notes/{id}` which returns markdown body — export is one `curl` away; bulk export is a v1.x task |
| Graph view / backlinks | Obsidian's signature feature | Requires bidirectional link parsing inside note bodies, a graph data structure, and a frontend to visualize — none of which maps to the MySQL/REST learning goals | The related-notes suggestion endpoint delivers the value (connections surfaced) without the parsing and UI overhead |
| Fine-tuning / model training | "Can I improve the AI on my notes?" | Entirely different discipline (MLOps, datasets, GPU resources) — not achievable in a home lab context and not the goal | Consume pre-trained models via Ollama + cloud API; prompt engineering is the lever |
| Cloud-managed hosting (AWS/GCP) | Easier deployment | Goal is Linux home lab fluency via Docker; managed services skip that learning | Docker Compose on local machine; target self-hosted VPS as v2 deployment |
| Note versioning / history | "I accidentally deleted content" | Requires append-only schema or event sourcing — significant complexity; MySQL binlog is not a user feature | Add `updated_at` + soft delete (`deleted_at`) for v1; history is a v2 concern |
| Attachments / file uploads | Images, PDFs, audio notes | Binary storage (S3 / local volume), multipart upload, MIME handling — each a non-trivial concern; text-only notes are sufficient for the learning scope | Store `source_url` pointing to external resources; v2 can add attachment endpoints |
| Email / webhook integrations | "Send notes from email" | Integration platform work (SMTP, webhooks, HMAC verification) — entirely separate from the core learning goals | REST API is already the integration surface |

---

## Feature Dependencies

```
[User Auth (JWT)]
    └──required by──> [Note CRUD]
    └──required by──> [Tag Management]
    └──required by──> [Collection Management]
    └──required by──> [Full-Text Search]
    └──required by──> [All AI endpoints]

[Note CRUD]
    └──required by──> [Tag Management]  (tags attach to notes)
    └──required by──> [Collection Management]  (collections contain notes)
    └──required by──> [Auto-summarization]
    └──required by──> [Auto-tagging]
    └──required by──> [Semantic Search]  (embeddings generated at note create/update)
    └──required by──> [Related Notes]

[Semantic Search / Embedding Infrastructure]
    └──required by──> [RAG Q&A]
    └──required by──> [Related Notes]

[Async Job Infrastructure]
    └──enhances──> [Auto-summarization]  (non-blocking AI calls)
    └──enhances──> [Auto-tagging]

[Full-Text Search]
    └──complements──> [Semantic Search]  (hybrid mode: keyword + vector)

[Rate Limiting]
    └──applies to──> [Auto-summarization, Auto-tagging, RAG Q&A]
```

### Dependency Notes

- **Auth required before everything:** JWT middleware must be wired before any data endpoint is built; every subsequent feature inherits the `current_user` dependency.
- **Note CRUD before AI features:** Summarization, tagging, and embedding require a note to exist; build and test CRUD + FTS first.
- **Embedding infrastructure before RAG Q&A and Related Notes:** ChromaDB container + embedding pipeline must be in place before either feature is buildable. These two features share identical retrieval infrastructure — build them in the same phase.
- **Async jobs optional but recommended:** Synchronous Ollama calls will block the HTTP worker for several seconds. The job status pattern decouples this, but a synchronous "fire and wait" version is acceptable for v1 if the async overhead feels premature.
- **FTS and semantic search are complementary, not conflicting:** MySQL FTS handles exact keyword matches efficiently (names, acronyms, code snippets). Semantic search handles concept-level queries. A `?mode=fulltext|semantic|hybrid` query param lets callers choose.

---

## MVP Definition

### Launch With (v1)

Minimum set that validates the core value proposition: "save content and retrieve it in natural language."

- [ ] **Note CRUD** — without this, nothing else works
- [ ] **User auth + JWT + data isolation** — multi-user is a stated requirement and learning goal
- [ ] **Tags (many-to-many) + Collections** — minimum organization layer users expect
- [ ] **MySQL Full-text search** — retrieval is the core value; FTS is the fastest path to it
- [ ] **OpenAPI docs + proper HTTP patterns** — Swagger UI is the v1 UI; pagination, filtering, error shapes
- [ ] **Auto-summarization via Ollama** — first local LLM integration; validates the hybrid AI architecture
- [ ] **Auto-tagging suggestions via Ollama** — same Ollama call pattern, low incremental cost
- [ ] **RAG Q&A** — the "wow" feature; requires semantic search infrastructure (ChromaDB); justifies the entire project

### Add After Validation (v1.x)

Add these once the core pipeline works end-to-end.

- [ ] **Related notes suggestions** — trivial to add once ChromaDB is running; high user value
- [ ] **Semantic search endpoint** — expose the ChromaDB retrieval as a standalone search mode
- [ ] **Async job status** — replace blocking Ollama calls with background jobs + poll endpoint
- [ ] **Rate limiting on AI routes** — add `slowapi` once abuse patterns are understood
- [ ] **Bulk markdown export** — `GET /export` returning a ZIP of per-user notes as `.md` files; low complexity, high goodwill

### Future Consideration (v2+)

Defer until the core is battle-tested.

- [ ] **Minimal HTML read-only UI** — single-page Jinja2 template served by FastAPI; not a SPA
- [ ] **Source URL / web clipping metadata enrichment** — auto-fetch title + description from `source_url` using `httpx`
- [ ] **Note version history** — append-only `note_versions` table; soft-delete
- [ ] **File attachment support** — binary upload to local volume with reference stored in MySQL
- [ ] **Public share links** — generate a signed read-only URL for a single note

---

## Feature Prioritization Matrix

| Feature | Learning Value | User Value | Implementation Cost | Priority |
|---------|---------------|------------|---------------------|----------|
| Note CRUD | HIGH (MySQL schema, ORM, REST verbs) | HIGH | LOW | P1 |
| User auth + JWT | HIGH (HTTP auth, bcrypt, token flow) | HIGH | MEDIUM | P1 |
| Tags many-to-many | HIGH (relational joins, junction table) | HIGH | MEDIUM | P1 |
| Collections | MEDIUM | MEDIUM | LOW | P1 |
| Full-text search | HIGH (MySQL FTS, query building) | HIGH | MEDIUM | P1 |
| OpenAPI + HTTP patterns | HIGH (REST semantics, pagination) | HIGH | LOW | P1 |
| Auto-summarization (Ollama) | HIGH (LLM routing, local API) | MEDIUM | MEDIUM | P1 |
| Auto-tagging (Ollama) | MEDIUM (reuses summarize pattern) | MEDIUM | LOW | P1 |
| RAG Q&A (cloud LLM + ChromaDB) | HIGH (embeddings, vector DB, prompt) | HIGH | HIGH | P1 |
| Related notes | LOW (reuses RAG infra) | HIGH | LOW | P2 |
| Semantic search endpoint | MEDIUM | HIGH | LOW | P2 |
| Async job status | MEDIUM (background tasks, polling) | MEDIUM | MEDIUM | P2 |
| Rate limiting | LOW (middleware config) | LOW | LOW | P2 |
| Bulk export | LOW | MEDIUM | LOW | P2 |
| Minimal HTML UI | LOW | MEDIUM | MEDIUM | P3 |
| Note versioning | LOW | MEDIUM | HIGH | P3 |
| File attachments | LOW | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for v1 — validates the core value and hits all stated learning goals
- P2: Should have — add in v1.x passes once P1 is stable
- P3: Nice to have — v2+ territory

---

## Competitor Feature Analysis

| Feature | Obsidian | Notion | Logseq | Trilium | Our Approach |
|---------|----------|--------|--------|---------|--------------|
| Core note CRUD | Local markdown files | Cloud database blocks | Local markdown + outlines | Server-backed tree | MySQL rows via REST API |
| Tags | Hashtag inline | Database properties | Inline `#tag` | Attribute system | Many-to-many `note_tags` table |
| Collections / folders | Filesystem folders | Databases / pages | Namespaces | Hierarchical tree | Flat `collections` table (no nesting in v1) |
| Full-text search | Local grep | Indexed cloud search | Local index | Built-in | MySQL `FULLTEXT` index |
| Auth / multi-user | Local file ownership | Workspace + SSO | Local only | Built-in user system | JWT with bcrypt; per-user row isolation |
| Auto-summarization | Plugin (community) | AI block (cloud) | Plugin | None | Ollama local (private) |
| Auto-tagging | None native | None native | None native | None | Ollama local |
| Semantic search | None native | AI Q&A (cloud) | None native | None | ChromaDB + embedding API |
| RAG Q&A | None native | Notion AI (cloud) | None native | None | ChromaDB + Claude/OpenAI cloud |
| Related notes | Graph view (visual) | "Related pages" | Graph (backlinks) | Link map | `/notes/{id}/related` via vector similarity |
| Web clipper | Browser extension | Browser extension | Browser extension | Browser extension | `source_url` field only (anti-feature for v1) |
| Import / export | Markdown vault | CSV, HTML, Markdown | Markdown, EDN | ENEX, Markdown | Single-note Markdown in GET response; bulk export in v1.x |
| API | Community plugin | Official REST API | None | REST API | FastAPI with full OpenAPI docs — first-class |
| Self-hosted | Yes (local files) | No | Yes (local files) | Yes (Docker) | Yes (Docker Compose) |

---

## Sources

- Obsidian feature overview: https://obsidian.md and https://productivitystack.io/guides/obsidian-getting-started/
- Second brain app comparisons (2026): https://www.atlasworkspace.ai/blog/best-second-brain-apps and https://buildin.ai/blog/best-second-brain-apps-2026
- Notion vs Obsidian vs Logseq comparison: https://www.postry.com.br/en/blog/notion-vs-obsidian-vs-logseq-second-brain-comparison
- Trilium Notes features: https://github.com/TriliumNext/Trilium and https://05t3.github.io/posts/Trilium_Notes/
- RAG + FastAPI implementation patterns: https://www.datacamp.com/tutorial/building-a-rag-system-with-langchain-and-fastapi and https://www.analyticsvidhya.com/blog/2026/03/building-a-rag-api-with-fastapi/
- Vector database comparison for self-hosted RAG: https://4xxi.com/articles/vector-database-comparison/ and https://jangwook.net/en/blog/en/vector-db-comparison-2026-qdrant-chroma-pgvector/
- MySQL full-text vs vector hybrid search: https://blogs.oracle.com/mysql/hybrid-semantic-keyword-search-in-mysql-heatwave and https://medium.com/@stephenc211/enhancing-mysql-searches-with-vector-embeddings-11f183932851
- Ollama + Python summarization patterns: https://nelson.cloud/local-text-summarization-with-ollama-and-python-is-just-string-manipulation/ and https://codingprojects.blog/posts/implementing-local-llm-workflows-with-ollama-and-python
- FastAPI pagination + JWT best practices: https://github.com/zhanymkanov/fastapi-best-practices and https://betterstack.com/community/guides/scaling-python/authentication-fastapi/
- PKM MVP and second brain framing: https://fortelabs.com/blog/the-4-notetaking-styles-how-to-choose-a-digital-notes-app-as-your-second-brain/ and https://buildin.ai/blog/best-second-brain-apps-2026

---

*Feature research for: Personal Knowledge Base / Second Brain API*
*Researched: 2026-06-23*
