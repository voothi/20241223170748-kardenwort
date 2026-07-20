#!/usr/bin/env python
# ==============================================================================
# Kardenwort Vocab — Windows SendTo Shortcuts Installer
#
# Creates shortcuts for each pipeline stage in the Windows "Send to" folder.
# ==============================================================================

import os
import subprocess
import sys
import argparse
import configparser

SHORTCUTS = [
    {
        "name": "Kardenwort Extract Vocab",
        "description": "Extracts vocabulary from sent files and imports them to Anki",
    },
    {
        "name": "Kardenwort Fill Vocab",
        "description": "Enrich vocabulary TSV using headless IntelliFiller AI",
    },
    {
        "name": "Kardenwort Import All",
        "description": "Imports an existing vocabulary TSV directly into Anki",
    }
]

SENDTO_DIRECTORY = r"%APPDATA%\Microsoft\Windows\SendTo"

def create_shortcut(name, target, arguments, description, sendto_dir):
    shortcut_path = os.path.join(sendto_dir, f"{name}.lnk")
    shortcut_path_escaped = shortcut_path.replace("'", "''")
    target_escaped = target.replace("'", "''")
    arguments_escaped = arguments.replace("'", "''")
    description_escaped = description.replace("'", "''")
    
    ps_script = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{shortcut_path_escaped}'); "
        f"$Shortcut.TargetPath = '{target_escaped}'; "
        f"$Shortcut.Arguments = '{arguments_escaped}'; "
        f"$Shortcut.Description = '{description_escaped}'; "
        f"$Shortcut.WindowStyle = 1; "
        f"$Shortcut.Save()"
    )
    
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"Created shortcut: {name}")
    except subprocess.CalledProcessError as exc:
        print(f"Error creating shortcut '{name}': {exc.stderr}")
        sys.exit(1)

def main(argv=None):
    if argv is None:
        if "pytest" in sys.modules:
            argv = []
        else:
            argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Kardenwort SendTo Shortcuts Installer")
    parser.add_argument("--list", action="store_true", help="List all registered shortcuts")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall all registered shortcuts")
    args = parser.parse_args(argv)

    sendto_dir = os.path.expandvars(SENDTO_DIRECTORY)

    if args.list:
        print("Registered SendTo shortcuts:")
        for s in SHORTCUTS:
            shortcut_path = os.path.join(sendto_dir, f"{s['name']}.lnk")
            status = "Installed" if os.path.exists(shortcut_path) else "Not Installed"
            print(f"  - {s['name']}: {s['description']} ({status})")
        return

    if args.uninstall:
        print("Uninstalling Kardenwort shortcuts...")
        for s in SHORTCUTS:
            shortcut_path = os.path.join(sendto_dir, f"{s['name']}.lnk")
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                print(f"Removed shortcut '{s['name']}'")
        # clean legacy ones
        for legacy in ("Kardenwort Vocab Processor",):
            old_path = os.path.join(sendto_dir, f"{legacy}.lnk")
            if os.path.exists(old_path):
                os.remove(old_path)
                print(f"Removed legacy shortcut '{legacy}'")
        return

    print("Installing Kardenwort shortcuts...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # Load config to get paths if available
    config_path = os.path.join(project_root, "config.ini")
    intellifiller_workspace_str = "../20251206123938-intellifiller-ai-addon-for-anki"
    if os.path.exists(config_path):
        try:
            config = configparser.ConfigParser(allow_no_value=True)
            config.read(config_path, encoding='utf-8')
            intellifiller_workspace_str = config.get('environment', 'intellifiller_workspace', fallback=intellifiller_workspace_str)
        except Exception:
            pass

    # Resolve paths
    python_path = sys.executable
    if python_path.lower().endswith("pythonw.exe"):
        python_path = python_path[:-len("pythonw.exe")] + "python.exe"

    sendto_vocab_path = os.path.join(current_dir, "sendto_vocab.py")
    runner_path = os.path.join(project_root, "src", "kardenwort", "core", "kardenwort_runner.py")
    
    # Resolve intellifiller workspace
    if os.path.isabs(intellifiller_workspace_str):
        intellifiller_workspace = intellifiller_workspace_str
    else:
        intellifiller_workspace = os.path.abspath(os.path.join(project_root, intellifiller_workspace_str))
    
    headless_entrypoint_path = os.path.join(intellifiller_workspace, "IntelliFiller", "headless_entrypoint.py")

    # Clean legacy shortcuts
    for legacy in ("Kardenwort Vocab Processor", "Kardenwort Vocab", "IntelliFiller Fill", "Kardenwort Import"):
        old_path = os.path.join(sendto_dir, f"{legacy}.lnk")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    # Register Kardenwort Extract Vocab
    create_shortcut(
        "Kardenwort Extract Vocab",
        python_path,
        f'"{sendto_vocab_path}" --sendto --pause',
        "Extracts vocabulary from sent files and imports them to Anki",
        sendto_dir
    )

    # Register Kardenwort Fill Vocab
    create_shortcut(
        "Kardenwort Fill Vocab",
        python_path,
        f'"{headless_entrypoint_path}" --prompt "English Vocabulary Analysis and Translation (JSON)" --tsv',
        "Enrich vocabulary TSV using headless IntelliFiller AI",
        sendto_dir
    )

    # Register Kardenwort Import All
    create_shortcut(
        "Kardenwort Import All",
        python_path,
        f'"{runner_path}" --import-only --tsv',
        "Imports an existing vocabulary TSV directly into Anki",
        sendto_dir
    )
    
    print("\nSUCCESS: All shortcuts created successfully!")

if __name__ == "__main__":
    main()
