import AdminAppointments from '../admin/Appointments'
import { useAuth } from '../../context/AuthContext'

/**
 * Read-only, and already scoped server-side: the backend only returns
 * appointments at hospitals this administrator manages.
 */
export default function HospitalAppointments() {
  const { managedHospitalIds } = useAuth()
  return <AdminAppointments hospitalScope={managedHospitalIds ?? []} />
}
