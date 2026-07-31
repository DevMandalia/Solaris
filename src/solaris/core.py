"""Portable Board core — config, paths, frontmatter helpers.

No instance-specific project names. Read Board/config.yml via BOARD_ROOT.
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
    tasks_dir: Path
    projects_dir: Path
    sprint_file: Path
    wiki_dir: Path | None
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
    def system_dir(self) -> Path:
        return self.root / "Board" / "_system"

    @property
    def triage_enabled(self) -> bool:
        return self.features.get("triage", True) is True

    @property
    def sprint_rollover_enabled(self) -> bool:
        return self.features.get("sprint_rollover", False) is True

    @property
    def initiative_rollup_enabled(self) -> bool:
        return self.features.get("initiative_rollup", False) is True


def discover_root(start: Path | None = None) -> Path:
    env = os.environ.get("BOARD_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "Board" / "config.yml").is_file():
            return p
        if (p / "board.config.yml").is_file():
            return p
    raise FileNotFoundError(
        "Board root not found. Set BOARD_ROOT or run from a tree with Board/config.yml"
    )


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
    cfg_path = root / "Board" / "config.yml"
    if not cfg_path.is_file():
        alt = root / "board.config.yml"
        if alt.is_file():
            cfg_path = alt
        else:
            raise FileNotFoundError(f"No config at {cfg_path}")
    raw = _parse_yaml(cfg_path.read_text(encoding="utf-8"))

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
        wiki_dir = None
    else:
        wp = Path(str(wiki_raw))
        wiki_dir = wp if wp.is_absolute() else root / wp

    legacy_tags = raw.get("legacy_filter_tags") or []
    return BoardConfig(
        root=root,
        tasks_dir=pjoin("tasks_dir", "Board/Tasks"),
        projects_dir=pjoin("projects_dir", "Board/Projects"),
        sprint_file=pjoin("sprint_file", "Board/Sprint.md"),
        wiki_dir=wiki_dir,
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
        "source",
        "created",
        "updated",
        "due",
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
    path = cfg.sprint_file
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if re.search(r"^active_sprint:\s*", text, re.M):
            text = re.sub(
                r"^active_sprint:\s*\S+",
                f"active_sprint: {week}",
                text,
                count=1,
                flags=re.M,
            )
        else:
            text = f"---\nactive_sprint: {week}\n---\n\n" + text
    else:
        text = (
            f"---\nactive_sprint: {week}\n---\n\n"
            f"# Active sprint\n\nISO week `{week}`.\n"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_lane(raw: str) -> str:
    lane = unquote(raw)
    if lane in ALL_LANES:
        return lane
    if lane in LEGACY_BACKLOG:
        return BACKLOG_LANE
    if lane == "todo":
        return "doing this week"
    if lane == "in-progress":
        return "in progress now"
    return lane


def status_for_lane(lane: str) -> str:
    if lane == "in progress now":
        return "in-progress"
    if lane == "doing this week":
        return "todo"
    if lane == TRIAGE_LANE:
        return "triage"
    return lane


def apply_lane(fm: dict[str, str], lane: str, sprint_week: str) -> None:
    fm["lane"] = yaml_scalar(lane)
    if lane in (BACKLOG_LANE, ARCHIVED_LANE, TRIAGE_LANE):
        fm["sprint"] = '""'
        fm["status"] = f'"{status_for_lane(lane)}"' if lane == TRIAGE_LANE else '""'
        if lane == TRIAGE_LANE:
            fm["status"] = '"triage"'
    elif lane in SPRINT_LANES:
        fm["sprint"] = f'"{sprint_week}"'
        fm["status"] = f'"{status_for_lane(lane)}"'
        # Clear carry when committing to active sprint work
        if lane in ("doing this week", "in progress now"):
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
