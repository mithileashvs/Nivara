"""Rule-based symptom -> DEPARTMENT routing.

This is routing for appointment booking only. It never diagnoses, predicts disease, or suggests
medicines, dosages or treatment. Rules live in the ``symptom_routing_rules`` collection (seeded from
``app/data/symptom_routing_rules.json``) and are editable by admins.
"""
import json
import re
from pathlib import Path
from typing import Any

from pymongo.errors import DuplicateKeyError  # noqa: F401

from app.core.errors import NotFoundError
from app.database.collections import C
from app.models.engagement import SymptomRoutingRule
from app.models.enums import DepartmentStatus, IntakeStatus
from app.schemas.admin import RoutingRuleCreate, RoutingRuleUpdate
from app.schemas.smart import DISCLAIMER
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.text import normalize
from app.utils.time_utils import utcnow

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "symptom_routing_rules.json"
FALLBACK_DEPARTMENT = "General Medicine"
MAX_SUGGESTIONS = 3

# Inputs asking for medication / diagnosis / treatment are not symptoms and are never processed.
OUT_OF_SCOPE = re.compile(
    r"\b(dose|dosage|mg|prescri\w*|medicine|medication|medicines|tablet|tablets|pill|pills|drug|drugs|antibiotic\w*|"
    r"treatment|treat|cure|diagnos\w*|what disease|which disease)\b",
    re.IGNORECASE,
)
OUT_OF_SCOPE_REASON = (
    "SmartCare does not diagnose conditions or recommend medicines, dosages or treatment, "
    "so this input was ignored. Only symptoms are used, and only to pick a department."
)
EMERGENCY_NOTICE = (
    "Some of the symptoms you entered can be signs of a medical emergency. If you or someone else is in "
    "immediate danger, contact your local emergency number now instead of waiting for an appointment."
)


def _phrase_in(keyword: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None


class DepartmentRoutingService:
    def __init__(self, db: Any) -> None:
        self.db = db

    @property
    def rules(self) -> Any:
        return self.db[C.SYMPTOM_ROUTING_RULES]

    async def ensure_default_rules(self) -> int:
        """Seed the default rules if the collection is empty. Returns the number inserted."""
        if await self.rules.count_documents({}) > 0:
            return 0
        data = json.loads(DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
        docs = [
            SymptomRoutingRule(
                department_name=r["department_name"], keywords=r["keywords"], weight=r.get("weight", 1.0),
                is_emergency=r.get("is_emergency", False),
            ).to_mongo()
            for r in data["rules"]
        ]
        await self.rules.insert_many(docs)
        return len(docs)

    async def suggest(self, symptoms: list[str], hospital_id: str | None = None) -> dict[str, Any]:
        usable: list[str] = []
        ignored: list[dict[str, str]] = []
        for raw in symptoms:
            if OUT_OF_SCOPE.search(raw):
                ignored.append({"input": raw, "reason": OUT_OF_SCOPE_REASON})
            else:
                usable.append(normalize(raw))

        rules = await self.rules.find({"is_active": True}).to_list(length=2000)
        per_dept: dict[str, dict[str, Any]] = {}
        matched_inputs: set[str] = set()
        emergency = False
        for symptom in usable:
            best_by_dept: dict[str, float] = {}
            for rule in rules:
                if any(_phrase_in(k, symptom) for k in rule["keywords"]):
                    name = rule["department_name"]
                    best_by_dept[name] = max(best_by_dept.get(name, 0.0), rule["weight"])
                    matched_inputs.add(symptom)
                    emergency = emergency or rule.get("is_emergency", False)
            for name, weight in best_by_dept.items():
                entry = per_dept.setdefault(name, {"score": 0.0, "symptoms": []})
                entry["score"] += weight
                entry["symptoms"].append(symptom)

        ranked = sorted(per_dept.items(), key=lambda kv: (-kv[1]["score"], kv[0]))[:MAX_SUGGESTIONS]
        suggestions = [
            {
                "department_name": name, "score": round(v["score"], 2), "matched_symptoms": v["symptoms"],
                "explanation": f"Matched {', '.join(v['symptoms'])} to the {name} department's routing rules.",
            }
            for name, v in ranked
        ]
        unmatched = [s for s in usable if s not in matched_inputs]
        if not suggestions:
            suggestions = [{
                "department_name": FALLBACK_DEPARTMENT, "score": 0.0, "matched_symptoms": [],
                "explanation": f"No specific routing rule matched, so {FALLBACK_DEPARTMENT} is suggested as the default starting point.",
            }]
        primary = suggestions[0]["department_name"]
        explanation = (
            f"Suggested department for booking: {primary}. "
            + ("This is based on keyword routing rules for the symptoms you listed. " if ranked else "")
            + "It is a scheduling aid, not medical advice."
        )
        return {
            "primary_department": primary,
            "suggested_departments": suggestions,
            "explanation": explanation,
            "unmatched_symptoms": unmatched,
            "ignored_inputs": ignored,
            "available_departments": await self._real_departments([s["department_name"] for s in suggestions], hospital_id),
            "emergency_notice": EMERGENCY_NOTICE if emergency else None,
            "disclaimer": DISCLAIMER,
        }

    async def _real_departments(self, names: list[str], hospital_id: str | None) -> list[dict[str, Any]]:
        open_hospitals = {
            h["_id"]: h["name"]
            async for h in self.db[C.HOSPITALS].find({"appointment_intake_status": IntakeStatus.OPEN}, {"name": 1})
        }
        query: dict[str, Any] = {
            "name_normalized": {"$in": [normalize(n) for n in names]},
            "status": DepartmentStatus.ACTIVE, "appointment_intake_status": IntakeStatus.OPEN,
            "hospital_id": {"$in": list(open_hospitals)},
        }
        if hospital_id:
            query["hospital_id"] = {"$in": [h for h in open_hospitals if h == oid(hospital_id)]}
        rows = await self.db[C.DEPARTMENTS].find(query).limit(10).to_list(length=10)
        return [
            {"department_id": str(d["_id"]), "hospital_id": str(d["hospital_id"]), "hospital_name": open_hospitals[d["hospital_id"]],
             "name": d["name"], "appointment_intake_status": d["appointment_intake_status"]}
            for d in rows
        ]

    # ---------------- admin CRUD ----------------

    async def list_rules(self, params: PageParams) -> tuple[list[dict], int]:
        return await paginate(self.rules, {}, params, sort=[("department_name_normalized", 1)])

    async def create_rule(self, payload: RoutingRuleCreate) -> dict:
        doc = SymptomRoutingRule(**payload.model_dump()).to_mongo()
        await self.rules.insert_one(doc)
        return doc

    async def update_rule(self, rule_id: str, payload: RoutingRuleUpdate) -> dict:
        rule = await self.rules.find_one({"_id": oid(rule_id)})
        if rule is None:
            raise NotFoundError("Routing rule not found", code="rule_not_found")
        merged = {**{k: rule[k] for k in ("department_name", "keywords", "weight", "is_emergency", "is_active")}, **payload.model_dump(exclude_unset=True)}
        normalized = SymptomRoutingRule(**merged)
        fields = {
            "department_name": normalized.department_name, "department_name_normalized": normalized.department_name_normalized,
            "keywords": normalized.keywords, "weight": normalized.weight, "is_emergency": normalized.is_emergency,
            "is_active": normalized.is_active, "updated_at": utcnow(),
        }
        return await self.rules.find_one_and_update({"_id": rule["_id"]}, {"$set": fields}, return_document=True)

    async def delete_rule(self, rule_id: str) -> None:
        res = await self.rules.delete_one({"_id": oid(rule_id)})
        if res.deleted_count == 0:
            raise NotFoundError("Routing rule not found", code="rule_not_found")
