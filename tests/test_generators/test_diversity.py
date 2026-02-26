import unittest
from dataclasses import dataclass

from tau2.generators.diversity import DiversityTracker, filter_ambiguous_names


class TestDiversityTracker(unittest.TestCase):
    def test_track_increments_count(self):
        tracker = DiversityTracker(seed=42)
        tracker.track("books", "b1")
        tracker.track("books", "b1")
        tracker.track("books", "b2")
        stats = tracker.stats()
        self.assertEqual(stats["books"]["b1"], 2)
        self.assertEqual(stats["books"]["b2"], 1)

    def test_sort_by_usage_least_first(self):
        tracker = DiversityTracker(seed=42)
        tracker.track("cat", "a")
        tracker.track("cat", "a")
        tracker.track("cat", "b")
        sorted_ids = tracker.sort_by_usage("cat", ["a", "b", "c"])
        # c has 0, b has 1, a has 2
        self.assertEqual(sorted_ids[0], "c")
        self.assertEqual(sorted_ids[-1], "a")

    def test_sample_picks_least_used(self):
        tracker = DiversityTracker(seed=42)
        tracker.track("cat", "a")
        tracker.track("cat", "a")
        tracker.track("cat", "b")
        # c has 0 uses, should be picked
        chosen = tracker.sample("cat", ["a", "b", "c"])
        self.assertEqual(chosen, "c")
        # Now c has 1, same as b. Next sample from {a,b,c}: b or c (both have 1)
        # a has 2, so won't be picked

    def test_sample_tracks_after_pick(self):
        tracker = DiversityTracker(seed=42)
        chosen = tracker.sample("cat", ["x", "y"])
        stats = tracker.stats()
        self.assertEqual(stats["cat"][chosen], 1)

    def test_sample_n(self):
        tracker = DiversityTracker(seed=42)
        tracker.track("cat", "a")
        tracker.track("cat", "a")
        result = tracker.sample_n("cat", ["a", "b", "c"], 2)
        self.assertEqual(len(result), 2)
        # a has 2 uses, b and c have 0 — should pick b and c
        self.assertNotIn("a", result)

    def test_sample_n_too_many_raises(self):
        tracker = DiversityTracker(seed=42)
        with self.assertRaises(ValueError):
            tracker.sample_n("cat", ["a", "b"], 3)

    def test_sample_empty_raises(self):
        tracker = DiversityTracker(seed=42)
        with self.assertRaises(ValueError):
            tracker.sample("cat", [])

    def test_reset(self):
        tracker = DiversityTracker(seed=42)
        tracker.track("cat", "a")
        tracker.reset()
        self.assertEqual(tracker.stats(), {})

    def test_deterministic_with_same_seed(self):
        """Same seed produces same sampling order."""
        results1 = []
        tracker1 = DiversityTracker(seed=123)
        for _ in range(5):
            results1.append(tracker1.sample("cat", ["a", "b", "c"]))

        results2 = []
        tracker2 = DiversityTracker(seed=123)
        for _ in range(5):
            results2.append(tracker2.sample("cat", ["a", "b", "c"]))

        self.assertEqual(results1, results2)

    def test_different_seeds_may_differ(self):
        """Different seeds may produce different tiebreak orderings."""
        tracker1 = DiversityTracker(seed=1)
        tracker2 = DiversityTracker(seed=999)
        # With enough samples, different seeds should eventually diverge
        results1 = [tracker1.sample("cat", ["a", "b", "c"]) for _ in range(10)]
        results2 = [tracker2.sample("cat", ["a", "b", "c"]) for _ in range(10)]
        # They should both have balanced counts but potentially different orders
        # Just check they're valid
        for r in results1 + results2:
            self.assertIn(r, ["a", "b", "c"])


class TestFilterAmbiguousNames(unittest.TestCase):
    def test_removes_duplicates(self):
        entities = [
            {"name": "Alice", "id": 1},
            {"name": "Bob", "id": 2},
            {"name": "Alice", "id": 3},
        ]
        result = filter_ambiguous_names(entities, "name")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Bob")

    def test_keeps_unique(self):
        entities = [
            {"name": "Alice", "id": 1},
            {"name": "Bob", "id": 2},
        ]
        result = filter_ambiguous_names(entities, "name")
        self.assertEqual(len(result), 2)

    def test_works_with_objects(self):
        @dataclass
        class Entity:
            name: str
            id: int

        entities = [Entity("Alice", 1), Entity("Bob", 2), Entity("Alice", 3)]
        result = filter_ambiguous_names(entities, "name")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Bob")

    def test_empty_list(self):
        result = filter_ambiguous_names([], "name")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
