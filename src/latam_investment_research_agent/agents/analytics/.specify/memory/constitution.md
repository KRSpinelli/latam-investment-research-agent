<!--
SYNC IMPACT REPORT
==================
Version change: [unversioned template] → 1.0.0
Principles added:
  - I. Performance First
  - II. Test-Driven Development (NON-NEGOTIABLE)
  - III. Single Responsibility
  - IV. SOLID Principles
  - V. Clean Code Standards
  - VI. Technology Stack Constraints
Sections added:
  - Core Principles
  - Quality Gates
  - Technology Stack & Architecture
  - Governance
Templates requiring updates:
  ✅ .specify/templates/plan-template.md — constitution gates align with existing structure; no change required
  ✅ .specify/templates/spec-template.md — success criteria format compatible; no change required
  ✅ .specify/templates/tasks-template.md — TDD task pattern (write tests first, verify fail, then implement) already enforced by template
Deferred TODOs: none
-->

# LATAM Investment Research Agent — Analytics Agent Constitution

## Core Principles

### I. Performance First

Performance is a first-class requirement, not an afterthought. This system processes financial
analysis workflows where latency directly impacts decision quality.

- All data access MUST use ClickHouse query patterns optimized for columnar reads.
- Async I/O MUST be used for all network-bound operations (LangGraph nodes, ClickHouse queries).
- Benchmarks MUST be established and tracked for any hot path introduced.
- Memory allocations in tight loops MUST be minimized; prefer pre-allocated buffers or streaming.
- Any change to a critical path MUST include a performance justification (measured, not estimated).

**Rationale**: Financial analysis workflows are latency-sensitive. A slow analytics agent produces
stale insight, which is worse than no insight.

### II. Test-Driven Development (NON-NEGOTIABLE)

TDD is mandatory. No production code is written before a failing test exists.

- Red-Green-Refactor cycle MUST be followed strictly: write a failing test → confirm it fails →
  implement the minimum code to pass → refactor.
- Unit tests MUST cover every public function and method.
- Integration tests MUST cover every LangGraph node and every ClickHouse query path.
- Tests MUST be independent; no test MUST depend on ordering or shared mutable state.
- Coverage threshold: 90% line coverage MUST be maintained on all modules.
- Performance regression tests MUST be included for hot paths identified in Principle I.

**Rationale**: Financial data pipelines are high-stakes. Bugs discovered in production can
cause incorrect investment signals. TDD shifts defect discovery left.

### III. Single Responsibility

Each function, method, class, and LangGraph node MUST achieve one and only one purpose.

- A function that fetches data MUST NOT also transform it.
- A function that validates MUST NOT also persist.
- LangGraph nodes MUST encapsulate exactly one logical step in the workflow graph.
- Classes MUST represent a single cohesive concept; if a class name requires "and" to describe
  it, it MUST be split.
- File modules MUST group related single-responsibility units; a module MUST NOT serve as a
  catch-all.

**Rationale**: Financial logic is complex. Mixing concerns creates bugs that are hard to isolate
and impossible to test in isolation.

### IV. SOLID Principles

All production code MUST adhere to SOLID object-oriented design principles.

- **Single Responsibility**: Enforced by Principle III above.
- **Open/Closed**: Classes and functions MUST be open for extension but closed for modification;
  prefer composition and dependency injection over inheritance chains.
- **Liskov Substitution**: Subtypes MUST be fully substitutable for their base types; violating
  this MUST be treated as a design defect.
- **Interface Segregation**: Protocols and abstract base classes MUST be narrow; a class MUST NOT
  be forced to implement methods it does not use.
- **Dependency Inversion**: High-level modules (LangGraph orchestration) MUST depend on
  abstractions, not concrete ClickHouse or I/O implementations. Inject dependencies; never
  hard-code them.

**Rationale**: SOLID design keeps the agent extensible as new data sources and analytical models
are added without requiring rewrites of existing verified logic.

### V. Clean Code Standards

All code MUST meet the following non-negotiable readability and documentation standards.

- **Docstrings**: Every public Python function, method, and class MUST have a Google-style
  docstring. Private helpers MUST have at minimum a one-line summary if their behavior is not
  self-evident.
- **No abbreviations**: Variable names, parameter names, and attribute names MUST be fully
  spelled out (e.g., `clickhouse_connection` not `ch_conn`, `investment_signal` not `sig`).
  Accepted exceptions: loop indices (`i`, `j`) and universally standardized names (e.g., `df`
  for a pandas DataFrame when type annotation makes the type obvious).
- **Naming precision**: Names MUST convey intent. A name that requires a comment to explain
  MUST be renamed.
- **No magic numbers or strings**: All constants MUST be named and placed in a `constants.py`
  or equivalent module.
- **Line length**: 100 characters maximum.
- **Type annotations**: All public function signatures MUST include full type annotations.

**Rationale**: Financial analytics code will be read, audited, and debugged by multiple engineers
under pressure. Clarity is a safety property.

### VI. Technology Stack Constraints

The stack is fixed. Deviations MUST be justified in writing and approved before implementation.

- **Language**: Python 3.12+
- **Workflow orchestration**: LangGraph (graph-based agent workflows)
- **Analytics database**: ClickHouse (columnar, high-performance OLAP)
- **Testing**: pytest with pytest-asyncio for async coverage
- **Type checking**: mypy in strict mode on all modules
- **Linting/formatting**: ruff for linting and formatting; black-compatible line length (100)
- **No ORMs**: ClickHouse queries MUST be written as explicit SQL or use the official
  `clickhouse-connect` driver. ORM abstractions over ClickHouse are prohibited.
- **Dependency management**: uv or Poetry; no ad-hoc pip installs committed to requirements.

**Rationale**: The stack is chosen for performance and reliability in financial data workflows.
Mixing in alternative orchestration frameworks or databases fragments the operational surface.

## Technology Stack & Architecture

### LangGraph Conventions

- Each agent graph MUST have a clearly defined `TypedDict` state schema annotated with all fields.
- Node functions MUST be pure with respect to state: receive state, return state delta.
- Conditional edges MUST delegate condition logic to a dedicated predicate function (not inline
  lambdas with complex logic).
- Graph compilation MUST happen once at module load time, not per-request.

### ClickHouse Conventions

- Queries MUST use parameterized placeholders; string interpolation into SQL is prohibited.
- Connection pooling MUST be configured; do not open a new connection per query.
- Long-running analytical queries MUST be profiled with `EXPLAIN` before merging.
- Schema migrations MUST be versioned and applied via a migration tool (e.g., dbmate or
  a dedicated migrations module).

### Project Structure

```text
src/
├── agents/
│   └── analytics/
│       ├── graph/          # LangGraph graph definitions and node functions
│       ├── models/         # TypedDict state schemas, Pydantic models
│       ├── services/       # Business logic (single-responsibility services)
│       ├── repositories/   # ClickHouse data access layer
│       ├── constants.py    # All named constants
│       └── config.py       # Dependency-injected configuration

tests/
├── unit/                   # Pure function tests
├── integration/            # LangGraph node + ClickHouse integration tests
└── performance/            # Benchmark tests for hot paths
```

## Quality Gates

All of the following MUST pass before any feature branch merges to main:

- [ ] All tests pass (`pytest`)
- [ ] Coverage ≥ 90% (`pytest --cov`)
- [ ] No mypy errors (`mypy --strict`)
- [ ] No ruff violations (`ruff check`)
- [ ] Every public function has a Google docstring
- [ ] No new abbreviations introduced in variable/parameter/attribute names
- [ ] Performance benchmarks for changed hot paths show no regression
- [ ] Constitution Check in plan.md completed and violations documented

## Governance

- This constitution supersedes all other development practices and style guides for this project.
- Amendments MUST be proposed as a pull request modifying this file with a bump to
  `CONSTITUTION_VERSION` following semantic versioning:
  - **MAJOR**: Removal or redefinition of a principle.
  - **MINOR**: Addition of a new principle or materially expanded guidance.
  - **PATCH**: Clarification, wording fix, or non-semantic refinement.
- Amendment pull requests MUST include an updated Sync Impact Report (HTML comment at the top
  of this file).
- All code reviews MUST verify compliance with this constitution before approval.
- Complexity that appears to violate a principle MUST be justified in the plan.md
  Complexity Tracking table; undocumented violations are grounds for rejection.
- Runtime development guidance lives in `CLAUDE.md` at the project root.

**Version**: 1.0.0 | **Ratified**: 2026-05-23 | **Last Amended**: 2026-05-23
