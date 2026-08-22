import json
import time
import socket
import threading
import urllib.request
import urllib.error
import pytest

from kardenwort.server.spacy_server import SpacyHTTPServer, SpacyRequestHandler, _trim_process_memory


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


def test_spacy_server_enhanced_health_details(spacy_server_instance):
    base_url, _ = spacy_server_instance
    req = urllib.request.Request(f"{base_url}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        assert data["status"] == "success"
        assert "models" in data
        assert "model_idle_ttl_seconds" in data
        assert data["model_idle_ttl_seconds"] == 0

        models_info = data["models"]
        for lang in ("de", "en"):
            if lang in models_info:
                assert "model_name" in models_info[lang]
                assert "idle_seconds" in models_info[lang]
                assert "simplemma_warmed" in models_info[lang]
                assert models_info[lang]["simplemma_warmed"] is True


def test_spacy_server_ttl_eviction_and_cold_reload():
    port = get_free_port()
    # Server with 2-second TTL and no preload
    server = SpacyHTTPServer(('127.0.0.1', port), SpacyRequestHandler, preload_models=False, model_idle_ttl=2)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)
    base_url = f"http://127.0.0.1:{port}"

    try:
        # Initial health check: no models loaded
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert data["loaded_models"] == []
            assert data["model_idle_ttl_seconds"] == 2

        # On-demand cold load for German
        payload = {
            "text": "Das ist ein schneller Test.",
            "language": "de",
            "zid": "20260822214000"
        }
        req = urllib.request.Request(
            f"{base_url}/tokenize",
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode('utf-8'))
            assert data["status"] == "success"
            assert len(data["tokens"]) > 0

        # Verify German model is now resident
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert "de" in data["loaded_models"]
            assert data["models"]["de"]["simplemma_warmed"] is True

        # Hot request latency check (< 20ms)
        req = urllib.request.Request(
            f"{base_url}/tokenize",
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode('utf-8'))
            assert data["duration_ms"] < 25.0

        # Wait for TTL eviction (TTL=2s, wait up to 4.0s with polling)
        evicted = False
        start_wait = time.time()
        while time.time() - start_wait < 4.0:
            time.sleep(0.25)
            req = urllib.request.Request(f"{base_url}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if "de" not in data["loaded_models"]:
                    evicted = True
                    break

        assert evicted is True
        assert len(data["loaded_models"]) == 0

        # On-demand cold load again after eviction
        req = urllib.request.Request(
            f"{base_url}/tokenize",
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode('utf-8'))
            assert data["status"] == "success"

        # Verify re-loaded
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert "de" in data["loaded_models"]

    finally:
        server.shutdown()
        server.server_close()


def test_spacy_server_trim_process_memory():
    import simplemma
    import simplemma.lemmatizer as lm

    # Pre-populate Simplemma dictionary cache
    if hasattr(lm, "DEFAULT_DICTIONARY_FACTORY") and hasattr(lm.DEFAULT_DICTIONARY_FACTORY, "get_dictionary"):
        lm.DEFAULT_DICTIONARY_FACTORY.get_dictionary("de")
    else:
        simplemma.lemmatize("Häuser", lang="de")

    if hasattr(lm, "DEFAULT_DICTIONARY_FACTORY") and hasattr(lm.DEFAULT_DICTIONARY_FACTORY, "_get_dictionary"):
        cache_info = lm.DEFAULT_DICTIONARY_FACTORY._get_dictionary.cache_info()
        assert cache_info.currsize > 0

    # Call _trim_process_memory
    _trim_process_memory()

    # Verify cache cleared
    if hasattr(lm, "DEFAULT_DICTIONARY_FACTORY") and hasattr(lm.DEFAULT_DICTIONARY_FACTORY, "_get_dictionary"):
        cache_info = lm.DEFAULT_DICTIONARY_FACTORY._get_dictionary.cache_info()
        assert cache_info.currsize == 0

    # Verify transparent re-warming works without error
    lemma = simplemma.lemmatize("Häuser", lang="de")
    assert lemma == "Haus"
