"""Render the public benchmark chart and table from one pyperf result."""

from __future__ import annotations

import argparse
from html import escape
from math import ceil
from pathlib import Path

import pyperf

SCENARIOS = (
    ("small_round_trip", "Small request/204 round trip"),
    ("headers_32", "Header block · 32 fields"),
    ("fragmented_5b", "Fragmented request · 5 B"),
    ("body_32k", "Request body · 32 KiB"),
    ("multiplexed_100", "Multiplexed batch · 100 streams"),
)
MULTIPLICATION_SIGN = "\N{MULTIPLICATION SIGN}"


def load_results(path: Path) -> tuple[list[tuple[str, float, float]], str, str]:
    """Load paired means and environment details from a pyperf suite."""
    suite = pyperf.BenchmarkSuite.load(str(path))
    means = {benchmark.get_name(): benchmark.mean() for benchmark in suite}
    rows = []
    for key, label in SCENARIOS:
        try:
            candidate = means[f"scenario/{key}/ngh2"]
            reference = means[f"scenario/{key}/h2"]
        except KeyError as error:
            raise ValueError(f"missing benchmark: {error.args[0]}") from None
        rows.append((label, candidate, reference))

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


def render_svg(
    rows: list[tuple[str, float, float]],
    details: str,
    h2_version: str,
) -> str:
    """Render an accessible dependency-free SVG comparison chart."""
    width = 960
    plot_x, plot_width = 360, 530
    row_height = 76
    detail_lines = details.splitlines()
    height = 128 + row_height * len(rows) + 20 * len(detail_lines)
    speedups = [reference / candidate for _, candidate, reference in rows]
    tick_step = max(1, ceil(max(1.0, *speedups) / 4))
    axis_max = tick_step * ceil(max(1.0, *speedups) / tick_step)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">ngh2 and h2 Python benchmark</title>',
        '<desc id="desc">Relative throughput for five HTTP/2 scenarios. Higher '
        f"is faster; h2 {escape(h2_version)} is the 1.00 baseline.</desc>",
        "<style>",
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}",
        ".canvas{fill:#fbfbfd}.primary{fill:#1d1d1f}.secondary{fill:#6e6e73}"
        ".grid{stroke:#e5e5ea}",
        ".candidate{fill:#3a6ea5}.reference{fill:#c7c7cc}",
        "</style>",
        f'<rect class="canvas" width="{width}" height="{height}"/>',
        '<text class="secondary" x="40" y="27" font-size="11" font-weight="500" '
        'letter-spacing="1.4">PYTHON · HTTP/2</text>',
        '<text class="primary" x="40" y="58" font-size="25" font-weight="500" '
        'letter-spacing="-0.4">Relative throughput by scenario</text>',
        f'<text class="secondary" x="40" y="83" font-size="13">h2 '
        f"{escape(h2_version)} = 1.00{MULTIPLICATION_SIGN} · higher is faster · "
        "latency per exchange</text>",
    ]

    for index in range(5):
        value = axis_max * index / 4
        x = plot_x + plot_width * index / 4
        svg.extend(
            [
                f'<line class="grid" x1="{x:.1f}" y1="108" x2="{x:.1f}" '
                f'y2="{112 + row_height * len(rows)}"/>',
                f'<text class="secondary" x="{x:.1f}" y="102" text-anchor="middle" '
                f'font-size="10">{value:g}{MULTIPLICATION_SIGN}</text>',
            ],
        )

    for index, (label, candidate, reference) in enumerate(rows):
        speedup = reference / candidate
        y = 124 + index * row_height
        reference_width = plot_width / axis_max
        candidate_width = plot_width * speedup / axis_max
        svg.extend(
            [
                f'<text class="primary" x="40" y="{y + 15}" font-size="13" '
                f'font-weight="500">{escape(label)}</text>',
                f'<text class="secondary" x="40" y="{y + 37}" font-size="11">'
                f"{candidate * 1e6:.2f} µs vs {reference * 1e6:.2f} µs</text>",
                f'<text class="secondary" x="308" y="{y + 12}" text-anchor="end" '
                'font-size="10">ngh2</text>',
                f'<rect class="candidate" x="{plot_x}" y="{y}" '
                f'width="{candidate_width:.1f}" height="15" rx="7.5"/>',
                f'<text class="primary" x="{min(plot_x + candidate_width + 10, 920):.1f}" '
                f'y="{y + 12}" font-size="11" font-weight="500">{speedup:.1f}'
                f"{MULTIPLICATION_SIGN}</text>",
                f'<text class="secondary" x="308" y="{y + 35}" text-anchor="end" '
                f'font-size="10">h2 {escape(h2_version)}</text>',
                f'<rect class="reference" x="{plot_x}" y="{y + 23}" '
                f'width="{reference_width:.1f}" height="10" rx="5"/>',
            ],
        )

    for index, line in enumerate(detail_lines):
        svg.append(
            f'<text class="secondary" x="40" y="{height - 30 + index * 17}" '
            f'font-size="10">{escape(line)}</text>',
        )
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def render_table(
    rows: list[tuple[str, float, float]],
    details: str,
    h2_version: str,
) -> str:
    """Render exact means as a Markdown table."""
    lines = [
        f"| Scenario | ngh2 (µs/exchange) | h2 {h2_version} (µs/exchange) | Relative throughput |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, candidate, reference in rows:
        lines.append(
            f"| {label} | {candidate * 1e6:.2f} | {reference * 1e6:.2f} | "
            f"{reference / candidate:.1f}{MULTIPLICATION_SIGN} |",
        )
    if details:
        lines.extend(("", f"_Environment: {details.replace(chr(10), ' · ')}_"))
    return "\n".join(lines) + "\n"


def main() -> None:
    """Load pyperf JSON and write the requested presentation artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--table", type=Path)
    args = parser.parse_args()

    rows, details, h2_version = load_results(args.results)
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.svg.write_text(
        render_svg(rows, details, h2_version),
        encoding="utf-8",
    )
    table = render_table(rows, details, h2_version)
    if args.table:
        args.table.parent.mkdir(parents=True, exist_ok=True)
        args.table.write_text(table, encoding="utf-8")
    else:
        print(table, end="")


if __name__ == "__main__":
    main()
