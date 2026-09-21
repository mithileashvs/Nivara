import { Route, Routes } from 'react-router-dom'
import { RedirectIfAuthenticated, RequireAuth, RequireRole } from './guards'
import { PublicLayout } from '../layouts/PublicLayout'
import { DashboardLayout } from '../layouts/DashboardLayout'
import { ROLES } from '../utils/constants'
import { adminNav, doctorNav, hospitalNav, patientNav } from '../utils/nav'

// public
import Landing from '../pages/public/Landing'
import Login from '../pages/public/Login'
import Register from '../pages/public/Register'
import About from '../pages/public/About'
import Contact from '../pages/public/Contact'
import NotFound from '../pages/public/NotFound'

// shared
import Notifications from '../pages/shared/Notifications'
import Help from '../pages/shared/Help'

// patient
import PatientDashboard from '../pages/patient/Dashboard'
import FindDoctors from '../pages/patient/FindDoctors'
import DoctorProfile from '../pages/patient/DoctorProfile'
import BookAppointment from '../pages/patient/BookAppointment'
import MyAppointments from '../pages/patient/MyAppointments'
import AppointmentDetail from '../pages/patient/AppointmentDetail'
import MedicalRecords from '../pages/patient/MedicalRecords'
import SmartSuggestions from '../pages/patient/SmartSuggestions'
import Waitlist from '../pages/patient/Waitlist'
import PatientProfile from '../pages/patient/Profile'
import PatientHospitals from '../pages/patient/Hospitals'

// doctor
import DoctorDashboard from '../pages/doctor/Dashboard'
import DoctorAppointments from '../pages/doctor/Appointments'
import DoctorAppointmentDetail from '../pages/doctor/AppointmentDetail'
import DoctorAvailability from '../pages/doctor/Availability'
import DoctorPatients from '../pages/doctor/Patients'
import DoctorStatistics from '../pages/doctor/Statistics'
import DoctorProfilePage from '../pages/doctor/Profile'

// admin
import AdminDashboard from '../pages/admin/Dashboard'
import AdminUsers from '../pages/admin/Users'
import AdminDoctors from '../pages/admin/Doctors'
import AdminHospitals from '../pages/admin/Hospitals'
import HospitalDetail from '../pages/admin/HospitalDetail'
import AdminDepartments from '../pages/admin/Departments'
import AdminAppointments from '../pages/admin/Appointments'
import AdminRoutingRules from '../pages/admin/RoutingRules'

// hospital administrator
import HospitalDashboard from '../pages/hospital/Dashboard'
import HospitalDoctors from '../pages/hospital/Doctors'
import HospitalDepartments from '../pages/hospital/Departments'
import HospitalAppointments from '../pages/hospital/Appointments'

/**
 * Route map. Guards mirror the backend's own authorisation so people are not
 * shown screens whose requests would be refused — the backend remains the
 * authority on every call.
 *
 * Hospital administration lives under /hospital and is reached by an ADMIN whose
 * `managed_hospital_ids` is a list. There is no fourth login role, because the
 * backend does not have one.
 */
export function AppRoutes() {
  return (
    <Routes>
      {/* ------------------------------------------------------- public */}
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="about" element={<About />} />
        <Route path="contact" element={<Contact />} />
      </Route>

      <Route element={<RedirectIfAuthenticated />}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Route>

      {/* ------------------------------------------------------ patient */}
      <Route element={<RequireRole roles={[ROLES.PATIENT]} />}>
        <Route element={<DashboardLayout nav={patientNav} />}>
          <Route path="/dashboard" element={<PatientDashboard />} />
          <Route path="/find-doctors" element={<FindDoctors />} />
          <Route path="/hospitals" element={<PatientHospitals />} />
          <Route path="/doctors/:doctorId" element={<DoctorProfile />} />
          <Route path="/book/:doctorId" element={<BookAppointment />} />
          <Route path="/appointments" element={<MyAppointments />} />
          <Route path="/appointments/:appointmentId" element={<AppointmentDetail />} />
          <Route path="/records" element={<MedicalRecords />} />
          <Route path="/smart-suggestions" element={<SmartSuggestions />} />
          <Route path="/waitlist" element={<Waitlist />} />
          <Route path="/notifications" element={<Notifications appointmentPathPrefix="/appointments" />} />
          <Route path="/profile" element={<PatientProfile />} />
          <Route path="/help" element={<Help />} />
        </Route>
      </Route>

      {/* ------------------------------------------------------- doctor */}
      <Route element={<RequireRole roles={[ROLES.DOCTOR]} />}>
        <Route
          path="/doctor"
          element={
            <DashboardLayout
              nav={doctorNav}
              notificationsPath="/doctor/notifications"
              profilePath="/doctor/profile"
            />
          }
        >
          <Route index element={<DoctorDashboard />} />
          <Route path="appointments" element={<DoctorAppointments />} />
          <Route path="appointments/:appointmentId" element={<DoctorAppointmentDetail />} />
          <Route path="availability" element={<DoctorAvailability />} />
          <Route path="patients" element={<DoctorPatients />} />
          <Route path="statistics" element={<DoctorStatistics />} />
          <Route
            path="notifications"
            element={<Notifications appointmentPathPrefix="/doctor/appointments" />}
          />
          <Route path="profile" element={<DoctorProfilePage />} />
          <Route path="help" element={<Help />} />
        </Route>
      </Route>

      {/* ------------------------------------------- platform administrator */}
      <Route element={<RequireRole roles={[ROLES.ADMIN]} hospitalScope={false} />}>
        <Route
          path="/admin"
          element={
            <DashboardLayout
              nav={adminNav}
              notificationsPath="/admin/notifications"
              profilePath="/admin"
            />
          }
        >
          <Route index element={<AdminDashboard />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="doctors" element={<AdminDoctors />} />
          <Route path="hospitals" element={<AdminHospitals />} />
          <Route path="hospitals/:hospitalId" element={<HospitalDetail basePath="/admin" />} />
          <Route path="departments" element={<AdminDepartments />} />
          <Route path="appointments" element={<AdminAppointments />} />
          <Route path="routing-rules" element={<AdminRoutingRules />} />
          <Route path="notifications" element={<Notifications appointmentPathPrefix="/admin/appointments" />} />
        </Route>
      </Route>

      {/* ------------------------------------------- hospital administrator */}
      <Route element={<RequireRole roles={[ROLES.ADMIN]} hospitalScope />}>
        <Route
          path="/hospital"
          element={
            <DashboardLayout
              nav={hospitalNav}
              notificationsPath="/hospital/notifications"
              profilePath="/hospital"
            />
          }
        >
          <Route index element={<HospitalDashboard />} />
          <Route path="doctors" element={<HospitalDoctors />} />
          <Route path="departments" element={<HospitalDepartments />} />
          <Route path="hospitals/:hospitalId" element={<HospitalDetail basePath="/hospital" />} />
          <Route path="appointments" element={<HospitalAppointments />} />
          <Route
            path="notifications"
            element={<Notifications appointmentPathPrefix="/hospital/appointments" />}
          />
        </Route>
      </Route>

      {/* Any signed-in person hitting an unknown path still gets a useful page. */}
      <Route element={<RequireAuth />}>
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
