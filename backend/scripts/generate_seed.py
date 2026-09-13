"""Generates supabase/seed.sql: StudioCo agency + 15 mock accounts with
8 weeks of signal_snapshot history each, matching supabase/schema.sql.

Run: python backend/scripts/generate_seed.py
Output is deterministic (fixed RNG seed + fixed UUIDs) so re-running
overwrites supabase/seed.sql with the same data.

Not idempotent against a live database: re-running the generated SQL
against Supabase inserts a second copy of StudioCo. To re-seed, first run
`delete from agency where name = 'StudioCo';` (cascades to accounts and
their signal_snapshot/baseline/health_score/alert rows).
"""

import random
import uuid
from datetime import date, timedelta
from pathlib import Path

RNG_SEED = 42
# Fixed namespace so account/snapshot UUIDs are stable across re-runs
# (uuid5 is deterministic given the same namespace + name).
NAMESPACE = uuid.UUID("2f6a5f2e-2b3a-4a8a-9a3e-cccccccccccc")

ACCOUNT_NAMES = [
    "Meridian Creative",
    "Northwind Digital",
    "Bluepeak Media",
    "Foundry & Co",
    "Lattice Brand Studio",
    "Harbor Row Agency",
    "Cobalt Collective",
    "Anchor & Ives",
    "Prism Digital Works",
    "Wren House Studio",
    "Fieldstone Marketing",
    "Vantage Point Media",
    "Solstice Creative Group",
    "Timberline Digital",
    "Echo & Oak",
]

# 0-indexed positions in ACCOUNT_NAMES that get a baked-in worsening trend.
WORSENING_INDEXES = {2, 7, 12}  # Bluepeak Media, Anchor & Ives, Solstice Creative Group

# Of the worsening accounts, this one also gets a new point of contact in
# its final period — on top of its existing signal drift, so the demo shows
# contact_changed joining signals_fired on an account that already alerts,
# rather than needing its own scenario to prove the signal works at all.
CONTACT_TURNOVER_INDEXES = {7}  # Anchor & Ives

WEEKS = 8


def slugify(name: str) -> str:
    # Turns an account name into an email-domain-safe slug, e.g.
    # "Foundry & Co" -> "foundry-co", for building fake contact emails.
    return name.lower().replace(" & ", "-").replace(" ", "-").replace("--", "-")


def stable_uuid(*parts: str) -> str:
    # Deterministic UUID derived from the given parts, so re-generating the
    # seed file produces identical IDs (helps with diffing/idempotency checks).
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def sql_str(value: str) -> str:
    # Quotes a Python string as a SQL string literal, escaping embedded quotes.
    return "'" + value.replace("'", "''") + "'"


CONTACT_FIRST_NAMES = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie"]
CONTACT_LAST_NAMES = ["Reed", "Kim", "Patel", "Nguyen", "Ortiz", "Chen", "Brooks", "Diaz"]


def build_accounts(rng: random.Random, agency_id: str) -> list[dict]:
    # Builds the 15 mock account records: contract terms, start date, and a
    # fake primary contact email derived from the account name. Accounts in
    # CONTACT_TURNOVER_INDEXES get two contact identities — the original
    # (used for early periods) and a new one (used from the turnover period
    # onward) — with the account record itself always reflecting the
    # *current* contact, matching how a real account would look after a
    # stakeholder change.
    accounts = []
    for idx, name in enumerate(ACCOUNT_NAMES):
        contract_value = rng.choice([3000, 4500, 6000, 7500, 8500, 10000, 12500, 15000, 18000, 22000, 25000])
        days_ago = rng.randint(120, 900)
        contract_start = date.today() - timedelta(days=days_ago)
        contact_first = rng.choice(CONTACT_FIRST_NAMES)
        contact_last = rng.choice(CONTACT_LAST_NAMES)
        slug = slugify(name)
        original_email = f"{contact_first.lower()}.{contact_last.lower()}@{slug}.com"

        new_email = None
        if idx in CONTACT_TURNOVER_INDEXES:
            new_first = rng.choice([n for n in CONTACT_FIRST_NAMES if n != contact_first])
            new_last = rng.choice([n for n in CONTACT_LAST_NAMES if n != contact_last])
            new_email = f"{new_first.lower()}.{new_last.lower()}@{slug}.com"

        accounts.append(
            {
                "id": stable_uuid("account", name),
                "agency_id": agency_id,
                "name": name,
                "contract_value_monthly": contract_value,
                "contract_start_date": contract_start.isoformat(),
                "primary_contact_email": new_email or original_email,
                "_original_contact_email": original_email,
                "_new_contact_email": new_email,
            }
        )
    return accounts


def week_periods(anchor_end: date, weeks: int) -> list[tuple[date, date]]:
    # Builds `weeks` consecutive 7-day (Mon-Sun) periods ending on anchor_end,
    # oldest first, e.g. [(w1_start, w1_end), ..., (w8_start, anchor_end)].
    periods = []
    for i in range(weeks):
        end = anchor_end - timedelta(weeks=(weeks - 1 - i))
        start = end - timedelta(days=6)
        periods.append((start, end))
    return periods


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_snapshots(rng: random.Random, account: dict, worsening: bool, periods: list[tuple[date, date]]) -> list[dict]:
    # Generates one signal_snapshot row per period for this account.
    # Healthy accounts get small random jitter around a stable baseline;
    # "worsening" accounts get a drift applied on top that ramps up over the
    # 8-week window (steepest in the last 3 periods) so the downstream
    # baseline/alerting logic has a clear trend to detect.
    base_response_hours = rng.uniform(2.0, 6.0)
    base_thread_count = rng.randint(15, 40)
    base_meetings_scheduled = rng.randint(2, 5)
    base_meetings_cancelled = rng.choice([0, 0, 0, 1])
    base_invoice_days_late = rng.choice([0, 0, 1, 2])

    original_email = account["_original_contact_email"]
    new_email = account.get("_new_contact_email")

    snapshots = []
    n = len(periods)
    for week_idx, (start, end) in enumerate(periods):
        # The new contact only shows up in the final period — "just
        # happened" — so it lands inside the 3-period trend window and
        # shows up in that alert's signals_fired.
        contact_email = new_email if (new_email and week_idx == n - 1) else original_email

        if worsening:
            # progress goes 0 -> 1 across the window, with an exponent >1 so
            # the drift accelerates rather than growing linearly (worse in
            # the most recent weeks, which is what the trend check needs).
            progress = (week_idx / (n - 1)) ** 1.6
            response_hours = base_response_hours + progress * rng.uniform(10, 18)
            thread_count = max(2, round(base_thread_count - progress * rng.uniform(8, 20)))
            meetings_scheduled = max(0, round(base_meetings_scheduled - progress * rng.uniform(1, 3)))
            meetings_cancelled = round(base_meetings_cancelled + progress * rng.uniform(1, 3))
            invoice_days_late = round(base_invoice_days_late + progress * rng.uniform(10, 22))
        else:
            # Healthy account: just jitter around the baseline, clamped/floored
            # so values stay realistic (no negative meeting counts, etc).
            jitter = lambda spread: rng.uniform(-spread, spread)
            response_hours = clamp(base_response_hours + jitter(0.6), 0.5, 12)
            thread_count = max(1, round(base_thread_count + jitter(3)))
            meetings_scheduled = max(0, round(base_meetings_scheduled + jitter(1)))
            meetings_cancelled = max(0, round(base_meetings_cancelled + jitter(1)))
            invoice_days_late = max(0, round(base_invoice_days_late + jitter(1)))

        snapshots.append(
            {
                "id": stable_uuid("snapshot", account["id"], start.isoformat()),
                "account_id": account["id"],
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "avg_response_time_hours": round(response_hours, 2),
                "email_thread_count": int(thread_count),
                "meetings_scheduled": int(meetings_scheduled),
                "meetings_cancelled": int(meetings_cancelled),
                "invoice_days_late": int(invoice_days_late),
                "primary_contact_email": contact_email,
            }
        )
    return snapshots


def render_sql(
    agency_id: str,
    accounts: list[dict],
    snapshots_by_account: dict[str, list[dict]],
    worsening_names: list[str],
    turnover_names: list[str],
) -> str:
    # Renders the generated data as a single SQL script with a header
    # comment, one multi-row INSERT for accounts, and one for signal_snapshot.
    lines = [
        "-- ClientPulse seed data: StudioCo agency + 15 mock accounts, 8 weeks of",
        "-- signal_snapshot history each. Generated by backend/scripts/generate_seed.py",
        "-- Run this after supabase/schema.sql has been applied.",
        "--",
        "-- Accounts with a baked-in worsening trend (for demo/alerting):",
        *[f"--   - {name}" for name in worsening_names],
        "--",
        "-- Of those, this one also gets a new point of contact in its final",
        "-- period, so its alert's signals_fired includes contact_changed:",
        *[f"--   - {name}" for name in turnover_names],
        "--",
        "-- Not idempotent: re-running this against a database that already has",
        "-- StudioCo will insert a duplicate copy. To re-seed from scratch first run:",
        "--   delete from agency where name = 'StudioCo';",
        "",
        f"insert into agency (id, name) values",
        f"  ({sql_str(agency_id)}, {sql_str('StudioCo')});",
        "",
        "insert into account (id, agency_id, name, contract_value_monthly, contract_start_date, primary_contact_email) values",
    ]

    # Build one VALUES row per account.
    account_rows = []
    for a in accounts:
        account_rows.append(
            "  ({id}, {agency_id}, {name}, {value}, {start}, {email})".format(
                id=sql_str(a["id"]),
                agency_id=sql_str(a["agency_id"]),
                name=sql_str(a["name"]),
                value=a["contract_value_monthly"],
                start=sql_str(a["contract_start_date"]),
                email=sql_str(a["primary_contact_email"]),
            )
        )
    lines.append(",\n".join(account_rows) + ";")
    lines.append("")

    # Build one VALUES row per (account, week) signal_snapshot.
    lines.append(
        "insert into signal_snapshot (id, account_id, period_start, period_end, avg_response_time_hours, "
        "email_thread_count, meetings_scheduled, meetings_cancelled, invoice_days_late, primary_contact_email) values"
    )
    snapshot_rows = []
    for account in accounts:
        for s in snapshots_by_account[account["id"]]:
            snapshot_rows.append(
                "  ({id}, {account_id}, {start}, {end}, {resp}, {threads}, {sched}, {cancelled}, {late}, {email})".format(
                    id=sql_str(s["id"]),
                    account_id=sql_str(s["account_id"]),
                    start=sql_str(s["period_start"]),
                    end=sql_str(s["period_end"]),
                    resp=s["avg_response_time_hours"],
                    threads=s["email_thread_count"],
                    sched=s["meetings_scheduled"],
                    cancelled=s["meetings_cancelled"],
                    late=s["invoice_days_late"],
                    email=sql_str(s["primary_contact_email"]),
                )
            )
    lines.append(",\n".join(snapshot_rows) + ";")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    rng = random.Random(RNG_SEED)
    agency_id = stable_uuid("agency", "StudioCo")

    accounts = build_accounts(rng, agency_id)

    # Anchor the most recent period on the last fully-completed week (the
    # most recent Sunday) so the seed data always looks like real history,
    # regardless of what day the script is run on.
    anchor_end = date.today()
    anchor_end -= timedelta(days=(anchor_end.weekday() + 1) % 7)  # roll back to most recent Sunday
    periods = week_periods(anchor_end, WEEKS)

    snapshots_by_account = {}
    worsening_names = []
    turnover_names = []
    for idx, account in enumerate(accounts):
        worsening = idx in WORSENING_INDEXES
        if worsening:
            worsening_names.append(account["name"])
        if idx in CONTACT_TURNOVER_INDEXES:
            turnover_names.append(account["name"])
        snapshots_by_account[account["id"]] = build_snapshots(rng, account, worsening, periods)

    sql = render_sql(agency_id, accounts, snapshots_by_account, worsening_names, turnover_names)

    # Write to supabase/seed.sql relative to the repo root (two levels up
    # from backend/scripts/).
    out_path = Path(__file__).resolve().parents[2] / "supabase" / "seed.sql"
    out_path.write_text(sql, encoding="utf-8")
    print(f"Wrote {out_path} ({len(accounts)} accounts, {len(accounts) * WEEKS} signal_snapshot rows)")


if __name__ == "__main__":
    main()
