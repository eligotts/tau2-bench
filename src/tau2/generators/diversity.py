"""Entity diversity utilities for balanced task generation."""

import random
from collections import defaultdict
from typing import Any, Sequence


class DiversityTracker:
    """Track entity usage counts to ensure balanced diversity across generated tasks.

    Uses a deterministic seed for reproducible sampling. Prefers least-used
    entities, with random tiebreaking among equally-used ones.
    """

    def __init__(self, seed: int = 42):
        self._counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._rng = random.Random(seed)

    def track(self, category: str, entity_id: str) -> None:
        """Increment usage count for an entity in a category."""
        self._counts[category][entity_id] += 1

    def sort_by_usage(self, category: str, ids: Sequence[str]) -> list[str]:
        """Return ids sorted by usage count (least-used first), random tiebreak."""
        counts = self._counts[category]
        shuffled = list(ids)
        self._rng.shuffle(shuffled)
        return sorted(shuffled, key=lambda x: counts.get(x, 0))

    def sample(self, category: str, ids: Sequence[str]) -> str:
        """Pick and track the least-used entity from ids."""
        if not ids:
            raise ValueError(f"No ids to sample from for category '{category}'")
        sorted_ids = self.sort_by_usage(category, ids)
        chosen = sorted_ids[0]
        self.track(category, chosen)
        return chosen

    def sample_n(self, category: str, ids: Sequence[str], n: int) -> list[str]:
        """Pick and track N least-used entities from ids."""
        if n > len(ids):
            raise ValueError(
                f"Cannot sample {n} from {len(ids)} ids in category '{category}'"
            )
        result = []
        available = list(ids)
        for _ in range(n):
            sorted_avail = self.sort_by_usage(category, available)
            chosen = sorted_avail[0]
            self.track(category, chosen)
            result.append(chosen)
            available.remove(chosen)
        return result

    def reset(self) -> None:
        """Reset all usage counts."""
        self._counts.clear()

    def stats(self) -> dict[str, dict[str, int]]:
        """Return current usage counts as a plain dict."""
        return {cat: dict(counts) for cat, counts in self._counts.items()}


def filter_ambiguous_names(
    entities: Sequence[Any], name_field: str = "name"
) -> list[Any]:
    """Remove entities whose display name appears more than once (ambiguous)."""
    name_counts: dict[str, int] = defaultdict(int)
    for entity in entities:
        name = getattr(entity, name_field, None) if hasattr(entity, name_field) else entity.get(name_field)
        if name is not None:
            name_counts[name] += 1

    result = []
    for entity in entities:
        name = getattr(entity, name_field, None) if hasattr(entity, name_field) else entity.get(name_field)
        if name is not None and name_counts[name] == 1:
            result.append(entity)
    return result
