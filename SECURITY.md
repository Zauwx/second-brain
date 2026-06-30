# Security Policy

Second Brain is a multi-user application with authentication and per-user data
isolation, so security reports are taken seriously.

## Supported Versions

The project is pre-1.0 and under active development. Security fixes are applied
to the `master` branch (the latest state). There are no maintained older
release lines yet.

| Version | Supported          |
|---------|--------------------|
| `master` (latest) | ✅ |
| Tagged pre-1.0 releases | ❌ |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, use one of these private channels:

1. **GitHub Security Advisories (preferred)** — go to the repository's
   **Security → Report a vulnerability** tab to open a private advisory.
2. **Email** — send details to **dxt.spedzox@gmail.com** with the subject
   `[SECURITY] Second Brain`.

Please include as much of the following as you can:

- The type of issue (e.g. authentication bypass, broken data isolation,
  injection, secret exposure).
- The affected endpoint, file, or component.
- Step-by-step instructions to reproduce.
- Proof-of-concept or exploit code, if available.
- The potential impact, including how an attacker might exploit it.

## What to Expect

- **Acknowledgement** within 5 business days.
- An assessment of the report and an expected timeline for a fix.
- Notification when the vulnerability is resolved.
- Credit for the discovery, if you would like it (let us know your preference).

Because this is a personal/learning project maintained in spare time, response
times are best-effort — but every report will be reviewed.

## Scope

In scope:

- Authentication and JWT handling (`app/auth/`, `app/core/security.py`)
- Per-user data isolation across notes, tags, collections, and search
- SQL injection, secret leakage, and insecure defaults

Out of scope:

- Vulnerabilities requiring a compromised host or physical access
- Issues in third-party dependencies that have no impact on this app's use of them
  (please report those upstream)
- Denial of service via unrealistic resource exhaustion on a self-hosted instance

Thank you for helping keep Second Brain and its users safe.
