import { useState } from 'react'
import { Download, FileSpreadsheet, ShieldCheck } from 'lucide-react'
import { downloadAnalyticsReport } from '../../api/analytics'
import { useToast } from '../../context/ToastContext'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ANALYTICS_REPORT_TYPES } from '../../utils/constants'
import { errorMessage } from '../../utils/errors'

export default function ReportsSection({ apiParams, filterValid, periodMeta, isPlatformAdmin }) {
  const toast = useToast()
  const [downloadingType, setDownloadingType] = useState(null)

  const handleDownload = async (reportType) => {
    if (!filterValid) {
      toast.error('Please enter a valid date range before exporting a report.')
      return
    }
    setDownloadingType(reportType)
    try {
      const filename = await downloadAnalyticsReport({ ...apiParams, report_type: reportType })
      toast.success(`Downloaded ${filename}`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setDownloadingType(null)
    }
  }

  return (
    <div className="space-y-6">
      <Alert tone="info" icon={ShieldCheck} title="Scoped Operational CSV Reports (Zero PII)" className="text-xs">
        Every export uses your exact selected date range ({periodMeta?.date_from || apiParams.preset}
        {periodMeta?.date_to ? ` to ${periodMeta.date_to}` : ''}), grouping ({apiParams.granularity}), and facility
        filters. {isPlatformAdmin ? 'Platform admin scope.' : 'Strictly restricted to your assigned hospital scope.'}{' '}
        Spreadsheet formula injection is automatically neutralized.
      </Alert>

      <div className="grid gap-4 md:grid-cols-2">
        {ANALYTICS_REPORT_TYPES.map((rep) => {
          const busy = downloadingType === rep.value
          return (
            <Card key={rep.value} className="flex flex-col justify-between transition-colors hover:border-forest-200">
              <CardHeader
                title={
                  <span className="flex items-center gap-2">
                    <FileSpreadsheet size={17} className="text-forest-500" aria-hidden="true" />
                    {rep.label}
                  </span>
                }
                description={rep.description}
              />
              <CardBody className="flex flex-1 flex-col justify-between gap-4">
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                    Included CSV Columns
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {rep.columns.map((col) => (
                      <span
                        key={col}
                        className="rounded-lg border border-line bg-canvas px-2 py-0.5 text-xs text-ink-muted"
                      >
                        {col}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-end border-t border-line pt-3">
                  <Button
                    variant="primary"
                    size="sm"
                    loading={busy}
                    disabled={!filterValid || Boolean(downloadingType && !busy)}
                    onClick={() => handleDownload(rep.value)}
                  >
                    <Download size={15} aria-hidden="true" />
                    Export CSV
                  </Button>
                </div>
              </CardBody>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
