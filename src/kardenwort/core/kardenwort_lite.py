import sys
import string

try:
    import simplemma
except ImportError:
    print("Error: simplemma is not installed. Please run 'pip install simplemma'.", file=sys.stderr)
    sys.exit(1)

def set_clipboard(text):
    """Writes text to the system clipboard across Windows, macOS, and Linux without external dependencies."""
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        
        # Explicitly define ctypes signatures to prevent 64-bit address truncation
        OpenClipboard = ctypes.windll.user32.OpenClipboard
        OpenClipboard.argtypes = [wintypes.HWND]
        OpenClipboard.restype = wintypes.BOOL
        
        EmptyClipboard = ctypes.windll.user32.EmptyClipboard
        EmptyClipboard.argtypes = []
        EmptyClipboard.restype = wintypes.BOOL
        
        CloseClipboard = ctypes.windll.user32.CloseClipboard
        CloseClipboard.argtypes = []
        CloseClipboard.restype = wintypes.BOOL
        
        SetClipboardData = ctypes.windll.user32.SetClipboardData
        SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        SetClipboardData.restype = wintypes.HANDLE
        
        GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
        GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        GlobalAlloc.restype = wintypes.HANDLE
        
        GlobalLock = ctypes.windll.kernel32.GlobalLock
        GlobalLock.argtypes = [wintypes.HANDLE]
        GlobalLock.restype = ctypes.c_void_p
        
        GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
        GlobalUnlock.argtypes = [wintypes.HANDLE]
        GlobalUnlock.restype = wintypes.BOOL
        
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 2
        
        if not OpenClipboard(None):
            return False
        try:
            EmptyClipboard()
            data = text.encode('utf-16-le') + b'\x00\x00'
            h_mem = GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not h_mem:
                return False
            ptr = GlobalLock(h_mem)
            if ptr:
                try:
                    ctypes.memmove(ptr, data, len(data))
                finally:
                    GlobalUnlock(h_mem)
                SetClipboardData(CF_UNICODETEXT, h_mem)
            return True
        finally:
            CloseClipboard()
            
    elif sys.platform == 'darwin':
        import subprocess
        try:
            p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
            return True
        except Exception:
            return False
            
    else: # Linux / BSD
        import subprocess
        for cmd in [['xclip', '-selection', 'clipboard'], ['xsel', '-clipboard', '-i']]:
            try:
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
                p.communicate(input=text)
                return True
            except Exception:
                continue
        return False

def main():
    # Ensure UTF-8 encoding for standard streams (useful for Windows consoles)
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')

    # Default languages supported
    langs = ('en', 'de', 'ru', 'uk')
    
    # Simple lightweight argument parser to keep startup time <100ms
    word_args = []
    for arg in sys.argv[1:]:
        if arg.startswith('--langs='):
            langs = tuple(arg.split('=')[1].split(','))
        else:
            word_args.append(arg)

    word = ""
    use_clipboard = False
    
    if word_args:
        word = word_args[0]
        use_clipboard = True
    else:
        word = sys.stdin.read()

    word = word.strip()
    if not word:
        return

    # Strip surrounding punctuation
    cleaned_word = word.strip(string.punctuation + " \t\n\r«»„“")
    
    if not cleaned_word:
        print(word, end="")
        if use_clipboard:
            set_clipboard(word)
        return

    # Smart Alphabet Detection to optimize lookups and prevent false positive mappings
    # between Cyrillic (RU/UK) and Latin (DE/EN) scripts.
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in cleaned_word)
    if has_cyrillic:
        # Filter to keep only Cyrillic languages if any are present in the list
        active_langs = tuple(l for l in langs if l in ('ru', 'uk'))
        if not active_langs:
            active_langs = langs
    else:
        # Filter out Cyrillic languages
        active_langs = tuple(l for l in langs if l not in ('ru', 'uk'))
        if not active_langs:
            active_langs = langs

    try:
        lemma = simplemma.lemmatize(cleaned_word, lang=active_langs)
        print(lemma, end="")
        if use_clipboard:
            set_clipboard(lemma)
    except Exception:
        print(cleaned_word, end="")
        if use_clipboard:
            set_clipboard(cleaned_word)

if __name__ == "__main__":
    main()
