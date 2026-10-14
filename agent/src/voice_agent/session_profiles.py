"""latency_profile -> concrete turn-handling numbers. Starting points; tuned via benchmarks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LatencyTuning:
    endpoint_min_delay: float
    endpoint_max_delay: float
    preemptive_generation: bool


LATENCY_PROFILES: dict[str, LatencyTuning] = {
    "aggressive": LatencyTuning(0.2, 2.0, True),
    "balanced": LatencyTuning(0.4, 3.0, True),
    "conservative": LatencyTuning(0.7, 4.5, False),
}
