"""Portable Board core — config, paths, frontmatter helpers.

No instance-specific project names. Read <board_dir>/config.yml via BOARD_ROOT.
board_dir defaults to the host repo basename on init; legacy `Board/` still works.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

TRIAGE_LANE = "triage"
BACKLOG_LANE = "backlog"
ARCHIVED_LANE = "archived"
SPRINT_LANES = frozenset({"doing this week", "in progress now", "blocked", "done"})
ALL_LANES = frozenset({TRIAGE_LANE, BACKLOG_LANE, ARCHIVED_LANE, *SPRINT_LANES})
LEGACY_BACKLOG = frozenset({"P0", "P1", "P2", "P3"})
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

TODAY = date.today().isoformat()


@dataclass
class BoardConfig:
    root: Path
    board_dir: str
    tasks_dir: Path
    projects_dir: Path
    sprint_file: Path
    wiki_dir: Path | None
    agents_dir: Path
    agent_dashboard: Path
    schema_version: int
    projects: list[dict[str, str]]
    folder_aliases: dict[str, str]
    features: dict[str, Any]
    rollover: dict[str, Any]
    intake: dict[str, Any]
    rollup: dict[str, Any]
    folder_to_project: dict[str, str] = field(default_factory=dict)
    project_filter_tag: dict[str, str] = field(default_factory=dict)
    project_domain: dict[str, str] = field(default_factory=dict)
    legacy_filter_tags: frozenset[str] = field(default_factory=frozenset)

    @property
    def board_path(self) -> Path:
        return self.root / self.board_dir

    @property
    def system_dir(self) -> Path:
        return self.board_path / "_system"

    @property
    def triage_enabled(self) -> bool:
        return self.features.get("triage", True) is True

    @property
    def sprint_rollover_enabled(self) -> bool:
        return self.features.get("sprint_rollover", False) is True

    @property
    def initiative_rollup_enabled(self) -> bool:
        return self.features.get("initiative_rollup", False) is True

    @property
    def agent_registry_enabled(self) -> bool:
        return self.features.get("agent_registry", False) is True


def _looks_like_board_config(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return any(
        marker in text
        for marker in ("tasks_dir:", "schema_version:", "\nprojects:", "board_dir:")
    )


def find_config_path(root: Path) -> Path | None:
    """Locate instance config under root (board.config.yml or <board_dir>/config.yml)."""
    root = root.resolve()
    alt = root / "board.config.yml"
    if alt.is_file():
        return alt

    basename_cfg = root / root.name / "config.yml"
    if basename_cfg.is_file() and _looks_like_board_config(basename_cfg):
        return basename_cfg

    legacy = root / "Board" / "config.yml"
    if legacy.is_file():
        return legacy

    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in ("node_modules", ".git", ".venv", "venv", "__pycache__"):
            continue
        cand = child / "config.yml"
        if cand.is_file() and _looks_like_board_config(cand):
            return cand
    return None


def discover_root(start: Path | None = None) -> Path:
    env = os.environ.get("BOARD_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if find_config_path(p) is not None:
            return p
    raise FileNotFoundError(
        "Board root not found. Set BOARD_ROOT or run from a tree with "
        "<board_dir>/config.yml (or Board/config.yml / board.config.yml)"
    )


def resolve_board_dir(root: Path, raw: dict[str, Any] | None = None, cfg_path: Path | None = None) -> str:
    """Resolve board folder name relative to BOARD_ROOT."""
    if raw and raw.get("board_dir"):
        return str(raw["board_dir"]).strip().strip("/") or "Board"
    if cfg_path is not None:
        cfg_path = cfg_path.resolve()
        root = root.resolve()
        if cfg_path.name == "config.yml" and cfg_path.parent != root:
            return cfg_path.parent.name
    env_bd = os.environ.get("BOARD_DIR", "").strip()
    if env_bd:
        return env_bd
    if (root / "Board" / "config.yml").is_file():
        return "Board"
    if (root / root.name / "config.yml").is_file():
        return root.name
    return "Board"


def _strip_inline_comment(s: str) -> str:
    in_single = in_double = False
    for i, ch in enumerate(s):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return s[:i].rstrip()
    return s


def _parse_scalar(raw: str) -> Any:
    s = _strip_inline_comment(raw).strip()
    if not s or s == "null" or s == "~":
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if s == "{}":
        return {}
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _parse_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML subset loader (mappings, lists, scalars) — no PyYAML required."""
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("config must be a mapping")
        return data
    except ImportError:
        pass

    lines = text.splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    def cur_container() -> Any:
        return stack[-1][1]

    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = cur_container()

        if line.startswith("- "):
            item_raw = line[2:].strip()
            if not isinstance(container, list):
                raise ValueError(f"list item without list parent: {raw}")
            if ":" in item_raw and not item_raw.startswith("{"):
                key, _, rest = item_raw.partition(":")
                d: dict[str, Any] = {key.strip(): _parse_scalar(rest)}
                container.append(d)
                stack.append((indent, d))
            else:
                container.append(_parse_scalar(item_raw))
            continue

        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not isinstance(container, dict):
            raise ValueError(f"key under non-mapping: {raw}")
        if rest == "":
            # Lookahead: list or mapping?
            j = i
            child: Any = {}
            while j < len(lines) and (not lines[j].strip() or lines[j].lstrip().startswith("#")):
                j += 1
            if j < len(lines):
                nxt = lines[j]
                nindent = len(nxt) - len(nxt.lstrip(" "))
                if nindent > indent and nxt.strip().startswith("- "):
                    child = []
            container[key] = child
            stack.append((indent, child))
        else:
            container[key] = _parse_scalar(rest)

    if not isinstance(root, dict):
        raise ValueError("config must be a mapping")
    return root


def load_config(root: Path | None = None) -> BoardConfig:
    root = (root or discover_root()).resolve()
    cfg_path = find_config_path(root)
    if cfg_path is None:
        raise FileNotFoundError(
            f"No board config under {root} (expected <board_dir>/config.yml or board.config.yml)"
        )
    raw = _parse_yaml(cfg_path.read_text(encoding="utf-8"))
    board_dir = resolve_board_dir(root, raw, cfg_path)

    def pjoin(key: str, default: str) -> Path:
        rel = raw.get(key, default)
        path = Path(rel)
        return path if path.is_absolute() else root / path

    projects = list(raw.get("projects") or [])
    aliases = dict(raw.get("folder_aliases") or {})
    folder_to_project: dict[str, str] = {}
    project_filter_tag: dict[str, str] = {}
    project_domain: dict[str, str] = {}
    for proj in projects:
        folder = str(proj["folder"])
        name = str(proj["name"])
        folder_to_project[folder] = name
        project_filter_tag[name] = str(proj.get("filter_tag", name))
        project_domain[name] = str(proj.get("domain", "general"))
    for alias, name in aliases.items():
        folder_to_project[str(alias)] = str(name)

    wiki_raw = raw.get("wiki_dir")
    wiki_dir: Path | None
    if wiki_raw in (None, "", "null"):
        # Prefer Wiki/ next to board when present
        default_wiki = root / "Wiki"
        wiki_dir = default_wiki if default_wiki.is_dir() else None
    else:
        wp = Path(str(wiki_raw))
        wiki_dir = wp if wp.is_absolute() else root / wp

    legacy_tags = raw.get("legacy_filter_tags") or []
    return BoardConfig(
        root=root,
        board_dir=board_dir,
        tasks_dir=pjoin("tasks_dir", f"{board_dir}/Tasks"),
        projects_dir=pjoin("projects_dir", "Wiki"),
        sprint_file=pjoin("sprint_file", f"{board_dir}/Sprints/index.md"),
        wiki_dir=wiki_dir,
        agents_dir=pjoin("agents_dir", f"{board_dir}/Agents"),
        agent_dashboard=pjoin(
            "agent_dashboard", f"{board_dir}/Agents/Agents Dashboard.md"
        ),
        schema_version=int(raw.get("schema_version") or 2),
        projects=projects,
        folder_aliases=aliases,
        features=dict(raw.get("features") or {}),
        rollover=dict(raw.get("rollover") or {}),
        intake=dict(raw.get("intake") or {}),
        rollup=dict(raw.get("rollup") or {}),
        folder_to_project=folder_to_project,
        project_filter_tag=project_filter_tag,
        project_domain=project_domain,
        legacy_filter_tags=frozenset(str(t) for t in legacy_tags),
    )


def unquote(val: str) -> str:
    return val.strip().strip('"').strip("'")


def yaml_scalar(value: str) -> str:
    if value is None:
        return '""'
    value = str(value)
    if not value:
        return '""'
    if value in ("true", "false", "null") or value.replace(".", "", 1).isdigit():
        return value
    if any(c in value for c in ' :"\'#[]{},\n') or value.startswith("-"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str], str]:
    if not text.startswith("---"):
        return {}, [], text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, [], text
    fm_block, body = parts[1], parts[2]
    fm: dict[str, str] = {}
    tags: list[str] = []
    in_tags = False
    for line in fm_block.splitlines():
        if in_tags:
            m = re.match(r"^\s+-\s*(.+)$", line)
            if m:
                tags.append(unquote(m.group(1)))
                continue
            in_tags = False
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if key == "tags":
                if val == "[]":
                    tags = []
                    fm["tags"] = "[]"
                elif val in ("", "|"):
                    in_tags = True
                    tags = []
                    fm["tags"] = "__list__"
                else:
                    fm["tags"] = val
                    tags = parse_tags(val)
                continue
            fm[key] = val
            continue
        m = re.match(r"^\s+-\s*(.+)$", line)
        if m and fm.get("tags") == "__list__":
            tags.append(unquote(m.group(1)))
    if tags and fm.get("tags") not in (None, "[]") and fm.get("tags") != "__list__":
        pass
    elif tags:
        fm["tags"] = "__list__"
    return fm, tags, body


def parse_tags(raw: str) -> list[str]:
    raw = unquote(raw).strip()
    if not raw or raw == "[]":
        return []
    if raw.startswith("["):
        return [t.strip().strip('"').strip("'") for t in raw.strip("[]").split(",") if t.strip()]
    return [raw]


def render_frontmatter(fm: dict[str, str]) -> str:
    tags_list = fm.pop("_tags_list", None)
    if tags_list is not None:
        fm.pop("tags", None)

    order = [
        "type",
        "title",
        "project",
        "domain",
        "lane",
        "priority",
        "kanban_order",
        "sprint",
        "status",
        "carry",
        "phase",
        "blocked_reason",
        "health",
        "health_updated",
        "progress_done",
        "progress_open",
        "progress_blocked",
        "roadmap_id",
        "initiative_id",
        "parent_initiative",
        "initiative_path",
        "agent_id",
        "plan_id",
        "source",
        "created",
        "updated",
        "due",
        "model",
        "owner",
        "plans_completed",
        "tasks_completed",
        "lines_added",
        "lines_removed",
        "prs",
        "tasks_total",
        "tasks_done",
        "completed",
        "wiki_path",
    ]
    lines: list[str] = []
    seen: set[str] = set()
    for key in order:
        if key in fm:
            lines.append(f"{key}: {fm[key]}")
            seen.add(key)
    for key in sorted(fm):
        if key not in seen:
            lines.append(f"{key}: {fm[key]}")
    if tags_list is not None:
        if tags_list:
            lines.append("tags:")
            lines.extend(f"  - {t}" for t in tags_list)
        else:
            lines.append("tags: []")
    elif "tags" not in fm:
        lines.append("tags: []")
    return "\n".join(lines)


def write_task(path: Path, fm: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not body.startswith("\n"):
        body = "\n" + body if body else "\n"
    path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")


def active_sprint(cfg: BoardConfig) -> str:
    if not cfg.sprint_file.is_file():
        return date.today().strftime("%G-W%V")
    m = re.search(
        r"^active_sprint:\s*(\S+)",
        cfg.sprint_file.read_text(encoding="utf-8"),
        re.M,
    )
    if m:
        return unquote(m.group(1))
    return date.today().strftime("%G-W%V")


def set_active_sprint(cfg: BoardConfig, week: str) -> None:
    """Set active_sprint on Sprints/index.md (regenerates index body)."""
    update_sprints_index(cfg, current_week=week)


# Status-style lane names used by Agent work / legacy kanban columns.
LANE_DISPLAY_ALIASES = {
    "todo": "doing this week",
    "in-progress": "in progress now",
}


def normalize_lane(raw: str) -> str:
    lane = unquote(raw)
    if lane in ALL_LANES:
        return lane
    if lane in LEGACY_BACKLOG:
        return BACKLOG_LANE
    if lane in LANE_DISPLAY_ALIASES:
        return LANE_DISPLAY_ALIASES[lane]
    return lane


def status_for_lane(lane: str) -> str:
    canonical = normalize_lane(lane)
    if canonical == "in progress now" or lane == "in-progress":
        return "in-progress"
    if canonical == "doing this week" or lane == "todo":
        return "todo"
    if canonical == TRIAGE_LANE:
        return "triage"
    return canonical


def apply_lane(fm: dict[str, str], lane: str, sprint_week: str) -> None:
    display = unquote(lane)
    canonical = normalize_lane(display)
    written = display if display in LANE_DISPLAY_ALIASES else canonical
    fm["lane"] = yaml_scalar(written)
    if canonical in (BACKLOG_LANE, ARCHIVED_LANE, TRIAGE_LANE):
        fm["sprint"] = '""'
        fm["status"] = f'"{status_for_lane(written)}"' if canonical == TRIAGE_LANE else '""'
        if canonical == TRIAGE_LANE:
            fm["status"] = '"triage"'
    elif canonical in SPRINT_LANES:
        fm["sprint"] = f'"{sprint_week}"'
        fm["status"] = f'"{status_for_lane(written)}"'
        if canonical in ("doing this week", "in progress now"):
            fm["carry"] = "false"
    fm["updated"] = TODAY


def infer_lane(fm: dict[str, str]) -> str:
    lane = normalize_lane(fm.get("lane", ""))
    if lane in ALL_LANES:
        return lane
    status = unquote(fm.get("status", ""))
    if status == "done" or lane == "done":
        return "done"
    if status == "triage":
        return TRIAGE_LANE
    if status in ("doing this week", "todo"):
        return "doing this week"
    if status in ("in progress now", "in-progress"):
        return "in progress now"
    if status == "blocked":
        return "blocked"
    priority = unquote(fm.get("priority", ""))
    if priority in LEGACY_BACKLOG:
        return BACKLOG_LANE
    return BACKLOG_LANE


def project_from_path(cfg: BoardConfig, path: Path) -> str | None:
    try:
        rel = path.relative_to(cfg.tasks_dir)
    except ValueError:
        return None
    if len(rel.parts) >= 2:
        return cfg.folder_to_project.get(rel.parts[0])
    return None


def folder_for_project(cfg: BoardConfig, project: str) -> str:
    for folder, name in cfg.folder_to_project.items():
        if name == project and folder not in cfg.folder_aliases:
            return folder
    # prefer exact folder match
    for p in cfg.projects:
        if p["name"] == project:
            return p["folder"]
    return project


def iter_task_files(cfg: BoardConfig) -> list[Path]:
    if not cfg.tasks_dir.is_dir():
        return []
    return sorted(
        p
        for p in cfg.tasks_dir.rglob("*.md")
        if "_archive" not in p.parts and p.name != "README.md"
    )


def iter_agent_plan_files(cfg: BoardConfig) -> list[Path]:
    """Plan ledgers live under Wiki/<Project>/…/Plans/ (not Board/Agents)."""
    roots: list[Path] = []
    if cfg.wiki_dir and cfg.wiki_dir.is_dir():
        roots.append(cfg.wiki_dir)
    else:
        # Bare-repo fallback used by plan-open when wiki_dir is unset
        bare = cfg.root / "Plans"
        if bare.is_dir():
            roots.append(bare)
    # Legacy fallback during migration
    legacy = cfg.agents_dir / "Plans"
    if legacy.is_dir():
        roots.append(legacy)
    out: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for path in root.rglob("*.md"):
            if "Plans" not in path.parts:
                continue
            if path in seen:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, _tags, _body = parse_frontmatter(text)
            typ = unquote(fm.get("type", ""))
            if typ in ("agent_plan", "plan") and unquote(fm.get("plan_id", "")):
                out.append(path)
                seen.add(path)
    return sorted(out)


def find_agent_plan(cfg: BoardConfig, plan_id: str) -> Path | None:
    plan_id = plan_id.strip()
    for path in iter_agent_plan_files(cfg):
        fm, _t, _b = parse_frontmatter(path.read_text(encoding="utf-8"))
        if unquote(fm.get("plan_id", "")) == plan_id or path.stem == plan_id:
            return path
    return None



def slugify(title: str, existing: set[str]) -> str:
    base = re.sub(r"[^\w\s-]", "", title.lower(), flags=re.UNICODE)
    base = re.sub(r"\s+", "-", base.strip())[:60].strip("-") or "task"
    slug = base
    n = 2
    while slug in existing:
        slug = f"{base}-{n}"
        n += 1
    existing.add(slug)
    return slug


def iso_week_ordinal(week: str) -> tuple[int, int]:
    """Parse YYYY-Www → (year, week) for gap math."""
    m = re.match(r"^(\d{4})-W(\d{2})$", week.strip())
    if not m:
        raise ValueError(f"Invalid ISO week: {week}")
    return int(m.group(1)), int(m.group(2))


def iso_week_delta(a: str, b: str) -> int:
    """Signed week difference b - a (approximate using ordinal weeks)."""
    ya, wa = iso_week_ordinal(a)
    yb, wb = iso_week_ordinal(b)
    return (yb * 53 + wb) - (ya * 53 + wa)


def monday_of_iso_week(week: str) -> date:
    """Monday (ISO day 1) for YYYY-Www."""
    year, w = iso_week_ordinal(week)
    return date.fromisocalendar(year, w, 1)


def sprint_folder_name(week: str) -> str:
    """Folder name MM-DD-YYYY for the Monday of the ISO week."""
    return monday_of_iso_week(week).strftime("%m-%d-%Y")


def sprints_dir(cfg: BoardConfig) -> Path:
    rel = (cfg.rollover or {}).get("sprints_dir") or f"{cfg.board_dir}/Sprints"
    path = Path(str(rel))
    return path if path.is_absolute() else cfg.root / path


def export_board_markdown(
    cfg: BoardConfig,
    *,
    include_done: bool = True,
    include_archived: bool = False,
    week_label: str | None = None,
    title: str = "Home — week snapshot",
) -> str:
    """Markdown kanban snapshot of all tasks (for week archive)."""
    from collections import defaultdict

    lane_order = [
        "triage",
        "backlog",
        "doing this week",
        "in progress now",
        "blocked",
        "done",
        "archived",
    ]
    by_lane: dict[str, list[str]] = defaultdict(list)
    for path in iter_task_files(cfg):
        text = path.read_text(encoding="utf-8")
        fm, _, _ = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "task":
            continue
        lane = infer_lane(fm)
        if lane == "done" and not include_done:
            continue
        if lane == "archived" and not include_archived:
            continue
        title_t = unquote(fm.get("title", path.stem))
        project = unquote(fm.get("project", ""))
        phase = unquote(fm.get("phase", ""))
        sprint = unquote(fm.get("sprint", ""))
        extra = f" `{phase}`" if phase else ""
        sprint_bit = f" · sprint `{sprint}`" if sprint else ""
        by_lane[lane].append(f"- [{project}] {title_t}{extra}{sprint_bit}")

    week = week_label or active_sprint(cfg)
    try:
        mon = monday_of_iso_week(week)
        sun = date.fromisocalendar(*iso_week_ordinal(week), 7)
        range_s = f"{mon.isoformat()} → {sun.isoformat()}"
    except ValueError:
        range_s = "?"

    lines = [
        f"# {title}",
        "",
        f"- **ISO week:** `{week}`",
        f"- **Range:** {range_s}",
        f"- **Archived:** {TODAY}",
        "",
    ]
    for lane in lane_order:
        if lane not in ALL_LANES:
            continue
        if lane == "done" and not include_done:
            continue
        if lane == "archived" and not include_archived:
            continue
        items = by_lane.get(lane) or []
        lines.append(f"## {lane} ({len(items)})")
        lines.append("")
        if items:
            lines.extend(items)
        else:
            lines.append("_empty_")
        lines.append("")
    return "\n".join(lines)


def ensure_week_folder(
    cfg: BoardConfig,
    week: str,
    *,
    write_home_snapshot: bool = False,
    home_title: str | None = None,
) -> Path:
    """Create Board/Sprints/MM-DD-YYYY/ with plan/goals/retro stubs; optional home.md."""
    folder = sprints_dir(cfg) / sprint_folder_name(week)
    folder.mkdir(parents=True, exist_ok=True)
    mon = monday_of_iso_week(week)
    sun = date.fromisocalendar(*iso_week_ordinal(week), 7)
    stubs = {
        "plan.md": f"""---
type: sprint-doc
sprint: {week}
doc: plan
---

# Weekly planning — {week}

Week of {mon.isoformat()} → {sun.isoformat()}.

## Commitments

-

## Notes

-
""",
        "goals.md": f"""---
type: sprint-doc
sprint: {week}
doc: goals
---

# Weekly goals — {week}

## Goals

-

## Success looks like

-
""",
        "retro.md": f"""---
type: sprint-doc
sprint: {week}
doc: retro
---

# Weekly retrospective — {week}

## Went well

-

## Improve

-

## Carry into next week

-
""",
    }
    for name, body in stubs.items():
        path = folder / name
        if not path.is_file():
            path.write_text(body, encoding="utf-8")
    if write_home_snapshot:
        home = folder / "home.md"
        home.write_text(
            export_board_markdown(
                cfg,
                include_done=True,
                week_label=week,
                title=home_title or f"Home — {week}",
            ),
            encoding="utf-8",
        )
    return folder


def patch_home_base_sprint_filter(home_base: Path, week: str) -> bool:
    """Set Home/Flow Done filter to sprint == \"<week>\". Returns True if patched."""
    if not home_base.is_file():
        return False
    text = home_base.read_text(encoding="utf-8")
    new_clause = f'sprint == "{week}"'
    patched, n = re.subn(r'sprint\s*==\s*"\d{4}-W\d{2}"', new_clause, text)
    if n:
        home_base.write_text(patched, encoding="utf-8")
        return True
    return False


def write_sprint_pointer(cfg: BoardConfig, week: str) -> None:
    """Alias: active sprint lives on Sprints/index.md."""
    update_sprints_index(cfg, current_week=week)


def update_sprints_index(cfg: BoardConfig, *, current_week: str, closed_week: str | None = None) -> None:
    """Write Board/Sprints/index.md — SoT for active_sprint + week index + ritual."""
    sdir = sprints_dir(cfg)
    sdir.mkdir(parents=True, exist_ok=True)
    # Prefer configured sprint_file when it is the index; else sdir/index.md
    index = cfg.sprint_file if cfg.sprint_file.name == "index.md" else (sdir / "index.md")
    weeks: list[str] = []
    for child in sorted(sdir.iterdir(), reverse=True):
        if child.is_dir() and (child / "plan.md").is_file():
            try:
                fm, _, _ = parse_frontmatter((child / "plan.md").read_text(encoding="utf-8"))
                w = unquote(fm.get("sprint", ""))
                if w:
                    weeks.append(w)
                    continue
            except Exception:
                pass
            weeks.append(child.name)
    seen: set[str] = set()
    ordered: list[str] = []
    for w in [current_week, closed_week or "", *weeks]:
        if not w or w in seen:
            continue
        seen.add(w)
        ordered.append(w)

    folder_name = sprint_folder_name(current_week)
    try:
        rel = sdir.relative_to(cfg.root).as_posix()
    except ValueError:
        rel = str(sdir)
    bd = cfg.board_dir

    lines = [
        "---",
        "type: meta",
        "title: Weekly sprints",
        f"active_sprint: {current_week}",
        "---",
        "",
        f"# Weekly sprints — `{current_week}`",
        "",
        f"Home (this week’s kanban): [[{bd}/Home.base#Home|Home]] · [[{bd}/Dashboard|Command Center]]",
        "",
        f"**This week:** [[{folder_name}/plan|Plan]] · [[{folder_name}/goals|Goals]] · "
        f"[[{folder_name}/retro|Retro]] · [[{folder_name}/home|Home snapshot]]",
        "",
        "## Ritual",
        "",
        "- **Sunday night** — week ends (ISO week cutoff).",
        f"- **Monday 00:05** (launchd) — rollover archives last week to `{rel}/MM-DD-YYYY/`, "
        "marks unfinished sprint work `carry: true`, starts a new Home board. "
        "Done cards stay `done` but drop off Home’s Done column (filtered by `sprint`). "
        "See [[Wiki/Dragonstone Ops/Cron/Board-weekly-home-rollover]].",
        "",
        f"Manual: `python3 {bd}/_system/tools/board_sprint_rollover.py --dry-run`",
        "",
        "## Weeks",
        "",
        "| Week | Monday folder | Docs |",
        "|------|---------------|------|",
    ]
    for w in ordered:
        try:
            folder = sprint_folder_name(w)
            label = w
        except ValueError:
            folder = w
            label = w
        lines.append(
            f"| `{label}` | [[{folder}/home|{folder}]] | "
            f"[[{folder}/plan|plan]] · [[{folder}/goals|goals]] · [[{folder}/retro|retro]] |"
        )
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
