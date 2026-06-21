import hmac
import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


PORT = int(os.environ.get("PORT", "3000"))
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
PRACTICE_NAME = os.environ.get("PRACTICE_NAME", "Stanhope Mews Surgery")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "hello@attribut.me")
EMAIL_TO = os.environ.get("EMAIL_TO", "jan.duplessis@nhs.net")
MAX_BODY_BYTES = 1024 * 1024


def first_present(payload, keys):
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return ""


def parse_rating(value):
    if isinstance(value, (int, float)):
        return int(value)

    star_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }
    normalized = str(value or "").strip().lower()

    if normalized in star_words:
        return star_words[normalized]

    match = re.search(r"[1-5]", normalized)
    return int(match.group(0)) if match else None


def normalize_review(payload):
    review_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    rating = parse_rating(
        first_present(
            review_payload,
            [
                "rating",
                "starRating",
                "star_rating",
                "stars",
                "number_rating",
                "review_rating",
                "reviewRating",
                "score",
            ],
        )
    )

    return {
        "businessName": str(
            first_present(review_payload, ["businessName", "business", "locationName"])
            or PRACTICE_NAME
        ),
        "reviewerName": str(
            first_present(review_payload, ["reviewerName", "authorName", "name", "reviewer"])
            or ""
        ),
        "rating": rating,
        "reviewText": str(
            first_present(review_payload, ["reviewText", "comment", "text", "review", "message"])
            or ""
        ),
        "reviewUrl": str(first_present(review_payload, ["reviewUrl", "url", "link"]) or ""),
        "createdAt": str(
            first_present(
                review_payload,
                ["createdAt", "created_time", "reviewCreatedAt", "publishedAt", "date"],
            )
            or ""
        ),
    }


def classify_review(review):
    rating = review.get("rating")

    if rating is not None:
        if rating >= 4:
            return "positive"
        if rating <= 2:
            return "negative"

    text = review.get("reviewText", "").lower()
    negative_terms = [
        "rude",
        "complaint",
        "terrible",
        "awful",
        "poor",
        "bad",
        "waiting",
        "wait",
        "phone",
        "appointment",
        "unhelpful",
        "ignored",
    ]

    if any(term in text for term in negative_terms):
        return "negative"

    return "neutral"


def build_draft_response(review):
    sentiment = classify_review(review)
    practice = review.get("businessName") or PRACTICE_NAME

    if sentiment == "positive":
        return {
            "sentiment": sentiment,
            "draftResponse": (
                "Thank you for taking the time to leave your feedback. "
                f"We are pleased to hear about your experience with {practice}, "
                "and we will share your comments with the team."
            ),
        }

    if sentiment == "negative":
        return {
            "sentiment": sentiment,
            "draftResponse": (
                "Thank you for your feedback. We are sorry to hear that your "
                "experience did not meet expectations. To protect patient "
                "confidentiality, we cannot discuss individual circumstances here, "
                "but we would welcome the opportunity to look into this directly. "
                f"Please contact {practice} so we can follow this up."
            ),
        }

    return {
        "sentiment": sentiment,
        "draftResponse": (
            "Thank you for sharing your feedback. We value comments from patients "
            f"and use them to help improve our service at {practice}."
        ),
    }


def build_email(review, draft):
    reviewer = review.get("reviewerName") or "Unknown reviewer"
    rating = review.get("rating")
    rating_text = f"{rating}/5" if rating is not None else "No rating provided"
    review_text = review.get("reviewText") or "No review text provided."
    review_url = review.get("reviewUrl") or "No review URL provided."
    created_at = review.get("createdAt") or "No date provided."

    subject = f"New Google Review: {rating_text} from {reviewer}"
    body = "\n".join(
        [
            f"New Google Review for {review.get('businessName') or PRACTICE_NAME}",
            "",
            f"Reviewer: {reviewer}",
            f"Rating: {rating_text}",
            f"Created: {created_at}",
            f"Review URL: {review_url}",
            "",
            "Review:",
            review_text,
            "",
            "Draft response:",
            draft.get("draftResponse", ""),
            "",
            "Safety notes:",
            "- Review this draft before publishing.",
            "- Do not confirm whether the reviewer is a patient.",
            "- Do not discuss clinical details or individual circumstances in public replies.",
        ]
    )

    return subject, body


def send_email_alert(review, draft):
    if not RESEND_API_KEY:
        return {
            "sent": False,
            "skipped": True,
            "reason": "RESEND_API_KEY is not configured.",
        }

    subject, body = build_email(review, draft)
    payload = json.dumps(
        {
            "from": EMAIL_FROM,
            "to": [EMAIL_TO],
            "subject": subject,
            "text": body,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
            resend_response = json.loads(response_body) if response_body else {}
            return {
                "sent": True,
                "provider": "resend",
                "id": resend_response.get("id"),
            }
    except urllib.error.HTTPError as error:
        return {
            "sent": False,
            "provider": "resend",
            "error": error.read().decode("utf-8"),
        }
    except urllib.error.URLError as error:
        return {
            "sent": False,
            "provider": "resend",
            "error": str(error.reason),
        }


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

    def send_json(self, status_code, body):
        response = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/health":
            self.send_json(
                200,
                {
                    "success": True,
                    "service": "google-reviews-webhook",
                },
            )
            return

        self.send_json(404, {"success": False, "error": "Not found."})

    def do_POST(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path != "/webhooks/google-review":
            self.send_json(404, {"success": False, "error": "Not found."})
            return

        if not self.is_authorized(parsed_url):
            self.send_json(401, {"success": False, "error": "Unauthorized webhook request."})
            return

        try:
            payload = self.read_json_body()
        except ValueError as error:
            self.send_json(400, {"success": False, "error": str(error)})
            return

        review = normalize_review(payload)
        draft = build_draft_response(review)
        email_status = send_email_alert(review, draft)

        self.send_json(
            200,
            {
                "success": True,
                "review": review,
                **draft,
                "email": email_status,
                "safetyNotes": [
                    "Draft only: review before publishing.",
                    "Do not confirm whether the reviewer is a patient.",
                    "Do not discuss clinical details or individual circumstances in public replies.",
                ],
            },
        )

    def is_authorized(self, parsed_url):
        if not WEBHOOK_SECRET:
            return True

        provided_secret = self.headers.get("x-webhook-secret", "")
        authorization = self.headers.get("authorization", "")

        if not provided_secret and authorization.startswith("Bearer "):
            provided_secret = authorization.removeprefix("Bearer ")

        if not provided_secret:
            query = parse_qs(parsed_url.query)
            provided_secret = query.get("secret", [""])[0]

        return hmac.compare_digest(provided_secret, WEBHOOK_SECRET)

    def read_json_body(self):
        content_length = int(self.headers.get("content-length", "0"))

        if content_length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large.")

        raw_body = self.rfile.read(content_length)

        if not raw_body.strip():
            return {}

        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("Request body must be valid JSON.")


def run():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Google reviews webhook listening on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
