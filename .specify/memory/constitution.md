<!--
SYNC IMPACT REPORT:
Version: 0.0.0 → 1.0.0
Modified Principles: Initial constitution creation
Added Sections: 
  - Core Principles (5 principles)
  - Output Format Standards
  - Development Workflow
  - Governance
Templates Requiring Updates:
  ✅ plan-template.md - Constitution Check gates defined
  ✅ spec-template.md - Functional requirements align with principles
  ✅ tasks-template.md - Task organization supports modular development
Follow-up TODOs: None - all placeholders filled
-->

# News-Check Constitution

## Core Principles

### I. Modular Pipeline Architecture
The application MUST maintain a clear three-stage pipeline: Scraping → Analysis → Generation. Each stage operates as an independent, testable module with well-defined interfaces. Modules MUST be independently executable for development and testing purposes.

**Rationale**: This separation enables parallel development, isolated testing, and easier maintenance. Each component can evolve independently without disrupting the entire pipeline.

### II. Category-Based Content Enforcement
The system MUST enforce minimum category requirements, specifically maintaining at least 3 Fintech articles in top results through active article replacement if necessary. Category scoring MUST be transparent, keyword-based, and auditable.

**Rationale**: Ensures balanced content representation aligned with business needs. The minimum Fintech requirement guarantees consistent coverage of critical financial technology topics regardless of daily news cycles.

### III. HTML Output Fidelity
All HTML output for email distribution MUST be directly copyable into email clients (especially Outlook) without requiring modification. HTML MUST use inline styles, avoid external CSS dependencies, and maintain visual fidelity across email clients. No post-processing of HTML output should be required by users.

**Rationale**: Eliminates friction in the distribution workflow. Users should copy-paste HTML directly from generated files into emails without formatting adjustments or technical knowledge.

### IV. LLM-Optional Analysis
The system MUST function in both LLM-enabled and keyword-only modes. Core functionality (scraping, deduplication, scoring, categorization) MUST NOT depend on LLM availability. LLM features provide enhancement but MUST NOT be required for operation.

**Rationale**: Ensures reliability and cost control. The system remains operational during API outages or when cost constraints require LLM-free operation. Keyword-based analysis provides consistent baseline functionality.

### V. Transparent Content Scoring
Article scoring MUST be deterministic and auditable. The scoring algorithm (60% keyword relevance + 40% trending factors) MUST be documented in code comments. All scoring components (keyword matches, trending score, category assignments) MUST be traceable in debug output or saved artifacts.

**Rationale**: Enables troubleshooting, tuning, and validation of results. Users should understand why articles were selected and be able to adjust parameters to meet changing needs.

## Output Format Standards

All generated documents MUST follow these standards:

- **Word Documents**: Use python-docx with consistent styling (Calibri font, defined margins, paragraph spacing)
- **HTML Email**: Inline styles only, no `<style>` blocks, tested for Outlook compatibility
- **Data Exports**: Excel format for raw data with clear column headers
- **Content Storage**: JSON format for fetched article content and error logs

**File Naming Convention**: All output files MUST include timestamps in `YYYYMMDD_HHMMSS` format to prevent overwrites and enable chronological tracking.

## Development Workflow

### Testing Requirements
- **Unit Tests**: Required for all scoring, categorization, and deduplication logic
- **Integration Tests**: Required for end-to-end pipeline execution
- **Mock Usage**: LLM calls MUST be mocked in tests to ensure reproducibility and speed
- **Coverage**: Pytest with coverage reporting configured in `pytest.ini`

### Code Organization
- `src/`: Core modules (scraper, analyzer, generator, models, config)
- `tests/`: Mirror structure of `src/` for test discoverability
- `Output/`: Generated reports and artifacts (not tracked in git)
- `docs/`: Project documentation and guides
- `.specify/`: Specification templates and governance files

### Configuration Management
All configuration MUST be centralized in `src/config.py`. API keys, thresholds, timeouts, and behavioral flags MUST be defined as module-level constants, not hardcoded in business logic.

## Governance

This constitution supersedes all other development practices and conventions. All feature specifications, implementation plans, and pull requests MUST verify compliance with these principles.

**Amendment Process**:
1. Proposed changes documented with rationale
2. Impact assessment on existing code and templates
3. Version bump following semantic versioning (MAJOR.MINOR.PATCH)
4. Update dependent templates (plan, spec, tasks)
5. Sync report appended to constitution

**Versioning Policy**:
- **MAJOR**: Backward-incompatible changes to core principles (e.g., removing category enforcement, changing pipeline architecture)
- **MINOR**: New principles added or existing principles materially expanded
- **PATCH**: Clarifications, wording improvements, non-semantic refinements

**Runtime Guidance**: Developers MUST consult `.github/copilot-instructions.md` for implementation patterns, common gotchas, and technical details not covered in this constitution.

**Compliance Review**: Each feature specification MUST include a "Constitution Check" section verifying alignment with all principles. Non-compliance MUST be explicitly justified with migration plans.

**Version**: 1.0.0 | **Ratified**: 2026-01-05 | **Last Amended**: 2026-01-05
