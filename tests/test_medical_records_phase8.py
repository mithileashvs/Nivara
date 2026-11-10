"""Phase 8 Medical Records, Secure Upload/Download, Sharing Consent, Timeline & Supabase Transport Suite."""
from __future__ import annotations

import httpx

from app.services.storage_service import MedicalStorageService
from tests.conftest import make_settings

VALID_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
VALID_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
VALID_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
VALID_WEBP = b"RIFF\x24\x00\x00\x00WEBP" + b"\x00" * 32


async def test_document_upload_validation_magic_bytes_xss_size_and_path_traversal(world, tmp_path):
    world.settings.local_storage_dir = str(tmp_path)
    # Valid formats: PDF, PNG, JPEG, WEBP
    for fname, content, mime in (
        ("../../secret/lab_report.pdf", VALID_PDF, "application/pdf"),
        ("scan.png", VALID_PNG, "image/png"),
        ("xray.jpg", VALID_JPEG, "image/jpeg"),
        ("derm.webp", VALID_WEBP, "image/webp"),
    ):
        r = await world.api(
            "POST",
            "/medical-records/documents/upload",
            world.p1,
            files={"file": (fname, content, mime)},
            data={"title": f"Test {fname}", "category": "LAB_REPORT"},
        )
        assert r.status_code == 201, r.text
        assert "/" not in r.json()["filename"] and "\\" not in r.json()["filename"]

    # Reject empty, disallowed extension, magic-byte mismatch, XSS/script payload
    bad_cases = (
        ("empty.pdf", b"", "application/pdf", "empty_file"),
        ("malware.exe", b"MZ\x90\x00", "application/octet-stream", "invalid_file_extension"),
        ("spoof.pdf", VALID_PNG, "application/pdf", "mime_extension_mismatch"),
        ("xss.png", VALID_PNG + b"<script>alert(1)</script>", "image/png", "dangerous_file_content"),
        ("php.png", VALID_PNG + b"<?php system('id'); ?>", "image/png", "dangerous_file_content"),
    )
    for fname, content, mime, code in bad_cases:
        r = await world.api(
            "POST",
            "/medical-records/documents/upload",
            world.p1,
            files={"file": (fname, content, mime)},
            data={"title": "Bad", "category": "OTHER"},
        )
        assert r.status_code == 400, f"{fname} should fail 400, got {r.status_code}: {r.text}"
        assert r.json()["error"]["code"] == code

    # Reject oversized upload
    world.settings.max_document_upload_bytes = 1024
    r_big = await world.api(
        "POST",
        "/medical-records/documents/upload",
        world.p1,
        files={"file": ("big.pdf", VALID_PDF + b"A" * 2048, "application/pdf")},
        data={"title": "Too Big", "category": "OTHER"},
    )
    assert r_big.status_code == 400 and r_big.json()["error"]["code"] == "file_too_large"


async def test_document_download_sharing_immediate_revocation_audit_and_delete(world, tmp_path):
    world.settings.local_storage_dir = str(tmp_path)
    up = await world.api(
        "POST",
        "/medical-records/documents/upload",
        world.p1,
        files={"file": ("cardio_echo.pdf", VALID_PDF, "application/pdf")},
        data={"title": "Cardiology Echo", "category": "IMAGING", "description": "Annual echo"},
    )
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]

    # Owner download checks binary & security headers
    dl_own = await world.api("GET", f"/medical-records/documents/{doc_id}/download", world.p1)
    assert dl_own.status_code == 200
    assert dl_own.content == VALID_PDF
    assert dl_own.headers.get("x-content-type-options") == "nosniff"
    assert "no-store" in (dl_own.headers.get("cache-control") or "")
    assert "attachment" in (dl_own.headers.get("content-disposition") or "")

    # Unrelated patient (p2) & unshared doctor (d1) blocked with 403 -> recorded as UNAUTHORIZED_ATTEMPT
    assert (await world.api("GET", f"/medical-records/documents/{doc_id}/download", world.p2)).status_code == 403
    assert (await world.api("GET", f"/medical-records/documents/{doc_id}/download", world.d1)).status_code == 403
    assert (await world.api("GET", f"/medical-records/shared/{doc_id}", world.d1)).status_code == 403

    # P1 grants explicit share consent to d1
    sh = await world.api(
        "POST",
        f"/medical-records/documents/{doc_id}/share",
        world.p1,
        json={"doctor_id": world.d1.id, "notes": "Please review prior to visit"},
    )
    assert sh.status_code == 201, sh.text
    assert sh.json()["consent_status"] == "GRANTED"

    # Doctor lists /shared (must resolve patient_name!) & downloads
    shared_list = (await world.api("GET", "/medical-records/shared", world.d1)).json()
    assert shared_list["total"] == 1
    assert shared_list["items"][0]["id"] == doc_id
    assert shared_list["items"][0]["patient_name"] == world.p1.name

    dl_doc = await world.api("GET", f"/medical-records/documents/{doc_id}/download", world.d1)
    assert dl_doc.status_code == 200 and dl_doc.content == VALID_PDF

    # P1 revokes consent -> d1 access immediately blocked
    rev = await world.api("DELETE", f"/medical-records/documents/{doc_id}/share/{world.d1.id}", world.p1)
    assert rev.status_code == 200 and rev.json()["consent_status"] == "REVOKED"
    assert (await world.api("GET", f"/medical-records/documents/{doc_id}/download", world.d1)).status_code == 403
    assert (await world.api("GET", f"/medical-records/shared/{doc_id}", world.d1)).status_code == 403
    assert (await world.api("GET", "/medical-records/shared", world.d1)).json()["total"] == 0

    # Patient & Admin audit visibility + admin stats (metadata only)
    p_audits = (await world.api("GET", "/medical-records/audits?page_size=50", world.p1)).json()
    actions = {a["action"] for a in p_audits["items"]}
    assert {"UPLOAD", "DOWNLOAD", "SHARE_GRANTED", "SHARE_REVOKED", "UNAUTHORIZED_ATTEMPT"} <= actions

    stats = (await world.api("GET", "/medical-records/admin/stats", world.admin)).json()
    assert stats["total_documents"] >= 1
    assert stats["active_shares"] == 0

    # Delete revokes and removes file
    del_r = await world.api("DELETE", f"/medical-records/documents/{doc_id}", world.p1)
    assert del_r.status_code == 200
    assert (await world.api("GET", f"/medical-records/documents/{doc_id}", world.p1)).status_code == 404


async def test_medical_timeline_aggregates_documents_appointments_and_consultation_notes(world, tmp_path):
    world.settings.local_storage_dir = str(tmp_path)
    await world.add_window(world.d1, start="09:00", end="10:00")
    appt = await world.book(world.p1, world.d1, "09:00", confirm=True)

    # Doctor records consultation notes
    note_r = await world.api(
        "POST",
        "/medical-records",
        world.d1,
        json={"appointment_id": appt["id"], "notes": "Routine physical checkup complete."},
    )
    assert note_r.status_code == 201, note_r.text

    # Patient uploads lab document
    up_r = await world.api(
        "POST",
        "/medical-records/documents/upload",
        world.p1,
        files={"file": ("cbc.pdf", VALID_PDF, "application/pdf")},
        data={"title": "CBC Panel", "category": "LAB_REPORT", "appointment_id": appt["id"]},
    )
    assert up_r.status_code == 201, up_r.text
    doc_id = up_r.json()["id"]

    # Patient timeline contains all 3 types
    tl = (await world.api("GET", "/medical-records/timeline?page_size=20", world.p1)).json()
    types = {item["item_type"] for item in tl["items"]}
    assert types == {"DOCUMENT", "APPOINTMENT", "CONSULTATION_NOTE"}

    # Treating doctor d1 can view p1's timeline; shared docs require consent; unrelated doctor d2 gets 403
    assert (await world.api("GET", f"/medical-records/patients/{world.p1.id}/timeline", world.d2)).status_code == 403
    tl_d1_before = (await world.api("GET", f"/medical-records/patients/{world.p1.id}/timeline", world.d1)).json()
    assert {i["item_type"] for i in tl_d1_before["items"]} == {"APPOINTMENT", "CONSULTATION_NOTE"}

    await world.api("POST", f"/medical-records/documents/{doc_id}/share", world.p1, json={"doctor_id": world.d1.id})
    tl_d1_after = (await world.api("GET", f"/medical-records/patients/{world.p1.id}/timeline", world.d1)).json()
    assert {i["item_type"] for i in tl_d1_after["items"]} == {"DOCUMENT", "APPOINTMENT", "CONSULTATION_NOTE"}


async def test_supabase_storage_provider_uses_private_authenticated_endpoints(monkeypatch):
    captured: list[tuple[str, str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append((request.method, str(request.url), dict(request.headers)))
        if request.method == "GET":
            return httpx.Response(200, content=VALID_PDF)
        return httpx.Response(200, json={"Key": "ok"})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: real_async_client(transport=transport, **{k: v for k, v in kwargs.items() if k != "transport"}),
    )

    sb_settings = make_settings(
        document_storage_provider="supabase",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-secret-value-for-testing-1234",
        supabase_storage_bucket="medical-documents",
    )
    svc = MedicalStorageService(sb_settings)
    storage_path, mime, size, provider = await svc.save_file("patient-1", "test.pdf", VALID_PDF)
    assert provider == "SUPABASE" and mime == "application/pdf" and size == len(VALID_PDF)
    downloaded, _ = await svc.read_file_bytes(storage_path, storage_provider="SUPABASE")
    assert downloaded == VALID_PDF
    await svc.delete_file(storage_path, storage_provider="SUPABASE")

    assert len(captured) == 3
    assert captured[0][0] == "POST"
    assert "/storage/v1/object/medical-documents/" in captured[0][1]
    assert captured[1][0] == "GET"
    assert "/storage/v1/object/authenticated/medical-documents/" in captured[1][1]
    assert "/object/public/" not in captured[1][1]
    assert captured[1][2].get("authorization") == "Bearer service-role-secret-value-for-testing-1234"
    assert captured[2][0] == "DELETE"
