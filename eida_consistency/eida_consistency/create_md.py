"""Create a global Markdown summary of all node reports."""

import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any

from eida_consistency.report.report import REPORT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def load_reports(report_dir: Path) -> List[Tuple[Path, Dict[str, Any]]]:
    """Load all JSON reports under reports/nodes/*."""
    reports: List[Tuple[Path, Dict[str, Any]]] = []
    for path in sorted(report_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            reports.append((path, data))
        except Exception as exc:
            logging.error(f"Failed to load {path}: {exc}")
    return reports


def build_markdown(reports: List[Tuple[Path, Dict[str, Any]]]) -> str:
    """Build Markdown summary content from loaded reports."""
    lines = ["# Global EIDA Consistency Summary", ""]

    # --- Global table ---
    lines.append("## Per-node summary")
    lines.append("")
    lines.append("| Node | Epochs Requested | Epochs Usable | Total Checks | Consistent | Inconsistent | Score |")
    lines.append("|------|------------------|---------------|--------------|------------|--------------|-------|")

    for path, rep in reports:
        s = rep.get("summary", {})
        node = s.get("node", "?")
        requested = s.get("candidates_requested", s.get("epochs", "?"))
        usable = s.get("candidates_generated", s.get("epochs", "?"))
        total_checked = s.get("total_checked", 0)
        total_consistent = s.get("total_consistent", 0)
        total_inconsistent = s.get("total_inconsistent", 0)
        score = s.get("score", 0.0)

        lines.append(
            f"| {node} | {requested} | {usable} | "
            f"{total_checked} | {total_consistent} | "
            f"{total_inconsistent} | {score} % |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Details per node ---
    for path, rep in reports:
        s = rep.get("summary", {})
        node = s.get("node", "?")
        lines.append(f"## Node: {node}")
        lines.append("")
        lines.append(f"- Seed: `{s.get('seed', '?')}`")
        lines.append(f"- Epochs requested: `{s.get('candidates_requested', s.get('epochs', '?'))}`")
        lines.append(f"- Epochs usable: `{s.get('candidates_generated', s.get('epochs', '?'))}`")
        lines.append(f"- Candidate pool: `{s.get('candidates_pool', '?')}`")
        lines.append(f"- Queries performed: `{s.get('queries_performed', '?')}`")
        lines.append(f"- Total checks: `{s.get('total_checked', 0)}`")
        lines.append(f"- Consistent: `{s.get('total_consistent', 0)}`")
        lines.append(f"- Inconsistent: `{s.get('total_inconsistent', 0)}`")
        lines.append(f"- Score: **{s.get('score', 0.0)} %**")
        lines.append("")

        # Reproduce command
        lines.append("### Reproduce")
        lines.append(
            f"```bash\nuv run eida-consistency consistency "
            f"--node {node} --epochs {s.get('candidates_requested', s.get('epochs', '?'))}\n```"
        )
        lines.append("")

        # Explore command
        lines.append("### Explore inconsistencies")
        lines.append(
            f"```bash\nuv run eida-consistency explore reports/nodes/{node.lower()}/*.json\n```"
        )
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def create_markdown_summary(report_dir: Path = REPORT_DIR / "nodes") -> Path:
    """Generate the global Markdown summary file."""
    reports = load_reports(report_dir)
    if not reports:
        logging.warning("No reports found.")
        return Path("")

    md = build_markdown(reports)
    out_path = REPORT_DIR / "summary.md"
    out_path.write_text(md, encoding="utf-8")
    logging.info(f"Markdown summary saved to {out_path}")
    return out_path


def main():
    create_markdown_summary()


if __name__ == "__main__":
    main()
