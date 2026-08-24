import requests
import config


class CRMError(Exception):
    """Custom error type so our code can distinguish 'the CRM API failed'
    from Python's normal built-in errors."""
    pass

def _headers():
    return {"Authorization": f"Bearer {config.CRM_API_TOKEN}"}

def list_all_accounts():
    """
    Fetches every account from the CRM, looping through all pages
    automatically. Returns a plain list of account dicts.
    """
    all_accounts = []
    page = 1

    while True:
        response = requests.get(
            f"{config.CRM_API_BASE}/accounts",
            headers=_headers(),
            params={"page": page},
        )
        if response.status_code != 200:
            raise CRMError(f"Failed to list accounts (page {page}): {response.status_code} {response.text}")

        data = response.json()
        all_accounts.extend(data["data"])

        if len(all_accounts) >= data["total"]:
            break
        page += 1

    return all_accounts

def get_account(account_id):
    """Fetches a single account by its id. Returns the account dict."""
    response = requests.get(
        f"{config.CRM_API_BASE}/accounts/{account_id}",
        headers=_headers(),
    )
    if response.status_code != 200:
        raise CRMError(f"Failed to get account {account_id}: {response.status_code} {response.text}")
    return response.json()


def update_account(account_id, fields):
    """
    Sends a PATCH request to update one or more fields on an existing
    account. `fields` is a dict of just the fields you want to change,
    e.g. {"status": "Inactive", "note": "duplicate of X"}.
    Returns the small confirmation response (NOT the full updated account -
    
    """
    response = requests.patch(
        f"{config.CRM_API_BASE}/accounts/{account_id}",
        headers=_headers(),
        json=fields,
    )
    if response.status_code != 200:
        raise CRMError(f"Failed to update account {account_id}: {response.status_code} {response.text}")
    return response.json()


def create_account(fields):
    """
    Sends a POST request to create a brand-new account. `fields` is a dict
    of the new account's data. Returns the response, which includes the
    new account_id (confirmed via testing).
    """
    response = requests.post(
        f"{config.CRM_API_BASE}/accounts",
        headers=_headers(),
        json=fields,
    )
    if response.status_code != 201:
        raise CRMError(f"Failed to create account: {response.status_code} {response.text}")
    return response.json()

def get_bellhaven_parent_id():
    """
    Dynamically finds the Bellhaven Senior Living parent account id at
    runtime rather than relying on a hardcoded value. This means the
    pipeline works correctly even if the sandbox resets or this is deployed
    against a different CRM instance.
    """
    accounts = list_all_accounts()
    for a in accounts:
        if "bellhaven senior living" in a["name"].lower() and not a["parent_id"]:
            return a["account_id"]
    raise CRMError("Could not find Bellhaven Senior Living parent account in CRM.")