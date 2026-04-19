import { useEffect, useState } from 'react'
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
]

const ROLE_LABELS: Record<string, string> = {
  twitter_visual: 'Twitter / X',
}

export function RenderedImagesGallery({
  bundleId,
  contentType,
  renderedImages,
  bundleCreatedAt,
}: RenderedImagesGalleryProps) {
  const mutation = useRerenderContentBundle(bundleId)

  // Track whether the bundle is still "young enough" to be in the polling window
  // (under 10 minutes old). Date.now() is impure so we read it once in a lazy
  // useState initializer (runs exactly at mount) and then a one-shot timer
  // flips the flag when the window closes. No Date.now() calls during render.
  const [isWithinPollingWindow, setIsWithinPollingWindow] = useState(() => {
    const ageMs = Date.now() - new Date(bundleCreatedAt).getTime()
    return ageMs < 10 * 60_000
  })
  useEffect(() => {
    const ageMs = Date.now() - new Date(bundleCreatedAt).getTime()
    const remainingMs = 10 * 60_000 - ageMs
    if (remainingMs <= 0) return
    const id = setTimeout(() => setIsWithinPollingWindow(false), remainingMs)
    return () => clearTimeout(id)
  }, [bundleCreatedAt])

  const expectedCount =
    contentType === 'infographic' || contentType === 'quote' ? 1 : 0

  // Nothing to render for text-only formats
  if (expectedCount === 0) return null

  const images = renderedImages ?? []
  const isPolling = images.length === 0 && isWithinPollingWindow

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
          <div className="grid grid-cols-1 gap-3">
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
        <div className="grid grid-cols-1 gap-3">
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
