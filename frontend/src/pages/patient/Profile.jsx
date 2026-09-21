import { useEffect, useState } from 'react'
import { PageHeader } from '../../components/Topbar'
import { Avatar } from '../../components/ui/Avatar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Field'
import { ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { useAuth } from '../../context/AuthContext'
import { getMyProfile, updateMyProfile } from '../../api/patients'
import { GENDERS } from '../../utils/constants'
import { errorMessage, fieldErrors } from '../../utils/errors'

/** Only the fields PatientUpdate accepts are editable; email is not one of them. */
export default function PatientProfile() {
  useDocumentTitle('Profile')
  const toast = useToast()
  const { refreshUser } = useAuth()
  const profile = useAsync(() => getMyProfile(), [])

  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  useEffect(() => {
    const p = profile.data
    if (!p) return
    setForm({
      name: p.name || '',
      phone: p.phone || '',
      date_of_birth: p.date_of_birth || '',
      gender: p.gender || '',
      address_line: p.basic_information?.address_line || '',
      city: p.basic_information?.city || '',
      emergency_contact_name: p.basic_information?.emergency_contact_name || '',
      emergency_contact_phone: p.basic_information?.emergency_contact_phone || '',
    })
  }, [profile.data])

  if (profile.loading || !form) return <LoadingSkeleton variant="cards" rows={1} />
  if (profile.error) return <ErrorState error={profile.error} onRetry={profile.reload} />

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErrors({})
    const payload = {
      name: form.name.trim(),
      ...(form.phone.trim() ? { phone: form.phone.trim() } : {}),
      ...(form.date_of_birth ? { date_of_birth: form.date_of_birth } : {}),
      ...(form.gender ? { gender: form.gender } : {}),
      basic_information: {
        address_line: form.address_line.trim() || null,
        city: form.city.trim() || null,
        emergency_contact_name: form.emergency_contact_name.trim() || null,
        ...(form.emergency_contact_phone.trim()
          ? { emergency_contact_phone: form.emergency_contact_phone.trim() }
          : {}),
      },
    }
    try {
      await updateMyProfile(payload)
      await refreshUser()
      profile.reload()
      toast.success('Profile saved.')
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="Profile" description="Your details, as your care team sees them." />

      <Card>
        <CardBody className="flex items-center gap-4">
          <Avatar name={profile.data.name} size="xl" />
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold text-forest-700">{profile.data.name}</p>
            <p className="truncate text-sm text-ink-muted">{profile.data.email}</p>
            <p className="mt-1 text-xs text-ink-faint">
              Your email address is fixed. Ask an administrator if it needs to change.
            </p>
          </div>
        </CardBody>
      </Card>

      <form onSubmit={save}>
        <Card>
          <CardHeader title="Personal details" />
          <CardBody className="space-y-4">
            <Input label="Full name" required value={form.name} onChange={set('name')} error={errors.name} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Phone"
                type="tel"
                value={form.phone}
                onChange={set('phone')}
                error={errors.phone}
                placeholder="+91 98765 43210"
              />
              <Input
                label="Date of birth"
                type="date"
                max={new Date().toISOString().slice(0, 10)}
                value={form.date_of_birth}
                onChange={set('date_of_birth')}
                error={errors.date_of_birth}
              />
            </div>
            <Select
              label="Gender"
              placeholder="Prefer not to say"
              value={form.gender}
              onChange={set('gender')}
              options={GENDERS}
              error={errors.gender}
            />
          </CardBody>
        </Card>

        <Card className="mt-5">
          <CardHeader title="Contact details" description="Used by the hospital if they need to reach you." />
          <CardBody className="space-y-4">
            <Input label="Address" value={form.address_line} onChange={set('address_line')} maxLength={200} error={errors.address_line} />
            <Input label="City" value={form.city} onChange={set('city')} maxLength={80} error={errors.city} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Emergency contact name"
                value={form.emergency_contact_name}
                onChange={set('emergency_contact_name')}
                maxLength={100}
                error={errors.emergency_contact_name}
              />
              <Input
                label="Emergency contact phone"
                type="tel"
                value={form.emergency_contact_phone}
                onChange={set('emergency_contact_phone')}
                error={errors.emergency_contact_phone}
              />
            </div>
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
