"""Regression tests for exact-code dictionary names missing from the registry."""
import unittest
from app.scripts.build_facility_registry import facility_name


class FacilityNameEvidenceTests(unittest.TestCase):
    def test_missing_legacy_name_keeps_source_locator(self):
        evidence = [{'code': 'DT_0095', 'name': '비금도', 'sha256': 'evidence', 'sheet': 'GD_OBS_ST', 'row': 60}]
        name, detail = facility_name(None, evidence)
        self.assertEqual(name, '비금도')
        self.assertEqual(detail['dictionary_evidence'], evidence)
        self.assertFalse(detail['identity_approved'])

    def test_two_source_names_do_not_choose_a_winner(self):
        name, detail = facility_name(None, [{'name': '이전 시설'}, {'name': '신규 시설'}])
        self.assertIsNone(name)
        self.assertEqual(detail['status'], 'CONFLICT')

    def test_legacy_conflict_preserves_both_claims(self):
        name, detail = facility_name('독도(구)', [{'name': '독도'}])
        self.assertEqual(name, '독도(구)')
        self.assertEqual(detail['status'], 'CONFLICT')
        self.assertEqual(detail['dictionary_names'], ['독도'])

    def test_duplicate_evidence_is_not_a_name_conflict(self):
        name, detail = facility_name('', [{'name': '비금도'}, {'name': '비금도'}])
        self.assertEqual(name, '비금도')
        self.assertEqual(detail['status'], 'SOURCE_DICTIONARY_EXACT_CODE')

    def test_missing_names_stay_missing(self):
        name, detail = facility_name(None, [{'name': None}, {'name': ' '}])
        self.assertIsNone(name)
        self.assertEqual(detail['status'], 'MISSING')


if __name__ == '__main__':
    unittest.main()
