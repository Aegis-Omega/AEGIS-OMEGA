#!/usr/bin/env python3
"""RED-first contract for deterministic department templates.

Static template text is useful candidate material. It is not current empirical
verification, constitutional approval, risk clearance, or board authority.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import platform_helpers as ph


class TemplateEpistemicBoundaryTests(unittest.TestCase):
    def test_every_deterministic_template_is_explicit_t2_candidate(self):
        for mode in sorted(ph.VALID_MODES):
            for dept in ph.PLATFORM_DEPARTMENTS:
                output = ph.dept_output('objective', mode, dept)
                upper = output.upper()
                self.assertIn('SYNTHETIC TEMPLATE', upper, (mode, dept, output))
                self.assertIn('T2', upper, (mode, dept, output))
                self.assertIn('NOT VERIFIED', upper, (mode, dept, output))

    def test_regulatory_template_does_not_self_promote_to_t1(self):
        output = ph.dept_output('objective', 'regulatory', ph.PLATFORM_DEPARTMENTS[0])
        self.assertNotIn('[T1]', output)
        self.assertIn('[T2]', output)

    def test_constitutional_template_does_not_emit_valid_verdict(self):
        dept = next(d for d in ph.PLATFORM_DEPARTMENTS if d['category'] == 'constitutional')
        output = ph.dept_output('objective', 'analysis', dept)
        upper = output.upper()
        self.assertNotIn('T0 VERDICT VALID', upper)
        self.assertIn('CONSTITUTIONAL STATUS: NOT_EVALUATED', upper)

    def test_governance_template_does_not_clear_risk_or_ethics(self):
        dept = next(d for d in ph.PLATFORM_DEPARTMENTS if d['category'] == 'governance')
        output = ph.dept_output('objective', 'analysis', dept)
        upper = output.upper()
        self.assertNotIn('RISK: LOW', upper)
        self.assertNotIn('ETHICAL CONCERNS: NONE', upper)
        self.assertIn('RISK/ETHICS STATUS: NOT_EVALUATED', upper)

    def test_executive_template_does_not_claim_board_alignment(self):
        dept = next(d for d in ph.PLATFORM_DEPARTMENTS if d['category'] == 'executive')
        output = ph.dept_output('objective', 'analysis', dept)
        upper = output.upper()
        self.assertNotIn('STRATEGIC ALIGNMENT: CONFIRMED', upper)
        self.assertIn('BOARD/ALIGNMENT STATUS: NOT_EVALUATED', upper)


if __name__ == '__main__':
    unittest.main(verbosity=2)
