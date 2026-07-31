# Contributing

Thanks for improving Solaris.

## Setup

```bash
pip install -e ".[dev]"
pytest
```

## Guidelines

- **Keep the core portable.** No personal vault paths, project names, or capture-stack assumptions in `src/solaris/` or `data/`.
- **Instance ≠ system.** Features that depend on a specific inbox (chat capture, wiki sync) belong in adapters outside this repo — or behind clear optional hooks.
- **Prefer CLI mutations** for task metadata so YAML stays valid.
- **Safety first:** rollover gap guards and source→lane rules are intentional; don’t weaken them without discussion.
- Add or update tests for behavior changes.
- Keep docs concise (`docs/humans.md`, `docs/agents.md`, `docs/safety.md`).

## PR checklist

- [ ] `pytest` passes
- [ ] No instance-specific names in core
- [ ] CHANGELOG updated for user-visible changes
