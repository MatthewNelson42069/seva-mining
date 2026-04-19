import { Button } from '@/components/ui/button'
import { useRerenderContentBundle } from '@/hooks/useContentBundle'
import type { RenderedImage } from '@/api/types'

interface RenderedImagesGalleryProps {
  bundleId: string
  contentType: string
  renderedImages: RenderedImage[] | null | undefined
  bundleCreatedAt: string
}

const ROLE_ORDER: RenderedImage['role'][] = [
  'twitter_visual',
  'instagram_slide_1',
  'instagram_slide_2',
  'instagram_slide_3',
]

const ROLE_LABELS: Record<string, string> = {
  twitter_visual: 'Twitter / X',
  instagram_slide_1: 'Instagram 1',
  instagram_slide_2: 'Instagram 2',
  instagram_slide_3: 'Instagram 3',
}

export function RenderedImagesGallery({
  bundleId,
  contentType,
  renderedImages,
  bundleCreatedAt,
}: RenderedImagesGalleryProps) {
  const mutation = useRerenderContentBundle(bundleId)

  const expectedCount =
    contentType === 'infographic' ? 4 : contentType === 'quote' ? 2 : 0

  // Nothing to render for text-only formats
  if (expectedCount === 0) return null

  const images = renderedImages ?? []
  const ageMinutes = (Date.now() - new Date(bundleCreatedAt).getTime()) / 60000
  const isPolling = images.length === 0 && ageMinutes < 10

  // Sort images by canonical role order
  const sortedImages = [...images].sort(
    (a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role),
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Rendered images
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || isPolling}
        >
          {mutation.isPending ? 'Queuing\u2026' : 'Regenerate images'}
        </Button>
      </div>

      {isPolling && (
        <>
          <p className="text-xs text-muted-foreground">Rendering images\u2026</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Array.from({ length: expectedCount }).map((_, i) => (
              <div
                key={i}
                className="aspect-video bg-muted/40 rounded animate-pulse"
                aria-label="Loading image"
              />
            ))}
          </div>
        </>
      )}

      {!isPolling && sortedImages.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {sortedImages.map((img) => (
            <a
              key={img.role}
              href={img.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block group"
            >
              <img
                src={img.url}
                alt={ROLE_LABELS[img.role] ?? img.role}
                className="w-full rounded border group-hover:opacity-90 transition-opacity"
                loading="lazy"
              />
              <p className="text-xs text-muted-foreground mt-1 text-center">
                {ROLE_LABELS[img.role] ?? img.role}
              </p>
            </a>
          ))}
        </div>
      )}

      {/* Graceful empty state: bundle > 10 min old, no images — just show regen button above */}
    </div>
  )
}
