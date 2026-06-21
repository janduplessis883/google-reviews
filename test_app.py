import unittest

from app import build_draft_response, build_email, classify_review, normalize_review


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

    def test_normalizes_nested_zapier_data_fields(self):
        review = normalize_review(
            {
                "payload_type": "json",
                "data": {
                    "reviewer": "David Korn",
                    "comment": "very thorough charming attention. no complaints only compliments",
                    "number_rating": 5,
                    "created_time": "2026-05-14T10:31:13.473785Z",
                    "star_rating": "FIVE",
                    "average_rating": 3.9000000953674316,
                },
            }
        )

        self.assertEqual(review["reviewerName"], "David Korn")
        self.assertEqual(review["rating"], 5)
        self.assertEqual(
            review["reviewText"],
            "very thorough charming attention. no complaints only compliments",
        )
        self.assertEqual(review["createdAt"], "2026-05-14T10:31:13.473785Z")

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

    def test_builds_plain_text_email(self):
        review = {
            "businessName": "Stanhope Mews Surgery",
            "reviewerName": "David Korn",
            "rating": 5,
            "reviewText": "Very thorough charming attention.",
            "reviewUrl": "https://example.com/review",
            "createdAt": "2026-05-14T10:31:13.473785Z",
        }
        draft = build_draft_response(review)

        subject, body = build_email(review, draft)

        self.assertEqual(subject, "New Google Review: 5/5 from David Korn")
        self.assertIn("Reviewer: David Korn", body)
        self.assertIn("Draft response:", body)
        self.assertIn(draft["draftResponse"], body)


if __name__ == "__main__":
    unittest.main()
