# LeadFlow — credential-free intake automation (portfolio demo)

A self-contained Python demo for lead intake, validation, duplicate suppression, priority routing, SQLite persistence and CSV export. Uses only the Python standard library; runs on a local computer, without a cloud server, subscriptions, or paid APIs.

### Start and test

    python -m unittest -v test_leadflow.py
    python leadflow.py --db demo.db serve --port 8765

Sample request:

    curl -X POST http://127.0.0.1:8765/leads -H "Content-Type: application/json" -d "{\"name\":\"Sample\",\"email\":\"sample@example.org\",\"source\":\"web\",\"budget_usd\":700}"

    python leadflow.py --db demo.db export leads.csv

The POST endpoint returns 201 for a new lead and 200 for an email+source duplicate. GET /health shows counts. High-priority leads create **unsent** outbox events.

### Input validation and spreadsheet safety

- Lead budgets must be finite whole-dollar amounts within the accepted range; `NaN`, positive/negative infinity, and out-of-range values are rejected without crashing the HTTP handler.
- CSV export prefixes spreadsheet-formula-looking text (leading `=`, `+`, `-`, or `@`) with an apostrophe. This protects common spreadsheet import workflows, but spreadsheet behavior varies by application. The underlying SQLite record is unchanged; consumers requiring raw data should integrate directly with a validated API instead of opening CSV in a spreadsheet.
- The demonstration includes loopback HTTP regression tests and cross-version CI on Python 3.11 and 3.12.
- **Not production-ready:** public deployment still requires authentication, HTTPS, authorization, secrets management, retention and deletion policies, and rate limiting.

### Fixed-scope freelance service

For a client-approved first milestone: integrate one lead source with one destination (CRM, Airtable, Google Sheets or another API); include validation, idempotency, error logging, a runnable test, and a handover. I can provide a scope and estimate based on sample payloads and credentials supplied securely by the client.

### Transparency and safety

This is an independently tested **demonstration**, not a claim of prior paying-client delivery. The web server binds to 127.0.0.1, **not the internet**, and does not send real email/SMS or contact a CRM. Data is stored in local SQLite; only synthetic records should be used for tests. A live deployment would need authentication, HTTPS, PII retention policies, consent, rate limits, secrets storage, and monitoring.

To discuss a paid project, open a GitHub issue describing the technical problem without including customer data or secrets.