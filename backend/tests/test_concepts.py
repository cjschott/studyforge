from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base, Concept, ConceptRelationship, SourceChunk, SourceConcept, SourceLibrary, SourceMaterial, User


def make_client(tmp_path, monkeypatch, login=True, role="admin"):
    monkeypatch.setenv("STUDYFORGE_SOURCE_ORIGINALS_DIR", str(tmp_path / "sources" / "originals"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(
            username="admin",
            display_name="Administrator",
            password_hash=hash_password("changeme"),
            role=role,
            is_active=True,
        )
        library = SourceLibrary(
            name="CompTIA",
            description="Security+ sources",
            category="certification",
        )
        db.add_all([user, library])
        db.commit()
        user_id = user.id
        library_id = library.id

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    if login:
        client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    return client, TestingSessionLocal, library_id, user_id


def create_material_with_chunks(session_factory, library_id, user_id, chunks):
    with session_factory() as db:
        material = SourceMaterial(
            library_id=library_id,
            title="Security+ Concept Notes",
            source_type="markdown",
            authority_level=4,
            confidence="reviewed",
            verification_status="needs_review",
            copyright_status="owned",
            original_filename="concepts.md",
            stored_path=str(Path("concepts.md")),
            original_url="",
            checksum=("a" * 63) + str(library_id),
            uploaded_by=user_id,
        )
        db.add(material)
        db.flush()
        for index, item in enumerate(chunks, start=1):
            db.add(
                SourceChunk(
                    source_id=material.id,
                    chunk_number=index,
                    page_number=item.get("page_number"),
                    heading=item.get("heading", ""),
                    text=item["text"],
                    checksum=(str(index) * 64)[:64],
                )
            )
        db.commit()
        return material.id


def create_concept(session_factory, name, **fields):
    with session_factory() as db:
        concept = Concept(
            name=name,
            normalized_name=fields.get("normalized_name") or name.lower(),
            description=fields.get("description", ""),
            course_code=fields.get("course_code"),
            status=fields.get("status", "generated"),
            confidence=fields.get("confidence", "generated"),
        )
        db.add(concept)
        db.commit()
        return concept.id


def create_source_concept_link(session_factory, material_id, concept_id, evidence="Firewall filters packets."):
    with session_factory() as db:
        chunk = db.query(SourceChunk).filter_by(source_id=material_id).order_by(SourceChunk.chunk_number).first()
        link = SourceConcept(
            source_id=material_id,
            source_chunk_id=chunk.id,
            concept_id=concept_id,
            evidence_text=evidence,
            confidence_score=0.8,
            extraction_method="manual",
        )
        db.add(link)
        db.commit()
        return link.id


def extract_names(response_json):
    return {item["concept"]["normalized_name"]: item["concept"] for item in response_json["concepts"]}


def test_unauthenticated_concept_endpoints_return_401(tmp_path, monkeypatch):
    client, _, _, _ = make_client(tmp_path, monkeypatch, login=False)

    endpoints = [
        ("GET", "/api/concepts", None),
        ("POST", "/api/concepts", {"name": "Firewall"}),
        ("GET", "/api/concepts/1", None),
        ("PUT", "/api/concepts/1", {"status": "reviewed"}),
        ("DELETE", "/api/concepts/1", None),
        ("GET", "/api/concepts/1/aliases", None),
        ("POST", "/api/concepts/1/aliases", {"alias": "Packet filter"}),
        ("DELETE", "/api/concepts/1/aliases/1", None),
        ("POST", "/api/concepts/1/merge", {"target_concept_id": 2}),
        ("POST", "/api/concepts/1/review", None),
        ("POST", "/api/concepts/1/verify", None),
        ("POST", "/api/concepts/1/reject", None),
        ("POST", "/api/concepts/1/restore", None),
        ("GET", "/api/concepts/1/evidence", None),
        ("GET", "/api/source-materials/1/concepts", None),
        ("POST", "/api/source-materials/1/extract-concepts", {}),
        ("GET", "/api/concepts/1/sources", None),
        ("GET", "/api/concepts/1/relationships", None),
        ("POST", "/api/concepts/1/relationships", {"concept_b_id": 2, "relationship_type": "related_to"}),
        ("PUT", "/api/concept-relationships/1", {"status": "reviewed"}),
        ("DELETE", "/api/concept-relationships/1", None),
    ]

    for method, path, payload in endpoints:
        response = client.request(method, path, json=payload)
        assert response.status_code == 401


def test_extracted_concepts_are_created_from_source_chunks(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [
            {
                "heading": "Identity and Access Control",
                "text": "Authentication: Verifies user identity.\nFirewall rules protect networks. Encryption protects data.",
            },
            {
                "heading": "Threats",
                "text": "Phishing and social engineering attacks target users. Malware can include a trojan or worm.",
            },
        ],
    )

    response = client.post(f"/api/source-materials/{material_id}/extract-concepts")
    body = response.json()
    names = extract_names(body)

    assert response.status_code == 200
    assert body["status"] == "completed"
    assert "authentication" in names
    assert "firewall" in names
    assert "encryption" in names
    assert names["firewall"]["status"] == "generated"
    assert names["firewall"]["confidence"] == "generated"
    assert body["concepts_linked"] >= 4


def test_duplicate_normalized_concepts_are_merged(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [
            {"heading": "Network Defense", "text": "A Firewall filters traffic at the network edge."},
            {"heading": "Controls", "text": "firewall policies should be reviewed. Firewall logs can feed a SIEM."},
        ],
    )

    extract_response = client.post(f"/api/source-materials/{material_id}/extract-concepts")
    list_response = client.get("/api/concepts?search=firewall")
    firewall_matches = [item for item in list_response.json() if item["normalized_name"] == "firewall"]

    assert extract_response.status_code == 200
    assert len(firewall_matches) == 1
    assert firewall_matches[0]["source_count"] == 1
    assert len(client.get(f"/api/concepts/{firewall_matches[0]['id']}/sources").json()) == 2


def test_concepts_link_back_to_source_chunks(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [
            {"heading": "VPN", "text": "VPN tunnels protect remote network access."},
            {"heading": "Authentication", "text": "Authentication confirms an identity before authorization."},
        ],
    )

    client.post(f"/api/source-materials/{material_id}/extract-concepts")
    concept = client.get("/api/concepts?search=vpn").json()[0]
    sources = client.get(f"/api/concepts/{concept['id']}/sources")

    assert sources.status_code == 200
    assert sources.json()[0]["source_id"] == material_id
    assert sources.json()[0]["source_chunk_id"] > 0
    assert "VPN" in sources.json()[0]["evidence_text"]


def test_concept_status_can_be_updated(tmp_path, monkeypatch):
    client, _, _, _ = make_client(tmp_path, monkeypatch)
    created = client.post("/api/concepts", json={"name": "Zero Trust"}).json()

    response = client.put(f"/api/concepts/{created['id']}", json={"status": "verified", "confidence": "verified"})

    assert response.status_code == 200
    assert response.json()["status"] == "verified"
    assert response.json()["confidence"] == "verified"


def test_concept_review_actions_update_status_and_restore_rejected(tmp_path, monkeypatch):
    client, _, _, _ = make_client(tmp_path, monkeypatch)
    created = client.post("/api/concepts", json={"name": "Certificate Pinning"}).json()

    reviewed = client.post(f"/api/concepts/{created['id']}/review")
    verified = client.post(f"/api/concepts/{created['id']}/verify")
    rejected = client.post(f"/api/concepts/{created['id']}/reject")
    restored = client.post(f"/api/concepts/{created['id']}/restore")

    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["confidence"] == "reviewed"
    assert verified.json()["status"] == "verified"
    assert verified.json()["confidence"] == "verified"
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["confidence"] == "unverified"
    assert restored.json()["status"] == "generated"
    assert restored.json()["confidence"] == "unverified"


def test_concept_aliases_can_be_added_listed_deleted_and_deduped(tmp_path, monkeypatch):
    client, _, _, _ = make_client(tmp_path, monkeypatch)
    concept = client.post("/api/concepts", json={"name": "Firewall"}).json()

    created = client.post(f"/api/concepts/{concept['id']}/aliases", json={"alias": "Packet Filter"})
    listed = client.get(f"/api/concepts/{concept['id']}/aliases")
    duplicate = client.post(f"/api/concepts/{concept['id']}/aliases", json={"alias": "packet   filter"})
    deleted = client.delete(f"/api/concepts/{concept['id']}/aliases/{created.json()['id']}")
    listed_after_delete = client.get(f"/api/concepts/{concept['id']}/aliases")

    assert created.status_code == 201
    assert created.json()["alias"] == "Packet Filter"
    assert created.json()["normalized_alias"] == "packet filter"
    assert listed.status_code == 200
    assert [alias["alias"] for alias in listed.json()] == ["Packet Filter"]
    assert duplicate.status_code == 409
    assert "duplicate" in duplicate.json()["detail"].lower()
    assert deleted.status_code == 200
    assert listed_after_delete.json() == []


def test_concept_merge_preserves_source_concepts_lineage(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"heading": "Firewall", "text": "Packet filters are firewall components."}],
    )
    target_id = create_concept(session_factory, "Firewall", normalized_name="firewall")
    source_id = create_concept(session_factory, "Packet Filter", normalized_name="packet filter")
    related_id = create_concept(session_factory, "ACL", normalized_name="acl")
    create_source_concept_link(session_factory, material_id, source_id, "Packet filters are firewall components.")
    client.post(f"/api/concepts/{source_id}/aliases", json={"alias": "Filtering firewall"})
    client.post(f"/api/concepts/{source_id}/relationships", json={"concept_b_id": related_id, "relationship_type": "component_of"})

    response = client.post(f"/api/concepts/{source_id}/merge", json={"target_concept_id": target_id})
    target_evidence = client.get(f"/api/concepts/{target_id}/evidence")
    target_aliases = client.get(f"/api/concepts/{target_id}/aliases")
    target_relationships = client.get(f"/api/concepts/{target_id}/relationships")
    source = client.get(f"/api/concepts/{source_id}", params={"include_rejected": "true"})

    assert response.status_code == 200
    assert response.json()["source_concept"]["status"] == "rejected"
    assert target_evidence.status_code == 200
    assert target_evidence.json()[0]["source_id"] == material_id
    assert target_evidence.json()[0]["evidence_text"] == "Packet filters are firewall components."
    assert {alias["normalized_alias"] for alias in target_aliases.json()} == {"packet filter", "filtering firewall"}
    assert target_relationships.json()[0]["concept_a_id"] == target_id
    assert target_relationships.json()[0]["concept_b_id"] == related_id
    assert source.json()["status"] == "rejected"


def test_concept_relationships_can_be_added_updated_and_rejected(tmp_path, monkeypatch):
    client, session_factory, _, _ = make_client(tmp_path, monkeypatch)
    firewall_id = create_concept(session_factory, "Firewall", normalized_name="firewall")
    acl_id = create_concept(session_factory, "ACL", normalized_name="acl")

    created = client.post(
        f"/api/concepts/{firewall_id}/relationships",
        json={"concept_b_id": acl_id, "relationship_type": "related_to", "confidence_score": 0.4},
    )
    updated = client.put(
        f"/api/concept-relationships/{created.json()['id']}",
        json={"relationship_type": "component_of", "status": "reviewed", "confidence_score": 0.85},
    )
    rejected = client.put(f"/api/concept-relationships/{created.json()['id']}", json={"status": "rejected"})

    assert created.status_code == 201
    assert created.json()["relationship_type"] == "related_to"
    assert updated.status_code == 200
    assert updated.json()["relationship_type"] == "component_of"
    assert updated.json()["status"] == "reviewed"
    assert updated.json()["confidence_score"] == 0.85
    assert rejected.json()["status"] == "rejected"


def test_concept_evidence_includes_source_metadata(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"heading": "VPN", "page_number": 4, "text": "VPN evidence from an extracted chunk."}],
    )
    concept_id = create_concept(session_factory, "VPN", normalized_name="vpn")
    create_source_concept_link(session_factory, material_id, concept_id, "VPN evidence from an extracted chunk.")

    evidence = client.get(f"/api/concepts/{concept_id}/evidence")

    assert evidence.status_code == 200
    assert evidence.json()[0]["source_title"] == "Security+ Concept Notes"
    assert evidence.json()[0]["source_type"] == "markdown"
    assert evidence.json()[0]["chunk_number"] == 1
    assert evidence.json()[0]["page_number"] == 4
    assert evidence.json()[0]["source_confidence"] == "reviewed"
    assert evidence.json()[0]["verification_status"] == "needs_review"


def test_rejected_concepts_are_hidden_by_default(tmp_path, monkeypatch):
    client, _, _, _ = make_client(tmp_path, monkeypatch)
    client.post("/api/concepts", json={"name": "Temporary Concept", "status": "rejected"})

    default_response = client.get("/api/concepts")
    include_response = client.get("/api/concepts?include_rejected=true")

    assert all(item["status"] != "rejected" for item in default_response.json())
    assert any(item["name"] == "Temporary Concept" for item in include_response.json())
