/** Re-export of useWeeklySweeps for consistency with other hooks living under /hooks.
 *  The canonical implementation lives in api/weeklySweeps.ts alongside the fetch helper.
 */
export { useWeeklySweeps } from '@/api/weeklySweeps'
export type { WeeklySweepCard, WeeklySweepFeedResponse } from '@/api/weeklySweeps'
