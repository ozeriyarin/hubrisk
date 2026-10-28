# v0 platform — Shaping Notes

## Scope

The domain-agnostic platform: model chain + retries + fallback, guard, budget, API + chat page, sessions, rate
limits, eval runner, offline tests, CI, Render Blueprint. No hubs, weather, scoring or domain prompts.

## Decisions

- Lift the base scaffold as-is; package name stays `app`; composition root stays `cli.compose`.
- Test mode guard runs on a `FunctionModel` returning a fixed in-scope `Screening`; the `TestModel` guard in the
  scaffold refused in-scope questions and made the CI eval smoke exit 1.
- Criterion tests for spec `<date>-<slug>` live in `tests/test_<slug>.py` so two specs' criterion numbers never
  collide; the coverage test enforces per spec.
- Existing unit tests stay; criterion tests are thin end-to-end tests over the same fakes.
- `SCOPE_DESCRIPTION` gets a one-sentence weather-hub-risk scope now so the guard is meaningful; v3 refines it.
- `prices.yaml` gains `version` and a verification date; model ids re-checked at implementation.
- Reserve `app/data/` and `app/scoring/` packages now.

## Context

- **Visuals:** none.
- **References:** the base scaffold (see `references.md`).
- **Product alignment:** roadmap Phase 1 item 1; mission bullet "production-shaped platform".

## Standards Applied

- python-style — package layout, Pydantic at boundaries, comments, commit messages.
- ai-calls — chain, retry layers, typed output, prompt changes ship with an eval report.
- guardrails — regex → Jev → Haiku order, policy in code, fixed refusals.
- budget — reserve/settle/release, caps, provider-side limits.
- secrets-and-config — env-only secrets, versioned YAML config, test mode.
- testing — offline fakes, criterion test naming, coverage test.
- evals — case categories, exit codes, `--down`.
- deployment — Render Blueprint, CI steps, health probe.
