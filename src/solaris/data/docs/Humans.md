---
type: meta
title: Solaris — Humans
audience: humans
---

# Solaris — Humans

How **you** use the board. Agents: `Board/_system/AGENT-CONTEXT.md`.

**Lanes:** triage → backlog → doing this week → in progress now → blocked → done / archived

## Daily

1. Open the Dashboard / Flow board.
2. Clear **Triage** if anything is waiting.
3. Work from **in progress now** (~1–3 cards).
4. Pull next from **doing this week** when you start something.
5. Ship → **done**. Cancel → **archived**.
6. Stuck → **blocked** + one-line reason.

You do **not** approve every agent ticket. Watch Flow optionally; history lives in git.

## Triage (intake)

Human/inbox captures land here — **not** agent execution tickets.

| Action | Do |
|--------|-----|
| Accept | → **backlog** (or **doing this week**). Set priority. |
| Reject | → **archived**. |
| Later | Leave in triage; clear in weekly review. |

## Capture

| How | Result |
|-----|--------|
| Intake adapter / inbox | **triage** |
| Template / manual | **backlog** (`source: board`) |
| Agent executes a plan | Tickets + lane moves (`source: agent`) |

## Weekly planning

1. Confirm `active_sprint` in `Board/Sprint.md`.
2. Review **Carried over**.
3. Rank **backlog** (top = highest).
4. Pull a realistic set into **doing this week**.
5. Update initiative **health** if needed.

## Weekly review

1. Triage empty or decided.
2. Blocked — still real?
3. Leftovers may `carry` on week flip.
4. Skim **done**; note anything durable in docs/wiki.
5. Archive old done later if noisy — git keeps history.

## Multi-step work

1. Optional initiative hub + roadmap.
2. Or shared `phase:` on tasks.
3. Approve the plan once → agent files tickets and runs.
4. Review outcomes, not every card.

## Priorities & WIP

- P0–P3 are tags, not columns.
- Soft WIP ~3 in **in progress now**.
- `phase: icebox` hides from Flow without archiving.

## Don’t

| Don’t | Do |
|-------|-----|
| Cancel → done | → archived |
| Hand-edit sprint after drag | Drag the lane |
| Clear every agent ticket | Treat board as ledger |

## Obsidian kanban broken (`unknown view type: kanban`)

Restricted mode blocks vendored plugins until you allow community plugins once. See Solaris repo `docs/obsidian-kanban.md`.
