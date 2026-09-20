"""Appointment optimisation: slot-level ranking of bookable appointment options.

Uses the same transparent factor scoring as doctor matching, but each *slot* is scored on its own
(earlier slots and slots inside the preferred time window rank higher). Not a medical recommendation.
"""
from typing import Any

from app.schemas.smart import MatchCriteria
from app.services.doctor_matching_service import DoctorMatchingService, slot_option


class AppointmentOptimizationService(DoctorMatchingService):
    async def find_options(self, c: MatchCriteria, page: int, page_size: int) -> dict[str, Any]:
        g = await self.gather(c)
        options: list[dict[str, Any]] = []
        for d in g.doctors:
            for s in self._preview(g.slots_by_doctor[d["_id"]], c):
                sc = self.score(g, d, [s], c, include_depth=False)
                options.append({
                    "slot": slot_option(s), "doctor_name": d["name"], "specialty": d["specialty"],
                    "hospital_name": g.hospitals[s["hospital_id"]]["name"], "department_name": g.departments[s["department_id"]]["name"],
                    "match_score": sc.score, "match_factors": sc.factors, "score_breakdown": sc.components,
                    "_sort": (-sc.score, s["start_at"], d["name"]),
                })
        options.sort(key=lambda o: o["_sort"])
        for o in options:
            o.pop("_sort")
        total = len(options)
        start = (page - 1) * page_size
        return {
            "items": options[start : start + page_size], "page": page, "page_size": page_size, "total": total,
            "total_pages": -(-total // page_size) if total else 0, "criteria_applied": self._criteria_applied(c, g),
        }
