import json
from flask import Flask, render_template, redirect, url_for
from state_store import get_connection, list_pending, mark_decided
from crm_client import update_account, create_account, list_all_accounts
import config

app = Flask(__name__)


@app.route("/")
def index():
    conn = get_connection()
    pending = list_pending(conn)

    # Fetch all accounts once, build a lookup by id, so we can show
    # "current value" alongside "proposed value" for every card
    accounts = list_all_accounts()
    accounts_by_id = {a["account_id"]: a for a in accounts}

    for p in pending:
        p["payload"] = json.loads(p["payload"])
        acct_id = p["payload"].get("account_id") or p["payload"].get("old_account_id")
        p["current_account"] = accounts_by_id.get(acct_id)

    return render_template("review.html", proposals=pending)


@app.route("/approve/<key>", methods=["POST"])
def approve(key):
    conn = get_connection()
    row = conn.execute("SELECT * FROM proposals WHERE proposal_key = ?", (key,)).fetchone()
    payload = json.loads(row["payload"])

    apply_to_crm(payload)
    mark_decided(conn, key, "approved")
    return redirect(url_for("index"))


@app.route("/reject/<key>", methods=["POST"])
def reject(key):
    conn = get_connection()
    mark_decided(conn, key, "rejected")
    return redirect(url_for("index"))


def apply_to_crm(proposal):
    """Executes the real CRM write for one approved proposal."""
    ptype = proposal["type"]

    if ptype == "new_account":
        create_account(proposal["fields"])

    elif ptype in ("field_update", "reparent", "duplicate", "orphan_needs_review"):
        update_account(proposal["account_id"], proposal["patch"])

    elif ptype == "chow":
        new_account = create_account(proposal["new_account_fields"])
        new_id = new_account["account_id"]
        update_account(proposal["old_account_id"], {config.FIELD_CHOW_CURRENT: new_id})


if __name__ == "__main__":
    app.run(debug=True, port=5000)