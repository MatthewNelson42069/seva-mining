/**
 * Per-tenant SummaryCard section configuration — Phase 10 DEF-08.
 *
 * Phase 9 D-08 (locked) — Multi-tenant Daily Summaries reuse the existing
 * three markdown columns (`gold_news_md`, `ontario_law_md`, `ontario_stats_md`)
 * semantically. Juno's "Defence News" markdown is physically stored in
 * `gold_news_md`, "Canadian Procurement" in `ontario_law_md`, and "World
 * Events Relevant to Defence" in `ontario_stats_md`. NO Alembic migration
 * was performed in Phase 9, and no Alembic migration is needed in Phase 10 —
 * the column names are stable; only the per-tenant display titles change.
 *
 * Consumer: `frontend/src/components/summary/SummaryCard.tsx` (Wave 3 /
 * 10-04-PLAN.md wires `useParams<{company: 'seva' | 'juno'}>()` into the
 * component and maps over `companySectionConfig[company]` to render the
 * three SectionBlocks dynamically). The matching Wave 0 RED test block in
 * `__tests__/SummaryCard.test.tsx` is currently `describe.skip` and will
 * be flipped to `describe` in Wave 3.
 *
 * Wave 0 (this plan) lands the production config map alone so Wave 3's
 * SummaryCard edit is a focused ~15-line diff (single file).
 */

import type { SummaryCard } from '@/api/summaries'

/**
 * One renderable section in a SummaryCard. `field` selects which of the
 * three physical markdown columns to render — the column-name reuse pattern
 * lets us avoid an Alembic migration while still presenting tenant-specific
 * section titles in the UI.
 */
export interface SectionConfig {
  /** Display title for the section heading (e.g., "Gold News", "Defence News"). */
  title: string
  /**
   * Physical column on the SummaryCard payload. Constrained to the three
   * existing markdown columns per Phase 9 D-08 semantic-reuse.
   */
  field: keyof Pick<SummaryCard, 'gold_news_md' | 'ontario_law_md' | 'ontario_stats_md'>
  /** Copy shown when the markdown is `null` (no content for this fire). */
  emptyFallback: string
}

/**
 * Per-tenant ordered list of SummaryCard sections.
 *
 * The two CompanyId values ('seva' | 'juno') match `queryKeys.ts`'s
 * CompanyId union — adding a third tenant requires (a) extending the
 * CompanyId type, (b) adding a key here, and (c) updating the database
 * CHECK constraint per the v3.2 TENANT-N-v32 path.
 */
export const companySectionConfig: Record<'seva' | 'juno', SectionConfig[]> = {
  // ----- Seva (gold sector, Phase 6+) -----
  seva: [
    {
      title: 'Gold News',
      field: 'gold_news_md',
      emptyFallback: 'No major moves in gold for this window.',
    },
    {
      title: 'Ontario Law',
      field: 'ontario_law_md',
      emptyFallback: 'No new Ontario mining-related laws today.',
    },
    {
      title: 'Ontario Stats',
      field: 'ontario_stats_md',
      emptyFallback: 'No new production statistics released today.',
    },
  ],
  // ----- Juno (defence sector, Phase 10 DEF-08) -----
  //
  // Semantic-rename via Phase 9 D-08 column reuse:
  //   gold_news_md      → "Defence News"
  //   ontario_law_md    → "Canadian Procurement"
  //   ontario_stats_md  → "World Events Relevant to Defence"
  juno: [
    {
      title: 'Defence News',
      field: 'gold_news_md',
      emptyFallback: 'No major defence-industry moves for this window.',
    },
    {
      title: 'Canadian Procurement',
      field: 'ontario_law_md',
      emptyFallback: 'No new Canadian defence procurement signals today.',
    },
    {
      title: 'World Events Relevant to Defence',
      field: 'ontario_stats_md',
      emptyFallback: 'No defence-relevant world events met the relevance threshold today.',
    },
  ],
}
