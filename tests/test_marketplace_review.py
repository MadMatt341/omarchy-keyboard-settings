import base64
import copy
import json
import unittest

from tools.check_marketplace_review import REPOSITORY, check, report_refs


SHA = "a" * 40


def reports():
    data = {"schemaVersion": 2, "repository": REPOSITORY,
            "pluginIds": ["madmatt.keyboard-settings"], "commitSha": SHA}
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    bodies = ["<!-- marketplace-validation -->\nQuattro compatibility passed at commit `aaaaaaa`\n**Ready for listing review.**",
              f"<!-- marketplace-security-baseline:v4 {encoded} -->"]
    return [{"user": {"login": "github-actions[bot]"},
             "performed_via_github_app": {"slug": "github-actions"}, "body": b}
            for b in bodies]


class ReviewTests(unittest.TestCase):
    def test_matching_remote_reports(self):
        self.assertIn(SHA, check(lambda path: reports() if "/comments?" in path else {"sha": SHA}))

    def test_drift(self):
        def read(path):
            if "/comments?" in path:
                return reports()
            return {"sha": "b" * 40 if path.endswith("/main") else SHA}
        with self.assertRaisesRegex(ValueError, "Review drift"):
            check(read)

    def test_missing_duplicate_and_spoofed_reports(self):
        spoof = copy.deepcopy(reports())
        spoof[0]["performed_via_github_app"] = None
        for comments in ([], reports()[:1], reports() + reports()[:1], spoof):
            with self.subTest(comments=comments), self.assertRaises(ValueError):
                report_refs(comments)

    def test_malformed_baseline(self):
        comments = reports()
        comments[1]["body"] = "<!-- marketplace-security-baseline:v5 broken -->"
        with self.assertRaises(ValueError):
            report_refs(comments)

    def test_pagination_and_concurrent_change(self):
        calls = []
        def read(path):
            calls.append(path)
            if path.endswith("&page=1"):
                return [{}] * 100
            if path.endswith("&page=2"):
                return reports()
            return {"sha": SHA}
        self.assertIn(SHA, check(read))
        self.assertTrue(any("page=2" in p for p in calls))
        heads = iter([SHA, "b" * 40])
        def moving(path):
            if "/comments?" in path:
                return reports()
            return {"sha": next(heads) if path.endswith("/main") else SHA}
        with self.assertRaisesRegex(ValueError, "changed during"):
            check(moving)
