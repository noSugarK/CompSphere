# Contributing

Contribution workflow for CompSphere. Code rules live in [CODING_STANDARDS.md](CODING_STANDARDS.md), UI rules in [FRONTEND_DESIGN_GUIDELINES.md](FRONTEND_DESIGN_GUIDELINES.md), and business design in [docs/](docs/README.md).

## Commits and branches

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>(<scope>): <short imperative subject>
```

- Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. Formatting-only changes use `chore`.
- Scope is optional; use the affected module or concern, such as `registrations`, `frontend`, `docker`, or `docs`.
- Explain non-obvious reasons in the body. Cite the requirement for business changes; breaking changes include a `BREAKING CHANGE:` footer and migration instructions.
- Keep commits focused; separate unrelated formatting and generated files from logic changes. Never commit secrets or real personal data.
- `main` receives reviewed PRs. Use short lowercase branches: `feat/<summary>`, `fix/<summary>`, or `codex/<summary>` for agent work.
- Coordinate history changes on shared branches; use `--force-with-lease` only when a rewrite is agreed.

## Pull requests

A reviewable PR:

1. States the problem, resulting behavior, and verification performed.
2. Runs applicable configured checks and includes tests for changed business behavior, following the coding standards.
3. Updates the affected requirement, permission, state, schema or API document together with the code. Update `.env.example` when configuration changes.
4. Includes logging for new HTTP endpoints, tasks and write paths per [DEVELOPMENT.md](DEVELOPMENT.md#2-日志与可观测性).
5. Resolves review comments with a change or an explanation.

Prefer small PRs. Review correctness, security and specification conformance; leave automatically enforceable formatting to tools.

## Tooling status

This repository currently contains design documents and deployment scaffolding. There are **no installed commit hooks, linter configurations or CI workflows**; malformed commits are not automatically rejected.

W1 must add the toolchain described in the coding standards and use the same checks locally and in CI. Run `pre-commit install` only after its configuration and dependencies exist. Until then, report available checks and any unverified behavior explicitly.
