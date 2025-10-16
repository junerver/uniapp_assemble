<!--
Sync Impact Report:
Version change: 1.2.0 → 1.3.0 (minor - added code hygiene principle)
Modified principles:
  - Code Quality Standards → Enhanced with temporary code cleanup requirements
Added sections:
  - Principle VIII: Code Hygiene and Cleanup (NEW mandatory principle)
  - Enhanced Code Quality Standards with temporary file cleanup enforcement
Removed sections: N/A
Templates requiring updates:
  - ✅ README.md (already reflects UV usage)
  - ✅ pyproject.toml (already configured for UV)
  - ⚠️ .specify/templates/plan-template.md (needs cleanup verification step)
  - ⚠️ .specify/templates/tasks-template.md (needs cleanup task type)
  - ⚠️ .gitignore (should exclude common temporary test files)
Follow-up TODOs:
  - Add pre-commit hook to detect common temporary file patterns
  - Update .gitignore with patterns for test/debug files
  - Document approved locations for temporary experimentation
-->

# GovCar Upgrade UniApp Assembly Constitution

## Core Principles

### I. Modular Architecture
Every component MUST be developed as a standalone, self-contained module with
clear interfaces. Modules MUST be independently testable, documented, and have
single responsibility. No organizational-only modules allowed.

### II. Cross-Platform Compatibility
All code MUST maintain compatibility across Web, iOS, and Android platforms.
Platform-specific implementations MUST be abstracted through unified interfaces.
Code sharing MUST be maximized while respecting platform constraints.

### III. Test-First Development (NON-NEGOTIABLE)
TDD is mandatory: Tests MUST be written → User-approved → Tests MUST fail →
Then implementation follows. Red-Green-Refactor cycle MUST be strictly enforced.
Unit tests, integration tests, and end-to-end tests required.

### IV. Component Reusability
All UI components and business logic modules MUST be designed for reuse across
different screens and features. Components MUST accept configurable props and
maintain consistent behavior patterns. Shared component library MUST be
maintained.

### V. Performance Optimization
All code MUST meet performance standards: Initial app load < 3 seconds, Page
transitions < 500ms, Memory usage optimized for mobile devices. Lazy loading
and code splitting MUST be implemented where appropriate. Performance metrics
MUST be continuously monitored and optimized.

### VI. User Experience Consistency
All user interfaces MUST maintain consistent interaction patterns, visual
design, and behavior across all platforms. User experience MUST be intuitive,
responsive, and accessible. UX consistency MUST be validated through user
testing and automated checks.

### VII. UV Package Management (MANDATORY)
UV MUST be used exclusively for all Python package management, virtual
environment creation, and script execution. Direct use of python, pip, or
python -m commands is PROHIBITED unless explicitly wrapped by uv.

**Rationale**: UV provides 10-20x faster dependency installation, deterministic
builds through uv.lock, and consistent cross-platform behavior. This eliminates
environment inconsistencies and reduces setup time from minutes to seconds.

**Enforcement**:
- All Python commands MUST use `uv run python` or `uv run <command>`
- Virtual environments MUST be created with `uv venv`
- Dependencies MUST be installed with `uv sync` or `uv add`
- Scripts MUST be executed with `uv run <script>`
- CI/CD pipelines MUST use UV for all Python operations
- Documentation MUST show UV commands exclusively

**Prohibited**:
- ❌ `python script.py` → ✅ `uv run python script.py`
- ❌ `pip install package` → ✅ `uv add package`
- ❌ `python -m pytest` → ✅ `uv run pytest`
- ❌ Manual virtualenv management → ✅ `uv venv` + `uv sync`

### VIII. Code Hygiene and Cleanup (MANDATORY)
Temporary verification scripts, debug code, test files, and experimental code
MUST be deleted immediately after verification is complete. No "throwaway code"
or "garbage files" are permitted in the repository.

**Rationale**: Temporary files create confusion, pollute the codebase, increase
maintenance burden, and can accidentally be deployed to production. Clean code
is maintainable code.

**Requirements**:
- Temporary test scripts MUST be deleted after validation completes
- Debug/diagnostic code MUST be removed before commit
- Experimental files MUST NOT be committed unless properly structured
- One-off verification code MUST be cleaned up immediately
- Commented-out code MUST be removed (use version control history instead)
- TODO comments MUST include issue numbers and cleanup dates

**Approved Temporary Locations** (auto-cleaned):
- `/temp/` directory (gitignored, auto-cleanup on startup)
- `/sandbox/` directory (gitignored, manual cleanup)
- Test files following pattern `test_*.py` or `*_test.py` in tests/ only

**Prohibited**:
- ❌ `debug_*.py` in src/ directory
- ❌ `test_*.html` in root or src/
- ❌ `temp_*.py` anywhere
- ❌ `scratch_*.js` files
- ❌ `foo.py`, `bar.py`, `asdf.py` throwaway files
- ❌ Large blocks of commented-out code

**Enforcement**:
- Pre-commit hooks MUST scan for common temporary file patterns
- Code review MUST reject PRs containing obvious temporary files
- CI/CD MUST fail if throwaway file patterns detected
- .gitignore MUST exclude common temporary file patterns

**Example Violations**:
```python
# ❌ WRONG - temporary debug file left in repo
# File: debug_download.py (found in root)
# File: test_base64_frontend.html (found in root)
# File: fix_apk_download.py (temporary fix script)

# ✅ CORRECT - use proper test structure or delete
# If needed for testing: tests/test_download.py
# If one-off debug: delete after verification
# If experimental: /sandbox/experiment_name.py (gitignored)
```

## Development Standards

### Code Quality Standards
- All code MUST follow consistent formatting and linting rules using ruff and
  black
- Python type hints MUST be used for type safety with mypy validation
- Code review is required for all changes with focus on readability and
  maintainability
- Documentation MUST be updated with functional changes
- Code quality metrics MUST be measured and maintained above 90% quality score
- Temporary files MUST be cleaned up before commits (see Principle VIII)
- Repository MUST remain clean and free of debug/throwaway files

### Project Management Standards
- UV MUST be used as the primary package management tool (see Principle VII)
- pyproject.toml MUST be used for all project configuration and dependency
  management
- Virtual environments MUST be managed through `uv venv` for consistency
- Dependencies MUST be explicitly declared with version constraints in
  pyproject.toml
- Development dependencies MUST be separated from production dependencies
- uv.lock MUST be committed to version control for reproducible builds
- All project scripts MUST be defined in pyproject.toml [project.scripts]
  section

### Tooling Standards
- Package installation: `uv add <package>` (REQUIRED)
- Script execution: `uv run <command>` (REQUIRED)
- Virtual environment: `uv venv` then `uv sync` (REQUIRED)
- Testing: `uv run pytest` (REQUIRED)
- Formatting: `uv run black src/` and `uv run ruff format src/` (REQUIRED)
- Type checking: `uv run mypy src/` (REQUIRED)
- Direct python/pip usage: PROHIBITED without uv wrapper

### Version Control Standards
- Feature branches MUST follow naming convention: `[###-feature-name]`
- Commits MUST be atomic and descriptive with conventional commit format
- Pull requests MUST include tests and documentation updates
- Main branch MUST always remain deployable
- Semantic versioning MUST be followed for all releases
- Temporary files MUST NOT be committed (enforce via .gitignore and hooks)
- Commit messages MUST explain why, not just what changed

### Testing Standards
- Unit tests MUST cover all business logic with pytest framework
- Integration tests MUST cover component interactions
- E2E tests MUST cover critical user journeys
- Test coverage MUST be maintained above 80%
- Performance tests MUST validate response times and resource usage
- UX tests MUST validate user interaction flows and accessibility
- All tests MUST be executed via `uv run pytest`
- Test files MUST follow proper naming convention and location (tests/ dir)
- Temporary test files MUST be deleted after validation

### User Experience Standards
- All user interfaces MUST follow established design system
- Accessibility standards (WCAG 2.1 AA) MUST be met
- Response times MUST be under 200ms for user interactions
- Error handling MUST be user-friendly and informative
- User feedback MUST be collected and incorporated into improvements

## Governance

This constitution supersedes all other development practices and guidelines.
All team members MUST adhere to these principles without exception.

**Amendment Process**:
1. Proposed changes MUST be documented with rationale and impact analysis
2. Changes MUST be reviewed and approved by project leads
3. Migration plan MUST be provided for breaking changes
4. Team MUST be notified of changes at least 1 week before implementation
5. All changes MUST be reflected in training materials and documentation

**Compliance Requirements**:
- All pull requests MUST verify constitutional compliance
- Code reviews MUST check adherence to principles, especially UV usage and code
  hygiene
- Performance violations MUST be explicitly justified with metrics
- UX violations MUST be validated through user testing
- Deviations MUST be documented and approved
- UV tooling violations MUST be rejected in code review
- Temporary file violations MUST be rejected in code review
- Cleanup tasks MUST be completed before PR approval

**Quality Assurance**:
- Automated quality gates MUST be enforced in CI/CD pipeline using UV
- Performance metrics MUST be continuously monitored
- User experience MUST be regularly evaluated through testing
- Code quality MUST be measured and tracked over time
- UV command compliance MUST be verified in automated checks
- Repository cleanliness MUST be verified via automated scans
- Pre-commit hooks MUST prevent temporary file commits

**Versioning Policy**:
- MAJOR: Backward incompatible changes or principle removals
- MINOR: New principles or expanded guidance
- PATCH: Clarifications, wording fixes, non-semantic changes

**Version**: 1.3.0 | **Ratified**: 2025-10-15 | **Last Amended**: 2025-10-16
