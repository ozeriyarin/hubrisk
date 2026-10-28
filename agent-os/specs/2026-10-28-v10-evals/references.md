# References for v10 evals

- `src/app/evals/runner.py` — `RunResult`, `CaseResult`, `Report` (computed fields), `check`, `run_case`.
- `src/app/evals/report.py::render_markdown` — header, category table, served-by line, failures.
- `src/app/agent/core.py::Service.ask` — builds the `Turn` from `result.new_messages()`; tool returns are
  `ToolReturnPart`s in `ModelRequest.parts`; `model_response_str()` gives the string the model saw.
- Engine numbers used in the cases (scoring 1.0.0): Minneapolis snow 5.2 (overall 38.27), Seattle wind 8.6,
  Houston rain 21.7 (overall 20.34), Phoenix heat 99.4, Chicago cold 10.1, Denver snow 4.7, Newark wind 7.7,
  Atlanta rain 14.0, Miami wind 3.1 (overall 10.62), Los Angeles heat 4.5, Detroit cold 6.5, Kansas City snow 1.8,
  Dallas overall 21.68 (rain 15.9 × 0.8 = 12.72, wind 4.9, heat 12.4 × 0.3 = 3.72, snow 0.2, cold 0.2 × 0.7 = 0.14),
  Chicago 2024 snow days 35 of 366 = 9.6%, Houston 2025 heavy-rain days 16, Miami vs Houston heat 0.0 vs 2.6.
