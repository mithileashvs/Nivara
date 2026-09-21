import {
  LayoutDashboard, Search, CalendarDays, FileText, Bell, User, LifeBuoy, Stethoscope,
  Users, Building2, LayoutGrid, BarChart3, Clock, Sparkles, ListChecks, ShieldCheck, Hospital,
} from 'lucide-react'

/** Sidebar entries per role. `exact` marks index routes so the highlight is accurate. */

export const patientNav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/find-doctors', label: 'Find doctors', icon: Search },
  { to: '/hospitals', label: 'Hospitals', icon: Hospital },
  { to: '/smart-suggestions', label: 'Symptom routing', icon: Sparkles },
  { to: '/appointments', label: 'My appointments', icon: CalendarDays },
  { to: '/waitlist', label: 'Waitlist', icon: ListChecks },
  { to: '/records', label: 'Medical records', icon: FileText },
  { to: '/notifications', label: 'Notifications', icon: Bell },
  { to: '/profile', label: 'Profile', icon: User },
  { to: '/help', label: 'Help & support', icon: LifeBuoy },
]

export const doctorNav = [
  { to: '/doctor', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/doctor/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/doctor/patients', label: 'Patients', icon: Users },
  { to: '/doctor/availability', label: 'Availability', icon: Clock },
  { to: '/doctor/statistics', label: 'Statistics', icon: BarChart3 },
  { to: '/doctor/notifications', label: 'Notifications', icon: Bell },
  { to: '/doctor/profile', label: 'Profile', icon: Stethoscope },
  { to: '/doctor/help', label: 'Help & support', icon: LifeBuoy },
]

export const adminNav = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/doctors', label: 'Doctors', icon: Stethoscope },
  { to: '/admin/hospitals', label: 'Hospitals', icon: Building2 },
  { to: '/admin/departments', label: 'Departments', icon: LayoutGrid },
  { to: '/admin/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/admin/routing-rules', label: 'Symptom routing rules', icon: ShieldCheck },
  { to: '/admin/notifications', label: 'Notifications', icon: Bell },
]

/** A hospital administrator is an ADMIN whose `managed_hospital_ids` is a list.
 *  The backend refuses platform-wide endpoints for them, so those links are absent. */
export const hospitalNav = [
  { to: '/hospital', label: 'Dashboard', icon: Hospital, exact: true },
  { to: '/hospital/departments', label: 'Departments', icon: LayoutGrid },
  { to: '/hospital/doctors', label: 'Doctors', icon: Stethoscope },
  { to: '/hospital/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/hospital/notifications', label: 'Notifications', icon: Bell },
]

/** Four items for the mobile bar — the rest stay in the drawer. */
export const mobileNavFor = (nav) => nav.slice(0, 4)
