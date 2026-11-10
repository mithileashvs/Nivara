import { Card, CardBody, CardHeader } from '../ui/Card'
import { EmptyState, ErrorState } from '../ui/States'

/**
 * Shared container for analytics visualizations with unified loading shimmer,
 * scoped error handling, and honest empty states.
 */
export function AnalyticsChartCard({
  title,
  description,
  action,
  loading = false,
  error = null,
  onRetry,
  empty = false,
  emptyTitle = 'No data in selected period',
  emptyDescription = 'Try widening the date range or clearing filters.',
  heightClass = 'h-72',
  className = '',
  children,
}) {
  return (
    <Card className={className}>
      <CardHeader title={title} description={description} action={action} />
      <CardBody>
        {loading ? (
          <div className={`skeleton w-full rounded-xl ${heightClass}`} aria-hidden="true" />
        ) : error ? (
          <ErrorState error={error} onRetry={onRetry} compact />
        ) : empty ? (
          <EmptyState title={emptyTitle} description={emptyDescription} />
        ) : (
          <div className={`w-full ${heightClass}`}>{children}</div>
        )}
      </CardBody>
    </Card>
  )
}
