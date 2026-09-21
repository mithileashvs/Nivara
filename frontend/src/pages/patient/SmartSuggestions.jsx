import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Plus, Sparkles, X } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { MedicalDisclaimer } from '../../components/MedicalDisclaimer'
import { ScoreBreakdown } from '../../components/ScoreBreakdown'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Select } from '../../components/ui/Field'
import { Badge } from '../../components/ui/StatusBadge'
import { ErrorState, LoadingBlock, EmptyState } from '../../components/ui/States'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { suggestDepartment, matchDoctors } from '../../api/smart'
import { formatTime, formatDate } from '../../utils/format'

/**
 * Symptom → department routing, plus the backend's doctor matching.
 *
 * This is appointment routing, nothing more. The backend explicitly ignores
 * inputs that ask for a diagnosis, medicine or dosage, and returns them under
 * `ignored_inputs` — those are surfaced honestly rather than hidden. The
 * disclaimer shown is the backend's own string when it sends one.
 */
export default function SmartSuggestions() {
  useDocumentTitle('Symptom routing')
  const { hospitals, hospitalById, departmentById } = useDirectory()

  const [symptoms, setSymptoms] = useState([])
  const [draft, setDraft] = useState('')
  const [hospitalId, setHospitalId] = useState('')

  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const [matches, setMatches] = useState(null)
  const [matchLoading, setMatchLoading] = useState(false)
  const [matchError, setMatchError] = useState(null)

  const addSymptom = () => {
    const value = draft.trim()
    if (!value || symptoms.includes(value) || symptoms.length >= 20) return
    setSymptoms((s) => [...s, value.slice(0, 80)])
    setDraft('')
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!symptoms.length) return
    setLoading(true)
    setError(null)
    setMatches(null)
    try {
      setResult(await suggestDepartment({ symptoms, hospital_id: hospitalId || undefined }))
    } catch (err) {
      setError(err)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  /** Ask the backend which doctors in that department have genuinely bookable slots. */
  const findDoctors = async (department) => {
    setMatchLoading(true)
    setMatchError(null)
    try {
      const page = await matchDoctors(
        { department_id: department.department_id, hospital_id: department.hospital_id },
        { page: 1, page_size: 10 },
      )
      setMatches({ department, page })
    } catch (err) {
      setMatchError(err)
    } finally {
      setMatchLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Which department should I book with?"
        description="List what you're experiencing and Nivara will point you to the right department."
      />

      <Card>
        <CardBody>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label htmlFor="symptom" className="mb-1.5 block text-sm font-medium text-forest-700">
                What are you experiencing?
              </label>
              <div className="flex gap-2">
                <input
                  id="symptom"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addSymptom()
                    }
                  }}
                  maxLength={80}
                  placeholder="Headache, fever, chest pain…"
                  className="h-11 flex-1 rounded-xl border border-line bg-surface px-3.5 text-sm placeholder:text-ink-faint hover:border-forest-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
                />
                <Button variant="secondary" onClick={addSymptom} disabled={!draft.trim()}>
                  <Plus size={16} aria-hidden="true" />
                  Add
                </Button>
              </div>
              <p className="mt-1.5 text-xs text-ink-muted">
                Add up to 20. Press Enter after each one.
              </p>
            </div>

            {symptoms.length > 0 && (
              <ul className="flex flex-wrap gap-2">
                {symptoms.map((s) => (
                  <li key={s}>
                    <button
                      type="button"
                      onClick={() => setSymptoms((prev) => prev.filter((x) => x !== s))}
                      className="inline-flex items-center gap-1.5 rounded-full border border-forest-200 bg-forest-50 px-3 py-1 text-sm text-forest-700 transition-colors hover:border-danger/40 hover:bg-danger-soft focus-ring"
                    >
                      {s}
                      <X size={13} aria-hidden="true" />
                      <span className="sr-only">Remove {s}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <Select
              label="Restrict to a hospital (optional)"
              placeholder="Any hospital"
              value={hospitalId}
              onChange={(e) => setHospitalId(e.target.value)}
              options={hospitals.map((h) => ({ value: h.id, label: h.name }))}
            />

            <Button type="submit" size="lg" loading={loading} disabled={!symptoms.length} className="w-full justify-center">
              <Sparkles size={17} aria-hidden="true" />
              Suggest a department
            </Button>
          </form>
        </CardBody>
      </Card>

      {error && <ErrorState error={error} />}
      {loading && <LoadingBlock label="Finding the right department" />}

      {result && !loading && (
        <>
          <MedicalDisclaimer text={result.disclaimer} emergencyNotice={result.emergency_notice} />

          <Card>
            <CardHeader
              title={`Suggested department: ${result.primary_department}`}
              description="Based on the symptoms you listed, for appointment routing."
            />
            <CardBody className="space-y-5">
              <p className="text-sm leading-relaxed text-ink-muted">{result.explanation}</p>

              {result.suggested_departments?.length > 0 && (
                <ul className="space-y-3">
                  {result.suggested_departments.map((s) => (
                    <li key={s.department_name} className="rounded-xl border border-line p-4">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-sm font-semibold text-forest-700">{s.department_name}</p>
                        <span className="text-xs tabular-nums text-ink-muted">
                          Match strength {s.score.toFixed(1)}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm text-ink-muted">{s.explanation}</p>
                      {s.matched_symptoms?.length > 0 && (
                        <p className="mt-2 flex flex-wrap gap-1.5">
                          {s.matched_symptoms.map((m) => (
                            <span key={m} className="rounded-md bg-forest-50 px-2 py-0.5 text-[0.7rem] text-forest-500">
                              {m}
                            </span>
                          ))}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {result.unmatched_symptoms?.length > 0 && (
                <p className="text-xs text-ink-muted">
                  Nivara had no routing rule for: {result.unmatched_symptoms.join(', ')}. Your
                  doctor is the right person to ask about those.
                </p>
              )}

              {result.ignored_inputs?.length > 0 && (
                <div className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3">
                  <p className="text-sm font-medium text-forest-700">Some input was not used</p>
                  <ul className="mt-1.5 space-y-1 text-xs text-ink-muted">
                    {result.ignored_inputs.map((i) => (
                      <li key={i.input}>
                        <span className="font-medium">{i.input}</span> — {i.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Departments you can book with now"
              description="Real departments matching the suggestion that are currently accepting requests."
            />
            {result.available_departments?.length ? (
              <ul className="divide-y divide-line">
                {result.available_departments.map((dept) => (
                  <li key={dept.department_id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-forest-700">{dept.name}</p>
                      <p className="truncate text-xs text-ink-muted">{dept.hospital_name}</p>
                    </div>
                    <Badge tone={dept.appointment_intake_status === 'OPEN' ? 'positive' : 'neutral'}>
                      {dept.appointment_intake_status === 'OPEN' ? 'Open' : 'Closed'}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => findDoctors(dept)}
                      loading={matchLoading}
                    >
                      Find doctors
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <CardBody>
                <EmptyState
                  title="No matching department is open right now"
                  description="Try another hospital, or browse all doctors instead."
                  action={
                    <Link
                      to="/find-doctors"
                      className="inline-flex h-11 items-center rounded-xl bg-forest px-5 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
                    >
                      Browse doctors
                    </Link>
                  }
                />
              </CardBody>
            )}
          </Card>
        </>
      )}

      {matchError && <ErrorState error={matchError} />}

      {matches && (
        <Card>
          <CardHeader
            title={`Doctors in ${matches.department.name}`}
            description="Ranked by Nivara, with the reasoning shown. Only doctors with genuinely open times appear."
          />
          {matches.page.items.length ? (
            <ul className="divide-y divide-line">
              {matches.page.items.map((m) => (
                <li key={m.doctor_id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        to={`/doctors/${m.doctor_id}`}
                        className="rounded text-sm font-semibold text-forest-700 transition-colors hover:text-forest focus-ring"
                      >
                        {m.doctor_name}
                      </Link>
                      <p className="mt-0.5 text-xs text-ink-muted">{m.specialty}</p>
                      {m.next_available && (
                        <p className="mt-1.5 text-xs text-ink-muted">
                          Next open time {formatDate(m.next_available.date)} at{' '}
                          {formatTime(m.next_available.start_time)}
                        </p>
                      )}
                    </div>
                    <Link
                      to={`/doctors/${m.doctor_id}`}
                      className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-forest px-3 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
                    >
                      View
                      <ArrowRight size={14} aria-hidden="true" />
                    </Link>
                  </div>
                  <ScoreBreakdown
                    score={m.match_score}
                    breakdown={m.score_breakdown}
                    factors={m.match_factors}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <CardBody>
              <EmptyState
                title="No doctors with open times"
                description="Nobody in this department has a bookable slot at the moment. Joining the waitlist will tell you when one opens."
              />
            </CardBody>
          )}
          <CardBody className="border-t border-line pt-4">
            <MedicalDisclaimer text={matches.page.disclaimer} />
          </CardBody>
        </Card>
      )}
    </div>
  )
}
