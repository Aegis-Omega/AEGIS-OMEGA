#!/usr/bin/env python3
"""Source-bound documentation contract: source prices, README, and legacy runbooks.

Read-only; inspect immutable HEAD objects, not uncommitted working-tree edits.
This does not verify provider checkout, deployment status, or legal partner rights.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def committed(path: str) -> str:
    return subprocess.run(
        ["git", "show", "HEAD:" + path], cwd=ROOT, check=True,
        capture_output=True, text=True, encoding="utf-8",
    ).stdout


def fields(text: str, declaration: str, names: tuple[str, ...]) -> dict[str, str]:
    """Read simple literal fields from one named object; reject missing/ambiguous keys."""
    obj = re.search(r"\bconst\s+" + re.escape(declaration) +
                    r"\s*:[^=]*=\s*\{([^}]*)\}", text, re.S)
    if not obj:
        raise ValueError("DECLARATION_MISSING:" + declaration)
    out = {}
    for name in names:
        hits = re.findall(r"\b" + re.escape(name) + r"\s*:\s*'([^']+)'", obj.group(1))
        if len(hits) != 1:
            raise ValueError("FIELD_AMBIGUOUS:" + declaration + "." + name)
        out[name] = hits[0]
    return out


def dollars(value: str) -> Decimal:
    try:
        return Decimal(value.lstrip("$"))
    except InvalidOperation as exc:
        raise ValueError("NOT_MONEY:" + value) from exc


def checked_prices(ui: str, backend: str) -> dict[str, Decimal]:
    names = ("operator", "sovereign")
    ui_price = fields(ui, "TIER_PRICE", names)
    email_price = fields(backend, "prices", names)
    result = {n: dollars(ui_price[n]) for n in names}
    for n in names:
        if result[n] != dollars(email_price[n]):
            raise ValueError("UI_BACKEND_PRICE_MISMATCH:" + n)
    return result


class ParserRegressions(unittest.TestCase):
    UI = "const TIER_PRICE: Record<string,string> = { operator: '49.00', sovereign: '499.00' }"
    BACKEND = "const prices: Record<string,string> = { explorer: 'free', operator: '$49', sovereign: '$499' }"

    def test_agreement(self):
        self.assertEqual(checked_prices(self.UI, self.BACKEND),
                         {"operator": Decimal(49), "sovereign": Decimal(499)})

    def test_mismatch_is_denied(self):
        with self.assertRaisesRegex(ValueError, "UI_BACKEND_PRICE_MISMATCH"):
            checked_prices(self.UI, self.BACKEND.replace("$499", "$4999"))

    def test_ambiguous_field_is_denied(self):
        with self.assertRaisesRegex(ValueError, "FIELD_AMBIGUOUS"):
            checked_prices(self.UI.replace("sovereign:", "operator: '0', sovereign:"),
                           self.BACKEND)


class CurrentHeadDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = committed("README.md")
        cls.ui = committed("hub/src/components/PricingPage.tsx")
        cls.backend = committed("supabase/functions/verify-paypal/index.ts")

    def test_ui_backend_prices_agree(self):
        self.assertEqual(set(checked_prices(self.ui, self.backend)),
                         {"operator", "sovereign"})

    def test_readme_pricing_matches_code(self):
        prices = checked_prices(self.ui, self.backend)
        row = next((l for l in self.readme.splitlines() if "Get a key at " in l), "")
        match = re.search(r"Operator \(\$(\d+)\).*Sovereign \(\$(\d+)\)", row)
        self.assertIsNotNone(match, "README_PRICE_ROW_MISSING")
        self.assertEqual(Decimal(match.group(1)), prices["operator"])
        self.assertEqual(Decimal(match.group(2)), prices["sovereign"])

    def test_readme_routes_to_current_map_not_old_handoff(self):
        self.assertIn("docs/architecture/OPTIMUS_EVOLUTION.md", self.readme)
        self.assertIn("REPO_MAP.md", self.readme)
        self.assertNotIn("HANDOFF.md](HANDOFF.md) (current ground truth)", self.readme)
        self.assertIn("dated historical handoff", self.readme)

    def test_stale_product_price_not_advertised(self):
        self.assertNotIn("Commercial creator tools ($19 each)", self.readme)
        self.assertIn("Creator tools shown as included", self.readme)

    def test_deprecated_sales_runbook_is_marked(self):
        deploy = committed("DEPLOY.md").splitlines()[:5]
        gumroad = committed("docs/GUMROAD_LISTINGS.md").splitlines()[:5]
        self.assertTrue(any("HISTORICAL DEPLOYMENT GUIDE" in x for x in deploy))
        self.assertTrue(any("HISTORICAL SALES COPY" in x for x in gumroad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
