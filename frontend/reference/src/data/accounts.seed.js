/** Seeded StudioCo agency book — 15 retainer clients, 3 clearly deteriorating. */
export const SEED_ACCOUNTS = [
  { id: 1, name: 'Northstar Health', industry: 'Healthcare', owner: 'Dana Whitfield', mrr: 18000, score: 58, lead: 'response', daysSinceContact: 11, since: 'Mar 2023', email: 'ops@northstarhealth.com', renewal: '2026-10-31' },
  { id: 2, name: 'Atlas Consulting', industry: 'Professional services', owner: 'Rafi Osei', mrr: 13500, score: 64, lead: 'freq', daysSinceContact: 9, since: 'Jan 2024', email: 'k.bright@atlasconsulting.co', renewal: '2026-12-01' },
  { id: 3, name: 'Silvercrest Property', industry: 'Property', owner: 'Dana Whitfield', mrr: 10500, score: 61, lead: 'cancel', daysSinceContact: 14, since: 'Sep 2022', email: 'marketing@silvercrest.com', renewal: '2026-09-30' },
  { id: 4, name: 'Kestrel Group', industry: 'Financial services', owner: 'Rafi Osei', mrr: 10500, score: 68, lead: 'pay', daysSinceContact: 8, since: 'Jun 2023', email: 'ops@kestrelgroup.com', renewal: '2027-01-15' },
  { id: 5, name: 'Vantage Labs', industry: 'B2B SaaS', owner: 'Priya Nandan', mrr: 11000, score: 72, lead: 'response', daysSinceContact: 6, since: 'Feb 2024', email: 'growth@vantagelabs.io', renewal: '2026-11-30' },
  { id: 6, name: 'Harbour & Finch', industry: 'Legal', owner: 'Priya Nandan', mrr: 9500, score: 74, lead: 'freq', daysSinceContact: 7, since: 'Nov 2022', email: 'comms@harbourfinch.com', renewal: '2026-10-15' },
  { id: 7, name: 'Ridgeline Sports', industry: 'Sports & leisure', owner: 'Rafi Osei', mrr: 6500, score: 78, lead: 'response', daysSinceContact: 5, since: 'Apr 2024', email: 'team@ridgelinesports.com', renewal: '2027-04-01' },
  { id: 8, name: 'Fairweather Foods', industry: 'FMCG', owner: 'Priya Nandan', mrr: 8800, score: 81, lead: 'response', daysSinceContact: 5, since: 'Aug 2023', email: 'brand@fairweatherfoods.com', renewal: '2027-02-01' },
  { id: 9, name: 'Orbit Payments', industry: 'Fintech', owner: 'Dana Whitfield', mrr: 13500, score: 84, lead: 'pay', daysSinceContact: 4, since: 'Oct 2023', email: 'marketing@orbitpay.com', renewal: '2026-10-01' },
  { id: 10, name: 'Greenline Co', industry: 'Sustainability', owner: 'Priya Nandan', mrr: 7500, score: 85, lead: 'freq', daysSinceContact: 4, since: 'Jul 2023', email: 'hello@greenline.co', renewal: '2027-07-01' },
  { id: 11, name: 'Marlow & Reed', industry: 'Real estate', owner: 'Rafi Osei', mrr: 5000, score: 86, lead: 'response', daysSinceContact: 3, since: 'May 2024', email: 'studio@marlowreed.com', renewal: '2027-05-01' },
  { id: 12, name: 'Acme Media', industry: 'Retail', owner: 'Dana Whitfield', mrr: 14000, score: 88, lead: 'response', daysSinceContact: 2, since: 'Feb 2022', email: 'press@acmemedia.com', renewal: '2027-02-28' },
  { id: 13, name: 'Pinnacle Dental', industry: 'Healthcare', owner: 'Priya Nandan', mrr: 3800, score: 89, lead: 'cancel', daysSinceContact: 3, since: 'Dec 2023', email: 'front@pinnacledental.com', renewal: '2026-12-15' },
  { id: 14, name: 'Studio Eleven', industry: 'Hospitality', owner: 'Rafi Osei', mrr: 6000, score: 91, lead: 'response', daysSinceContact: 2, since: 'Mar 2024', email: 'ben@studioeleven.com', renewal: '2027-03-01' },
  { id: 15, name: 'Cobalt Interiors', industry: 'Design', owner: 'Dana Whitfield', mrr: 4500, score: 93, lead: 'freq', daysSinceContact: 1, since: 'Jan 2023', email: 'studio@cobaltinteriors.com', renewal: '2027-01-01' }
];

export const PERIODS = ['Jun 30', 'Jul 7', 'Jul 14', 'Jul 21', 'Jul 28', 'Aug 4', 'Aug 11', 'Aug 18', 'Aug 25', 'Sep 1', 'Sep 8', 'Sep 15'];

/**
 * LLM output, generated once per alert on the backend and stored on the alert row.
 * The model reads the fired signals; it never sets the score.
 */
export const BRIEFS = {
  1: {
    verdict: "Northstar's relationship health has declined sharply over the last three weeks.",
    brief: "Northstar's email response times have stretched from a typical 4.1 hours to just under ten, while their cancellation rate has climbed about 40% above baseline. Both signals moved together, which historically indicates the relationship has lost its internal sponsor rather than simply hitting a busy month.",
    action: 'Schedule a strategic check-in this week.',
    actionWhy: 'Use the conversation to understand whether priorities, expectations or delivery quality have changed — and confirm who now owns the relationship on their side.'
  },
  2: {
    verdict: 'Atlas has quietly reduced contact for six consecutive weeks, with meetings down nearly a third.',
    brief: 'Meeting frequency at Atlas is down by almost a third against their own baseline and the two most recent monthly reviews were rescheduled rather than held. Response times remain acceptable, so this reads as reduced engagement rather than dissatisfaction.',
    action: 'Re-establish the monthly review cadence.',
    actionWhy: 'Propose a fixed recurring slot and bring one piece of forward-looking strategic work; the gap here is guidance, not delivery.'
  },
  3: {
    verdict: 'Silvercrest is cancelling sessions at twice their usual rate and has gone quiet for two weeks.',
    brief: 'Silvercrest is now cancelling sessions at roughly twice their usual rate, and invoices have started slipping past terms — an unusual combination for an account that paid on time for eleven straight months.',
    action: 'Escalate to the agency owner and call, do not email.',
    actionWhy: 'Payment drift alongside disengagement usually signals a budget review upstream.'
  },
  4: {
    verdict: 'Kestrel is paying later and meeting less than their own norm.',
    brief: 'Invoices are running close to six days later than Kestrel\u2019s eleven-month average and one of the last three sessions was cancelled. Response times are unchanged, so the drift looks procedural.',
    action: 'Confirm the invoicing contact is still correct.',
    actionWhy: 'A finance-side personnel change explains this pattern more often than dissatisfaction does.'
  },
  5: {
    verdict: 'Vantage is slower to reply than usual, but engagement holds.',
    brief: 'Replies from Vantage now take close to twice as long as their 4.1-hour baseline, with meeting cadence unchanged. One signal drifting alone rarely predicts churn.',
    action: 'Keep on watch; no outreach needed this week.',
    actionWhy: 'Revisit if a second signal starts drifting or the trend continues for another two periods.'
  }
};

export const DEFAULT_BRIEF = (name) => ({
  verdict: name + ' is behaving in line with their own baseline.',
  brief: 'No signal at ' + name + ' has moved more than one standard deviation from its eight-week baseline.',
  action: 'No action needed.',
  actionWhy: 'ClientPulse will flag the account if two or more signals start drifting together.'
});

export const ACTIVITY = {
  1: [
    { date: 'Sep 15', text: 'Alert fired — composite risk 0.42, third consecutive worsening period.', level: 'risk' },
    { date: 'Sep 11', text: 'Monthly strategy session cancelled by client, 3 hours before start.', level: 'risk' },
    { date: 'Sep 8', text: 'Reply to campaign brief took 9.7 hours (baseline 4.1h).', level: 'watch' },
    { date: 'Sep 2', text: 'Invoice #4192 paid 4 days late.', level: 'watch' },
    { date: 'Aug 26', text: 'Quarterly review held — no issues raised.', level: 'healthy' }
  ]
};

export const DEFAULT_ACTIVITY = [
  { date: 'Sep 14', text: 'Weekly signal sync completed — all signals within baseline.', level: 'healthy' },
  { date: 'Sep 9', text: 'Status call held as scheduled.', level: 'healthy' },
  { date: 'Sep 3', text: 'Invoice paid on terms.', level: 'healthy' }
];
