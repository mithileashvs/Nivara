import AdminDepartments from '../admin/Departments'
import { useAuth } from '../../context/AuthContext'

/** The same screen as the platform view, limited to this administrator's hospitals. */
export default function HospitalDepartments() {
  const { managedHospitalIds } = useAuth()
  return <AdminDepartments hospitalScope={managedHospitalIds ?? []} />
}
