import unittest

from app.extraction.llm_extractor import normalize_result


class LlmExtractionNormalizationTests(unittest.TestCase):
    def test_masked_parties_and_missing_fields_are_null(self):
        result = normalize_result({
            "tribunal": "محكمة التعقيب",
            "parties": {"demandeur": "ح.ح", "defendeur": "س.س"},
        })
        self.assertIsNone(result["parties"]["demandeur"])
        self.assertIsNone(result["parties"]["defendeur"])
        self.assertIsNone(result["banque"])

    def test_normalizes_case_number_and_date(self):
        result = normalize_result({
            "numero_dossier": "68182.2019.دد القضية",
            "date_decision": "2020/10/13",
        })
        self.assertEqual(result["numero_dossier"], "68182/2019")
        self.assertEqual(result["date_decision"], "13/10/2020")


if __name__ == "__main__":
    unittest.main()
