from scraper import scrape_all_locations
from crm_client import list_all_accounts, get_bellhaven_parent_id
from matcher import run_matching
from state_store import get_connection, add_proposal, already_exists, make_key


def main():
    print("Scraping website...")
    locations = scrape_all_locations()
    print(f"  found {len(locations)} locations")

    print("Fetching CRM accounts...")
    accounts = list_all_accounts()
    print(f"  found {len(accounts)} accounts")

    print("Resolving Bellhaven parent account...")
    bellhaven_parent_id = get_bellhaven_parent_id()
    print(f"  resolved: {bellhaven_parent_id}")

    print("Running matcher...")
    proposals = run_matching(locations, accounts)
    print(f"  generated {len(proposals)} candidate proposals")

    print("Updating review queue...")
    conn = get_connection()
    inserted, skipped = 0, 0
    for p in proposals:
        key = make_key(p)
        if already_exists(conn, key):
            skipped += 1
            continue
        add_proposal(conn, p)
        inserted += 1

    print(f"Done. {inserted} new proposals added, {skipped} already known (skipped).")
    print("Run 'python review_app.py' to review and approve/reject.")


if __name__ == "__main__":
    main()