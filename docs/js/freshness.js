/**
 * When the page should say its data is old.
 *
 * The data refreshes every 8 hours, but GitHub starts scheduled runs late: over
 * the first 183 runs of the 2026 season the longest gap between two was 13.9
 * hours, and none reached 16. Past 18 hours a refresh has failed or been
 * skipped, and the lines may have moved.
 */
export const REFRESH_EVERY_HOURS = 8;
export const STALE_AFTER_HOURS = 18;

/** The notice to show for data built at `generatedAt`, or null if it is fresh enough. */
export function staleNotice(generatedAt, now = Date.now()) {
  const built = Date.parse(generatedAt);
  if (Number.isNaN(built)) return 'Last refreshed at an unknown time. Prices, public picks and results may be out of date.';
  const hours = (now - built) / 3600_000;
  if (hours <= STALE_AFTER_HOURS) return null;
  const age = hours < 48 ? `${Math.round(hours)} hours ago` : `${Math.round(hours / 24)} days ago`;
  return `Last refreshed ${age}; the usual gap is ${REFRESH_EVERY_HOURS} hours. Prices, public picks and results may have moved since.`;
}
