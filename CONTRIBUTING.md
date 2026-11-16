# Contributing

This document defines how changes are committed, branched, and reviewed in
CompSphere. Product and code behaviour are specified in
[`docs/`](docs/README.md); this file only governs the contribution workflow.

Commit messages follow the [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
specification. Tooling and CI rely on that structure: a malformed message fails
the commit.

## Commit message format

```
<type>(<scope>): <subject>
                                            <- blank line
<body>                                      <- optional, wrapped at 72
                                            <- blank line
<footer>                                    <- optional
```

The subject is required; scope, body and footer are optional except where noted.

### Types

| Type | Use for |
| --- | --- |
| `feat` | A new user-visible capability |
| `fix` | A defect correction |
| `refactor` | Structure change with no behavioural difference |
| `perf` | Performance change (body must state before/after figures) |
| `docs` | Documentation only |
| `test` | Tests only |
| `build` | Dependencies, packaging, Dockerfile, image build |
| `ci` | CI/CD configuration and scripts |
| `chore` | Maintenance with no source logic change |
| `revert` | Reverts a previous commit; body must contain `Reverts <sha>` |

There is no `style` type. Formatting-only changes go in `chore` and never mix
with logic changes in the same commit.

### Scopes

Scope must name a directory that already exists. Inventing a scope is rejected.

- Backend, by Django app: `accounts`, `profiles`, `orgs`, `rbac`, `teams`,
  `competitions`, `groups`, `registrations`, `awards`, `certificates`,
  `notifications`, `stats`, `audit`, `core`, `config`
- Frontend, by top-level `src/` directory: `api`, `stores`, `router`,
  `layouts`, `views`, `components`, `utils`, `styles`
- Cross-cutting: `deps`, `docker`, `docs`

### Subject rules

- Imperative mood, no trailing period, 50 characters or fewer.
- States what the change does: `fix encoding in registration export`, not
  `export issue resolved`.
- No filler: `update`, `wip`, `fix bug`, `misc`, `1`.

### Body rules

- Explain **why**, not **what**. The diff already shows what changed.
- Wrap at 72 characters.
- Changes that implement a specified rule must cite the source document, for
  example `Refs: docs/01-PRD.md#3.6` or `Refs: docs/02-permission-matrix.md`
  §4.2. This is what makes a later requirement change traceable to the code it
  affects.
- Breaking changes: start the footer with `BREAKING CHANGE:` and describe the
  migration. Also update the affected `docs/` file and `.env.example` in the
  same commit.

### Examples

```
feat(registrations): enforce group member count limits on submit

min_members/max_members were only validated client side, so the API
accepted out-of-range teams. Validation now runs inside
services.create_snapshot() within the same transaction as the member
snapshot write.

Refs: docs/01-PRD.md#3.6
```

```
fix(certificates): keep certificate numbers stable across edition edits

The sequence was derived from the edition primary key, so merging
edition rows would have silently renumbered already-issued certificates.
Numbers now come from a per-edition counter that is never reused.

Refs: docs/03-state-machines.md#6
Closes: #142
```

## Commit atomicity

Every commit must leave the tree in a working state and do exactly one thing.

Not allowed in a single commit:

- Logic changes plus unrelated reformatting
- Two unrelated modules
- Local artefacts: `.env`, keys, `node_modules/`, `__pycache__/`, `dist/`,
  `*.log`, `.DS_Store`, IDE settings

`.gitignore` already covers the generated artefacts above; if something shows up
in `git status` that shouldn't be committed, fix `.gitignore` in a separate
`chore` commit rather than adding the file to the tree.

## Branching

| Branch | Rule |
| --- | --- |
| `main` | Always deployable. Only receives merged pull requests, never direct pushes |
| `feat/<scope>-<summary>` | Cut from `main` |
| `fix/<summary>` | Cut from `main` |
| `release/<version>` | Only when a tag needs to be prepared |

Branch names are lowercase, hyphen-separated, and short enough to read in `git
branch`. Do not rebase or force-push a branch that already has an open pull
request. Personal branches without a pull request may be rebased, using
`--force-with-lease`.

## Pull requests

A pull request is ready for review when all of the following hold:

1. CI is green: lint, typecheck, tests.
2. New or changed service-layer logic has tests. Coverage for `rbac`,
   `registrations` and `awards` stays at or above 80%.
3. Any change to a status value, permission code, or error code updates
   `docs/02`, `docs/03` and `docs/06` in the same pull request. Documents and
   code are reviewed as one unit; see `docs/07-task-breakdown.md` ("文档即代码").
4. New HTTP endpoints, Celery tasks and database write paths emit the logs
   required by `DEVELOPMENT.md` §2. A pull request that adds an endpoint without
   logging is rejected without further review.
5. The description states the requirement being satisfied and how the change was
   verified, including commands run and their output.

Keep a pull request under roughly 400 changed lines of effective code. Split
larger work into an infrastructure commit first, then the business logic.

### Review

- Reviewers comment on correctness, security and specification conformance.
  Style that a linter can enforce is settled by the linter, not by review.
- Author resolves every comment by either changing the code or replying with
  the reason; silent dismissal is not a resolution.
- Approval does not transfer responsibility for the change from author to
  reviewer.

## Tooling

Enforced locally through `pre-commit`, with the same configuration used in CI:

- Backend: `ruff format`, `ruff check`, `mypy` (strict on `apps/*/services.py`
  and `core/`)
- Frontend: `eslint --fix`, `prettier --check`, `vue-tsc --noEmit`

Install once per clone:

```bash
pre-commit install
```

Running a hook with `--all-files` is a `chore` commit on its own.

## Where to look next

| Topic | Document |
| --- | --- |
| Requirements, roles, scope | `docs/01-PRD.md` |
| Permission model | `docs/02-permission-matrix.md` |
| State machines | `docs/03-state-machines.md` |
| Schema | `docs/04-database-design.md` |
| Architecture and layering | `docs/05-architecture.md` |
| API contract and error codes | `docs/06-api-spec.md` |
| Milestones and task order | `docs/07-task-breakdown.md` |
| Deployment and backups | `docker/README.md` |
| Logging, UI, copy, interaction rules | `DEVELOPMENT.md` |
