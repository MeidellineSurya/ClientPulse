/**
 * Data access layer. Everything the UI needs goes through these functions, so
 * swapping mock data for the FastAPI backend is a one-file change:
 *
 *   const USE_MOCK = false;
 *   ...
 *   export const getAccounts = () => fetch('/api/accounts').then((r) => r.json());
 *
 * The shapes returned here match the PRD data model (account, signal_snapshot,
 * baseline, health_score, alert).
 */
import { SEED_ACCOUNTS, PERIODS, BRIEFS, DEFAULT_BRIEF, ACTIVITY, DEFAULT_ACTIVITY } from './accounts.seed';
import {
  computeDrifts, signalValues, signalLabels, firedSignals, scoreBreakdown,
  statusOf, statusKeyOf, SIGNALS, BASELINE_SIGMA
} from '../lib/scoring';

const USE_MOCK = true;
const LATENCY = 220; // keep the loading states honest in the demo

const wait = (value) => new Promise((res) => setTimeout(() => res(value), LATENCY));

/** Deterministic pseudo-random walk so the seeded history is stable across reloads. */
function rng(seed) {
  let r = (seed * 9301 + 49297) % 233280;
  return () => { r = (r * 9301 + 49297) % 233280; return r / 233280 - 0.5; };
}

function history(end, drop, seed, jitter) {
  const rnd = rng(seed);
  const start = end + drop;
  const out = [];
  for (let i = 0; i < 12; i++) {
    const t = i < 9 ? (i / 9) * 0.28 : 0.28 + ((i - 8) / 3) * 0.72;
    out.push(start - drop * t + rnd() * jitter);
  }
  out[11] = end;
  return out;
}

function buildAccount(a) {
  const { drifts, composite } = computeDrifts(a.score, a.lead);
  const values = signalValues(drifts);
  const labels = signalLabels(values);
  const fired = firedSignals(values);
  const statusKey = statusKeyOf(a.score);
  const scoreDelta = statusKey === 'risk' ? -(14 + (a.id % 3) * 3) : statusKey === 'watch' ? -(4 + (a.id % 3)) : a.id % 4;

  const scoreSeries = history(a.score, -scoreDelta, a.id + 3, 1.6)
    .map((v, i) => ({ period: PERIODS[i], score: Math.round(Math.max(35, Math.min(99, v))) }));

  const signals = SIGNALS.map((s, j) => {
    const sd = s.baseline * BASELINE_SIGMA;
    const jitter = { response: 0.5, cancel: 1.0, pay: 0.6, freq: 0.3 }[s.key];
    const series = history(values[s.key], s.baseline - values[s.key], a.id * 7 + j, jitter)
      .map((v, i) => ({ period: PERIODS[i], value: Math.round(v * 100) / 100, recent: i >= 8 ? Math.round(v * 100) / 100 : null }));
    return {
      key: s.key, label: s.label, unit: s.unit, weight: s.weight,
      baseline: s.baseline, sigma: sd,
      current: Math.round(values[s.key] * 100) / 100,
      drift: Math.round(drifts[s.key] * 100) / 100,
      delta: labels[s.key], fired: fired.includes(s.key),
      series
    };
  });

  const driver = statusKey === 'healthy'
    ? (a.score >= 88 ? 'Engagement rising' : 'Stable')
    : a.lead === 'response' ? 'Response time ' + labels.response + ' slower'
    : a.lead === 'cancel' ? 'Cancellations ' + labels.cancel
    : a.lead === 'pay' ? 'Payment lag ' + labels.pay
    : 'Meetings ' + labels.freq;

  return {
    ...a,
    status: statusOf(a.score),
    statusKey,
    composite,
    drifts,
    labels,
    driver,
    scoreDelta,
    scoreSeries,
    signals,
    breakdown: scoreBreakdown(drifts),
    ...(BRIEFS[a.id] || DEFAULT_BRIEF(a.name)),
    activity: ACTIVITY[a.id] || DEFAULT_ACTIVITY
  };
}

const ACCOUNTS = SEED_ACCOUNTS.map(buildAccount);

const ALERT_DATES = ['Sep 15', 'Sep 15', 'Sep 14', 'Sep 12', 'Sep 9', 'Sep 5', 'Sep 2'];
let ALERTS = ACCOUNTS.filter((a) => a.score < 76).map((a, i) => ({
  id: 100 + a.id,
  accountId: a.id,
  triggeredAt: ALERT_DATES[i] || 'Sep 1',
  severity: a.score < 65 ? 'Critical' : a.score < 70 ? 'High' : 'Watch',
  signalsFired: a.signals.filter((s) => s.fired).map((s) => ({ name: s.label, value: s.delta })),
  aiBrief: a.brief,
  suggestedAction: a.action,
  status: i > 3 ? 'Resolved' : 'Open'
}));

export const getAccounts = () => (USE_MOCK ? wait(ACCOUNTS) : fetch('/api/accounts').then((r) => r.json()));
export const getAccount = (id) => (USE_MOCK ? wait(ACCOUNTS.find((a) => a.id === Number(id))) : fetch('/api/accounts/' + id).then((r) => r.json()));
export const getAlerts = () => (USE_MOCK ? wait(ALERTS.map((al) => ({ ...al, account: ACCOUNTS.find((a) => a.id === al.accountId) }))) : fetch('/api/alerts').then((r) => r.json()));

export function setAlertStatus(alertId, status) {
  if (!USE_MOCK) return fetch('/api/alerts/' + alertId, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) });
  ALERTS = ALERTS.map((al) => (al.id === alertId ? { ...al, status } : al));
  return wait(ALERTS.find((al) => al.id === alertId));
}

export function getPortfolio(accounts) {
  const atRisk = accounts.filter((a) => a.statusKey === 'risk');
  const watch = accounts.filter((a) => a.statusKey === 'watch');
  const healthy = accounts.filter((a) => a.statusKey === 'healthy');
  const median = PERIODS.map((period, i) => {
    const col = accounts.map((a) => a.scoreSeries[i].score).sort((x, y) => x - y);
    return { period, score: col[Math.floor(col.length / 2)] };
  });
  return {
    atRisk, watch, healthy, median,
    atRiskRevenue: atRisk.reduce((t, a) => t + a.mrr, 0),
    healthyRevenue: healthy.reduce((t, a) => t + a.mrr, 0),
    portfolioScore: Math.round(accounts.reduce((t, a) => t + a.score, 0) / accounts.length)
  };
}

export { PERIODS };
