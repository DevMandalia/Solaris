"""Sync task lane → sprint/status; migrate legacy lanes. Config-driven."""

from __future__ import annotations

from pathlib import Path

from solaris.core import (
    ALL_LANES,
    ARCHIVED_LANE,
    BACKLOG_LANE,
    LEGACY_BACKLOG,
    PRIORITY_RANK,
    SPRINT_LANES,
    TRIAGE_LANE,
    BoardConfig,
    active_sprint,
    apply_lane,
    infer_lane,
    iter_task_files,
    load_config,
    normalize_lane,
    parse_frontmatter,
    project_from_path,
    render_frontmatter,
    unquote,
)

# Back-compat names for hermes imports
LEGACY_SPRINT = frozenset({"todo", "in-progress"})
# Populated from config.legacy_filter_tags when available
LEGACY_FILTER_TAGS: frozenset[str] = frozenset()


def _cfg() -> BoardConfig:
    return load_config()


# Lazy module-level aliases used by older hermes code
def _refresh_globals() -> None:
    global VAULT, TASKS_ROOT, SPRINT_NOTE, FOLDER_TO_PROJECT, PROJECT_FILTER_TAG
    global LEGACY_FILTER_TAGS
    cfg = _cfg()
    VAULT = cfg.root
    TASKS_ROOT = cfg.tasks_dir
    SPRINT_NOTE = cfg.sprint_file
    FOLDER_TO_PROJECT = dict(cfg.folder_to_project)
    PROJECT_FILTER_TAG = dict(cfg.project_filter_tag)
    LEGACY_FILTER_TAGS = cfg.legacy_filter_tags


try:
    _refresh_globals()
except Exception:
    VAULT = Path.cwd()
    TASKS_ROOT = VAULT / "Board" / "Tasks"
    SPRINT_NOTE = VAULT / "Board" / "Sprint.md"
    FOLDER_TO_PROJECT = {}
    PROJECT_FILTER_TAG = {}
    LEGACY_FILTER_TAGS = frozenset()


def ensure_epic_filter_tag(cfg: BoardConfig, fm: dict[str, str], tags: list[str]) -> bool:
    project = unquote(fm.get("project", ""))
    epic_tag = cfg.project_filter_tag.get(project)
    if not epic_tag:
        return False
    legacy = cfg.legacy_filter_tags or LEGACY_FILTER_TAGS
    cleaned = [
        t
        for t in tags
        if t not in cfg.project_filter_tag.values() and t not in legacy
    ]
    new_tags = [epic_tag] + cleaned
    if tags == new_tags:
        return False
    fm["_tags_list"] = new_tags
    return True


def backlog_sort_key(fm: dict[str, str]) -> tuple[int, int]:
    lane = infer_lane(fm)
    if lane != BACKLOG_LANE:
        return (999, 999999)
    pr = unquote(fm.get("priority", "P2"))
    rank = PRIORITY_RANK.get(pr, 2)
    order_raw = unquote(fm.get("kanban_order", "9999"))
    try:
        order = int(float(order_raw))
    except ValueError:
        order = 9999
    return (rank, order)


def sync_task_file(cfg: BoardConfig, path: Path, sprint_week: str) -> bool:
    text = path.read_text(encoding="utf-8")
    fm, tags, body = parse_frontmatter(text)
    if unquote(fm.get("type", "")) != "task":
        return False

    changed = False
    proj = project_from_path(cfg, path)
    if proj and unquote(fm.get("project", "")) != proj:
        fm["project"] = f'"{proj}"'
        changed = True

    lane = infer_lane(fm)
    before = {k: unquote(fm.get(k, "")) for k in ("lane", "sprint", "status", "carry")}
    apply_lane(fm, lane, sprint_week)
    after = {k: unquote(fm.get(k, "")) for k in ("lane", "sprint", "status", "carry")}
    if before != after:
        changed = True

    if ensure_epic_filter_tag(cfg, fm, tags):
        changed = True
    if "_tags_list" not in fm:
        fm["_tags_list"] = tags

    if not changed:
        return False

    path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")
    return True


def sync_all(cfg: BoardConfig | None = None) -> int:
    cfg = cfg or _cfg()
    week = active_sprint(cfg)
    n = 0
    for path in iter_task_files(cfg):
        if sync_task_file(cfg, path, week):
            n += 1
    return n


def migrate_lanes(cfg: BoardConfig | None = None) -> int:
    cfg = cfg or _cfg()
    paths = iter_task_files(cfg)
    entries: list[tuple] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        fm, tags, body = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "task":
            continue
        entries.append((path, fm, tags, body))

    backlog_items = [
        (p, fm, t, b)
        for p, fm, t, b in entries
        if infer_lane(fm) == BACKLOG_LANE or unquote(fm.get("lane", "")) in LEGACY_BACKLOG
    ]
    backlog_items.sort(key=lambda x: backlog_sort_key(x[1]))
    for i, (path, fm, tags, body) in enumerate(backlog_items):
        fm["kanban_order"] = str(i)

    week = active_sprint(cfg)
    changed = 0
    for path, fm, tags, body in entries:
        lane = infer_lane(fm)
        apply_lane(fm, lane, week)
        ensure_epic_filter_tag(cfg, fm, tags)
        if "_tags_list" not in fm:
            fm["_tags_list"] = tags
        new_text = f"---\n{render_frontmatter(fm)}\n---{body}"
        if new_text != path.read_text(encoding="utf-8"):
            path.write_text(new_text, encoding="utf-8")
            changed += 1
    return changed


def move_tasks_to_project_folders(cfg: BoardConfig | None = None) -> int:
    cfg = cfg or _cfg()
    moved = 0
    for path in list(cfg.tasks_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, _tags, _ = parse_frontmatter(text)
        project = unquote(fm.get("project", ""))
        folder = next(
            (f for f, t in cfg.folder_to_project.items() if project == t),
            cfg.projects[0]["folder"] if cfg.projects else "Tasks",
        )
        dest_dir = cfg.tasks_dir / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / path.name
        if dest != path:
            path.rename(dest)
            moved += 1
    return moved


__all__ = [
    "ALL_LANES",
    "ARCHIVED_LANE",
    "BACKLOG_LANE",
    "FOLDER_TO_PROJECT",
    "LEGACY_BACKLOG",
    "LEGACY_FILTER_TAGS",
    "LEGACY_SPRINT",
    "PRIORITY_RANK",
    "PROJECT_FILTER_TAG",
    "SPRINT_LANES",
    "TRIAGE_LANE",
    "active_sprint",
    "apply_lane",
    "infer_lane",
    "migrate_lanes",
    "move_tasks_to_project_folders",
    "normalize_lane",
    "parse_frontmatter",
    "sync_all",
    "sync_task_file",
    "unquote",
]
