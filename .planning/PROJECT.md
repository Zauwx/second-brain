# Second Brain — Base de connaissances personnelle avec IA

## What This Is

Une application "second brain" auto-hébergée : l'utilisateur sauvegarde des notes, articles et liens, les organise (tags, collections) et interroge sa propre base de connaissances en langage naturel. C'est avant tout un **projet d'apprentissage fil-rouge** : il sert de support concret pour monter en compétences sur MySQL, les REST API / HTTP, l'IA générative (LLMs locaux et cloud), Docker, Linux, et un vrai pipeline CI/CD + versioning. Pour : le développeur lui-même, comme outil personnel **et** comme pièce maîtresse de son profil GitHub.

## Core Value

L'utilisateur peut sauvegarder du contenu et **retrouver / interroger ses connaissances en langage naturel** (RAG) — c'est la fonction qui doit marcher avant tout le reste.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. Hypotheses until shipped. -->

**Domaine — Connaissances (MySQL + REST)**
- [ ] L'utilisateur peut créer / lire / modifier / supprimer des notes (texte + source/URL)
- [ ] L'utilisateur peut organiser ses notes avec des tags (relation many-to-many)
- [ ] L'utilisateur peut regrouper des notes en collections
- [ ] L'utilisateur peut rechercher dans ses notes (recherche texte / full-text)
- [ ] L'API REST est documentée automatiquement (Swagger / OpenAPI) et testée

**Auth & multi-utilisateur (HTTP)**
- [ ] L'utilisateur peut créer un compte et se connecter (JWT)
- [ ] Chaque utilisateur ne voit que ses propres données (isolation)

**IA — Locale (Ollama)**
- [ ] L'utilisateur peut générer automatiquement un résumé d'une note via un LLM local
- [ ] L'utilisateur peut obtenir des tags suggérés automatiquement via un LLM local

**IA — Cloud (RAG / Q&A)**
- [ ] L'utilisateur peut poser une question en langage naturel et obtenir une réponse fondée sur ses notes (RAG via API cloud)

**Infra, DevOps & montée en compétences Linux**
- [ ] L'app tourne entièrement en conteneurs Docker (API, MySQL, Ollama)
- [ ] Il existe deux environnements distincts : dev/live et prod (configs séparées)
- [ ] Le projet vit dans un repo GitHub avec un pipeline CI/CD (lint, tests, build d'image)
- [ ] Le versioning est propre (git, tags sémantiques, branches)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Interface web riche / SPA — v1 est **API-first** + Swagger ; une UI minimale viendra plus tard (focus apprentissage REST/HTTP/MySQL d'abord)
- Application mobile — hors sujet pour l'objectif d'apprentissage
- Collaboration temps réel / partage entre utilisateurs — complexité non nécessaire pour le cœur de valeur
- Hébergement cloud public managé (AWS/GCP) — l'objectif est le home lab auto-hébergé sur le poste Windows
- Fine-tuning de modèles — on consomme des LLMs (local + API), on n'en entraîne pas

## Context

- **Poste de travail** : Windows 11 ; Docker Desktop fait tourner des conteneurs **Linux** → c'est précisément le terrain d'apprentissage Linux du projet.
- **Objectif de fond** : combler des lacunes identifiées par l'utilisateur en MySQL, REST API & HTTP, IA/LLMs, et **surtout CI/CD + versioning + Linux**. Le projet est conçu pour que chaque compétence s'apprenne **en livrant l'app**, pas en parallèle.
- **IA hybride** : LLM local (Ollama) pour les tâches simples/privées (résumé, tagging) ; API cloud pour le raisonnement lourd (RAG, Q&A). Apprendre à **router** entre les deux est un objectif explicite.
- **Portfolio** : le repo doit être présentable (README, CI verte, structure propre, commits clairs) pour valoriser le profil GitHub.

## Constraints

- **Tech stack**: Python + FastAPI (backend/API) — meilleur écosystème IA/LLM, doc Swagger auto, très demandé.
- **Tech stack**: MySQL (base de données) — objectif d'apprentissage explicite ; modèle relationnel riche attendu (jointures, many-to-many, index, full-text).
- **Tech stack**: Docker / Docker Compose — environnements dev/live + prod ; tout conteneurisé.
- **Tech stack**: IA hybride — Ollama (local) + une API LLM cloud (Claude/OpenAI) pour le RAG.
- **Plateforme**: Développement sur Windows via Docker Desktop ; conteneurs Linux (apprentissage Linux ciblé).
- **DevOps**: GitHub + CI/CD (GitHub Actions) + versioning sémantique — exigence de premier rang, pas un accessoire.
- **Sécurité**: Auth JWT multi-utilisateur avec isolation des données ; secrets hors du repo.

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| App "second brain" / base de connaissances comme fil rouge | Modèle relationnel riche (MySQL), REST API naturelle, et usage IA local+cloud évident ; valorisant sur GitHub | — Pending |
| Python + FastAPI | Écosystème IA/LLM, Swagger auto, compétence très recherchée | — Pending |
| API-first (Swagger) avant toute UI | Maximiser l'apprentissage REST/HTTP/MySQL ; livrer un cœur testable vite | — Pending |
| Multi-utilisateur + JWT | Apprendre auth/autorisation/isolation, sujets HTTP formateurs | — Pending |
| IA local (Ollama) + cloud (API) | Apprendre à router selon coût/confidentialité/puissance | — Pending |
| Docker dev/live + prod sur Windows | Conteneurs Linux = apprentissage Linux ; deux environnements = vrai cycle de déploiement | — Pending |
| CI/CD + versioning traités comme objectifs de 1er rang | Lacune explicite à combler ; rend le repo portfolio-ready | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-25 — Phase 3 (Auth + Per-User Data Isolation) complete: JWT register/login, refresh-token rotation + logout, and per-user note isolation (403/404 on cross-user access) verified against real MySQL (66 tests passing).*
