"""Command-line interface for eida-consistency.

Examples
--------
$ uv run eida-consistency --log-level DEBUG consistency --node NOA --epochs 5
$ uv run eida-consistency compare report1.json report2.json
$ uv run eida-consistency consistency --delete-old
$ uv run eida-consistency explore --index 7 --index 8
$ uv run eida-consistency reload-nodes
$ uv run eida-consistency list-nodes
"""

import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import click
from eida_consistency.runner import run_consistency_check
from eida_consistency.report.compare import compare_reports
from eida_consistency.report.report import delete_old_reports, REPORT_DIR
from eida_consistency.explorer import explore_boundaries
from eida_consistency.utils import nodes


def normalize_log_level(level: str) -> int:
    """Normalize a log level string to its numeric value or raise on invalid."""
    numeric = getattr(logging, str(level).upper(), None)
    if not isinstance(numeric, int):
        raise click.BadParameter(f"Invalid log level: {level}")
    return numeric


def _setup_logging(level: str) -> None:
    """Configure root logger once."""
    numeric = normalize_log_level(level)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group(invoke_without_command=True)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    show_default=True,
    help="Set logging verbosity.",
)
@click.option(
    "--report-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=REPORT_DIR,
    show_default=True,
    help="Directory to store and load reports.",
)
@click.pass_context
def cli(ctx, log_level, report_dir):
    """EIDA consistency checker."""
    _setup_logging(log_level)
    ctx.obj = {"log_level": log_level, "report_dir": Path(report_dir)}
    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        click.echo(ctx.get_help())
        ctx.exit(1)


# ----------------------------------------------------------------------
# consistency command
# ----------------------------------------------------------------------
@cli.command()
@click.option("--node", help="EIDA node code (e.g., RESIF, NOA)")
@click.option("--epochs", type=int, default=10, show_default=True, help="Number of epochs")
@click.option("--duration", type=int, default=600, show_default=True, help="Duration (s), must be >= 600")
@click.option("--seed", type=int, help="Random seed")
@click.option(
    "--delete-old",
    is_flag=True,
    help="Delete all but the latest report (standalone mode).",
)
@click.option(
    "--stdout",
    "print_stdout",
    is_flag=True,
    help="Also print the JSON report to stdout.",
)
@click.option(
    "--upload",
    is_flag=True,
    help="Upload report to configured S3 bucket after saving locally.",
)
@click.pass_context
def consistency(ctx, node, epochs, duration, seed, delete_old, print_stdout, upload):
    """Run availability + dataselect consistency check, or housekeeping with --delete-old."""
    report_dir: Path = ctx.obj["report_dir"]

    if delete_old:
        delete_old_reports(report_dir, keep=1)
        logging.info("Old reports cleaned up, kept only the latest one.")
        return

    if not node:
        raise click.UsageError("--node is required unless --delete-old is used")
    if duration < 600:
        raise click.BadParameter("Duration must be at least 600 seconds (10 minutes).")

    # Run the check and get the report path
    report_path = run_consistency_check(
        node=node,
        epochs=epochs,
        duration=duration,
        seed=seed,
        print_stdout=print_stdout,
        report_dir=report_dir,
    )

    # Upload if requested
    if upload:
        from eida_consistency.report.storage import upload_report
        url = upload_report(str(report_path))
        if url:
            click.echo(f"Report uploaded: {url}")
        else:
            click.echo(f"Upload failed, report kept locally at: {report_path}")
    else:
        click.echo(f"Report saved locally at: {report_path}")


# ----------------------------------------------------------------------
# compare command
# ----------------------------------------------------------------------
@cli.command()
@click.argument("report1", type=str)
@click.argument("report2", type=str)
@click.pass_context
def compare(ctx, report1, report2):
    """Compare two JSON report files."""
    report_dir: Path = ctx.obj["report_dir"]
    compare_reports(report1, report2, report_dir=report_dir)


# ----------------------------------------------------------------------
# explore command
# ----------------------------------------------------------------------
@cli.command()
@click.argument("report", required=False, type=click.Path(path_type=Path))
@click.option(
    "--index", "-i",
    multiple=True, type=int,
    help="Indices of inconsistent results to explore (default: all)."
)
@click.option(
    "--days", "-d",
    default=30, show_default=True, type=int,
    help="Maximum number of days to explore backward/forward."
)
@click.option("--verbose", is_flag=True, help="Print query URLs while exploring")
@click.pass_context
def explore(ctx, report, index, days, verbose):
    """Explore day-by-day boundaries of inconsistencies from a report."""
    report_dir: Path = ctx.obj["report_dir"]

    if not report:
        try:
            report = max(report_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
            logging.info(f"Using latest report: {report}")
        except ValueError:
            raise click.UsageError(f"No report files found in {report_dir}")

    indices = list(index) if index else None
    explore_boundaries(report, indices, max_days=days, verbose=verbose)


# ----------------------------------------------------------------------
# reload-nodes command
# ----------------------------------------------------------------------
@cli.command(name="reload-nodes")
def reload_nodes():
    """Reload EIDA node list from routing service and update cache."""
    try:
        new_nodes = nodes.refresh_cache_from_routing()
        logging.info(f"Reloaded {len(new_nodes)} nodes from routing service.")
        for name, url, _ in new_nodes:
            logging.info(f"  {name}: {url}")
    except Exception as exc:
        raise click.ClickException(f"Failed to reload nodes: {exc}")


# ----------------------------------------------------------------------
# list-nodes command
# ----------------------------------------------------------------------
@cli.command(name="list-nodes")
def list_nodes():
    """List currently cached EIDA nodes."""
    nodes_list = nodes.load_or_refresh_cache()
    logging.info(f"{len(nodes_list)} nodes currently cached:")
    for name, url, _ in nodes_list:
        logging.info(f"  {name}: {url}")


if __name__ == "__main__":
    cli()
