<!--
Thanks for contributing! Please fill in the sections below.
Keep the PR focused on a single logical change.
-->

## Summary

<!-- What does this PR do, and why? -->

## Related issue

<!-- e.g. Closes #123. Open an issue first for non-trivial changes. -->

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that changes existing behavior)
- [ ] Documentation only
- [ ] Refactor / chore (no functional change)

## How was this tested?

<!-- Describe the tests you added/ran and how you verified the change. -->

## Checklist

- [ ] My branch is up to date with `master`
- [ ] `uv run ruff check app/ tests/` passes
- [ ] `uv run mypy app/` passes
- [ ] `uv run pytest` passes (Docker running for the MySQL testcontainer)
- [ ] New behavior is covered by tests
- [ ] User-facing changes are reflected in the README/docs
- [ ] The change preserves per-user data isolation (queries scoped to the authenticated user)
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
