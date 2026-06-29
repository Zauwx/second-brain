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

- [x] **NOTE-01**: User can create a note with text content and an optional source URL/title
- [x] **NOTE-02**: User can retrieve a single note and list their own notes
- [x] **NOTE-03**: User can update their own note
- [x] **NOTE-04**: User can delete their own note

### Organization

- [x] **ORG-01**: User can create tags and attach/detach them to notes (many-to-many)
- [x] **ORG-02**: User can filter notes by one or more tags
- [x] **ORG-03**: User can create collections and add/remove notes from them
- [x] **ORG-04**: User can list the notes contained in a collection

### Search

- [ ] **SRCH-01**: User can full-text search their notes by keyword (MySQL FULLTEXT)

### Local AI (Ollama)

- [ ] **AIL-01**: User can generate an automatic summary of a note via a local LLM
- [ ] **AIL-02**: User can get automatically suggested tags for a note via a local LLM

### Cloud AI / RAG

- [ ] **RAG-01**: User can ask a natural-language question and get an answer grounded in their own notes, with source citations (RAG via cloud LLM)
- [ ] **RAG-02**: User can get a list of related/similar notes for a given note (via embeddings)

### API Quality (REST / HTTP)

- [x] **API-01**: List endpoints support pagination, filtering, and sorting with correct HTTP status codes
- [x] **API-02**: The API exposes auto-generated OpenAPI/Swagger documentation
- [x] **API-03**: The API has an automated test suite (pytest) covering the core endpoints

### DevOps & Infrastructure

- [x] **OPS-01**: The whole app runs in Docker containers (api, mysql, ollama) via Docker Compose
- [ ] **OPS-02**: There are separate dev/live and prod environment configurations (compose overrides + env files)
- [ ] **OPS-03**: A CI pipeline (GitHub Actions) runs lint and tests on every push
- [ ] **OPS-04**: CI builds and publishes a versioned Docker image; releases are tagged with semantic versions
- [x] **OPS-05**: Repo foundations prevent Windows/secret pitfalls (.gitignore excludes secrets, .gitattributes forces LF, .env.example provided)

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
| OPS-05 | Phase 1 | Complete |
| NOTE-01 | Phase 2 | Complete |
| NOTE-02 | Phase 2 | Complete |
| NOTE-03 | Phase 2 | Complete |
| NOTE-04 | Phase 2 | Complete |
| API-01 | Phase 2 | Complete |
| API-02 | Phase 2 | Complete |
| API-03 | Phase 2 | Complete |
| OPS-01 | Phase 2 | Complete |
| AUTH-01 | Phase 3 | Pending |
| AUTH-02 | Phase 3 | Pending |
| AUTH-03 | Phase 3 | Pending |
| AUTH-04 | Phase 3 | Pending |
| ORG-01 | Phase 4 | Complete |
| ORG-02 | Phase 4 | Complete |
| ORG-03 | Phase 4 | Complete |
| ORG-04 | Phase 4 | Complete |
| SRCH-01 | Phase 4 | Pending |
| AIL-01 | Phase 5 | Pending |
| AIL-02 | Phase 5 | Pending |
| RAG-01 | Phase 6 | Pending |
| RAG-02 | Phase 6 | Pending |
| OPS-02 | Phase 7 | Pending |
| OPS-03 | Phase 7 | Pending |
| OPS-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25 (Phase 1: 1, Phase 2: 8, Phase 3: 4, Phase 4: 5, Phase 5: 2, Phase 6: 2, Phase 7: 3)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-23*
*Last updated: 2026-06-23 after roadmap creation — all 25 v1 requirements mapped*
