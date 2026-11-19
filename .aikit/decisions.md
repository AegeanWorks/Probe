# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: probe: the battery is fs+shell+git+imports by default; timing+web are opt-in
- **Date**: 2026-11-19
- **Status**: Accepted
- **Context**: A new project testing this agent's capabilities end to end. The default run must be quick and offline-safe; the deep lane gives on-demand timing and web evidence against the profile page.
- **Decision**: Default: run fs, shell, git, imports. --deep adds timing and web; --url overrides the web target. Reports land in the gitignored reports/.
- **Consequences**: The default gate stays fast and offline; the deep lane is manual evidence; every check records its observation, so a report claims a pass only when the observation supports it.
