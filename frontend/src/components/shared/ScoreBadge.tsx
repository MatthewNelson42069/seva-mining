interface ScoreBadgeProps {
  score: number
}

export function ScoreBadge({ score }: ScoreBadgeProps) {
  if (score == null) return null
  return (
    <span className="font-mono text-sm text-muted-foreground">
      {score.toFixed(1)}/10
    </span>
  )
}
