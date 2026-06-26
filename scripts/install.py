#!/usr/bin/env python
# ==============================================================================
# Kardenwort Vocab — Windows SendTo Shortcut Installer
#
# Creates a "Kardenwort Vocab" shortcut in the Windows "Send to" folder.
# After installation:
#   1. Select one or more text/subtitle files (.txt or .srt) in Windows Explorer.
#   2. Right-click → Send to → Kardenwort Vocab.
#   3. The processor runs, stages the inputs, extracts vocabulary, and imports to Anki.
# ==============================================================================

import os
import subprocess
import sys

SHORTCUT_DISPLAY_NAME = "Kardenwort Vocab"
LEGACY_SHORTCUT_NAMES = ("Kardenwort Vocab Processor",)
SENDTO_DIRECTORY = r"%APPDATA%\Microsoft\Windows\SendTo"

def main():
    print(f"=== {SHORTCUT_DISPLAY_NAME} Shortcut Installer ===")

    # 1. Locate paths relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, "sendto_vocab.py")

    if not os.path.exists(script_path):
        print(f"Error: Could not find {script_path}")
        sys.exit(1)

    # Use python.exe (NOT pythonw.exe) so a visible console window appears
    python_path = sys.executable
    if python_path.lower().endswith("pythonw.exe"):
        python_path = python_path[:-len("pythonw.exe")] + "python.exe"

    sendto_dir = os.path.expandvars(SENDTO_DIRECTORY)
    os.makedirs(sendto_dir, exist_ok=True)
    shortcut_path = os.path.join(sendto_dir, f"{SHORTCUT_DISPLAY_NAME}.lnk")

    # 2. Clean up legacy shortcuts
    for legacy_name in LEGACY_SHORTCUT_NAMES:
        old_path = os.path.join(sendto_dir, f"{legacy_name}.lnk")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
                print(f"Cleaned up legacy shortcut: {os.path.basename(old_path)}")
            except Exception as exc:
                print(f"Warning: Could not remove old shortcut: {exc}")

    print(f"Script Path:       {script_path}")
    print(f"Python Path:       {python_path}")
    print(f"SendTo Directory:  {sendto_dir}")
    print(f"Shortcut Path:     {shortcut_path}")

    # Escape single quotes for PowerShell single-quoted strings
    shortcut_path_escaped = shortcut_path.replace("'", "''")
    python_path_escaped = python_path.replace("'", "''")
    script_path_escaped = script_path.replace("'", "''")

    # 3. Build the shortcut via PowerShell + WScript.Shell COM
    ps_script = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{shortcut_path_escaped}'); "
        f"$Shortcut.TargetPath = '{python_path_escaped}'; "
        f"$Shortcut.Arguments = '\"{script_path_escaped}\" --sendto --pause'; "
        f"$Shortcut.Description = 'Extracts vocabulary from sent files and imports them to Anki'; "
        f"$Shortcut.WindowStyle = 1; "   # SW_SHOWNORMAL
        f"$Shortcut.Save()"
    )

    try:
        print(f"\nCreating shortcut in Windows 'Send to' menu...")
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"\nSUCCESS: '{SHORTCUT_DISPLAY_NAME}' shortcut created!")
        print("\nHow to use:")
        print("  1. Select one or more text/subtitle files (.txt or .srt) in Windows Explorer.")
        print(f"  2. Right-click → Send to → '{SHORTCUT_DISPLAY_NAME}'.")
        print("  3. The processor runs, stages the inputs, extracts vocabulary, and imports to Anki.")
    except subprocess.CalledProcessError as exc:
        print(f"Error: Failed to create shortcut.\nPowerShell error:\n{exc.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    main()
