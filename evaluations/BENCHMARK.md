# GXCode quantitative benchmark

Run `python evaluations/benchmark.py`. The report is written to
`evaluations/benchmark_result.json`.

The benchmark uses fixed synthetic workloads and the actual project
implementations. It measures permission decision accuracy, dangerous-case
blocking, P95 decision latency, tool-result spill rate and character
reduction, context message reduction and user-requirement retention, and
Agent tool-chain completion/latency. It does not measure SWE-bench repair
success, multi-agent collaboration, OS-level sandboxing, or MCP lazy-loading;
those capabilities are not implemented in the current repository.
