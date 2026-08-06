from enum import Enum

class ErrorCode(Enum):
    """
    Error Catalog defining deterministic OS exit codes for operational failures.
    Each member is permanently bound to a unique integer, enabling calling agents
    (e.g., Go exec.Command, PowerShell) to diagnose failure categories instantly
    from the OS process exit code.
    """
    ERR_DICT_MISSING = 101
    ERR_SCHEMA_MISMATCH = 102
    ERR_FILE_READ_ABORT = 103
    ERR_UNHANDLED_EXCEPTION = 104

class StructuredError(Exception):
    """
    Centralized error model that formats exceptions as validated JSON error objects.
    Exposes an .exit() method to output the JSON and sys.exit() with the mapped error code.
    """
    def __init__(self, error_code: ErrorCode, message: str, context: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.context = context or {}

    def to_dict(self):
        return {
            "error_code": self.error_code.name,
            "message": self.message,
            "context": self.context
        }
    
    def to_json(self):
        import json
        return json.dumps(self.to_dict())
    
    def exit(self):
        import sys
        print(self.to_json(), file=sys.stderr)
        sys.exit(self.error_code.value)

def setup_structured_logging():
    import sys
    import json
    
    if "--structured-output" in sys.argv or "--json-ipc" in sys.argv:
        class StructuredStderrLogger:
            def __init__(self, original_stderr):
                self.original_stderr = original_stderr
                
            def write(self, message):
                msg = message.strip()
                if not msg:
                    return
                # Suppress non-JSON stderr output or format it as telemetry
                # Let's just suppress it to keep it pure, or format as telemetry.
                # The spec says "suppressed or formatted". Formatting is safer to not lose logs.
                try:
                    # if it's already JSON (like our StructuredError), pass it through
                    json.loads(msg)
                    self.original_stderr.write(msg + "\n")
                except ValueError:
                    # format as telemetry
                    json_msg = json.dumps({"telemetry": msg}, ensure_ascii=False)
                    self.original_stderr.write(json_msg + "\n")
                self.original_stderr.flush()

            def flush(self):
                self.original_stderr.flush()
                
        if not isinstance(sys.stderr, StructuredStderrLogger):
            sys.stderr = StructuredStderrLogger(sys.stderr)
