---
status: partial
phase: 01-gold-news-card-web-feed
source: [01-VERIFICATION.md]
started: 2026-04-27T23:55:00Z
updated: 2026-04-27T23:55:00Z
---

## Current Test

[awaiting human testing — all 3 items require Railway deploy + actual cron fire]

## Tests

### 1. WhatsApp end-to-end delivery
expected: `WHATSAPP_DELIVERY_ENABLED=true` set in Railway env. On the next 08:00 PT or 12:00 PT cron fire, a teaser WhatsApp message arrives within 2 min, < 400 chars, contains the feed URL, and follows the format "📊 Summary {time PT}: {1-sentence lead}. Read full → {feed_url}". On a forced failure (e.g., temporarily break a downstream call), a failure-alert message arrives independently with format "⚠️ Summary {time PT} FAILED: section(s) {failed_sections}. agent_run_id: {short_id}".
result: [pending — requires Railway env flip + cron fire]

### 2. Browser feed rendering after first cron fire
expected: Open `/` in browser; SummaryFeedPage renders the Gold News card with title "Summary as of {time PT} — {Month Day}". The Gold News section shows a 1-sentence "Why it matters" lead + 3-5 bullets with `(Source Name)` citations. Ontario Law and Ontario Stats sections render their stub empty-state copy. Status badge is HIDDEN when status='completed' (clean default), amber pill on 'partial', red pill on 'failed'. Markdown is sanitized — no `<script>`, no `<iframe>`, no `javascript:` URLs render (already covered by automated XSS tests but worth a visual confirm).
result: [pending — requires deploy + cron fire]

### 3. Legacy route preservation
expected: `/digest` route still loads DigestPage with prev/next navigation (existing v1.0 functionality). `/settings` route still loads SettingsPage with all 6 tabs (Watchlists, Keywords, Scoring, Notifications, Agent Runs, Schedule). `/queue` redirects to `/`. `/agents/:slug` (e.g., `/agents/breaking-news`) redirects to `/`. `/login` route still functional.
result: [pending — requires deploy + browser check]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

[none yet — all items are pending human validation, not failures]
