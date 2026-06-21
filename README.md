# Google Reviews Webhook

Small Python Render web service that accepts Google Review data from Zapier and returns a safe draft response for Stanhope Mews Surgery.

## Endpoints

### Health check

```http
GET /health
```

### Zapier webhook

```http
POST /webhooks/google-review
```

Send JSON like:

```json
{
  "business": "Stanhope Mews Surgery",
  "authorName": "Jane Smith",
  "starRating": "2 stars",
  "comment": "Hard to get through on the phone",
  "url": "https://example.com/review"
}
```

The response includes:

```json
{
  "success": true,
  "sentiment": "negative",
  "draftResponse": "Thank you for your feedback...",
  "email": {
    "sent": true,
    "provider": "resend",
    "id": "..."
  }
}
```

## Local run

```bash
python app.py
```

Then test:

```bash
curl -X POST http://localhost:3000/webhooks/google-review \
  -H "content-type: application/json" \
  -H "x-webhook-secret: choose-a-long-random-secret" \
  -d '{"business":"Stanhope Mews Surgery","authorName":"Jane Smith","starRating":"2 stars","comment":"Hard to get through on the phone"}'
```

If `WEBHOOK_SECRET` is set, Zapier must send the same value in either:

- Header: `x-webhook-secret`
- Header: `Authorization: Bearer your-secret`
- Query string: `/webhooks/google-review?secret=your-secret`

Prefer the `x-webhook-secret` header in Zapier.

## Render setup

1. Push this project to GitHub.
2. In Render, create a new **Web Service** from the repo.
3. Use:
   - Build command: leave blank
   - Start command: `python app.py`
   - Health check path: `/health`
4. Add environment variables:
   - `PRACTICE_NAME=Stanhope Mews Surgery`
   - `WEBHOOK_SECRET=choose-a-long-random-secret`
   - `RESEND_API_KEY=your-resend-api-key`
   - `EMAIL_FROM=hello@attribut.me`
   - `EMAIL_TO=jan.duplessis@nhs.net`
5. In Zapier, POST review data to:

```text
https://your-render-service.onrender.com/webhooks/google-review
```

The first version intentionally creates draft replies only. Review them before posting publicly.

## Email alerts

When `RESEND_API_KEY` is configured, every accepted webhook sends a plain-text email alert through Resend.

Defaults:

```text
EMAIL_FROM=hello@attribut.me
EMAIL_TO=jan.duplessis@nhs.net
```

Make sure `hello@attribut.me` is a verified sender or domain in Resend.
