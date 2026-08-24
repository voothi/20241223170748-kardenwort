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

# Ensure 'src' root is in sys.path when executed directly as a script
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

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
            with getattr(self.server, 'models_lock', threading.Lock()):
                models_dict = getattr(self.server, 'models', {})
                access_dict = getattr(self.server, 'access_times', {})
                warmed_dict = getattr(self.server, 'simplemma_warmed', {})
                ttl_val = getattr(self.server, 'model_idle_ttl', 0)
                now = time.time()

                models_info = {}
                for lang, nlp in models_dict.items():
                    model_name = getattr(nlp, 'meta', {}).get('name', 'custom') if hasattr(nlp, 'meta') else 'custom'
                    idle_sec = round(now - access_dict.get(lang, now), 2)
                    models_info[lang] = {
                        "model_name": model_name,
                        "idle_seconds": idle_sec,
                        "simplemma_warmed": warmed_dict.get(lang, False)
                    }
                loaded_models_list = list(models_dict.keys())

            self._send_json(200, {
                "status": "success",
                "service": "kardenwort-spacy-server",
                "loaded_models": loaded_models_list,
                "models": models_info,
                "model_idle_ttl_seconds": ttl_val,
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
                            "tag": token.tag_,
                            "morphology": str(token.morph) if token.morph else "",
                            "sentence_index": sent_idx,
                            "idx": token.idx,
                            "whitespace": token.whitespace_
                        })

                duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                with self.server.models_lock:
                    self.server.access_times[language] = time.time()
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
    Custom ThreadingHTTPServer with thread-safe model management, on-demand loading,
    Simplemma pre-warming, and configurable idle TTL unloading.
    """
    def __init__(self, server_address, RequestHandlerClass, preload_models: bool = True, model_idle_ttl: int = 0):
        self.allow_reuse_address = False
        self.daemon_threads = True
        self.disable_nagle_algorithm = True

        super().__init__(server_address, RequestHandlerClass)

        self.start_time = time.time()
        self.seq_counter = 0
        self.seq_lock = threading.Lock()
        self.models_lock = threading.RLock()
        self.model_idle_ttl = max(0, int(model_idle_ttl))
        self.models: Dict[str, Any] = {}
        self.access_times: Dict[str, float] = {}
        self.simplemma_warmed: Dict[str, bool] = {}
        self.janitor_stop_event = threading.Event()
        self.janitor_thread: Optional[threading.Thread] = None

        if preload_models:
            self.preload_all_models()

        if self.model_idle_ttl > 0:
            self.start_janitor()

    def _load_spacy_pipeline(self, lang: str):
        """Loads and configures SpaCy pipeline and warms up Simplemma for the specified language."""
        candidates_map = {
            "de": ["de_core_news_lg", "de_core_news_md", "de_core_news_sm"],
            "en": ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"]
        }
        model_candidates = candidates_map.get(lang, [f"{lang}_core_news_lg", f"{lang}_core_news_sm", f"{lang}_core_web_sm"])

        nlp = None
        for model_name in model_candidates:
            try:
                logger.info(f"Loading SpaCy model '{model_name}' for language '{lang}'...")
                nlp = spacy.load(model_name, exclude=["ner", "parser"])
                configure_spacy_model(nlp)
                logger.info(f"Successfully loaded '{model_name}' for language '{lang}'")
                break
            except Exception as e:
                logger.debug(f"Candidate model '{model_name}' not available: {e}")

        if nlp is None:
            logger.warning(f"Could not load standard models for '{lang}'. Initializing blank pipeline.")
            try:
                nlp = spacy.blank(lang)
                configure_spacy_model(nlp)
            except Exception as e:
                logger.error(f"Failed to initialize blank model for '{lang}': {e}")
                if self.models:
                    nlp = next(iter(self.models.values()))
                else:
                    raise RuntimeError(f"Cannot initialize pipeline for language '{lang}': {e}")

        # Simplemma dictionary pre-warming
        try:
            import simplemma
            simplemma.lemmatize("init", lang=lang)
            self.simplemma_warmed[lang] = True
            logger.debug(f"Simplemma dictionary pre-warmed for '{lang}'")
        except Exception as e:
            self.simplemma_warmed[lang] = False
            logger.debug(f"Simplemma pre-warming skipped for '{lang}': {e}")

        return nlp

    def preload_all_models(self):
        """Preload German and English language models during boot."""
        with self.models_lock:
            for lang in ["de", "en"]:
                try:
                    self.load_or_get_model(lang)
                except Exception as e:
                    logger.error(f"Failed to preload model for language '{lang}': {e}")

    def load_or_get_model(self, lang: str):
        """Thread-safe method to return active model or dynamically load it on demand."""
        with self.models_lock:
            if lang in self.models:
                self.access_times[lang] = time.time()
                if not self.simplemma_warmed.get(lang, False):
                    try:
                        import simplemma
                        simplemma.lemmatize("init", lang=lang)
                        self.simplemma_warmed[lang] = True
                    except Exception as e:
                        logger.debug(f"Simplemma re-warming skipped for '{lang}': {e}")
                return self.models[lang]

            nlp = self._load_spacy_pipeline(lang)
            self.models[lang] = nlp
            self.access_times[lang] = time.time()
            return nlp

    def start_janitor(self):
        """Starts background eviction thread if TTL > 0."""
        if self.model_idle_ttl > 0 and (self.janitor_thread is None or not self.janitor_thread.is_alive()):
            self.janitor_stop_event.clear()
            self.janitor_thread = threading.Thread(target=self._janitor_loop, name="SpacyModelJanitor", daemon=True)
            self.janitor_thread.start()
            logger.info(f"Model eviction janitor started with TTL={self.model_idle_ttl}s")

    def _janitor_loop(self):
        """Background loop to evict idle models exceeding TTL."""
        check_interval = max(0.25, min(5.0, self.model_idle_ttl / 4.0 if self.model_idle_ttl > 0 else 1.0))
        while not self.janitor_stop_event.wait(timeout=check_interval):
            if self.model_idle_ttl <= 0:
                continue
            with self.models_lock:
                now = time.time()
                to_evict = []
                for lang, last_time in list(self.access_times.items()):
                    if (now - last_time) >= self.model_idle_ttl:
                        to_evict.append(lang)

                if to_evict:
                    for lang in to_evict:
                        logger.info(f"Evicting idle SpaCy model for '{lang}' (idle for {round(now - self.access_times[lang], 2)}s >= TTL {self.model_idle_ttl}s)")
                        self.models.pop(lang, None)
                        self.access_times.pop(lang, None)
                        self.simplemma_warmed.pop(lang, None)

                    if not self.models:
                        logger.info("All SpaCy models evicted. Performing deep idle memory trimming.")
                        _trim_process_memory()
                    else:
                        import gc
                        gc.collect()

    def server_close(self):
        self.janitor_stop_event.set()
        if self.janitor_thread is not None and self.janitor_thread.is_alive():
            self.janitor_thread.join(timeout=2.0)
        super().server_close()


def _trim_process_memory():
    """
    Performs deep memory compaction:
    1. Clears Simplemma dictionary LRU cache.
    2. Runs Python garbage collection.
    3. Reclaims MSVCRT C-heap pages.
    4. Flushes process working set memory pages to OS standby/free list (Windows).
    """
    try:
        import simplemma.lemmatizer as lm
        if hasattr(lm, "DEFAULT_DICTIONARY_FACTORY") and hasattr(lm.DEFAULT_DICTIONARY_FACTORY, "_get_dictionary"):
            lm.DEFAULT_DICTIONARY_FACTORY._get_dictionary.cache_clear()
    except Exception as e:
        logger.debug(f"Simplemma cache clear skipped/failed: {e}")

    try:
        import gc
        gc.collect()
    except Exception:
        pass

    try:
        import ctypes
        if hasattr(ctypes, "cdll") and hasattr(ctypes.cdll, "msvcrt"):
            ctypes.cdll.msvcrt._heapmin()
    except Exception as e:
        logger.debug(f"msvcrt._heapmin skipped/failed: {e}")

    try:
        import ctypes
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "kernel32"):
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
    except Exception as e:
        logger.debug(f"SetProcessWorkingSetSize skipped/failed: {e}")


def start_spacy_server(host: str = "127.0.0.1", port: int = 8081, preload_models: bool = True, model_idle_ttl: int = 0):
    """
    Starts the persistent SpaCy HTTP server.
    """
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(f"Host must be a loopback address (127.0.0.1). Specified: {host}")

    server = SpacyHTTPServer((host, port), SpacyRequestHandler, preload_models=preload_models, model_idle_ttl=model_idle_ttl)
    logger.info(f"SpaCy HTTP Server started on http://{host}:{port} (preload={preload_models}, model_idle_ttl={model_idle_ttl}s)")
    print(f"SpaCy HTTP Server started on http://{host}:{port} (preload={preload_models}, model_idle_ttl={model_idle_ttl}s)", flush=True)

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
    import argparse
    parser = argparse.ArgumentParser(description="Kardenwort SpaCy Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind to")
    parser.add_argument("--model-ttl", type=int, default=0, help="Model inactivity TTL in seconds (0 = disabled / always resident)")
    parser.add_argument("--no-preload", action="store_true", help="Do not preload models on boot; load on demand")
    parser.add_argument("--preload-models", action="store_true", default=True, help="Preload models on boot (default)")
    parser.add_argument("pos_port", nargs="?", type=int, default=None, help="Positional port")
    cli_args, _ = parser.parse_known_args()
    resolved_port = cli_args.pos_port if cli_args.pos_port is not None else cli_args.port
    preload = not cli_args.no_preload
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    start_spacy_server(host=cli_args.host, port=resolved_port, preload_models=preload, model_idle_ttl=cli_args.model_ttl)
