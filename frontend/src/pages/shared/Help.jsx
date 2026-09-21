import { PageHeader } from '../../components/Topbar'
import { Card, CardBody } from '../../components/ui/Card'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'

/* Explains how Nivara actually behaves. No ticketing endpoint exists, so
   this page does not offer a support form that would go nowhere. */
const FAQS = [
  [
    'Why does my appointment say "awaiting doctor"?',
    'Choosing a time creates a request and holds that slot. Your doctor accepts or declines it themselves — administrators never decide this. You are notified either way.',
  ],
  [
    'How long is my time held?',
    'Until your doctor decides, or until the hold expires. If it expires, the request is cancelled automatically and the time is released to anyone waiting for it.',
  ],
  [
    'Can I move an appointment?',
    'Yes, to another open time with the same doctor. Moving it sends it back for approval, so it returns to awaiting a decision until your doctor confirms the new time.',
  ],
  [
    'The hospital stopped taking appointments. Is mine cancelled?',
    'No. Closing intake only stops new requests. Appointments already requested or confirmed are never cancelled by it.',
  ],
  [
    'Does Nivara tell me what is wrong with me?',
    'No. It suggests which department to book with, and nothing more. It does not diagnose conditions, predict diseases, prescribe medicines, recommend dosages or plan treatment. For a medical emergency, contact your local emergency services.',
  ],
  [
    'Who can read my consultation notes?',
    'You and the doctor who wrote them. Administrators have no access to medical records at all.',
  ],
  [
    'Why can I not see any open times?',
    'Times come from a doctor\u2019s published working hours. If none are shown, that doctor has not published availability for those dates, everything is taken, or intake is closed. The waitlist will tell you when something opens.',
  ],
]

export default function Help() {
  useDocumentTitle('Help & support')
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Help & support" description="How Nivara works, and where to get help." />

      <Card>
        <ul className="divide-y divide-line">
          {FAQS.map(([q, a]) => (
            <li key={q} className="px-5 py-4">
              <h2 className="text-sm font-semibold text-forest-700">{q}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{a}</p>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="border-danger/30 bg-danger-soft">
        <CardBody>
          <h2 className="text-sm font-semibold text-forest-700">In an emergency</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
            Do not use Nivara. Contact your local emergency services immediately.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-forest-700">Still stuck?</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
            Contact the administrator at your hospital. They manage accounts, doctor profiles and
            departments, and can correct anything that looks wrong.
          </p>
        </CardBody>
      </Card>
    </div>
  )
}
