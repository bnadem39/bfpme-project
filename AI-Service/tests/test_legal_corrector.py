import unittest

from app.ocr.pdf_detector import is_text_corrupted
from app.preprocess.legal_corrector import correct_legal_references


class LegalCorrectorTests(unittest.TestCase):
    def test_repairs_broken_article_list(self):
        source = "مخالفة الفيتول10\n ي11\n ي60 من المجلة"
        expected = "مخالفة الفصول10 و11 و60 من المجلة"
        self.assertEqual(correct_legal_references(source), expected)

    def test_does_not_replace_ya_outside_numbers(self):
        source = "صدر الحكم في القضية"
        self.assertEqual(correct_legal_references(source), source)

    def test_detects_dense_double_letters_from_broken_text_layer(self):
        broken = ("المحكمررة بموجررب حكمهررا عرردد بترراريخ " * 8)
        self.assertTrue(is_text_corrupted(broken))


if __name__ == "__main__":
    unittest.main()
