<!--
Sync Impact Report:
Version change: 1.0.1 → 1.1.0 (minor - enhanced development standards and tooling)
Modified principles: Code Quality Standards (added uv package management), Development Standards (enhanced user experience consistency focus)
Added sections: Project Management Standards, Enhanced User Experience Consistency
Removed sections: N/A
Templates requiring updates: ✅ All templates reviewed and aligned
Follow-up TODOs: N/A
-->

# GovCar Upgrade UniApp Assembly Constitution

## Core Principles

### I. Modular Architecture
Every component MUST be developed as a standalone, self-contained module with clear interfaces. Modules MUST be independently testable, documented, and have single responsibility. No organizational-only modules allowed.

### II. Cross-Platform Compatibility
All code MUST maintain compatibility across Web, iOS, and Android platforms. Platform-specific implementations MUST be abstracted through unified interfaces. Code sharing MUST be maximized while respecting platform constraints.

### III. Test-First Development (NON-NEGOTIABLE)
TDD is mandatory: Tests MUST be written → User-approved → Tests MUST fail → Then implementation follows. Red-Green-Refactor cycle MUST be strictly enforced. Unit tests, integration tests, and end-to-end tests required.

### IV. Component Reusability
All UI components and business logic modules MUST be designed for reuse across different screens and features. Components MUST accept configurable props and maintain consistent behavior patterns. Shared component library MUST be maintained.

### V. Performance Optimization (ENHANCED)
All code MUST meet performance standards: Initial app load < 3 seconds, Page transitions < 500ms, Memory usage optimized for mobile devices. Lazy loading and code splitting MUST be implemented where appropriate. Performance metrics MUST be continuously monitored and optimized.

### VI. User Experience Consistency (NEW)
All user interfaces MUST maintain consistent interaction patterns, visual design, and behavior across all platforms. User experience MUST be intuitive, responsive, and accessible. UX consistency MUST be validated through user testing and automated checks.

## Development Standards

### Code Quality Standards (ENHANCED)
- All code MUST follow consistent formatting and linting rules using ruff and black
- Python type hints MUST be used for type safety with mypy validation
- Code review is required for all changes with focus on readability and maintainability
- Documentation MUST be updated with functional changes
- Code quality metrics MUST be measured and maintained above 90% quality score

### Project Management Standards (NEW)
- UV MUST be used as the primary package management tool
- pyproject.toml MUST be used for all project configuration and dependency management
- Virtual environments MUST be managed through uv for consistency
- Dependencies MUST be explicitly declared with version constraints
- Development dependencies MUST be separated from production dependencies

### Version Control Standards
- Feature branches MUST follow naming convention: `[###-feature-name]`
- Commits MUST be atomic and descriptive with conventional commit format
- Pull requests MUST include tests and documentation updates
- Main branch MUST always remain deployable
- Semantic versioning MUST be followed for all releases

### Testing Standards (ENHANCED)
- Unit tests MUST cover all business logic with pytest framework
- Integration tests MUST cover component interactions
- E2E tests MUST cover critical user journeys
- Test coverage MUST be maintained above 80%
- Performance tests MUST validate response times and resource usage
- UX tests MUST validate user interaction flows and accessibility

### User Experience Standards (NEW)
- All user interfaces MUST follow established design system
- Accessibility standards (WCAG 2.1 AA) MUST be met
- Response times MUST be under 200ms for user interactions
- Error handling MUST be user-friendly and informative
- User feedback MUST be collected and incorporated into improvements

## Governance

This constitution supersedes all other development practices and guidelines. All team members MUST adhere to these principles without exception.

**Amendment Process**:
1. Proposed changes MUST be documented with rationale and impact analysis
2. Changes MUST be reviewed and approved by project leads
3. Migration plan MUST be provided for breaking changes
4. Team MUST be notified of changes at least 1 week before implementation
5. All changes MUST be reflected in training materials and documentation

**Compliance Requirements**:
- All pull requests MUST verify constitutional compliance
- Code reviews MUST check adherence to principles
- Performance violations MUST be explicitly justified with metrics
- UX violations MUST be validated through user testing
- Deviations MUST be documented and approved

**Quality Assurance**:
- Automated quality gates MUST be enforced in CI/CD pipeline
- Performance metrics MUST be continuously monitored
- User experience MUST be regularly evaluated through testing
- Code quality MUST be measured and tracked over time

**Versioning Policy**:
- MAJOR: Backward incompatible changes or principle removals
- MINOR: New principles or expanded guidance
- PATCH: Clarifications, wording fixes, non-semantic changes

**Version**: 1.1.0 | **Ratified**: 2025-10-15 | **Last Amended**: 2025-10-15