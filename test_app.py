import unittest

from app import build_draft_response, classify_review, normalize_review


class ReviewResponseTests(unittest.TestCase):
    def test_normalizes_common_zapier_review_fields(self):
        review = normalize_review(
            {
                "business": "Stanhope Mews Surgery",
                "authorName": "Jane Smith",
                "starRating": "2 stars",
                "comment": "Hard to get through on the phone",
                "url": "https://example.com/review",
            }
        )

        self.assertEqual(review["businessName"], "Stanhope Mews Surgery")
        self.assertEqual(review["reviewerName"], "Jane Smith")
        self.assertEqual(review["rating"], 2)
        self.assertEqual(review["reviewText"], "Hard to get through on the phone")
        self.assertEqual(review["reviewUrl"], "https://example.com/review")

    def test_uses_confidential_negative_response_for_low_ratings(self):
        result = build_draft_response(
            {
                "businessName": "Stanhope Mews Surgery",
                "rating": 1,
                "reviewText": "Very poor service",
            }
        )

        self.assertEqual(result["sentiment"], "negative")
        self.assertIn("patient confidentiality", result["draftResponse"])
        self.assertIn("cannot discuss individual circumstances", result["draftResponse"])

    def test_classifies_high_ratings_as_positive(self):
        self.assertEqual(
            classify_review(
                {
                    "rating": 5,
                    "reviewText": "Great team",
                }
            ),
            "positive",
        )


if __name__ == "__main__":
    unittest.main()
