#!/usr/bin/env python3
"""Agent registry + plan ledger (wiki) + Agents Dashboard metrics.

Usage:
  python3 Board/_system/tools/board_agent.py register --id cursor-dragonstone \\
    --name "Cursor — Dragonstone" --model "cursor-grok" --owner "Devaang Mandalia"
  python3 Board/_system/tools/board_agent.py plan-open --agent cursor-dragonstone \\
    --title "Ship agent dashboard" --project "Dragonstone Ops" --initiative-id in_eks
  python3 Board/_system/tools/board_agent.py plan-close 2026-08-01-ship-agent-dashboard \\
    --lines-added 400 --lines-removed 40 --prs 0
  python3 Board/_system/tools/board_agent.py dashboard
  python3 Board/_system/tools/board_agent.py list
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from solaris.agent_gate import (
    GatePaths,
    bind_session,
    clear_session,
    compute_status,
    load_gate_config,
    load_session,
)
from solaris.core import (
    TODAY,
    find_agent_plan,
    infer_lane,
    iter_agent_plan_files,
    iter_task_files,
    load_config,
    parse_frontmatter,
    render_frontmatter,
    slugify,
    unquote,
)

def _templates_dir() -> Path:
    here = Path(__file__).resolve().parent
    candidates = [here / "data" / "templates", here.parent / "templates"]
    try:
        from importlib import resources
        candidates.insert(0, Path(str(resources.files("solaris"))) / "data" / "templates")
    except Exception:
        pass
    for c in candidates:
        if Path(c).is_dir() and (Path(c) / "agent.md").is_file():
            return Path(c)
    raise FileNotFoundError("agent templates not found")


DASH_START = "<!-- agent-metrics:start -->"
DASH_END = "<!-- agent-metrics:end -->"


def _agent_path(cfg, agent_id: str) -> Path:
    return cfg.agents_dir / f"{agent_id}.md"


def _require_agent(cfg, agent_id: str) -> Path:
    path = _agent_path(cfg, agent_id)
    if not path.is_file():
        raise SystemExit(
            f"Agent not registered: {agent_id}\n"
            f"Run: board_agent.py register --id {agent_id} --name ... --model ... --owner ..."
        )
    return path


def _read_md(path: Path) -> tuple[dict[str, str], list[str], str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def _write_md(path: Path, fm: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not body.startswith("\n"):
        body = "\n" + body
    path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")


def _template(name: str) -> str:
    return (_templates_dir() / name).read_text(encoding="utf-8")


def _fill(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, val in mapping.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def _int(fm: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(unquote(fm.get(key, str(default))) or default)
    except ValueError:
        return default


def _wiki_link(rel: str) -> str:
    rel = rel.replace("\\", "/")
    if rel.endswith(".md"):
        rel = rel[:-3]
    return rel


def cmd_register(args: argparse.Namespace) -> int:
    cfg = load_config()
    agent_id = args.id.strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", agent_id):
        raise SystemExit("agent id must be lowercase slug: [a-z0-9][a-z0-9_-]{1,63}")

    path = _agent_path(cfg, agent_id)
    if path.exists() and not args.force:
        raise SystemExit(f"Already registered: {path.relative_to(cfg.root)} (use --force)")

    mapping = {
        "agent_id": agent_id,
        "title": args.name,
        "model": args.model,
        "owner": args.owner,
        "created": TODAY,
        "updated": TODAY,
        "notes": args.notes or "_No notes yet._",
    }
    text = _fill(_template("agent.md"), mapping)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(path.relative_to(cfg.root))
    _regenerate_dashboard(cfg)
    return 0


def _default_plan_path(cfg, project: str, initiative_id: str, plan_id: str) -> str:
    """Plans live under the project/initiative wiki — never Board/Agents/Plans."""
    if not cfg.wiki_dir:
        if initiative_id:
            return str(Path("Plans") / project / initiative_id / f"{plan_id}.md")
        return str(Path("Plans") / project / f"{plan_id}.md")
    try:
        wiki_rel = cfg.wiki_dir.relative_to(cfg.root).as_posix()
    except ValueError:
        wiki_rel = "Wiki"
    if initiative_id:
        return f"{wiki_rel}/{project}/Initiatives/{initiative_id}/Plans/{plan_id}.md"
    return f"{wiki_rel}/{project}/Plans/{plan_id}.md"


def cmd_plan_open(args: argparse.Namespace) -> int:
    cfg = load_config()
    agent_id = args.agent.strip()
    _require_agent(cfg, agent_id)

    existing = {p.stem for p in iter_agent_plan_files(cfg)}
    plan_id = args.plan_id or slugify(f"{TODAY}-{args.title}", existing)
    if find_agent_plan(cfg, plan_id) and not args.force:
        raise SystemExit(f"Plan already exists: {plan_id}")

    wiki_path = args.wiki_path or _default_plan_path(
        cfg, args.project, args.initiative_id or "", plan_id
    )
    plan_abs = cfg.root / wiki_path
    if plan_abs.exists() and not args.force:
        raise SystemExit(f"Plan already exists: {wiki_path}")

    mapping = {
        "plan_id": plan_id,
        "agent_id": agent_id,
        "title": args.title,
        "project": args.project,
        "initiative_id": args.initiative_id or "",
        "created": TODAY,
        "task_list": "_No tasks yet — create with `board_task.py create --agent ... --plan-id ...`._",
        "summary": args.summary or "",
        "context": args.context or "",
    }
    plan_abs.parent.mkdir(parents=True, exist_ok=True)
    plan_abs.write_text(_fill(_template("wiki-agent-plan.md"), mapping), encoding="utf-8")

    agent_path = _agent_path(cfg, agent_id)
    fm, tags, body = _read_md(agent_path)
    fm["updated"] = TODAY
    fm["_tags_list"] = tags
    link = _wiki_link(wiki_path)
    if plan_id not in body:
        body = body.rstrip() + f"\n- [[{link}|{plan_id}]] (open)\n"
    _write_md(agent_path, fm, body)

    print(wiki_path)
    try:
        paths = GatePaths.from_root(cfg.root)
        bind_session(paths, agent_id=agent_id, plan_id=plan_id, plan_path=wiki_path)
        print(f"session bound -> {plan_id}", file=sys.stderr)
    except Exception as exc:
        print(f"warning: session bind failed: {exc}", file=sys.stderr)
    _regenerate_dashboard(cfg)
    return 0


def _tasks_for_plan(cfg, plan_id: str) -> list[tuple[Path, dict[str, str]]]:
    rows = []
    for path in iter_task_files(cfg):
        text = path.read_text(encoding="utf-8")
        fm, _tags, _ = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "task":
            continue
        if unquote(fm.get("plan_id", "")) != plan_id:
            continue
        rows.append((path, fm))
    return rows


def cmd_plan_close(args: argparse.Namespace) -> int:
    cfg = load_config()
    plan_id = args.plan_id.strip()
    plan_path = find_agent_plan(cfg, plan_id)
    if not plan_path or not plan_path.is_file():
        raise SystemExit(f"Plan not found: {plan_id}")

    fm, tags, body = _read_md(plan_path)
    status = unquote(fm.get("status", "open"))
    if status == "completed" and not args.force:
        raise SystemExit(f"Plan already completed: {plan_id} (use --force)")

    agent_id = unquote(fm.get("agent_id", ""))
    agent_path = _require_agent(cfg, agent_id)

    tasks = _tasks_for_plan(cfg, plan_id)
    tasks_total = len(tasks)
    tasks_done = sum(1 for _p, tfm in tasks if infer_lane(tfm) == "done")

    lines_added = args.lines_added
    lines_removed = args.lines_removed
    prs = args.prs

    prev_added = _int(fm, "lines_added")
    prev_removed = _int(fm, "lines_removed")
    prev_prs = _int(fm, "prs")
    prev_done = _int(fm, "tasks_done")
    was_completed = status == "completed"

    fm["type"] = "agent_plan"
    fm["status"] = "completed"
    fm["completed"] = TODAY
    fm["updated"] = TODAY
    fm["lines_added"] = str(lines_added)
    fm["lines_removed"] = str(lines_removed)
    fm["prs"] = str(prs)
    fm["tasks_total"] = str(tasks_total)
    fm["tasks_done"] = str(tasks_done)
    fm["_tags_list"] = tags

    checklist = "\n".join(
        f"- [{'x' if infer_lane(tfm) == 'done' else ' '}] "
        f"{unquote(tfm.get('title', p.stem))} (`{p.relative_to(cfg.root)}`)"
        for p, tfm in tasks
    ) or "_No linked tasks._"
    if "## Tasks" in body:
        body = re.sub(
            r"(## Tasks\n)(.*?)(?=\n## |\Z)",
            r"\1\n" + checklist + "\n\n",
            body,
            count=1,
            flags=re.S,
        )
    elif "## Task map" in body:
        body = re.sub(
            r"(## Task map\n)(.*?)(?=\n## |\Z)",
            r"\1\n" + checklist + "\n\n",
            body,
            count=1,
            flags=re.S,
        )
    body = body.rstrip() + f"\n\n- {TODAY}: plan closed (+{lines_added}/-{lines_removed} loc, {prs} prs)\n"
    _write_md(plan_path, fm, body)

    afm, atags, abody = _read_md(agent_path)
    if was_completed:
        afm["tasks_completed"] = str(max(0, _int(afm, "tasks_completed") - prev_done + tasks_done))
        afm["lines_added"] = str(max(0, _int(afm, "lines_added") - prev_added + lines_added))
        afm["lines_removed"] = str(max(0, _int(afm, "lines_removed") - prev_removed + lines_removed))
        afm["prs"] = str(max(0, _int(afm, "prs") - prev_prs + prs))
    else:
        afm["plans_completed"] = str(_int(afm, "plans_completed") + 1)
        afm["tasks_completed"] = str(_int(afm, "tasks_completed") + tasks_done)
        afm["lines_added"] = str(_int(afm, "lines_added") + lines_added)
        afm["lines_removed"] = str(_int(afm, "lines_removed") + lines_removed)
        afm["prs"] = str(_int(afm, "prs") + prs)
    afm["updated"] = TODAY
    afm["_tags_list"] = atags
    abody = abody.replace(f"|{plan_id}]] (open)", f"|{plan_id}]] (completed)")
    _write_md(agent_path, afm, abody)

    try:
        paths = GatePaths.from_root(cfg.root)
        sess = load_session(paths)
        if not sess.get("plan_id") or sess.get("plan_id") == plan_id:
            clear_session(paths)
    except Exception as exc:
        print(f"warning: session clear failed: {exc}", file=sys.stderr)

    _regenerate_dashboard(cfg)
    print(
        f"{plan_path.relative_to(cfg.root)} completed  "
        f"tasks={tasks_done}/{tasks_total}  +{lines_added}/-{lines_removed}  prs={prs}"
    )
    return 0


def _iter_agents(cfg) -> list[Path]:
    if not cfg.agents_dir.is_dir():
        return []
    skip = {
        "Dashboard.md",
        "Agents Dashboard.md",
        "README.md",
        "AGENT-CONTEXT.md",
        "Agent-Context.md",
        "INSTANCE.md",
    }
    return sorted(
        p for p in cfg.agents_dir.glob("*.md") if p.is_file() and p.name not in skip
    )


def _metric_box(value: str, label: str, *, wide: bool = False) -> str:
    cls = "agent-metric agent-metric-wide" if wide else "agent-metric"
    return (
        f'<div class="{cls}">'
        f'<div class="agent-metric-value">{html.escape(value)}</div>'
        f'<div class="agent-metric-label">{html.escape(label)}</div>'
        f"</div>"
    )


def _agent_roster_html(cfg) -> str:
    cards: list[str] = []
    for path in _iter_agents(cfg):
        fm, _t, _b = _read_md(path)
        if unquote(fm.get("type", "")) != "agent":
            continue
        aid = unquote(fm.get("agent_id", path.stem))
        title = unquote(fm.get("title", aid))
        model = unquote(fm.get("model", ""))
        owner = unquote(fm.get("owner", ""))
        meta_bits = [b for b in (model, owner) if b]
        meta = " · ".join(meta_bits)
        square = "".join(
            [
                _metric_box(str(_int(fm, "plans_completed")), "Plans"),
                _metric_box(str(_int(fm, "tasks_completed")), "Tasks"),
                _metric_box(str(_int(fm, "prs")), "PRs"),
            ]
        )
        loc = "".join(
            [
                _metric_box(f"+{_int(fm, 'lines_added')}", "LOC added", wide=True),
                _metric_box(f"−{_int(fm, 'lines_removed')}", "LOC removed", wide=True),
            ]
        )
        square_fmt = square.replace(
            '</div><div class="agent-metric',
            '</div>\n      <div class="agent-metric',
        )
        loc_fmt = loc.replace(
            '</div><div class="agent-metric',
            '</div>\n        <div class="agent-metric',
        )
        metrics_fmt = (
            f"{square_fmt}\n"
            f'      <div class="agent-metrics-loc">\n'
            f"        {loc_fmt}\n"
            f"      </div>"
        )
        cards.append(
            f'<div class="agent-card" data-agent-id="{html.escape(aid)}">\n'
            f'  <div class="agent-card-name">'
            f'<a class="internal-link" href="{html.escape(cfg.board_dir)}/Agents/{html.escape(aid)}" '
            f'data-href="{html.escape(cfg.board_dir)}/Agents/{html.escape(aid)}">{html.escape(title)}</a>'
            f"</div>\n"
            f'  <div class="agent-card-meta">{html.escape(meta)}</div>\n'
            f'  <div class="agent-metrics">\n'
            f"      {metrics_fmt}\n"
            f"  </div>\n"
            f"</div>"
        )
    if not cards:
        cards.append(
            '<div class="agent-card agent-card-empty">\n'
            '  <div class="agent-card-name">No agents registered</div>\n'
            '  <div class="agent-card-meta">Run board_agent.py register</div>\n'
            "</div>"
        )
    return '<div class="agent-roster">\n' + "\n".join(cards) + "\n</div>"


def _open_plans_section(cfg) -> str:
    lines = []
    for path in iter_agent_plan_files(cfg):
        fm, _t, _b = _read_md(path)
        if unquote(fm.get("status", "")) != "open":
            continue
        # Prefer wiki plans over legacy Board/Agents/Plans duplicates
        try:
            rel = path.relative_to(cfg.root).as_posix()
        except ValueError:
            rel = str(path)
        if "/Agents/Plans/" in rel:
            continue
        pid = unquote(fm.get("plan_id", path.stem))
        title = unquote(fm.get("title", pid))
        agent = unquote(fm.get("agent_id", ""))
        project = unquote(fm.get("project", ""))
        link = _wiki_link(rel)
        lines.append(f"- [[{link}|{title}]] — `{agent}` · {project}")
    return "\n".join(lines) if lines else "_No open plans._"


def _dashboard_body(cfg) -> str:
    bd = cfg.board_dir
    return f"""---
type: meta
title: Agents Dashboard
audience: humans+agents
cssclasses:
  - agent-dashboard
updated: {TODAY}
---

# Agents Dashboard

{DASH_START}
{_agent_roster_html(cfg)}
{DASH_END}

> [!warning] Hard rules
> 1. **Register** (or confirm your profile) before touching any code.
> 2. **Open a plan** after user approval — write it under the **project / initiative wiki**, file tasks with `agent_id` + `plan_id`.
> 3. Execute on [[{bd}/Home.base#Agent work|Home.base → Agent work]]; mark tasks **done** as you finish.
> 4. **Close the plan** with self-reported LOC/PR metrics.

### Session start

```bash
export BOARD_ROOT=<repo-root>
solaris agent list
solaris agent list --plans --open
solaris agent gate-status
```

CLI: `solaris agent …`

## Open plans

{_open_plans_section(cfg)}

## Agent work

Live lanes for `source: agent` cards — same view as [[{bd}/Home.base#Agent work|Home.base → Agent work]].

![[{bd}/Home.base#Agent work]]

## Boards

- [[{bd}/Home.base#By agent|By agent]] — open agent work grouped by `agent_id`
- [[{bd}/Home.base#Flow|Flow]] — full execution ledger
- [[{bd}/Dashboard|Command Center]]
- Agent profiles: `{bd}/Agents/<agent_id>.md`

## Register

```bash
solaris agent register \\
  --id my-agent --name "My Agent" --model "model-id" --owner "Your Name"
```
"""


def _regenerate_dashboard(cfg) -> Path:
    path = cfg.agent_dashboard
    path.parent.mkdir(parents=True, exist_ok=True)
    roster = _agent_roster_html(cfg)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if DASH_START in text and DASH_END in text:
            text = re.sub(
                re.escape(DASH_START) + r".*?" + re.escape(DASH_END),
                DASH_START + "\n" + roster + "\n" + DASH_END,
                text,
                count=1,
                flags=re.S,
            )
            if "## Open plans" in text:
                open_sec = _open_plans_section(cfg)
                text = re.sub(
                    r"(## Open plans\n\n)(.*?)(?=\n## |\Z)",
                    r"\1" + open_sec + "\n\n",
                    text,
                    count=1,
                    flags=re.S,
                )
            text = re.sub(r"^updated:.*$", f"updated: {TODAY}", text, count=1, flags=re.M)
            path.write_text(text, encoding="utf-8")
            return path
    path.write_text(_dashboard_body(cfg), encoding="utf-8")
    return path


def cmd_dashboard(_args: argparse.Namespace) -> int:
    cfg = load_config()
    path = _regenerate_dashboard(cfg)
    print(path.relative_to(cfg.root))
    return 0


def cmd_gate_status(_args: argparse.Namespace) -> int:
    cfg = load_config()
    paths = GatePaths.from_root(cfg.root)
    gcfg = load_gate_config(paths)
    status = compute_status(paths, gcfg)
    print(f"agent_id:      {status.agent_id}")
    print(f"rules_read:    {status.rules_read}")
    print(f"registered:    {status.registered}")
    print(f"open_plans:    {', '.join(p['plan_id'] for p in status.open_plans) or '(none)'}")
    print(f"session_plan:  {status.session_plan_id or '(none)'}")
    print(f"session_bound: {status.session_bound}")
    print(f"tasks:         {status.task_count}")
    print(f"dry_run:       {status.dry_run}")
    print(f"ready:         {status.ready}")
    if not status.ready:
        for m in status.missing:
            print(f"missing: {m}")
        return 1
    return 0


def cmd_session_bind(args: argparse.Namespace) -> int:
    cfg = load_config()
    paths = GatePaths.from_root(cfg.root)
    gcfg = load_gate_config(paths)
    agent_id = args.agent or gcfg.agent_id
    plan_id = args.plan_id.strip()
    plan_path = find_agent_plan(cfg, plan_id)
    if not plan_path:
        raise SystemExit(f"Plan not found / not open: {plan_id}")
    fm, _t, _b = _read_md(plan_path)
    if unquote(fm.get("status", "")) != "open":
        raise SystemExit(f"Plan is not open: {plan_id} (status={unquote(fm.get('status', ''))})")
    if unquote(fm.get("agent_id", "")) != agent_id:
        raise SystemExit(
            f"Plan agent_id {unquote(fm.get('agent_id', ''))!r} != {agent_id!r}"
        )
    rel = str(plan_path.relative_to(cfg.root))
    bind_session(paths, agent_id=agent_id, plan_id=plan_id, plan_path=rel)
    print(f"bound {agent_id} -> {plan_id} ({rel})")
    return 0


def cmd_session_unbind(_args: argparse.Namespace) -> int:
    cfg = load_config()
    paths = GatePaths.from_root(cfg.root)
    clear_session(paths)
    print("session unbound")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cfg = load_config()
    if args.plans:
        n = 0
        for path in iter_agent_plan_files(cfg):
            fm, _t, _b = _read_md(path)
            status = unquote(fm.get("status", ""))
            if args.open and status != "open":
                continue
            try:
                rel = path.relative_to(cfg.root)
            except ValueError:
                rel = path
            if "/Agents/Plans/" in str(rel):
                continue
            print(
                f"{status:10} {unquote(fm.get('agent_id', '')):20} "
                f"{unquote(fm.get('plan_id', path.stem))}  "
                f"{unquote(fm.get('title', ''))}  ({rel})"
            )
            n += 1
        print(f"# {n} plans", file=sys.stderr)
        return 0

    n = 0
    for path in _iter_agents(cfg):
        fm, _t, _b = _read_md(path)
        if unquote(fm.get("type", "")) != "agent":
            continue
        print(
            f"{unquote(fm.get('status', '')):8} {unquote(fm.get('agent_id', path.stem)):24} "
            f"plans={_int(fm, 'plans_completed')} tasks={_int(fm, 'tasks_completed')} "
            f"+{_int(fm, 'lines_added')}/-{_int(fm, 'lines_removed')} prs={_int(fm, 'prs')}  "
            f"{unquote(fm.get('title', ''))}"
        )
        n += 1
    print(f"# {n} agents", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Board agent registry and plan ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="Register a persistent agent profile")
    r.add_argument("--id", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--owner", required=True)
    r.add_argument("--notes", default="")
    r.add_argument("--force", action="store_true")
    r.set_defaults(func=cmd_register)

    po = sub.add_parser("plan-open", help="Open a plan under the project/initiative wiki")
    po.add_argument("--agent", required=True)
    po.add_argument("--title", required=True)
    po.add_argument("--project", required=True)
    po.add_argument("--initiative-id", default="")
    po.add_argument("--wiki-path", default="", help="Override wiki plan path")
    po.add_argument("--plan-id", default="")
    po.add_argument("--summary", default="")
    po.add_argument("--context", default="")
    po.add_argument("--force", action="store_true")
    po.set_defaults(func=cmd_plan_open)

    pc = sub.add_parser("plan-close", help="Close a plan with self-reported metrics")
    pc.add_argument("plan_id")
    pc.add_argument("--lines-added", type=int, required=True)
    pc.add_argument("--lines-removed", type=int, required=True)
    pc.add_argument("--prs", type=int, required=True)
    pc.add_argument("--force", action="store_true")
    pc.set_defaults(func=cmd_plan_close)

    d = sub.add_parser("dashboard", help="Regenerate Agents Dashboard roster")
    d.set_defaults(func=cmd_dashboard)

    g = sub.add_parser("gate-status", help="Check agent-board-gate readiness")
    g.set_defaults(func=cmd_gate_status)

    sb = sub.add_parser("session-bind", help="Bind session to an open plan_id")
    sb.add_argument("--plan-id", required=True, dest="plan_id")
    sb.add_argument("--agent", default="")
    sb.set_defaults(func=cmd_session_bind)

    su = sub.add_parser("session-unbind", help="Clear session plan bind")
    su.set_defaults(func=cmd_session_unbind)

    l = sub.add_parser("list", help="List agents or plans")
    l.add_argument("--plans", action="store_true")
    l.add_argument("--open", action="store_true", help="With --plans, only open")
    l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
