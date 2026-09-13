"""Generate deterministic, scenario-rich ClientPulse demonstration data.

The output seeds one StudioCo agency with 48 mock accounts. Most accounts have
26 completed weekly signal snapshots; one intentionally new account has only six
weeks, so the scoring path is exercised against insufficient history too.

Run from the repository root or backend directory:
    python backend/scripts/generate_seed.py

The emitted SQL is deterministic for a fixed generation date, but it is not an
idempotent live-database import. It is a local/bootstrap seed artifact only.
"""

import math
import random
import uuid
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

RNG_SEED = 42
NAMESPACE = uuid.UUID("2f6a5f2e-2b3a-4a8a-9a3e-cccccccccccc")
WEEKS = 26
NEW_ACCOUNT_WEEKS = 6

ACCOUNT_NAMES = [
    "Meridian Creative", "Northwind Digital", "Bluepeak Media", "Foundry & Co",
    "Lattice Brand Studio", "Harbor Row Agency", "Cobalt Collective", "Anchor & Ives",
    "Prism Digital Works", "Wren House Studio", "Fieldstone Marketing", "Vantage Point Media",
    "Solstice Creative Group", "Timberline Digital", "Echo & Oak", "Redwood Strategy",
    "Juniper Studio", "Crescent Social", "Atlas Content Lab", "Morrow Design",
    "Keystone Brandworks", "Willow & Wire", "Brightline Partners", "Sable Growth",
    "Canvas North", "Kindred Creative", "Copperfield Media", "Sunroom Digital",
    "Common Thread Co", "Oakline Studio", "Noble Harbor", "Daybreak Marketing",
    "Summit & Slate", "Paper Kite Agency", "Yellowbrick Creative", "Signal & Story",
    "Mosaic Collective", "Fern & Finch", "Northstar Studio", "Wavelength Media",
    "Trueform Agency", "Horizon House", "Sidecar Digital", "Pine & Pixel",
    "Ember Creative", "Tandem Studio", "Violet Lane", "Orbit Brand Co",
]

# This is deliberately a finite, labelled demonstration corpus rather than a
# random sea of vaguely bad accounts. Every scenario is a useful scoring
# control: stable/noisy/recovery are false-positive traps; the deterioration
# cases isolate individual signals; the new account tests short-history safety.
SCENARIOS = (
    ["stable"] * 18
    + ["worsening"] * 8
    + ["response_shock"] * 4
    + ["invoice_deterioration"] * 4
    + ["cancellation_deterioration"] * 3
    + ["recovery"] * 4
    + ["seasonal"] * 3
    + ["noisy_healthy"] * 3
    + ["new_account"]
)
assert len(ACCOUNT_NAMES) == len(SCENARIOS) == 48

# Kept for compatibility with historical documentation and scenario tests.
WORSENING_INDEXES = {index for index, scenario in enumerate(SCENARIOS) if scenario == "worsening"}
CONTACT_TURNOVER_INDEXES = {7}
CONTACT_FIRST_NAMES = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie"]
CONTACT_LAST_NAMES = ["Reed", "Kim", "Patel", "Nguyen", "Ortiz", "Chen", "Brooks", "Diaz"]


def slugify(name: str) -> str:
    return name.lower().replace(" & ", "-").replace(" ", "-").replace("--", "-")


def stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_accounts(rng: random.Random, agency_id: str) -> list[dict]:
    accounts = []
    for index, (name, scenario) in enumerate(zip(ACCOUNT_NAMES, SCENARIOS)):
        contract_value = rng.choice([3000, 4500, 6000, 7500, 8500, 10000, 12500, 15000, 18000, 22000, 25000])
        contract_start = date.today() - timedelta(days=rng.randint(120, 900))
        first, last = rng.choice(CONTACT_FIRST_NAMES), rng.choice(CONTACT_LAST_NAMES)
        slug = slugify(name)
        original_email = f"{first.lower()}.{last.lower()}@{slug}.com"
        new_email = None
        if index in CONTACT_TURNOVER_INDEXES:
            new_first = rng.choice([item for item in CONTACT_FIRST_NAMES if item != first])
            new_last = rng.choice([item for item in CONTACT_LAST_NAMES if item != last])
            new_email = f"{new_first.lower()}.{new_last.lower()}@{slug}.com"
        accounts.append({
            "id": stable_uuid("account", name),
            "agency_id": agency_id,
            "name": name,
            "scenario": scenario,
            "contract_value_monthly": contract_value,
            "contract_start_date": contract_start.isoformat(),
            "primary_contact_email": new_email or original_email,
            "_original_contact_email": original_email,
            "_new_contact_email": new_email,
        })
    return accounts


def week_periods(anchor_end: date, weeks: int) -> list[tuple[date, date]]:
    return [
        (anchor_end - timedelta(weeks=(weeks - 1 - index), days=6), anchor_end - timedelta(weeks=(weeks - 1 - index)))
        for index in range(weeks)
    ]


def _snapshot_values(rng: random.Random, *, scenario: str, progress: float, base: dict) -> dict:
    jitter = lambda spread: rng.uniform(-spread, spread)
    response = base["response"] + jitter(0.6)
    threads = base["threads"] + jitter(3)
    scheduled = base["scheduled"] + jitter(1)
    cancelled = base["cancelled"] + jitter(1)
    late = base["late"] + jitter(1)

    if scenario == "worsening":
        severity = progress ** 1.6
        response += severity * rng.uniform(10, 18)
        threads -= severity * rng.uniform(8, 20)
        scheduled -= severity * rng.uniform(1, 3)
        cancelled += severity * rng.uniform(1, 3)
        late += severity * rng.uniform(10, 22)
    elif scenario == "response_shock" and progress >= 0.92:
        response += 16 + (progress - 0.92) * 35
        threads -= 8
    elif scenario == "invoice_deterioration":
        late += (progress ** 1.5) * 24
    elif scenario == "cancellation_deterioration":
        cancelled += (progress ** 1.5) * 5
        scheduled -= (progress ** 1.2) * 2
    elif scenario == "recovery":
        # A genuine recovery after an initially poor period: it must not be
        # misrepresented as an active churn trend merely because its older
        # history was bad.
        severity = max(0.0, 1.0 - max(0.0, progress - 0.45) / 0.55)
        response += severity * 13
        threads -= severity * 10
        scheduled -= severity * 2
        cancelled += severity * 3
        late += severity * 16
    elif scenario == "seasonal":
        cycle = math.sin(progress * math.pi * 4)
        response += cycle * 2.2
        threads -= cycle * 5
        scheduled -= cycle
        cancelled += max(0.0, cycle * 1.5)
        late += max(0.0, cycle * 3)
    elif scenario == "noisy_healthy":
        response += jitter(2.5)
        threads += jitter(8)
        scheduled += jitter(2)
        cancelled += jitter(2)
        late += jitter(3)

    return {
        "avg_response_time_hours": round(clamp(response, 0.5, 48.0), 2),
        "email_thread_count": max(1, round(threads)),
        "meetings_scheduled": max(0, round(scheduled)),
        "meetings_cancelled": max(0, round(cancelled)),
        "invoice_days_late": max(0, round(late)),
    }


def build_snapshots(rng: random.Random, account: dict, periods: list[tuple[date, date]]) -> list[dict]:
    base = {
        "response": rng.uniform(2.0, 6.0),
        "threads": rng.randint(15, 40),
        "scheduled": rng.randint(2, 5),
        "cancelled": rng.choice([0, 0, 0, 1]),
        "late": rng.choice([0, 0, 1, 2]),
    }
    snapshots = []
    for index, (start, end) in enumerate(periods):
        progress = index / max(1, len(periods) - 1)
        values = _snapshot_values(rng, scenario=account["scenario"], progress=progress, base=base)
        contact_email = account.get("_new_contact_email") if account.get("_new_contact_email") and index == len(periods) - 1 else account["_original_contact_email"]
        snapshots.append({
            "id": stable_uuid("snapshot", account["id"], start.isoformat()),
            "account_id": account["id"],
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            **values,
            "primary_contact_email": contact_email,
        })
    return snapshots


def build_seed_dataset(rng: random.Random, agency_id: str, *, anchor_end: date) -> dict:
    accounts = build_accounts(rng, agency_id)
    all_periods = week_periods(anchor_end, WEEKS)
    snapshots_by_account = {}
    for account in accounts:
        periods = all_periods[-NEW_ACCOUNT_WEEKS:] if account["scenario"] == "new_account" else all_periods
        snapshots_by_account[account["id"]] = build_snapshots(rng, account, periods)
    return {
        "accounts": accounts,
        "snapshots_by_account": snapshots_by_account,
        "scenario_counts": dict(sorted(Counter(account["scenario"] for account in accounts).items())),
    }


def render_sql(agency_id: str, accounts: list[dict], snapshots_by_account: dict[str, list[dict]], scenario_counts: dict[str, int]) -> str:
    lines = [
        "-- ClientPulse deterministic seed data: StudioCo agency + 48 scenario-rich mock accounts.",
        f"-- Most accounts have {WEEKS} completed weekly signal snapshots; new-account controls have {NEW_ACCOUNT_WEEKS}.",
        "-- Generated by backend/scripts/generate_seed.py. Apply schema and migrations first.",
        "-- Scenario coverage:",
        *[f"--   - {scenario}: {count}" for scenario, count in scenario_counts.items()],
        "--",
        "-- This bootstrap seed is not idempotent against a live database. Do not re-run it on an",
        "-- already seeded production project; use a reviewed import/migration path instead.",
        "",
        f"insert into agency (id, name) values ({sql_str(agency_id)}, {sql_str('StudioCo')});",
        "",
        "insert into account (id, agency_id, name, contract_value_monthly, contract_start_date, primary_contact_email) values",
    ]
    account_rows = [
        "  ({id}, {agency_id}, {name}, {value}, {start}, {email})".format(
            id=sql_str(account["id"]), agency_id=sql_str(account["agency_id"]), name=sql_str(account["name"]),
            value=account["contract_value_monthly"], start=sql_str(account["contract_start_date"]), email=sql_str(account["primary_contact_email"]),
        )
        for account in accounts
    ]
    lines.extend([",\n".join(account_rows) + ";", ""])
    lines.append("insert into signal_snapshot (id, account_id, period_start, period_end, avg_response_time_hours, email_thread_count, meetings_scheduled, meetings_cancelled, invoice_days_late, primary_contact_email) values")
    snapshot_rows = [
        "  ({id}, {account_id}, {start}, {end}, {response}, {threads}, {scheduled}, {cancelled}, {late}, {email})".format(
            id=sql_str(snapshot["id"]), account_id=sql_str(snapshot["account_id"]), start=sql_str(snapshot["period_start"]),
            end=sql_str(snapshot["period_end"]), response=snapshot["avg_response_time_hours"], threads=snapshot["email_thread_count"],
            scheduled=snapshot["meetings_scheduled"], cancelled=snapshot["meetings_cancelled"], late=snapshot["invoice_days_late"], email=sql_str(snapshot["primary_contact_email"]),
        )
        for account in accounts for snapshot in snapshots_by_account[account["id"]]
    ]
    lines.extend([",\n".join(snapshot_rows) + ";", ""])
    return "\n".join(lines)


def main() -> None:
    rng = random.Random(RNG_SEED)
    agency_id = stable_uuid("agency", "StudioCo")
    anchor_end = date.today() - timedelta(days=(date.today().weekday() + 1) % 7)
    dataset = build_seed_dataset(rng, agency_id, anchor_end=anchor_end)
    sql = render_sql(agency_id, dataset["accounts"], dataset["snapshots_by_account"], dataset["scenario_counts"])
    out_path = Path(__file__).resolve().parents[2] / "supabase" / "seed.sql"
    out_path.write_text(sql, encoding="utf-8")
    snapshots = sum(len(rows) for rows in dataset["snapshots_by_account"].values())
    print(f"Wrote {out_path} ({len(dataset['accounts'])} accounts, {snapshots} signal_snapshot rows)")


if __name__ == "__main__":
    main()
