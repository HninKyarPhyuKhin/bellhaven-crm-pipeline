import re
from rapidfuzz import fuzz
import config

# Common boilerplate words that show up in senior-living names but don't
# help us tell facilities apart - we strip these before comparing names.
NOISE_WORDS = re.compile(
    r"\b(senior living|assisted living|memory (support|care)|skilled nursing|"
    r"nursing (&|and) rehab(ilitation)?|health(care)? (centre|center|campus)|"
    r"short-term rehabilitation( (&|and) nursing)?|rehab(ilitation)? center|"
    r"care center|nursing home|retirement home|health campus|of )\b",
    re.IGNORECASE,
)
PARENT_TAG = re.compile(r"\(parent account\)", re.IGNORECASE)


def normalize_name(name):
    """Strips common boilerplate so names compare fairly."""
    n = PARENT_TAG.sub("", name)
    n = NOISE_WORDS.sub(" ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n.lower())
    n = re.sub(r"\s+", " ", n).strip()
    return n


def name_similarity(a, b):
    """Returns 0-100, how similar two names are after normalizing."""
    return fuzz.token_sort_ratio(normalize_name(a), normalize_name(b))


def address_similarity(a, b):
    """Loose comparison of two street addresses - handles abbreviation
    differences like 'Ave' vs 'Avenue' by normalizing then fuzzy-matching."""
    if not a or not b:
        return 0
    norm_a = re.sub(r"[^a-z0-9 ]", "", a.lower())
    norm_b = re.sub(r"[^a-z0-9 ]", "", b.lower())
    return fuzz.token_sort_ratio(norm_a, norm_b)


def find_best_match(location, crm_accounts):
    """
    Finds the CRM account that best matches one website location.
    Requires city agreement first before ranking by name similarity,
    to avoid merging same-named facilities in different cities.
    Returns (best_account, score) or (None, 0) if nothing plausible found.
    """
    city = location.get("city", "").strip().lower()
    candidates = crm_accounts
    if city:
        candidates = [
            a for a in crm_accounts
            if (a.get(config.FIELD_CITY) or "").strip().lower() == city
        ]
        if not candidates:
            return None, 0

    best, best_score = None, 0
    for acct in candidates:
        score = name_similarity(location["name"], acct.get(config.FIELD_NAME, ""))
        if score > best_score:
            best, best_score = acct, score
    return best, best_score


def find_rename_candidate(location, crm_accounts, already_matched_ids):
    """
    Fallback for facilities renamed so heavily that name similarity alone
    won't catch them. Requires city + state AND a closely matching street
    address before accepting a match. City/state alone isn't enough —
    two unrelated facilities can share a city (e.g. 'Bellhaven at Union
    Square' vs 'Union Square Senior Living', same city, different street —
    a real false positive we caught during review and guard against here).
    """
    city = location.get("city", "").strip().lower()
    state = location.get("state", "").strip().lower()
    website_street = location.get("street", "")
    if not city or not website_street:
        return None

    candidates = [
        a for a in crm_accounts
        if a[config.FIELD_ID] not in already_matched_ids
        and (a.get(config.FIELD_CITY) or "").strip().lower() == city
        and (a.get(config.FIELD_STATE) or "").strip().lower() == state
    ]

    address_verified = [
        a for a in candidates
        if address_similarity(website_street, a.get(config.FIELD_STREET, "")) >= 80
    ]

    if len(address_verified) == 1:
        return address_verified[0]
    return None


def needs_chow(account):
    """Per the SOP: CHOW is required only if BOTH revenue history exists
    AND there's outstanding AR right now."""
    revenue = account.get(config.FIELD_REVENUE) or 0
    ar = account.get(config.FIELD_AR) or 0
    return revenue > 0 and ar > 0


def classify_match(location, account, bellhaven_parent_id=None):
    """
    Given a website location matched to a CRM account, decides what change
    (if any) is needed. Returns a proposal dict, or None if already correct.
    """
    if bellhaven_parent_id is None:
        bellhaven_parent_id = config.BELLHAVEN_PARENT_ID

    field_diffs = {}
    if normalize_name(account.get(config.FIELD_NAME, "")) != normalize_name(location["name"]):
        field_diffs[config.FIELD_NAME] = location["name"]
    if location.get("street") and account.get(config.FIELD_STREET) != location["street"]:
        field_diffs[config.FIELD_STREET] = location["street"]
    if location.get("zip") and account.get(config.FIELD_ZIP) != location["zip"]:
        field_diffs[config.FIELD_ZIP] = location["zip"]

    wrong_parent = account.get(config.FIELD_PARENT_ID) != bellhaven_parent_id

    if wrong_parent:
        if needs_chow(account):
            return {
                "type": "chow",
                "old_account_id": account[config.FIELD_ID],
                "new_account_fields": {
                    config.FIELD_NAME: location["name"],
                    config.FIELD_PARENT_ID: bellhaven_parent_id,
                    config.FIELD_CITY: location.get("city", ""),
                    config.FIELD_STATE: location.get("state", ""),
                    config.FIELD_ZIP: location.get("zip", ""),
                    config.FIELD_STREET: location.get("street", ""),
                    config.FIELD_CARE_TYPE: ", ".join(location.get("care_offerings", [])),
                    config.FIELD_STATUS: config.STATUS_ACTIVE,
                    config.FIELD_NOTE: f"Created via CHOW from account {account[config.FIELD_ID]} due to outstanding AR.",
                },
            }
        else:
            patch = {config.FIELD_PARENT_ID: bellhaven_parent_id}
            patch.update(field_diffs)
            return {
                "type": "reparent",
                "account_id": account[config.FIELD_ID],
                "patch": patch,
            }

    if field_diffs:
        return {
            "type": "field_update",
            "account_id": account[config.FIELD_ID],
            "patch": field_diffs,
        }

    return None  # confident match, nothing to do


def new_account_proposal(location, bellhaven_parent_id=None):
    """Website location has no matching CRM account - propose creating one."""
    if bellhaven_parent_id is None:
        bellhaven_parent_id = config.BELLHAVEN_PARENT_ID

    return {
        "type": "new_account",
        "fields": {
            config.FIELD_NAME: location["name"],
            config.FIELD_PARENT_ID: bellhaven_parent_id,
            config.FIELD_CITY: location.get("city", ""),
            config.FIELD_STATE: location.get("state", ""),
            config.FIELD_ZIP: location.get("zip", ""),
            config.FIELD_STREET: location.get("street", ""),
            config.FIELD_CARE_TYPE: ", ".join(location.get("care_offerings", [])),
            config.FIELD_STATUS: config.STATUS_ACTIVE,
            config.FIELD_NOTE: "Created: found on website with no matching CRM account.",
        },
    }


def find_duplicates(bellhaven_accounts):
    """
    Finds CRM accounts under Bellhaven with identical normalized name +
    city + state. Keeps whichever has more revenue as the survivor.
    """
    proposals = []
    seen = {}
    for acct in bellhaven_accounts:
        key = (
            normalize_name(acct.get(config.FIELD_NAME, "")),
            (acct.get(config.FIELD_CITY) or "").lower(),
            (acct.get(config.FIELD_STATE) or "").lower(),
        )
        if key in seen:
            survivor = seen[key]
            loser = acct
            if (loser.get(config.FIELD_REVENUE) or 0) > (survivor.get(config.FIELD_REVENUE) or 0):
                survivor, loser = loser, survivor
            proposals.append({
                "type": "duplicate",
                "account_id": loser[config.FIELD_ID],
                "patch": {
                    config.FIELD_DUPLICATE_OF: survivor[config.FIELD_ID],
                    config.FIELD_STATUS: config.STATUS_INACTIVE,
                },
            })
        else:
            seen[key] = acct
    return proposals


def find_orphans(bellhaven_accounts, matched_ids):
    """CRM accounts under Bellhaven not matched to any website location -
    flagged for human review, never auto-deactivated."""
    proposals = []
    for acct in bellhaven_accounts:
        if acct[config.FIELD_ID] in matched_ids:
            continue
        if PARENT_TAG.search(acct.get(config.FIELD_NAME, "")):
            continue
        proposals.append({
            "type": "orphan_needs_review",
            "account_id": acct[config.FIELD_ID],
            "patch": {
                config.FIELD_STATUS: config.STATUS_NEEDS_REVIEW,
                config.FIELD_NOTE: "Not found on Bellhaven website during most recent scrape.",
            },
        })
    return proposals


def run_matching(website_locations, crm_accounts, bellhaven_parent_id=None):
    """
    Top-level entry point. Returns a list of proposal dicts covering every
    classification outcome.
    """
    if bellhaven_parent_id is None:
        bellhaven_parent_id = config.BELLHAVEN_PARENT_ID

    proposals = []
    matched_ids = set()

    for loc in website_locations:
        best, score = find_best_match(loc, crm_accounts)

        if best is None or score < config.FUZZY_NAME_MATCH_THRESHOLD:
            fallback = find_rename_candidate(loc, crm_accounts, matched_ids)
            if fallback is not None:
                matched_ids.add(fallback[config.FIELD_ID])
                result = classify_match(loc, fallback, bellhaven_parent_id)
                if result:
                    result["note_to_reviewer"] = "Low name similarity - matched on city/state only. Please verify this is the same facility."
                    proposals.append(result)
                continue
            proposals.append(new_account_proposal(loc, bellhaven_parent_id))
            continue

        matched_ids.add(best[config.FIELD_ID])
        result = classify_match(loc, best, bellhaven_parent_id)
        if result:
            proposals.append(result)

    bellhaven_accounts = [
        a for a in crm_accounts
        if a.get(config.FIELD_PARENT_ID) == bellhaven_parent_id
    ]
    bellhaven_accounts = [
        a for a in bellhaven_accounts
        if not a.get(config.FIELD_NAME, "").startswith("ZZTEST")
    ]
    proposals.extend(find_duplicates(bellhaven_accounts))
    proposals.extend(find_orphans(bellhaven_accounts, matched_ids))

    return proposals