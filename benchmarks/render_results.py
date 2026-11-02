"""Render the public benchmark table from one pyperf result."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyperf
from compare_h2 import SCENARIOS

MULTIPLICATION_SIGN = "\N{MULTIPLICATION SIGN}"
TABLE_START = "<!-- benchmark-table:start -->"
TABLE_END = "<!-- benchmark-table:end -->"


Row = tuple[str, str, float, float]


def load_results(path: Path) -> tuple[list[Row], str, str]:
    """Load paired means and environment details from a pyperf suite."""
    suite = pyperf.BenchmarkSuite.load(str(path))
    means = {benchmark.get_name(): benchmark.mean() for benchmark in suite}
    rows = []
    for key, label, _ in SCENARIOS:
        try:
            candidate = means[f"http2_{key}/ngh2"]
            reference = means[f"http2_{key}/h2"]
        except KeyError as error:
            raise ValueError(f"missing benchmark: {error.args[0]}") from None
        rows.append((key, label, candidate, reference))

    metadata = suite.get_metadata()
    _, finished = suite.get_dates()
    h2_version = str(metadata["h2_version"])
    versions = (
        f"ngh2 {metadata['ngh2_version']}",
        f"h2 {h2_version}",
        f"CPython {metadata['python_version']}",
    )
    environment = (
        metadata.get("machine_name")
        or metadata.get("cpu_model_name")
        or f"{metadata.get('cpu_count', '?')} CPUs",
        metadata.get("platform"),
        finished.date().isoformat(),
    )
    details = "\n".join(
        " · ".join(str(value) for value in line if value)
        for line in (versions, environment)
    )
    return rows, details, h2_version


def format_time(seconds: float) -> str:
    """Format a per-iteration time in µs, or in ms from one millisecond."""
    if seconds < 1e-3:
        return f"{seconds * 1e6:,.2f} µs"
    return f"{seconds * 1e3:,.2f} ms"


def render_table(
    rows: list[Row],
    details: str,
    h2_version: str,
) -> str:
    """Render mean times per iteration and the speedup as a Markdown table."""
    lines = [
        f"| Scenario | ngh2 | h2 {h2_version} | ngh2 speedup |",
        "| --- | ---: | ---: | ---: |",
    ]
    for _, label, candidate, reference in rows:
        lines.append(
            f"| {label} | {format_time(candidate)} | {format_time(reference)} | "
            f"{reference / candidate:.1f}{MULTIPLICATION_SIGN} |",
        )
    if details:
        lines.extend(("", f"_Environment: {details.replace(chr(10), ' · ')}_"))
    return "\n".join(lines) + "\n"


def replace_marked_table(document: str, table: str) -> str:
    """Return the document with the text between the table markers replaced."""
    before, start, rest = document.partition(TABLE_START)
    _, end, after = rest.partition(TABLE_END)
    if not start or not end:
        raise ValueError("benchmark table markers not found")
    return f"{before}{TABLE_START}\n{table}{TABLE_END}{after}"


def main() -> None:
    """Load pyperf JSON and write the requested presentation artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--table", type=Path)
    parser.add_argument(
        "--readme",
        type=Path,
        help="replace the table between the README benchmark markers",
    )
    args = parser.parse_args()

    rows, details, h2_version = load_results(args.results)
    table = render_table(rows, details, h2_version)
    if args.table:
        args.table.parent.mkdir(parents=True, exist_ok=True)
        args.table.write_text(table, encoding="utf-8")
    else:
        print(table, end="")
    if args.readme:
        args.readme.write_text(
            replace_marked_table(args.readme.read_text(encoding="utf-8"), table),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
