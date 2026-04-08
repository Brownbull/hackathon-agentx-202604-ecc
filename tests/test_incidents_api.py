import io
import uuid


async def test_create_incident_success(client):
    resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "test@example.com",
            "description": "The checkout page is returning 500 errors when users try to apply discount codes.",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["reporter_email"] == "test@example.com"
    assert body["status"] == "submitted"
    assert body["severity"] is None  # Not triaged yet
    assert "id" in body


async def test_create_incident_with_name(client):
    resp = await client.post(
        "/api/incidents",
        data={
            "reporter_name": "Jane Doe",
            "reporter_email": "jane@example.com",
            "description": "Product images are not loading on the catalog page after the latest deploy.",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["reporter_name"] == "Jane Doe"


async def test_create_incident_description_too_short(client):
    resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "test@example.com",
            "description": "Error",
        },
    )
    assert resp.status_code == 422


async def test_create_incident_missing_email(client):
    resp = await client.post(
        "/api/incidents",
        data={
            "description": "A long enough description for the incident report.",
        },
    )
    assert resp.status_code == 422


async def test_create_incident_with_file(client):
    files = [("files", ("error.txt", io.BytesIO(b"stack trace here"), "text/plain"))]
    resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "test@example.com",
            "description": "Server crash with the following stack trace attached.",
        },
        files=files,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["filename"] == "error.txt"
    assert body["attachments"][0]["mime_type"] == "text/plain"


async def test_create_incident_file_too_large(client):
    # Create content exceeding 5MB limit
    large_content = b"x" * (5 * 1024 * 1024 + 1)
    files = [("files", ("big.txt", io.BytesIO(large_content), "text/plain"))]
    resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "test@example.com",
            "description": "Submitting with a file that exceeds the size limit.",
        },
        files=files,
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"]


async def test_create_incident_bad_file_type(client):
    files = [("files", ("malware.exe", io.BytesIO(b"binary"), "application/x-msdownload"))]
    resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "test@example.com",
            "description": "Submitting with a disallowed file type.",
        },
        files=files,
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]


async def test_list_incidents(client):
    # Create one first
    await client.post(
        "/api/incidents",
        data={
            "reporter_email": "list@example.com",
            "description": "Test incident for listing — should appear in results.",
        },
    )
    resp = await client.get("/api/incidents")
    assert resp.status_code == 200
    body = resp.json()
    assert "incidents" in body
    assert "total" in body
    assert body["total"] >= 1


async def test_get_incident_by_id(client):
    # Create
    create_resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "detail@example.com",
            "description": "Test incident for detail view — checking all fields.",
        },
    )
    incident_id = create_resp.json()["id"]

    # Get
    resp = await client.get(f"/api/incidents/{incident_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == incident_id
    assert body["reporter_email"] == "detail@example.com"


async def test_get_incident_not_found(client):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/incidents/{fake_id}")
    assert resp.status_code == 404


async def test_pages_render_html(client):
    """Verify HTML pages return 200 and contain expected content."""
    # Home / incidents list
    resp = await client.get("/incidents")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "SRE Triage Agent" in resp.text

    # New incident form
    resp = await client.get("/incidents/new")
    assert resp.status_code == 200
    assert "Report New Incident" in resp.text


async def test_incident_detail_page_renders(client):
    """Verify detail page renders for an existing incident."""
    create_resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "page@example.com",
            "description": "Testing that the detail page renders correctly with incident data.",
        },
    )
    incident_id = create_resp.json()["id"]

    resp = await client.get(f"/incidents/{incident_id}")
    assert resp.status_code == 200
    assert "page@example.com" in resp.text
    assert "No triage yet" in resp.text  # Not triaged yet


async def test_incident_not_found_page(client):
    """Verify 404 page for missing incident."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/incidents/{fake_id}")
    assert resp.status_code == 404
    assert "Not Found" in resp.text


async def test_search_by_partial_id(client):
    """Search endpoint finds incidents by partial UUID prefix."""
    create_resp = await client.post(
        "/api/incidents",
        data={
            "reporter_email": "search@example.com",
            "description": "Test incident for search by partial ID — should be findable.",
        },
    )
    incident_id = create_resp.json()["id"]
    prefix = incident_id[:8]

    resp = await client.get(f"/incidents/search?q={prefix}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert prefix in resp.text
    assert "search@example.com" in resp.text


async def test_search_empty_query(client):
    """Search with empty query returns page with no results."""
    resp = await client.get("/incidents/search?q=")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_search_no_match(client):
    """Search with non-existent prefix returns empty results."""
    resp = await client.get("/incidents/search?q=00000000")
    assert resp.status_code == 200
    assert "0 results" in resp.text or "Showing" in resp.text


async def test_search_sanitizes_input(client):
    """Search strips spaces and special characters."""
    resp = await client.get("/incidents/search?q=%20%3Cscript%3E")
    assert resp.status_code == 200
    assert "<script>" not in resp.text
