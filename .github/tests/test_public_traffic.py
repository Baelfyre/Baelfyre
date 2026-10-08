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

PUBLIC = "Baelfyre/Baelfyre"
OPEN = "Baelfyre/ApprovedPublic"
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
