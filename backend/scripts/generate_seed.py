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
    ["stable"] * 16
    + ["worsening"] * 8
    + ["response_shock"] * 4
    + ["invoice_deterioration"] * 4
    + ["cancellation_deterioration"] * 3
    + ["recovery"] * 4
    + ["seasonal"] * 3
    + ["noisy_healthy"] * 3
    + ["new_account"]
    + ["acute_churn"]
    + ["contact_watch"]
)
assert len(ACCOUNT_NAMES) == len(SCENARIOS) == 48

# Kept for compatibility with historical documentation and scenario tests.
WORSENING_INDEXES = {index for index, scenario in enumerate(SCENARIOS) if scenario == "worsening"}
# Four accounts carry real, staggered contact histories. Each tuple contains
# the zero-based reporting periods where a known contact transitions to a new
# known identity; only Orbit's final event is currently active.
CONTACT_CHANGE_SCHEDULES = {
    13: (5, 12, 19),
    24: (6, 14, 22),
    36: (4, 11, 18),
    47: (6, 15, 25),
}
CONTACT_TURNOVER_INDEXES = set(CONTACT_CHANGE_SCHEDULES)
CONTACT_FIRST_NAMES = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie"]
CONTACT_LAST_NAMES = ["Reed", "Kim", "Patel", "Nguyen", "Ortiz", "Chen", "Brooks", "Diaz"]

# Deterministic demo inbox coverage. These are presentation fixtures for a
# realistic mixed queue, not inputs to scoring or alert decisions.
DEMO_ALERT_PROFILES_BY_SCENARIO = {
    "worsening": [
        ("open", "critical"),
        ("open", "high"),
        ("open", "medium"),
        ("acknowledged", "critical"),
        ("acknowledged", "high"),
        ("acknowledged", "medium"),
        ("resolved", "high"),
        ("resolved", "low"),
    ],
    "response_shock": [
        ("open", "high"),
        ("acknowledged", "medium"),
        ("resolved", "medium"),
        ("resolved", "low"),
    ],
    "cancellation_deterioration": [
        ("open", "high"),
        ("acknowledged", "medium"),
        ("resolved", "low"),
    ],
    "contact_watch": [("acknowledged", "medium")],
    "recovery": [
        ("resolved", "low"),
        ("resolved", "medium"),
    ],
    "acute_churn": [("open", "critical")],
}

DEMO_ALERT_SIGNALS_BY_SCENARIO = {
    "worsening": [
        "avg_response_time_hours",
        "meetings_cancelled",
        "invoice_days_late",
    ],
    "response_shock": ["avg_response_time_hours"],
    "cancellation_deterioration": [
        "meetings_scheduled",
        "meetings_cancelled",
    ],
    "contact_watch": ["contact_changed", "avg_response_time_hours"],
    "recovery": ["avg_response_time_hours", "invoice_days_late"],
    "acute_churn": [
        "avg_response_time_hours",
        "meetings_cancelled",
        "invoice_days_late",
    ],
}


def slugify(name: str) -> str:
    return name.lower().replace(" & ", "-").replace(" ", "-").replace("--", "-")


def stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def build_demo_alert_profiles(accounts: list[dict]) -> dict[str, dict[str, object]]:
    """Return a deterministic mixed alert lifecycle for the demo inbox."""
    seen = Counter()
    profiles = {}
    for account in accounts:
        scenario = account["scenario"]
        ordinal = seen[scenario]
        seen[scenario] += 1
        options = DEMO_ALERT_PROFILES_BY_SCENARIO.get(scenario, [])
        has_contact_history = bool(account.get("_contact_change_indexes"))
        if ordinal >= len(options):
            if not has_contact_history:
                continue
            status, severity = "resolved", "low"
            signals = []
        else:
            status, severity = options[ordinal]
            signals = list(DEMO_ALERT_SIGNALS_BY_SCENARIO[scenario])
        if has_contact_history and "contact_changed" not in signals:
            signals.append("contact_changed")
        profiles[account["id"]] = {
            "status": status,
            "severity": severity,
            "signals_fired": signals,
        }
    return profiles


def sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_accounts(rng: random.Random, agency_id: str) -> list[dict]:
    accounts = []
    scenario_ordinals = Counter()
    for index, (name, scenario) in enumerate(zip(ACCOUNT_NAMES, SCENARIOS)):
        scenario_variant = scenario_ordinals[scenario]
        scenario_ordinals[scenario] += 1
        contract_value = rng.choice([3000, 4500, 6000, 7500, 8500, 10000, 12500, 15000, 18000, 22000, 25000])
        contract_start = date.today() - timedelta(days=rng.randint(120, 900))
        first, last = rng.choice(CONTACT_FIRST_NAMES), rng.choice(CONTACT_LAST_NAMES)
        slug = slugify(name)
        original_email = f"{first.lower()}.{last.lower()}@{slug}.com"
        contact_emails = [original_email]
        if index in CONTACT_TURNOVER_INDEXES:
            for change_number in range(1, 4):
                contact_first = CONTACT_FIRST_NAMES[(index + change_number * 2) % len(CONTACT_FIRST_NAMES)]
                contact_last = CONTACT_LAST_NAMES[(index + change_number * 3) % len(CONTACT_LAST_NAMES)]
                candidate = f"{contact_first.lower()}.{contact_last.lower()}@{slug}.com"
                if candidate in contact_emails:
                    candidate = f"{contact_first.lower()}.{contact_last.lower()}{change_number}@{slug}.com"
                contact_emails.append(candidate)
        accounts.append({
            "id": stable_uuid("account", name),
            "agency_id": agency_id,
            "name": name,
            "scenario": scenario,
            "_scenario_variant": scenario_variant,
            "contract_value_monthly": contract_value,
            "contract_start_date": contract_start.isoformat(),
            "primary_contact_email": contact_emails[-1],
            "_original_contact_email": original_email,
            "_new_contact_email": contact_emails[-1] if len(contact_emails) > 1 else None,
            "_contact_emails": contact_emails,
            "_contact_change_indexes": CONTACT_CHANGE_SCHEDULES.get(index, ()),
        })
    return accounts


def week_periods(anchor_end: date, weeks: int) -> list[tuple[date, date]]:
    return [
        (anchor_end - timedelta(weeks=(weeks - 1 - index), days=6), anchor_end - timedelta(weeks=(weeks - 1 - index)))
        for index in range(weeks)
    ]


def _snapshot_values(
    rng: random.Random,
    *,
    scenario: str,
    variant: int,
    progress: float,
    base: dict,
) -> dict:
    jitter = lambda spread: rng.uniform(-spread, spread)
    response = base["response"] + jitter(0.6)
    threads = base["threads"] + jitter(3)
    scheduled = base["scheduled"] + jitter(1)
    cancelled = base["cancelled"] + jitter(1)
    late = base["late"] + jitter(1)

    # Real client telemetry breathes week to week even when its longer trend
    # is stable. Distinct deterministic waves keep each signal legible without
    # adding display-only noise or changing the evidence after generation.
    week = progress * (WEEKS - 1)
    phase = variant * 0.71
    response_wave = math.sin(week * 0.83 + phase) + 0.45 * math.sin(week * 1.91 + 0.4)
    thread_wave = math.sin(week * 0.61 + phase + 1.3) + 0.35 * math.sin(week * 1.57)
    activity_wave = math.sin(week * 0.74 + phase + 0.8) + 0.5 * math.sin(week * 1.69 + 0.2)
    cancellation_wave = math.sin(week * 0.92 + phase + 2.1) + 0.4 * math.sin(week * 1.43)
    payment_wave = math.sin(week * 0.67 + phase + 2.7) + 0.45 * math.sin(week * 1.77 + 0.6)
    response += response_wave * 1.7
    threads += thread_wave * 5.0
    scheduled += activity_wave * 1.9
    cancelled += 2.2 + cancellation_wave * 1.7
    late += 3.0 + payment_wave * 2.5

    if scenario == "new_account":
        # Six periods are still enough to show an honest cadence rather than a
        # misleading flat placeholder while the account establishes a baseline.
        short_index = min(5, round(progress * 5))
        response = (2.5, 2.2, 2.7, 2.3, 2.8, 2.4)[short_index]
        threads = (12, 15, 11, 14, 10, 13)[short_index]
        scheduled = (4, 3, 5, 2, 4, 3)[short_index]
        cancelled = (0, 1, 0, 2, 0, 1)[short_index]
        late = (0, 1, 0, 2, 0, 1)[short_index]

    if scenario == "worsening":
        # Stagger the onset across accounts so the portfolio moves in waves
        # instead of every at-risk curve jumping on the same reporting date.
        onset = 0.58 + variant * 0.04
        severity = max(0.0, (progress - onset) / (1.0 - onset)) ** 2
        response += severity * 34
        threads -= severity * 28
        scheduled -= severity * 6
        cancelled += severity * 14
        late += severity * 38
    elif scenario == "response_shock":
        onset = 0.72 + variant * 0.04
        severity = max(0.0, (progress - onset) / (1.0 - onset)) ** 2
        response += severity * 20
        threads -= severity * 8
    elif scenario == "invoice_deterioration":
        # Payment trouble is a Watch case only when it is accompanied by a
        # modest communications drift, rather than masquerading as a full
        # multi-signal churn episode.
        late += (progress ** 1.35) * 34
        response += (progress ** 1.35) * 10
    elif scenario == "cancellation_deterioration":
        onset = 0.68 + variant * 0.08
        severity = max(0.0, (progress - onset) / (1.0 - onset)) ** 2
        cancelled += severity * 22
        scheduled -= severity * 7
    elif scenario == "acute_churn":
        # One fast collapse remains, but it begins before the final bars so it
        # does not manufacture a portfolio-wide cliff on the same date.
        onset = 0.70
        severity = max(0.0, (progress - onset) / (1.0 - onset)) ** 2
        response += severity * 30
        threads -= severity * 24
        scheduled -= severity * 4
        cancelled += severity * 8
        late += severity * 34
    elif scenario == "contact_watch":
        # The discrete contact change adds 20 points; mild response drift
        # supplies the remaining evidence needed for a Watch-tier graph.
        response += (progress ** 1.5) * 11
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
        response += cycle * 2.2 + (progress ** 1.5) * 8
        threads -= cycle * 5
        scheduled -= cycle
        cancelled += max(0.0, cycle * 1.5) + (progress ** 1.5) * 4
        late += max(0.0, cycle * 3) + (progress ** 1.5) * 5
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
        values = _snapshot_values(
            rng,
            scenario=account["scenario"],
            variant=account["_scenario_variant"],
            progress=progress,
            base=base,
        )
        contact_email = account["_original_contact_email"]
        for change_index, changed_email in zip(
            account["_contact_change_indexes"], account["_contact_emails"][1:]
        ):
            if index >= change_index:
                contact_email = changed_email
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
