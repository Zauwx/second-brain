# Requirements: Second Brain

**Defined:** 2026-06-23
**Core Value:** L'utilisateur peut sauvegarder du contenu et retrouver / interroger ses connaissances en langage naturel (RAG).

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Authentication

- [ ] **AUTH-01**: User can sign up with an email and password
- [ ] **AUTH-02**: User can log in and receive a JWT access token
- [ ] **AUTH-03**: User stays authenticated across requests, with token refresh (no re-login each call)
- [ ] **AUTH-04**: User can only access their own data — every query is scoped to the authenticated user

### Notes

- [ ] **NOTE-01**: User can create a note with text content and an optional source URL/title
- [ ] **NOTE-02**: User can retrieve a single note and list their own notes
- [ ] **NOTE-03**: User can update their own note
- [ ] **NOTE-04**: User can delete their own note

### Organization

- [ ] **ORG-01**: User can create tags and attach/detach them to notes (many-to-many)
- [ ] **ORG-02**: User can filter notes by one or more tags
- [ ] **ORG-03**: User can create collections and add/remove notes from them
- [ ] **ORG-04**: User can list the notes contained in a collection

### Search

- [ ] **SRCH-01**: User can full-text search their notes by keyword (MySQL FULLTEXT)

### Local AI (Ollama)

- [ ] **AIL-01**: User can generate an automatic summary of a note via a local LLM
- [ ] **AIL-02**: User can get automatically suggested tags for a note via a local LLM

### Cloud AI / RAG

- [ ] **RAG-01**: User can ask a natural-language question and get an answer grounded in their own notes, with source citations (RAG via cloud LLM)
- [ ] **RAG-02**: User can get a list of related/similar notes for a given note (via embeddings)

### API Quality (REST / HTTP)

- [ ] **API-01**: List endpoints support pagination, filtering, and sorting with correct HTTP status codes
- [ ] **API-02**: The API exposes auto-generated OpenAPI/Swagger documentation
- [ ] **API-03**: The API has an automated test suite (pytest) covering the core endpoints

### DevOps & Infrastructure

- [ ] **OPS-01**: The whole app runs in Docker containers (api, mysql, ollama) via Docker Compose
- [ ] **OPS-02**: There are separate dev/live and prod environment configurations (compose overrides + env files)
- [ ] **OPS-03**: A CI pipeline (GitHub Actions) runs lint and tests on every push
- [ ] **OPS-04**: CI builds and publishes a versioned Docker image; releases are tagged with semantic versions
- [ ] **OPS-05**: Repo foundations prevent Windows/secret pitfalls (.gitignore excludes secrets, .gitattributes forces LF, .env.example provided)

## v2 Requirements

Deferred to a future release. Tracked but not in the current roadmap.

### Import / Export

- **IO-01**: User can import and export notes in bulk as Markdown

### Search (advanced)

- **SRCH-02**: Hybrid search merging full-text and semantic results (rank fusion)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Rich web SPA frontend | v1 is API-first + Swagger; UI deferred to keep focus on REST/HTTP/MySQL learning |
| Mobile application | Out of scope for the learning objective |
| Real-time collaboration / sharing between users | High complexity, not core to personal-knowledge value |
| Web clipper browser extension | Nice-to-have, large surface for v1 |
| File attachments / binary uploads | Adds storage concerns unrelated to core learning goals |
| Graph view / backlinks visualization | Visualization, not core to API/data/AI learning |
| LLM fine-tuning | Project consumes LLMs (local + API); does not train them |
| Managed public cloud hosting (AWS/GCP) | Objective is self-hosted home lab on the Windows host |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| OPS-05 | TBD | Pending |
| OPS-01 | TBD | Pending |
| AUTH-01 | TBD | Pending |
| AUTH-02 | TBD | Pending |
| AUTH-03 | TBD | Pending |
| AUTH-04 | TBD | Pending |
| NOTE-01 | TBD | Pending |
| NOTE-02 | TBD | Pending |
| NOTE-03 | TBD | Pending |
| NOTE-04 | TBD | Pending |
| ORG-01 | TBD | Pending |
| ORG-02 | TBD | Pending |
| ORG-03 | TBD | Pending |
| ORG-04 | TBD | Pending |
| SRCH-01 | TBD | Pending |
| AIL-01 | TBD | Pending |
| AIL-02 | TBD | Pending |
| RAG-01 | TBD | Pending |
| RAG-02 | TBD | Pending |
| API-01 | TBD | Pending |
| API-02 | TBD | Pending |
| API-03 | TBD | Pending |
| OPS-02 | TBD | Pending |
| OPS-03 | TBD | Pending |
| OPS-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 0 (to be filled by roadmap)
- Unmapped: 25 ⚠️

---
*Requirements defined: 2026-06-23*
*Last updated: 2026-06-23 after initial definition*
