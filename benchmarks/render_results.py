"""Render the public benchmark chart and table from one pyperf result."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

import pyperf
from compare_h2 import SCENARIOS

MULTIPLICATION_SIGN = "\N{MULTIPLICATION SIGN}"
TABLE_START = "<!-- benchmark-table:start -->"
TABLE_END = "<!-- benchmark-table:end -->"


Row = tuple[str, str, float, float]
# One small request, many small requests, and the largest bodies, where the
# speedup is smallest.
CHART_SCENARIOS = (
    "consecutive_x1_empty",
    "parallel_x10_empty",
    "parallel_x10_res_10mb",
)


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


def render_svg(rows: list[Row], h2_version: str) -> str:
    """Render ngh2 and h2 times for the chart scenarios as paired bars."""
    chart = [row for row in rows if row[0] in CHART_SCENARIOS]
    width, padding, name_width, value_width = 760, 24, 72, 96
    group_height, bar_height, badge_width = 98, 12, 104
    plot_x = padding + name_width
    plot_width = width - plot_x - padding - value_width
    height = 2 * padding + group_height * len(chart) - 32
    reference_name = f"h2 {h2_version}"

    # ngh2 and its speedup badge share the Python blue from the ngh2 logo.
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">ngh2 and h2 time per iteration</title>',
        '<desc id="desc">'
        + "; ".join(
            f"{escape(label)}: ngh2 {format_time(candidate)}, "
            f"{escape(reference_name)} {format_time(reference)}, "
            f"{reference / candidate:.1f} times faster"
            for _, label, candidate, reference in chart
        )
        + ".</desc>",
        "<style>",
        "text{font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
        "Helvetica,Arial,sans-serif;font-variant-numeric:tabular-nums}",
        ".card{fill:#ffffff;stroke:#d1d9e0}.rule{stroke:#eff2f5}"
        ".primary{fill:#1f2328}.secondary{fill:#59636e}"
        ".candidate{fill:#4b8bbe}.reference{fill:#d1d9e0}"
        ".badge{fill:#4b8bbe;fill-opacity:0.14}.badge-text{fill:#306998}",
        "@media (prefers-color-scheme:dark){.card{fill:#0d1117;stroke:#3d444d}"
        ".rule{stroke:#262c36}.primary{fill:#f0f6fc}.secondary{fill:#9198a1}"
        ".reference{fill:#3d444d}.badge{fill-opacity:0.22}"
        ".badge-text{fill:#8ab4df}}",
        "</style>",
        f'<rect class="card" x="0.5" y="0.5" width="{width - 1}" '
        f'height="{height - 1}" rx="12"/>',
    ]
    for index, (_, label, candidate, reference) in enumerate(chart):
        y = padding + index * group_height
        longest = max(candidate, reference)
        badge_x = width - padding - badge_width
        if index:
            svg.append(
                f'<line class="rule" x1="{padding}" y1="{y - 16}" '
                f'x2="{width - padding}" y2="{y - 16}"/>',
            )
        svg.extend(
            [
                f'<text class="primary" x="{padding}" y="{y + 16}" font-size="14" '
                f'font-weight="600">{escape(label)}</text>',
                f'<rect class="badge" x="{badge_x}" y="{y}" width="{badge_width}" '
                'height="22" rx="11"/>',
                f'<text class="badge-text" x="{badge_x + badge_width / 2}" '
                f'y="{y + 15}" text-anchor="middle" font-size="12" font-weight="700">'
                f"{reference / candidate:.1f}{MULTIPLICATION_SIGN} faster</text>",
            ],
        )
        bars = (
            ("ngh2", candidate, "candidate"),
            (reference_name, reference, "reference"),
        )
        for offset, (name, seconds, style) in enumerate(bars):
            top = y + 34 + offset * 20
            length = max(bar_height, plot_width * seconds / longest)
            svg.extend(
                [
                    f'<text class="secondary" x="{padding}" y="{top + 10}" '
                    f'font-size="12" font-weight="500">{escape(name)}</text>',
                    f'<rect class="{style}" x="{plot_x}" y="{top}" '
                    f'width="{length:.1f}" height="{bar_height}" '
                    f'rx="{bar_height / 2}"/>',
                    f'<text class="primary" x="{plot_x + length + 8:.1f}" '
                    f'y="{top + 10}" '
                    f'font-size="12" font-weight="500">{format_time(seconds)}</text>',
                ],
            )
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


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
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--table", type=Path)
    parser.add_argument(
        "--readme",
        type=Path,
        help="replace the table between the README benchmark markers",
    )
    args = parser.parse_args()

    rows, details, h2_version = load_results(args.results)
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.svg.write_text(
        render_svg(rows, h2_version),
        encoding="utf-8",
    )
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
