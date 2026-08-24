# Bellhaven CRM Reconciliation

## Approach

The pipeline has four pieces, matching the assessment's required deliverables:

1. **Scraper** (`scraper.py`) — scrapes the live Bellhaven website's `/communities`
   list pages (following pagination via the "Next" link, not a hardcoded page
   count) and each community's individual detail page (for street address and
   zip, which aren't on the list cards).
2. **Matcher** (`matcher.py`) — matches each scraped location to a CRM account
   and classifies the outcome.
3. **Review app** (`review_app.py`, Flask) — shows every proposal with its
   supporting evidence (current CRM value vs. proposed value, side by side)
   and only writes to the CRM when a human clicks Approve.
4. **Schedule** (`.github/workflows/daily.yml`) — a GitHub Actions workflow
   that runs the pipeline daily.

## Matching logic

Facility names in this dataset are not reliable identifiers on their own —
senior-living chains reuse template names ("Manor," "Gardens," "Estates")
across unrelated cities. The real CRM data contains an "Amberly Manor" in
Colorado Springs, CO, which is a completely different facility from the
"Amberly Manor" the website lists in Hudson, OH.

Because of this, matching requires **city + state agreement first**, and only
ranks by name similarity (via `rapidfuzz`, threshold 82/100) among candidates
that already share a city. If no CRM account in that city has a similar
enough name, a fallback rule checks whether exactly one unmatched CRM account
in the same city **also has a closely matching street address** (≥80
similarity) — this catches facilities that were renamed so heavily that name
similarity alone misses them (e.g., "Sunny Acres Retirement Home" → "Bellhaven
Willow Creek," "Riverbend Manor Care Center" → "Bellhaven of Chagrin Falls").

**A real false positive was caught and fixed during review**: the first
version of this fallback matched only on city/state, and it incorrectly
matched "Bellhaven at Union Square" (a real website location) to "Union
Square Senior Living" (an unrelated existing CRM account in the same town,
completely different street address). This was caught during manual review by
comparing addresses, and the matcher was corrected to require address
agreement before accepting this kind of low-name-similarity match. This is
the reason the review step, not just the matcher, matters — the tool's first
guess was wrong, and the human-in-the-loop step caught it before it reached
the CRM.

## CHOW handling

Per the SOP: an account gets the CHOW treatment (preserve the old account
unchanged, create a new one under the correct parent, link via
`chow_current_account`) only if it has both `lifetime_revenue > 0` AND
`outstanding_ar > 0`. If either is missing, it's a direct reparent instead.

Two real accounts triggered CHOW: **Bellhaven of Marietta** (revenue $51,250,
AR $3,800, wrongly parented under Cedar Trail Communities) and **Bellhaven of
Tiffin** (revenue $84,000, AR $12,400, also under Cedar Trail). **Bellhaven
Crossings of Lima** was a useful contrast case: wrong parent, revenue $47,000,
but AR = $0 — correctly handled as a direct reparent, not a CHOW, confirming
the AND logic in the rule works as intended on real data.

## Duplicates and orphans

One real duplicate pair was found: two identical "Bellhaven of Owosso"
records under the correct parent. The one with the lower/no revenue was
marked `Inactive` with `duplicate_of_account` pointing at the survivor.

Accounts under the Bellhaven parent that don't appear on the current website
are flagged `Needs Review` with an explanatory note — never auto-deactivated,
since a scrape miss and a genuine closure look identical from this data alone,
and only a human should make that call.

## Idempotency

Every proposal is fingerprinted (SHA-256 hash of account id + change type +
target values) and stored in a local SQLite file (`state.db`). Before
inserting a new proposal, the pipeline checks whether that exact fingerprint
already exists — pending, approved, or rejected — and skips it if so. This
was verified directly: running `pipeline.py` twice in a row with no changes
produced "0 new proposals, N already known" on the second run, and proposals
that were manually marked approved/rejected did not reappear on a subsequent
run.

## Known limitations

- Matching relies on city/state + name/address heuristics, not a unique
  external identifier. It's possible (though not observed in this dataset)
  for two unrelated facilities to share both a city and a similar enough
  name/address to produce a false match.
- `state.db` is a local file; the GitHub Actions workflow commits it back to
  the repo between runs as a simple way to persist state in CI. A production
  deployment would more likely use a real persistent database.
- Care offerings from the website are joined into a single `care_type` string
  on write; the CRM's own care_type field appears to expect a single value
  per account, so this may need refinement if a facility has multiple
  distinct offerings on the website.
