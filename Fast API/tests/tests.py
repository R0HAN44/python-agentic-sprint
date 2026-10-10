from fastapi.testclient import TestClient
from unittest.mock import patch
from src.main import app
from src.schemas import ExtractionError

client = TestClient(app)

def test_extract_happy_path():
    """Test successful extraction with valid trial text."""
    response = client.post(
        "/extract",
        json={"text": "A randomized controlled trial evaluated the efficacy of Metformin XR..."}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify structure and expected values from your mock data
    assert data["population"]["sample_size"] == 250
    assert data["metadata"]["phase"] == "Phase 3"
    assert data["metadata"]["sponsor"] == "ABC Pharmaceuticals"


def test_extract_missing_text_field():
    """Test request validation when the 'text' key is entirely missing."""
    response = client.post("/extract", json={})
    
    # Pydantic validation error returns 422
    assert response.status_code == 422


def test_extract_empty_or_whitespace_text():
    """Test client error when text is empty or only whitespace."""
    response = client.post("/extract", json={"text": "   "})
    
    assert response.status_code == 422
    assert "Text must not be empty" in response.json()["detail"]


@patch(".main.extract")
def test_extract_service_failure(mock_extract_trial):
    """Test handling of unexpected internal service failures (HTTP 500)."""
    # Force the mock service function to raise our custom ExtractionError
    mock_extract_trial.side_effect = ExtractionError("Database connection lost")

    response = client.post(
        "/extract",
        json={"text": "Valid trial text that triggers a service failure"}
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Database connection lost"