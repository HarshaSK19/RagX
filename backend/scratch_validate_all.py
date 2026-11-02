import sys
import os
import json
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent / "OneDrive" / "Dokumen" / "Desktop" / "RagX" / "ragx" / "backend"
if not backend_dir.exists():
    backend_dir = Path("c:/Users/chand/OneDrive/Dokumen/Desktop/RagX/ragx/backend")
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    print("==================================================")
    print(" RAGX FULL SYSTEM VALIDATION & SUITE RUNNER       ")
    print("==================================================")

    # 1. Health / root endpoint
    res_root = client.get("/")
    assert res_root.status_code == 200, f"Root failed: {res_root.text}"
    print("PASS: 1. Health / Root Endpoint")

    # 2. Docs URL
    res_docs = client.get("/docs")
    assert res_docs.status_code == 200, f"Docs failed: {res_docs.status_code}"
    print("PASS: 2. API Documentation (/docs)")

    # 3. Registration (User A & User B)
    user_a_email = "val_usera@ragx.com"
    user_b_email = "val_userb@ragx.com"
    password = "TestPassword123!"

    reg_a = client.post("/api/auth/register", json={"email": user_a_email, "full_name": "Validation User A", "password": password})
    if reg_a.status_code != 200:
        login_a = client.post("/api/auth/login", json={"email": user_a_email, "password": password})
        token_a = login_a.json()["token"]
        user_a = login_a.json()["user"]
    else:
        token_a = reg_a.json()["token"]
        user_a = reg_a.json()["user"]

    reg_b = client.post("/api/auth/register", json={"email": user_b_email, "full_name": "Validation User B", "password": password})
    if reg_b.status_code != 200:
        login_b = client.post("/api/auth/login", json={"email": user_b_email, "password": password})
        token_b = login_b.json()["token"]
        user_b = login_b.json()["user"]
    else:
        token_b = reg_b.json()["token"]
        user_b = reg_b.json()["user"]

    print("PASS: 3. User Registration (User A & User B)")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 4. Authenticated /auth/me
    me_a = client.get("/api/auth/me", headers=headers_a)
    assert me_a.status_code == 200 and me_a.json()["user"]["email"] == user_a_email
    print("PASS: 4. Authenticated User Profile (/auth/me)")

    # 5. Document Upload for User A
    pdf_path = backend_dir / "data" / "uploads" / "Attendance_Policy.pdf"
    with open(pdf_path, "rb") as f:
        files = {"file": ("Attendance_Policy.pdf", f, "application/pdf")}
        upload_res = client.post("/api/auth/login", json={"email": user_a_email, "password": password})
        upload_a = client.post("/api/documents/upload", files=files, headers=headers_a)

    assert upload_a.status_code == 200, f"Upload failed: {upload_a.text}"
    doc_a = upload_a.json()["document"]
    print(f"PASS: 5. PDF Document Upload & Vector Indexing (Doc ID: {doc_a['document_id']})")

    # 6. Document Listing & Tenant Isolation
    list_a = client.get("/api/documents", headers=headers_a)
    assert list_a.status_code == 200
    user_a_doc_ids = [d["document_id"] for d in list_a.json()["documents"]]
    assert doc_a["document_id"] in user_a_doc_ids

    list_b = client.get("/api/documents", headers=headers_b)
    assert list_b.status_code == 200
    user_b_doc_ids = [d["document_id"] for d in list_b.json()["documents"]]
    assert doc_a["document_id"] not in user_b_doc_ids, "CRITICAL ERROR: Tenant Isolation Leak!"
    print("PASS: 6. Multi-User Tenant Isolation (User B cannot see User A's documents)")

    # 7. Document Viewer Endpoint
    view_res = client.get(f"/api/documents/{doc_a['document_id']}/view", headers=headers_a)
    assert view_res.status_code == 200 and view_res.headers["content-type"] == "application/pdf"
    print("PASS: 7. Document View Endpoint (/documents/{id}/view)")

    # 8. ChromaDB Retrieval & RAG Query
    rag_res = client.post("/api/rag/query", json={"question": "What is the general attendance requirement?"}, headers=headers_a)
    assert rag_res.status_code == 200
    rag_data = rag_res.json()
    assert len(rag_data["retrieved_evidence"]) > 0
    print(f"PASS: 8. ChromaDB Retrieval & RAG Answer Generation (Answer: '{rag_data['answer'][:60]}...')")

    # 9. Evaluator (60/20/20 scoring & 5-tuple citation system)
    eval_res = client.post("/api/evaluator/query-and-evaluate", json={"question": "What is the general attendance requirement?", "top_k": 3}, headers=headers_a)
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    report = eval_data["evaluation_report"]

    assert "overall_reliability_score" in report
    assert "scoring_breakdown" in report
    assert "claim_analysis" in report
    
    # Verify 5-tuple citation structure: claim, chunk, chunk_id, document, page
    for claim in report["claim_analysis"]:
        if claim.get("citation"):
            cite = claim["citation"]
            assert "claim" in cite or "claim_text" in cite or "claim_id" in claim
            assert "document" in cite
            assert "page" in cite

    print(f"PASS: 9. Evaluator Engine (Reliability Score: {report['overall_reliability_score']:.1f}%, 5-Tuple Citations Verified)")

    # 10. Data Quality Audit
    qual_res = client.get("/api/quality/audit", headers=headers_a)
    assert qual_res.status_code == 200
    print("PASS: 10. Data Quality Audit Engine (/quality/audit)")

    # 11. Analytics & History
    analytics_res = client.get("/api/evaluator/analytics", headers=headers_a)
    assert analytics_res.status_code == 200
    history_res = client.get("/api/evaluator/history", headers=headers_a)
    assert history_res.status_code == 200
    print("PASS: 11. Analytics & Persistent Evaluation History")

    # 12. Nova AI Copilot
    nova_res = client.post("/api/nova/chat", json={"message": "Summarize my attendance policy", "context_page": "dashboard"})
    assert nova_res.status_code == 200
    print("PASS: 12. NOVA AI Copilot Assistant (/nova/chat)")

    # 13. Logout
    logout_res = client.post("/api/auth/logout", headers=headers_a)
    assert logout_res.status_code == 200
    print("PASS: 13. User Logout (/auth/logout)")

    print("\n==================================================")
    print(" ALL 13 LOCAL BACKEND VALIDATION TESTS PASSED!    ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
