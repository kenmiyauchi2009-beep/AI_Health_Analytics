from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedItem:
    name: str
    score: float


@dataclass(frozen=True)
class ClusterSummary:
    cluster_id: int
    patient_count: int
    top_symptoms: list[RankedItem]
    top_diseases: list[RankedItem]


@dataclass(frozen=True)
class ClusterAssignmentResult:
    cluster_id: int
    confidence: float
    distances: list[float]
    summary: ClusterSummary


@dataclass(frozen=True)
class ClusterComparison:
    left: ClusterSummary
    right: ClusterSummary
    shared_symptoms: list[str]
    shared_diseases: list[str]
