"""Regression tests for publishing only explicitly approved public traffic."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_traffic
import generate_traffic_card
import public_traffic_policy as privacy
import verify_public_traffic

PUBLIC = "Baelfyre/Baelfyre"
OPEN = "Baelfyre/Orchestra"
PRIVATE = "Baelfyre/UnlistedPrivate"


class TestPublicationBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.policy_path = root / "public-sources.json"
        self.status_path = root / "profile-status.json"
        self.data_path = root / "repository-traffic.json"
        self.policy_path.write_text(json.dumps({
            "schema_version": privacy.POLICY_SCHEMA,
            "repositories": [PUBLIC, OPEN]
        }), encoding="utf-8")
        self.status_path.write_text(json.dumps({"projects": [
            {"repository": OPEN, "auth": "public"},
            {"repository": PRIVATE, "auth": "private"}
        ]}), encoding="utf-8")
        policy = patch.object(privacy, "POLICY_PATH", self.policy_path)
        status = patch.object(privacy, "PROFILE_STATUS_PATH", self.status_path)
        policy.start()
        status.start()
        self.addCleanup(policy.stop)
        self.addCleanup(status.stop)

    def snapshot(self, sources):
        return {
            "schema_version": privacy.TRAFFIC_SCHEMA,
            "window": "rolling_14_days",
            "snapshots": [{"snapshot_date": "2026-10-09", "repositories": sources}]
        }

    def metrics(self, views=100):
        return {
            "status": "ok",
            "views": {"count": views, "uniques": 5},
            "clones": {"count": 10, "uniques": 2}
        }

    def test_publication_allowlist_excludes_private_project(self):
        self.assertEqual(collect_traffic.repository_list(), [PUBLIC, OPEN])
        self.policy_path.write_text(json.dumps({
            "schema_version": privacy.POLICY_SCHEMA,
            "repositories": [PUBLIC, PRIVATE]
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            privacy.load_publication_policy()

    def test_unlisted_repository_is_denied(self):
        self.policy_path.write_text(json.dumps({
            "schema_version": privacy.POLICY_SCHEMA,
            "repositories": [PUBLIC, "Baelfyre/Unknown"]
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            privacy.load_publication_policy()

    def test_missing_policy_and_duplicate_entries_fail_closed(self):
        self.policy_path.unlink()
        with self.assertRaises(OSError):
            privacy.load_publication_policy()
        self.policy_path.write_text(json.dumps({
            "schema_version": privacy.POLICY_SCHEMA,
            "repositories": [PUBLIC, PUBLIC]
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            privacy.load_publication_policy()

    def test_private_top_repository_is_rejected_before_render(self):
        self.data_path.write_text(json.dumps(self.snapshot({
            PRIVATE: self.metrics(900000),
            OPEN: self.metrics(10)
        })), encoding="utf-8")
        with self.assertRaises(ValueError):
            generate_traffic_card.load_data(self.data_path)

    def test_collector_refuses_historical_private_records(self):
        self.data_path.write_text(json.dumps(self.snapshot({
            PRIVATE: self.metrics(1), PUBLIC: self.metrics()
        })), encoding="utf-8")
        with patch.object(collect_traffic, "OUTPUT", self.data_path):
            with self.assertRaises(ValueError):
                collect_traffic.load_output()

    def test_public_data_generates_only_public_card(self):
        self.data_path.write_text(json.dumps(self.snapshot({
            PUBLIC: self.metrics(10), OPEN: self.metrics(20)
        })), encoding="utf-8")
        output = Path(self.tmp.name) / "card.svg"
        generate_traffic_card.generate(self.data_path, output)
        svg = output.read_text(encoding="utf-8")
        self.assertIn(OPEN, svg)
        self.assertNotIn(PRIVATE, svg)

    def test_featured_repository_stays_orchestra_when_profile_has_more_views(self):
        data = self.snapshot({
            PUBLIC: self.metrics(150),
            OPEN: self.metrics(15),
        })
        summary = generate_traffic_card.summarize(data["snapshots"][0])
        self.assertEqual(summary["featured"]["name"], OPEN)
        self.assertEqual(summary["total_views"], 165)
        self.data_path.write_text(json.dumps(data), encoding="utf-8")
        output = Path(self.tmp.name) / "feature-card.svg"
        generate_traffic_card.generate(self.data_path, output)
        svg = output.read_text(encoding="utf-8")
        self.assertIn("FEATURED PUBLIC REPOSITORY", svg)
        self.assertIn(OPEN, svg)
        self.assertIn("15 views - 5 unique visitors", svg)
        self.assertNotIn(PRIVATE, svg)

    def test_featured_repository_pending_does_not_impersonate_profile_metrics(self):
        data = self.snapshot({PUBLIC: self.metrics(120)})
        summary = generate_traffic_card.summarize(data["snapshots"][0])
        self.assertIsNone(summary["featured"])
        self.data_path.write_text(json.dumps(data), encoding="utf-8")
        output = Path(self.tmp.name) / "pending-card.svg"
        generate_traffic_card.generate(self.data_path, output)
        svg = output.read_text(encoding="utf-8")
        self.assertIn(OPEN, svg)
        self.assertIn("Awaiting first Orchestra traffic snapshot", svg)
        self.assertNotIn("120 views - 5 unique visitors", svg)
        self.assertNotIn(PRIVATE, svg)

    def test_visibility_check_rejects_private_or_unavailable_repo(self):
        with patch.object(collect_traffic, "urlopen", return_value=io.BytesIO(
            b'{"private":true,"visibility":"private"}'
        )):
            with self.assertRaises(ValueError):
                collect_traffic.require_public_visibility(PUBLIC, "test")
        with patch.object(collect_traffic, "urlopen", return_value=io.BytesIO(
            b'{"private":false,"visibility":"public"}'
        )):
            collect_traffic.require_public_visibility(PUBLIC, "test")

    def test_visibility_check_rejects_internal_or_missing_visibility(self):
        with patch.object(collect_traffic, "urlopen", return_value=io.BytesIO(
            b'{"private":false,"visibility":"internal"}'
        )):
            with self.assertRaises(ValueError):
                collect_traffic.require_public_visibility(PUBLIC, "test")
        with patch.object(collect_traffic, "urlopen", return_value=io.BytesIO(
            b'{"private":false}'
        )):
            with self.assertRaises(ValueError):
                collect_traffic.require_public_visibility(PUBLIC, "test")
        with patch.object(collect_traffic, "urlopen", return_value=io.BytesIO(
            b'{"private":false,"visibility":null}'
        )):
            with self.assertRaises(ValueError):
                collect_traffic.require_public_visibility(PUBLIC, "test")
        with patch.object(collect_traffic, "urlopen", return_value=io.BytesIO(
            b'{"private":false,"visibility":123}'
        )):
            with self.assertRaises(ValueError):
                collect_traffic.require_public_visibility(PUBLIC, "test")

    def test_write_snapshot_pre_write_rejection(self):
        with patch.object(collect_traffic, "OUTPUT", self.data_path), \
             patch.object(collect_traffic, "repository_list", return_value=[PUBLIC, PRIVATE]), \
             patch.object(collect_traffic, "require_public_visibility", return_value=None), \
             patch.object(collect_traffic, "collect_repository", return_value=self.metrics()):
            with self.assertRaises(ValueError):
                collect_traffic.write_snapshot("test-token")
        self.assertFalse(self.data_path.exists())

    def test_malformed_snapshots_fail_closed(self):
        with self.assertRaises(ValueError):
            privacy.validate_published_dataset({"schema_version": privacy.TRAFFIC_SCHEMA, "window": "rolling_14_days", "snapshots": "invalid"}, (PUBLIC,))
        with self.assertRaises(ValueError):
            privacy.validate_published_dataset({"schema_version": privacy.TRAFFIC_SCHEMA, "window": "rolling_14_days", "snapshots": ["not-a-dict"]}, (PUBLIC,))
        with self.assertRaises(ValueError):
            privacy.validate_published_dataset({"schema_version": privacy.TRAFFIC_SCHEMA, "window": "rolling_14_days", "snapshots": [{"repositories": "not-a-dict"}]}, (PUBLIC,))

    def test_svg_verifier_catches_unapproved_and_shortened_identities(self):
        card_file = Path(self.tmp.name) / "card.svg"
        card_file.write_text(f'<svg><text>{PRIVATE}</text></svg>', encoding="utf-8")
        self.data_path.write_text(json.dumps(self.snapshot({PUBLIC: self.metrics()})), encoding="utf-8")
        with patch.object(verify_public_traffic, "CARD_PATH", card_file), \
             patch.object(verify_public_traffic, "TRAFFIC_PATH", self.data_path), \
             patch.object(verify_public_traffic, "PROFILE_STATUS_PATH", self.status_path):
            with self.assertRaises(ValueError):
                verify_public_traffic.verify()

        long_private = "Baelfyre/VeryLongUnapprovedPrivateRepositoryNameExceeding"
        shortened = f"{long_private[:39]}..."
        card_file.write_text(f'<svg><text>{shortened}</text></svg>', encoding="utf-8")
        long_status_path = Path(self.tmp.name) / "long-status.json"
        long_status_path.write_text(json.dumps({"projects": [{"repository": long_private, "auth": "private"}]}), encoding="utf-8")
        with patch.object(verify_public_traffic, "CARD_PATH", card_file), \
             patch.object(verify_public_traffic, "TRAFFIC_PATH", self.data_path), \
             patch.object(verify_public_traffic, "PROFILE_STATUS_PATH", long_status_path):
            with self.assertRaises(ValueError):
                verify_public_traffic.verify()

    def test_committed_public_snapshots_have_no_private_sources(self):
        root = Path(__file__).resolve().parents[2]
        data = json.loads((root / "analytics/repository-traffic.json").read_text(encoding="utf-8"))
        status = json.loads((root / "profile-status.json").read_text(encoding="utf-8"))
        policy_sources = set(json.loads((root / "analytics/public-traffic-sources.json").read_text(encoding="utf-8"))["repositories"])
        for snapshot in data["snapshots"]:
            self.assertTrue(set(snapshot["repositories"]).issubset(policy_sources))
            for project in status["projects"]:
                if project.get("auth") == "private":
                    self.assertNotIn(project["repository"], snapshot["repositories"])


if __name__ == "__main__":
    unittest.main()
