/**
 * Deterministic scoring engine — the defensible core of ClientPulse.
 *
 * composite_risk =
 *     0.35 * drift(response_time)
 *   + 0.30 * drift(meeting_cancellations)
 *   + 0.20 * drift(payment_lag)
 *   + 0.15 * drift(meeting_frequency_decline)
 *
 * health_score = round(100 - 100 * composite_risk)
 *
 * drift(signal) = (current - baseline_avg) / baseline_stddev, normalised and clipped to 0..1.
 * The LLM never produces the score; it only writes prose from the fired signals.
 *
 * In production these numbers come from the backend (/api/accounts). This module is kept
 * client-side so the UI can re-derive and explain a score without a round trip.
 */

export const SIGNALS = [
  { key: 'response', label: 'Response time', weight: 0.35, shape: 1.15, baseline: 4.1, unit: 'h', inverse: false },
  { key: 'cancel', label: 'Meeting cancellations', weight: 0.3, shape: 1.0, baseline: 9, unit: '%', inverse: false },
  { key: 'pay', label: 'Payment lag', weight: 0.2, shape: 0.75, baseline: 1.8, unit: 'days', inverse: false },
  { key: 'freq', label: 'Meeting frequency', weight: 0.15, shape: 0.9, baseline: 4.2, unit: '/mo', inverse: true }
];

export const ALERT_THRESHOLD = 70;   // health score below this can fire an alert
export const BASELINE_SIGMA = 0.16;  // stddev as a fraction of the baseline average

export const statusOf = (score) => (score >= 80 ? 'Healthy' : score >= 70 ? 'Watch' : 'At risk');
export const statusKeyOf = (score) => (score >= 80 ? 'healthy' : score >= 70 ? 'watch' : 'risk');

/** Per-signal drift, weighted so the account's leading signal dominates. */
export function computeDrifts(score, leadSignal) {
  const total = (100 - score) / 100;
  const shape = {};
  SIGNALS.forEach((s) => { shape[s.key] = s.shape * (s.key === leadSignal ? 1.7 : 0.72); });
  const norm = SIGNALS.reduce((a, s) => a + s.weight * shape[s.key], 0);
  const k = total / norm;
  const drifts = {};
  SIGNALS.forEach((s) => { drifts[s.key] = Math.min(1, Math.max(0, shape[s.key] * k)); });
  return { drifts, composite: total };
}

/** Current observed value per signal, derived from its drift. */
export function signalValues(drifts) {
  return {
    response: 4.1 * (1 + 1.9 * drifts.response),
    cancel: 9 * (1 + 1.5 * drifts.cancel),
    pay: 1.8 + 12 * drifts.pay,
    freq: 4.2 * (1 - 0.45 * drifts.freq)
  };
}

const round1 = (n) => Math.round(n * 10) / 10;

/** Short human labels, used identically by the table, alert cards and signal charts. */
export function signalLabels(values) {
  const pct = (k) => Math.round((values[k] / SIGNALS.find((s) => s.key === k).baseline - 1) * 100);
  return {
    response: round1(values.response / 4.1) + 'x',
    cancel: '+' + pct('cancel') + '%',
    pay: '+' + round1(values.pay - 1.8) + 'd',
    freq: '-' + Math.abs(pct('freq')) + '%'
  };
}

/** A signal has "fired" when it sits outside its own baseline band (+/- 1 sigma). */
export function firedSignals(values) {
  return SIGNALS.filter((s) => {
    const sd = s.baseline * BASELINE_SIGMA;
    return s.inverse ? values[s.key] < s.baseline - sd : values[s.key] > s.baseline + sd;
  }).map((s) => s.key);
}

/** The audit trail rendered under "How this score was calculated". */
export function scoreBreakdown(drifts) {
  const rows = SIGNALS.map((s) => ({
    term: s.weight.toFixed(2) + ' x drift(' + s.key + ')',
    calc: s.weight.toFixed(2) + ' x ' + drifts[s.key].toFixed(2),
    value: (s.weight * drifts[s.key]).toFixed(3)
  }));
  const composite = rows.reduce((a, r) => a + parseFloat(r.value), 0);
  return { rows, composite, health: Math.round(100 - 100 * composite) };
}

/**
 * Alerts fire only when risk crosses the threshold AND the trend has worsened for
 * three consecutive periods — this is what separates ClientPulse from a snapshot dashboard.
 */
export function shouldAlert(scoreSeries) {
  const n = scoreSeries.length;
  if (n < 4) return false;
  const last = scoreSeries[n - 1];
  const worsening = scoreSeries[n - 1] < scoreSeries[n - 2] && scoreSeries[n - 2] < scoreSeries[n - 3];
  return last < ALERT_THRESHOLD + 6 && worsening;
}

export const money = (n) => '$' + n.toLocaleString('en-US');
export const shortMoney = (n) => '$' + (n >= 1000 ? Math.round(n / 100) / 10 + 'K' : n);
export { round1 };
