import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aegis_crm_presync_gate import InvalidInput, evaluate, main  # noqa: E402


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)

    def csv(self, name, headers, rows):
        path = self.p / name
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return path

    def crm(self, rows=None):
        if rows is None:
            rows = [["100", "Case@Example.Test", "", "", "Acme"]]
        return self.csv("crm.csv", ["hs_object_id", "email", "phone", "mobilephone", "company"], rows)

    def src(self, name, rows):
        return self.csv(f"{name}.csv", ["source_record_id", "email", "phone", "company"], rows)

    def single(self, crm_rows=None, source_rows=None):
        crm = self.crm(crm_rows)
        source = self.src("google_contacts", source_rows if source_rows is not None else [["g1", "case@example.test", "", "Acme"]])
        return evaluate(crm, {"google_contacts": source}, ("google_contacts",))

    def test_primary_email_normalizes_to_review_candidate(self):
        obj = self.single(source_rows=[["g1", " CASE@EXAMPLE.TEST ", "", "Acme"]])
        self.assertEqual(obj["candidates"][0]["verdict"], "MATCH_REVIEW")
        self.assertEqual(obj["candidates"][0]["candidate_crm_id"], "100")
        self.assertFalse(obj["can_enable_sync"])

    def test_unmatched_never_creates_record(self):
        obj = self.single(source_rows=[["g1", "new@example.test", "", ""]])
        self.assertEqual(obj["candidates"][0]["verdict"], "UNMATCHED_HOLD")
        self.assertIsNone(obj["candidates"][0]["candidate_crm_id"])

    def test_duplicate_crm_primary_email_is_hold(self):
        obj = self.single(crm_rows=[["100", "case@example.test", "", "", ""], ["101", "CASE@example.test", "", "", ""]])
        self.assertEqual(obj["candidates"][0]["verdict"], "CRM_COLLISION_HOLD")
        self.assertEqual(obj["crm"]["duplicate_primary_email_groups"], 1)

    def test_cross_source_overlap_has_no_automerge(self):
        c = self.crm()
        g = self.src("google_contacts", [["g1", "case@example.test", "", ""]])
        o = self.src("outlook_default", [["o1", "case@example.test", "", ""]])
        x = evaluate(c, {"google_contacts": g, "outlook_default": o}, ("google_contacts", "outlook_default"))
        self.assertEqual(x["cross_source_email_overlap_groups"], 1)
        self.assertEqual([a["verdict"] for a in x["candidates"]], ["CROSS_SOURCE_REVIEW"] * 2)

    def test_same_source_duplicate_email_not_cross_source(self):
        c = self.crm()
        g = self.src("google_contacts", [
            ["g1", "case@example.test", "", ""],
            ["g2", "CASE@example.test", "", ""],
        ])
        x = evaluate(c, {"google_contacts": g}, ("google_contacts",))
        self.assertEqual(x["cross_source_email_overlap_groups"], 0)
        self.assertEqual(x["same_source_duplicate_email_groups"], 1)
        self.assertEqual([a["verdict"] for a in x["candidates"]], ["FIELD_REVIEW"] * 2)
        self.assertTrue(all("DUPLICATE_EMAIL_WITHIN_SOURCE" in a["flags"] for a in x["candidates"]))
        self.assertFalse(x["can_merge"])

    def test_same_source_and_cross_source_flag_both(self):
        c = self.crm()
        g = self.src("google_contacts", [
            ["g1", "case@example.test", "", ""],
            ["g2", "CASE@example.test", "", ""],
        ])
        o = self.src("outlook_default", [["o1", "case@example.test", "", ""]])
        x = evaluate(c, {"google_contacts": g, "outlook_default": o},
                     ("google_contacts", "outlook_default"))
        self.assertEqual(x["cross_source_email_overlap_groups"], 1)
        self.assertEqual(x["same_source_duplicate_email_groups"], 1)
        self.assertEqual(x["verdict_counts"], {"CROSS_SOURCE_REVIEW": 3})
        self.assertEqual(x["flag_counts"]["DUPLICATE_EMAIL_WITHIN_SOURCE"], 2)
        self.assertEqual(x["flag_counts"]["CROSS_SOURCE_EMAIL_OVERLAP"], 3)
        self.assertFalse(x["can_enable_sync"])

    def test_missing_source_is_unknown_not_zero(self):
        x = evaluate(self.crm(), {"google_contacts": self.src("google_contacts", [])})
        self.assertEqual(x["missing_source_snapshots"], ["outlook_default", "outlook_iphone"])
        self.assertEqual(list(x["source_snapshots"]), ["google_contacts"])
        self.assertEqual(x["status"], "INPUT_INCOMPLETE_HOLD")

    def test_supplied_empty_file_is_zero_for_that_file_only(self):
        x = self.single(source_rows=[])
        self.assertEqual(x["source_snapshots"]["google_contacts"]["rows"], 0)
        self.assertEqual(x["status"], "CANDIDATES_EVALUATED_HOLD")

    def test_duplicate_source_record_id_is_invalid(self):
        with self.assertRaises(InvalidInput):
            self.single(source_rows=[["dup", "case@example.test", "", ""], ["dup", "x@example.test", "", ""]])

    def test_non_opaque_source_id_is_invalid(self):
        with self.assertRaises(InvalidInput):
            self.single(source_rows=[["case@example.test", "case@example.test", "", ""]])

    def test_email_missing_cannot_match_by_phone_or_name(self):
        x = self.single(source_rows=[["g1", "", "12345", "Acme"]])
        self.assertEqual(x["candidates"][0]["verdict"], "MISSING_EMAIL_HOLD")

    def test_email_malformed(self):
        x = self.single(source_rows=[["g1", "not-an-email", "", "Acme"]])
        self.assertEqual(x["candidates"][0]["verdict"], "INVALID_EMAIL_HOLD")

    def test_phone_gap_is_review_not_auto_fill(self):
        x = self.single(source_rows=[["g1", "case@example.test", "12345", "Acme"]])
        self.assertEqual(x["candidates"][0]["verdict"], "FIELD_REVIEW")
        self.assertIn("CRM_PHONE_EMPTY_SOURCE_HAS_VALUE", x["candidates"][0]["flags"])

    def test_phone_conflict(self):
        x = self.single(crm_rows=[["100", "case@example.test", "1234", "", "Acme"]],
                        source_rows=[["g1", "case@example.test", "9999", "Acme"]])
        self.assertIn("PHONE_CONFLICT", x["candidates"][0]["flags"])

    def test_company_disagreement(self):
        x = self.single(source_rows=[["g1", "case@example.test", "", "Other"]])
        self.assertIn("COMPANY_DISAGREEMENT", x["candidates"][0]["flags"])

    def test_duplicate_hubspot_object_id_invalid(self):
        with self.assertRaises(InvalidInput):
            self.single(crm_rows=[["100", "a@example.test", "", "", ""], ["100", "b@example.test", "", "", ""]])

    def test_output_has_no_pii(self):
        x = self.single(source_rows=[["g1", "case@example.test", "555-3223", "Acme"]])
        raw = json.dumps(x)
        for secret in ["case@example.test", "555-3223", "Acme"]:
            self.assertNotIn(secret, raw)
        self.assertIn("g1", raw)

    def test_deterministic_candidate_order(self):
        a = self.single(source_rows=[["z", "new@example.test", "", ""], ["a", "case@example.test", "", ""]])
        b = self.single(source_rows=[["a", "case@example.test", "", ""], ["z", "new@example.test", "", ""]])
        self.assertEqual(a["candidates"], b["candidates"])

    def test_real_fixture_three_sources(self):
        f = ROOT / "fixtures"
        x = evaluate(f / "crm.csv", {z: f / (z + ".csv") for z in ["google_contacts", "outlook_default", "outlook_iphone"]})
        self.assertEqual(x["crm"]["rows"], 2)
        self.assertEqual(len(x["candidates"]), 4)
        self.assertEqual(x["cross_source_email_overlap_groups"], 1)
        self.assertFalse(x["can_import"])

    def test_cli_incomplete_exit_code_three(self):
        c = self.crm()
        g = self.src("google_contacts", [])
        p = self.p / "out.json"
        self.assertEqual(main(["--crm", str(c), "--source", "google_contacts=" + str(g), "--out", str(p)]), 3)
        self.assertEqual(json.loads(p.read_text())["status"], "INPUT_INCOMPLETE_HOLD")

    def test_cli_bad_file_exit_code_two(self):
        out = self.p / "out.json"
        self.assertEqual(main(["--crm", str(self.p / "missing.csv"), "--out", str(out)]), 2)
        self.assertEqual(json.loads(out.read_text())["status"], "INVALID_INPUT_HOLD")


if __name__ == "__main__":
    unittest.main()
