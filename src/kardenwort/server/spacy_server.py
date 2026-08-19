import sys
import os
import json
import time
import socket
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import spacy
from kardenwort.core.kardenwort import configure_spacy_model, retokenize_hyphenated_compounds

logger = logging.getLogger("kardenwort.spacy_server")


def generate_server_zid(server) -> str:
    """
    Generates a unique server-side ZID per request.
    Uses thread-safe monotonic incrementing to prevent collision within the same second.
    """
    now = datetime.now()
    with server.seq_lock:
        server.seq_counter = (server.seq_counter + 1) % 10000
        seq = server.seq_counter
    return f"{now:%Y%m%d%H%M%S}-{seq:04d}"


class SpacyRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler serving high-performance SpaCy tokenization and health checks.
    """

    def setup(self):
        super().setup()
        # Enforce strict 5-second socket timeout to prevent Slowloris-style thread hangs
        self.connection.settimeout(5.0)

    def address_string(self):
        # Override to bypass Windows reverse DNS lookups (<1ms vs 2s-5s latency)
        return self.client_address[0]

    def log_message(self, format_str, *args):
        # Suppress access logs for health checks to prevent polling log spam
        if self.path and ('/health' in self.path or self.path == '/'):
            return
        logger.info("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), format_str % args))

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'X-ZID, X-Trace-ID, Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code: int, data_obj: dict):
        body = json.dumps(data_obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, error_code: str, message: str, zid: Optional[str] = None, trace_id: Optional[str] = None):
        payload = {
            "status": "error",
            "error_code": error_code,
            "message": message,
            "zid": zid or generate_server_zid(self.server),
        }
        if trace_id:
            payload["trace_id"] = trace_id
        self._send_json(status_code, payload)

    def _read_json_body(self) -> dict:
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                return {}
            raw_data = self.rfile.read(content_length)
            return json.loads(raw_data.decode('utf-8'))
        except Exception as e:
            raise ValueError(f"Invalid JSON payload: {e}")

    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/')
        if path == '':
            path = '/'

        # Health endpoint
        if path in ('/health', '/api/v1/health', '/'):
            uptime = round(time.time() - getattr(self.server, 'start_time', time.time()), 2)
            loaded_models = list(getattr(self.server, 'models', {}).keys())
            self._send_json(200, {
                "status": "success",
                "service": "kardenwort-spacy-server",
                "loaded_models": loaded_models,
                "uptime_seconds": uptime
            })
            return

        self._send_error(404, "NOT_FOUND", f"Unknown endpoint: {path}")

    def do_POST(self):
        path = self.path.split('?')[0].rstrip('/')

        # Tokenize endpoint
        if path in ('/tokenize', '/api/v1/tokenize'):
            try:
                body = self._read_json_body()
            except ValueError as e:
                self._send_error(400, "INVALID_PAYLOAD", str(e))
                return

            text = body.get("text", "")
            if not text:
                self._send_error(400, "MISSING_FIELD", "Missing required field 'text'")
                return

            language = body.get("language", "de")
            req_zid = body.get("zid") or self.headers.get("X-ZID") or generate_server_zid(self.server)
            req_trace_id = body.get("trace_id") or self.headers.get("X-Trace-ID") or f"{req_zid}:tokenize"

            nlp = self.server.models.get(language)
            if not nlp:
                # Fallback to general loader or first available model
                nlp = self.server.load_or_get_model(language)

            t0 = time.perf_counter()
            try:
                doc = nlp(text)
                doc = retokenize_hyphenated_compounds(doc)

                tokens = []
                # If doc has sentences (sentencizer/parser)
                has_sents = doc.has_annotation("SENT_START")
                if has_sents:
                    sentences = list(doc.sents)
                else:
                    sentences = [doc]

                for sent_idx, sent in enumerate(sentences, start=1):
                    for token in sent:
                        if token.is_space:
                            continue
                        tokens.append({
                            "word": token.text,
                            "lemma": token.lemma_,
                            "pos": token.pos_,
                            "morphology": str(token.morph) if token.morph else "",
                            "sentence_index": sent_idx
                        })

                duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                logger.info(f"[{req_zid}] [{req_trace_id}] Tokenized {len(tokens)} tokens in {duration_ms}ms (lang={language})")

                self._send_json(200, {
                    "status": "success",
                    "zid": req_zid,
                    "trace_id": req_trace_id,
                    "tokens": tokens,
                    "duration_ms": duration_ms
                })
            except Exception as e:
                logger.error(f"[{req_zid}] [{req_trace_id}] Tokenization error: {e}", exc_info=True)
                self._send_error(500, "TOKENIZE_FAILED", str(e), zid=req_zid, trace_id=req_trace_id)
            return

        # Shutdown endpoint
        if path in ('/shutdown', '/api/v1/shutdown'):
            req_zid = self.headers.get("X-ZID") or generate_server_zid(self.server)
            self._send_json(200, {
                "status": "success",
                "zid": req_zid,
                "message": "Server shutting down..."
            })

            def shutdown_server():
                time.sleep(0.1)
                try:
                    self.server.shutdown()
                    self.server.server_close()
                except Exception as e:
                    logger.error(f"Error during server shutdown: {e}")

            threading.Thread(target=shutdown_server, daemon=True).start()
            return

        self._send_error(404, "NOT_FOUND", f"Unknown endpoint: {path}")


class SpacyHTTPServer(ThreadingHTTPServer):
    """
    Custom ThreadingHTTPServer with pre-loaded NLP models and Windows optimizations.
    """
    def __init__(self, server_address, RequestHandlerClass, preload_models=True):
        self.allow_reuse_address = False
        self.daemon_threads = True
        self.disable_nagle_algorithm = True

        super().__init__(server_address, RequestHandlerClass)

        self.start_time = time.time()
        self.seq_counter = 0
        self.seq_lock = threading.Lock()
        self.models: Dict[str, Any] = {}

        if preload_models:
            self.preload_all_models()

    def preload_all_models(self):
        """Preload German and English language models during boot."""
        for lang, model_candidates in [
            ("de", ["de_core_news_lg", "de_core_news_md", "de_core_news_sm"]),
            ("en", ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"])
        ]:
            model_loaded = False
            for model_name in model_candidates:
                try:
                    logger.info(f"Loading SpaCy model '{model_name}' for language '{lang}'...")
                    nlp = spacy.load(model_name, exclude=["ner", "parser"])
                    configure_spacy_model(nlp)
                    self.models[lang] = nlp
                    logger.info(f"Successfully loaded '{model_name}' for language '{lang}'")
                    model_loaded = True
                    break
                except Exception as e:
                    logger.debug(f"Candidate model '{model_name}' not available: {e}")

            if not model_loaded:
                logger.warning(f"Could not load standard models for '{lang}'. Initializing blank pipeline.")
                try:
                    nlp = spacy.blank(lang)
                    configure_spacy_model(nlp)
                    self.models[lang] = nlp
                except Exception as e:
                    logger.error(f"Failed to initialize blank model for '{lang}': {e}")

    def load_or_get_model(self, lang: str):
        """Load or return cached model for given language."""
        if lang in self.models:
            return self.models[lang]
        try:
            nlp = spacy.blank(lang)
            configure_spacy_model(nlp)
            self.models[lang] = nlp
            return nlp
        except Exception:
            return self.models.get("de") or self.models.get("en")


def start_spacy_server(host: str = "127.0.0.1", port: int = 8081, preload_models: bool = True):
    """
    Starts the persistent SpaCy HTTP server.
    """
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(f"Host must be a loopback address (127.0.0.1). Specified: {host}")

    server = SpacyHTTPServer((host, port), SpacyRequestHandler, preload_models=preload_models)
    logger.info(f"SpaCy HTTP Server started on http://{host}:{port}")
    print(f"SpaCy HTTP Server started on http://{host}:{port}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by KeyboardInterrupt.")
    finally:
        try:
            server.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    port = 8081
    host = "127.0.0.1"
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    start_spacy_server(host=host, port=port)
