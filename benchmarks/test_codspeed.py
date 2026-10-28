"""Track ngh2's share of the h2 comparison workloads with CodSpeed."""

import pytest
from compare_h2 import SCENARIOS, Ngh2RoundTrip


@pytest.mark.parametrize(
    ("headers", "fragment_size", "body_chunks", "batch_size"),
    [scenario[2:] for scenario in SCENARIOS],
    ids=[scenario[0] for scenario in SCENARIOS],
)
def test_round_trip(benchmark, headers, fragment_size, body_chunks, batch_size):
    workload = Ngh2RoundTrip(headers, fragment_size, body_chunks, batch_size)
    # The first exchange fills the HPACK dynamic tables; later ones reuse them.
    workload()

    requests, body_bytes, responses = benchmark(workload)

    assert (requests, responses) == (batch_size, batch_size)
    assert body_bytes == batch_size * sum(map(len, body_chunks))
