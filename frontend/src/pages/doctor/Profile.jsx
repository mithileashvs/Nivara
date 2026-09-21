import { useEffect, useState } from 'react'
import { PageHeader } from '../../components/Topbar'
import { Avatar } from '../../components/ui/Avatar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Checkbox, Input } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { RatingStars } from '../../components/RatingStars'
import { IntakeToggle } from '../../components/IntakeToggle'
import { ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { setDoctorIntake, updateMyDoctorProfile } from '../../api/doctors'
import { CONSULTATION_TYPES } from '../../utils/constants'
import { errorMessage, fieldErrors } from '../../utils/errors'

/**
 * Doctors edit experience, fee and consultation types. Specialty and hospital or
 * department affiliations are platform-verified and changed by an administrator,
 * so those are shown read-only rather than as inputs that would be rejected.
 */
export default function DoctorProfilePage() {
  useDocumentTitle('Profile')
  const { user, doctorProfile, refreshDoctorProfile } = useAuth()
  const { hospitalById, departmentById } = useDirectory()
  const toast = useToast()

  const [form, setForm] = useState(null)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    if (!doctorProfile) return
    setForm({
      experience: String(doctorProfile.experience ?? 0),
      consultation_fee: String(doctorProfile.consultation_fee ?? 0),
      consultation_types: doctorProfile.consultation_types ?? [],
    })
  }, [doctorProfile])

  if (loadError) return <ErrorState error={loadError} onRetry={() => refreshDoctorProfile().catch(setLoadError)} />
  if (!doctorProfile || !form) return <LoadingSkeleton variant="cards" rows={1} />

  const toggleType = (value) =>
    setForm((f) => ({
      ...f,
      consultation_types: f.consultation_types.includes(value)
        ? f.consultation_types.filter((v) => v !== value)
        : [...f.consultation_types, value],
    }))

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErrors({})
    try {
      await updateMyDoctorProfile({
        experience: Number(form.experience),
        consultation_fee: Number(form.consultation_fee),
        ...(form.consultation_types.length ? { consultation_types: form.consultation_types } : {}),
      })
      await refreshDoctorProfile()
      toast.success('Profile saved.')
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const changeIntake = async (status, reason) => {
    try {
      await setDoctorIntake(doctorProfile.id, status, reason)
      await refreshDoctorProfile()
      toast.success(status === 'OPEN' ? 'Accepting new requests.' : 'New requests paused.')
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const hospitals = (doctorProfile.hospital_ids ?? []).map((id) => hospitalById[id]?.name).filter(Boolean)
  const departments = (doctorProfile.department_ids ?? []).map((id) => departmentById[id]?.name).filter(Boolean)

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="Profile" description="How you appear to patients on Nivara." />

      <Card>
        <CardBody className="flex flex-wrap items-center gap-4">
          <Avatar name={user?.name} size="xl" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-semibold text-forest-700">{user?.name}</p>
            <p className="truncate text-sm text-ink-muted">{doctorProfile.specialty}</p>
            <p className="truncate text-xs text-ink-faint">{user?.email}</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <StatusBadge status={doctorProfile.profile_status} kind="generic" />
              <RatingStars average={doctorProfile.rating_average} count={doctorProfile.rating_count} />
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="New appointment requests"
          description="Pausing stops new requests. Appointments already accepted are unaffected."
          action={<IntakeToggle status={doctorProfile.availability_status} onChange={changeIntake} />}
        />
      </Card>

      <form onSubmit={save}>
        <Card>
          <CardHeader title="Practice details" />
          <CardBody className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Years of experience"
                type="number"
                min="0"
                max="70"
                value={form.experience}
                onChange={(e) => setForm((f) => ({ ...f, experience: e.target.value }))}
                error={errors.experience}
              />
              <Input
                label="Consultation fee"
                type="number"
                min="0"
                step="1"
                value={form.consultation_fee}
                onChange={(e) => setForm((f) => ({ ...f, consultation_fee: e.target.value }))}
                error={errors.consultation_fee}
              />
            </div>

            <fieldset>
              <legend className="mb-2 text-sm font-medium text-forest-700">Consultation types you offer</legend>
              <div className="space-y-2">
                {CONSULTATION_TYPES.map((t) => (
                  <Checkbox
                    key={t.value}
                    label={t.label}
                    checked={form.consultation_types.includes(t.value)}
                    onChange={() => toggleType(t.value)}
                  />
                ))}
              </div>
              {errors.consultation_types && (
                <p className="mt-1.5 text-xs text-danger">{errors.consultation_types}</p>
              )}
            </fieldset>
          </CardBody>
        </Card>

        <Card className="mt-5">
          <CardHeader
            title="Verified details"
            description="Changed by an administrator, so patients can trust them."
          />
          <CardBody>
            <dl className="grid gap-5 sm:grid-cols-2">
              <Detail label="Specialty" value={doctorProfile.specialty} />
              <Detail label="Profile status" value={doctorProfile.profile_status} />
              <Detail label="Hospitals" value={hospitals.join(', ') || 'Not assigned'} />
              <Detail label="Departments" value={departments.join(', ') || 'Not assigned'} />
            </dl>
          </CardBody>
        </Card>

        <div className="mt-5 flex justify-end">
          <Button type="submit" size="lg" loading={saving}>
            Save changes
          </Button>
        </div>
      </form>
    </div>
  )
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="mt-1 text-sm text-forest-700">{value}</dd>
    </div>
  )
}
