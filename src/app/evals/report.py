"""Markdown rendering of an eval Report, committed next to the JSON under evals/results/."""

from __future__ import annotations

from app.evals.runner import Report


def render_markdown(report: Report) -> str:
    total = len(report.cases)
    passed = sum(c.passed for c in report.cases)
    lines = [
        f"# Eval report — {report.started_at}",
        "",
        f"- models: {' → '.join(report.models)}",
        f"- guard: {report.guard}",
        f"- config version: {report.config_version}; prompt version: {report.prompt_version}; repeat: {report.repeat}",
        f"- result: **{passed}/{total} cases**, exit code {report.exit_code}, total cost {report.total_cost_usd:.4f} USD",
        "",
        "| Category | Cases | Runs |",
        "|---|---|---|",
    ]
    for cat, d in report.by_category.items():
        lines.append(f"| {cat} | {d['passed']}/{d['cases']} | {d['runs_passed']}/{d['runs']} |")
    lines += ["", "Served by: " + ", ".join(f"{k} ×{v}" for k, v in sorted(report.served_by.items())), ""]
    failures = [c for c in report.cases if not c.passed]
    if failures:
        lines += ["## Failures and flaky cases", ""]
        for c in failures:
            tag = "flaky" if c.flaky else "failed"
            lines.append(f"### `{c.id}` ({c.category}, {tag} {c.passes}/{len(c.runs)})")
            lines.append(f"> {c.question}")
            for i, r in enumerate(c.runs, 1):
                if not r.passed:
                    lines.append(f"- run {i}: {'; '.join(r.reasons)} — answer: {r.answer[:200]!r}")
            lines.append("")
    if report.notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in report.notes] + [""]
    return "\n".join(lines)
