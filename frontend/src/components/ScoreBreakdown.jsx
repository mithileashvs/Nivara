/**
 * The backend returns a fully itemised `score_breakdown` for matching and
 * appointment options. We render exactly those factors and points — no score is
 * computed or invented in the frontend.
 */
export function ScoreBreakdown({ score, breakdown = [], factors = [] }) {
  return (
    <details className="group mt-3 border-t border-line pt-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-xs text-ink-muted focus-ring">
        <span>
          Match score{' '}
          <span className="font-semibold tabular-nums text-forest-700">{Math.round(score)}</span> / 100
          {factors.length > 0 && <span className="ml-1.5">· {factors.slice(0, 2).join(', ')}</span>}
        </span>
        <span className="text-forest-400 group-open:hidden">Why this ranking?</span>
        <span className="hidden text-forest-400 group-open:inline">Hide</span>
      </summary>

      <ul className="mt-3 space-y-2">
        {breakdown.map((c) => (
          <li key={c.factor} className="text-xs">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-medium text-forest-700">{c.detail || c.factor}</span>
              <span className="shrink-0 tabular-nums text-ink-muted">
                {c.points.toFixed(1)} / {c.weight.toFixed(0)} pts
              </span>
            </div>
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-forest-50">
              <div
                className="h-full rounded-full bg-forest-300"
                style={{ width: `${Math.min(100, Math.max(0, c.achieved * 100))}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </details>
  )
}
