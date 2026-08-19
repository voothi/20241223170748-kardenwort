import json
import time
import socket
import threading
import urllib.request
import urllib.error
import pytest

from kardenwort.server.spacy_server import SpacyHTTPServer, SpacyRequestHandler


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def spacy_server_instance():
    port = get_free_port()
    server = SpacyHTTPServer(('127.0.0.1', port), SpacyRequestHandler, preload_models=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)
    base_url = f"http://127.0.0.1:{port}"
    yield base_url, server
    server.shutdown()
    server.server_close()


def test_spacy_server_health(spacy_server_instance):
    base_url, _ = spacy_server_instance
    req = urllib.request.Request(f"{base_url}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        assert data["status"] == "success"
        assert data["service"] == "kardenwort-spacy-server"
        assert "loaded_models" in data
        assert isinstance(data["loaded_models"], list)
        assert "uptime_seconds" in data


def test_spacy_server_tokenize_german(spacy_server_instance):
    base_url, _ = spacy_server_instance
    payload = {
        "text": "Der schnelle braune Fuchs springt über den faulen Hund.",
        "language": "de",
        "zid": "20260819002800",
        "trace_id": "20260819002800:test:1"
    }
    req = urllib.request.Request(
        f"{base_url}/tokenize",
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        assert data["status"] == "success"
        assert data["zid"] == "20260819002800"
        assert data["trace_id"] == "20260819002800:test:1"
        assert "tokens" in data
        assert len(data["tokens"]) > 0
        assert "duration_ms" in data

        first_token = data["tokens"][0]
        assert "word" in first_token
        assert "lemma" in first_token
        assert "pos" in first_token
        assert "morphology" in first_token
        assert "sentence_index" in first_token
        assert first_token["sentence_index"] == 1


def test_spacy_server_tokenize_english(spacy_server_instance):
    base_url, _ = spacy_server_instance
    payload = {
        "text": "The quick brown fox jumps.",
        "language": "en",
        "zid": "20260819002801",
    }
    req = urllib.request.Request(
        f"{base_url}/api/v1/tokenize",
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        assert data["status"] == "success"
        assert data["zid"] == "20260819002801"
        assert len(data["tokens"]) == 6
        words = [t["word"] for t in data["tokens"]]
        assert "quick" in words


def test_spacy_server_missing_text(spacy_server_instance):
    base_url, _ = spacy_server_instance
    payload = {"language": "de"}
    req = urllib.request.Request(
        f"{base_url}/tokenize",
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 400


def test_spacy_server_not_found(spacy_server_instance):
    base_url, _ = spacy_server_instance
    req = urllib.request.Request(f"{base_url}/nonexistent")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 404
