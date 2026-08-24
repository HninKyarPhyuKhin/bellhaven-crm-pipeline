import os
from dotenv import load_dotenv

load_dotenv()

# --- Base URLs ---
CRM_API_BASE = "https://analyst-assessment-production.up.railway.app/api/v1"
WEBSITE_BASE = "https://analyst-assessment-production.up.railway.app"

# --- Auth ---
CRM_API_TOKEN = os.environ["BELLHAVEN_CRM_TOKEN"]

# --- Known account field names (confirmed via real API testing) ---
FIELD_ID = "account_id"
FIELD_NAME = "name"
FIELD_PARENT_ID = "parent_id"
FIELD_PARENT_NAME = "parent_name"
FIELD_CITY = "billing_city"
FIELD_STATE = "billing_state"
FIELD_ZIP = "billing_zip"
FIELD_STREET = "billing_street"
FIELD_CARE_TYPE = "care_type"
FIELD_STATUS = "status"
FIELD_NOTE = "note"
FIELD_DUPLICATE_OF = "duplicate_of_account"
FIELD_CHOW_CURRENT = "chow_current_account"
FIELD_REVENUE = "lifetime_revenue"
FIELD_AR = "outstanding_ar"

# --- Valid status values ---
STATUS_ACTIVE = "Active"
STATUS_INACTIVE = "Inactive"
STATUS_NEEDS_REVIEW = "Needs Review"

# --- The Bellhaven parent account's real id (confirmed via API) ---
BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"

# --- Matching thresholds (we'll tune these once we test on real data) ---
FUZZY_NAME_MATCH_THRESHOLD = 82