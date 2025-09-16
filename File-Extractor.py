import os
import sys
import time
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from colorama import Fore, Style, just_fix_windows_console
import pyfiglet

# Enable ANSI on Windows safely (no-op elsewhere)
just_fix_windows_console()

# =========================
# Utilities for path safety
# =========================
def is_subpath(child: Path, parent: Path) -> bool:
    """
    Returns True if 'child' is inside 'parent' directory tree.
    Uses pathlib parents semantics (robust vs string checks).
    """
    try:
        child_res = child.resolve()
        parent_res = parent.resolve()
    except Exception:
        child_res = child
        parent_res = parent
    return parent_res in child_res.parents

def normalize_destination(dst_input: str, src_abs: str) -> str:
    """
    Make a safe absolute destination:
    - Absolute or ~ : honor it (expanduser + resolve).
    - Relative like 'Output-Files': place next to source root, not under CWD.
      Example:
        source: /home/user/project/tmpwork
        dst_input: "Output-Files"
        result: /home/user/project/Output-Files
    """
    p = Path(dst_input).expanduser()
    if p.is_absolute():
        return str(p.resolve())
    src = Path(src_abs).resolve()
    safe_base = src.parent
    return str((safe_base / p.name).resolve())

# =========================
# Input helpers
# =========================
def prompt_yes_no(msg):
    while True:
        resp = input(msg).strip().lower()
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print(f"{Fore.RED}  Invalid input. Please enter 'yes' or 'no'.{Style.RESET_ALL}")

def prompt_existing_dir(msg):
    while True:
        p = input(msg).strip()
        if not p:
            print(f"{Fore.RED}  Path cannot be empty.{Style.RESET_ALL}")
            continue
        try:
            path = Path(p).expanduser().resolve()
        except Exception:
            print(f"{Fore.RED}  Invalid path. Try again.{Style.RESET_ALL}")
            continue
        if not path.exists() or not path.is_dir():
            print(f"{Fore.RED}  Directory does not exist. Provide an existing folder.{Style.RESET_ALL}")
            continue
        return str(path)

def prompt_destination_dir(msg, source_abs: str):
    """
    Reads input, normalizes to a safe absolute path (sibling of source if relative),
    blocks dangerous system paths, validates not inside source, then auto-creates.
    """
    while True:
        p = input(msg).strip()
        if not p:
            print(f"{Fore.RED}  Path cannot be empty.{Style.RESET_ALL}")
            continue

        # Normalize destination relative to source parent if relative
        try:
            normalized = normalize_destination(p, source_abs)
        except Exception as e:
            print(f"{Fore.RED}  Invalid path: {e}{Style.RESET_ALL}")
            continue

        path = Path(normalized)

        # Block critical system locations
        forbidden_prefixes = ('/sys', '/proc', '/dev')
        if any(str(path).startswith(prefix) for prefix in forbidden_prefixes):
            print(f"{Fore.RED}  Cannot use system locations as destination.{Style.RESET_ALL}")
            continue

        # Robust containment check
        src_path = Path(source_abs).resolve()
        try:
            dst_path = path.resolve()
        except Exception:
            dst_path = path

        if dst_path == src_path or is_subpath(dst_path, src_path):
            print(f"{Fore.RED}  Error: Destination folder cannot be inside source folder.{Style.RESET_ALL}")
            print(f"{Style.BRIGHT}{Fore.CYAN}  Tip: Use an absolute path outside source, e.g., ~/Desktop/Output-Files or /home/kali/Output-Files{Style.RESET_ALL}")
            continue

        # Auto-create destination root after validation
        try:
            dst_path.mkdir(parents=True, exist_ok=True)
            if not dst_path.is_dir():
                print(f"{Fore.RED}  Failed to create directory: {dst_path}{Style.RESET_ALL}")
                continue

            # Quick write check
            test_file = dst_path / ".write_test"
            try:
                test_file.touch()
                test_file.unlink()
            except Exception:
                print(f"{Fore.YELLOW}  ⚠ Directory created but may not be writable: {dst_path}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}  ✓ Directory ready: {dst_path}{Style.RESET_ALL}")
            return str(dst_path)
        except PermissionError:
            print(f"{Fore.RED}  Permission denied for: {dst_path}{Style.RESET_ALL}")
            print(f"{Style.BRIGHT}{Fore.CYAN}  Tip: Choose a location like ~/Desktop/Output-Files or /tmp/Output-Files{Style.RESET_ALL}")
        except OSError as e:
            print(f"{Fore.RED}  OS error while creating directory: {e}{Style.RESET_ALL}")

def prompt_extensions(msg):
    while True:
        raw = input(msg).strip()
        toks = [t.strip() for t in raw.split(",") if t.strip()]
        if not toks:
            print(f"{Fore.RED}  Provide at least one extension like .pdf,.jpg{Style.RESET_ALL}")
            continue
        exts = []
        bad = []
        for t in toks:
            t = t.lower()
            if not t.startswith("."):
                t = "." + t
            cond = len(t) > 1 and len(t) <= 16 and t.replace(".", "").isalnum()
            if cond:
                exts.append(t)
            else:
                bad.append(t)
        if bad or not exts:
            print(f"{Fore.RED}  Invalid extensions: {', '.join(bad) if bad else '(none)'}{Style.RESET_ALL}")
            continue
        return exts

# =========================
# Core copy logic
# =========================
def copy_filtered_files(
    source_folder,
    destination_folder,
    file_extensions,
    remove_duplicates,
    create_folders,
    dry_run=False,
    max_workers=1,
    auto_rename_on_conflict=True,
):
    """
    Copy files with specified extensions from source to destination.
    Enhancements:
    - Prevent destination inside source using pathlib parents semantics.
    - Auto-creates destination root (and needed subdirs) safely.
    - Preserves structure only where matching files exist (no empty dirs).
    - If no eligible subfolders but root has matches, still runs.
    - If nothing matches at all, prints clear message and exits gracefully.
    """
    source_folder = str(Path(source_folder).expanduser().resolve())
    destination_folder = str(Path(destination_folder).expanduser().resolve())

    # Normalize extension set
    exts = set((ext if ext.startswith(".") else f".{ext}").lower().strip()
               for ext in file_extensions if ext.strip())

    copied_files = 0
    skipped_files = 0

    # Robust safety check: prevent destination inside source
    src_path = Path(source_folder)
    dst_path = Path(destination_folder)
    if dst_path == src_path or is_subpath(dst_path, src_path):
        print(f"{Fore.RED}Error: Destination folder cannot be inside source folder.{Style.RESET_ALL}")
        return copied_files, skipped_files

    # Ensure destination exists
    try:
        Path(destination_folder).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"{Fore.RED}  Error creating destination: {e}{Style.RESET_ALL}")
        return copied_files, skipped_files

    bold_arrow = f"{Fore.YELLOW}{Style.BRIGHT} ⥤ {Style.RESET_ALL}"
    label_bold = Style.BRIGHT
    reset = Style.RESET_ALL

    # Header
    print(f"\n{Fore.CYAN}{Style.BRIGHT}  {'⥦'*36}{reset}")
    print(f"{Fore.CYAN}{Style.BRIGHT}   Starting File Extraction Operation{reset}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {'⥩'*36}{reset}")
    print(f"{Fore.RED}  {label_bold}Source{reset}{bold_arrow}{source_folder}")
    print(f"{Fore.RED}  {label_bold}Destination{reset}{bold_arrow}{destination_folder}")
    print(f"{Fore.RED}  {label_bold}Extensions{reset}{bold_arrow}{', '.join(sorted(exts))}")
    print(f"{Fore.RED}  {label_bold}Remove Duplicates{reset}{bold_arrow}{'Yes' if remove_duplicates else 'No'}")
    print(f"{Fore.RED}  {label_bold}Create Folder Structure{reset}{bold_arrow}{'Same as Source' if create_folders else 'Only Files'}\n")

    # Small initializing animation
    init_stop = threading.Event()
    def display_initializing():
        dots = 0
        while not init_stop.is_set():
            sys.stdout.write(f"\r{Fore.LIGHTBLUE_EX}  Getting things ready, please wait{'.' * (dots % 4)}   ")
            sys.stdout.flush()
            time.sleep(0.4)
            dots += 1
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    init_thread = threading.Thread(target=display_initializing, daemon=True)
    init_thread.start()

    # First pass: discover files and eligible directories
    file_list = []             # list of (root, filename)
    eligible_dirs = set()      # roots that contain at least one matching file
    root_has_files = False     # whether source root itself has matching files

    for root, _, files in os.walk(source_folder):
        matched_in_this_root = False
        for name in files:
            if any(name.lower().endswith(e) for e in exts):
                file_list.append((root, name))
                matched_in_this_root = True
        if matched_in_this_root:
            eligible_dirs.add(root)
            if os.path.normpath(root) == os.path.normpath(source_folder):
                root_has_files = True

    # Stop init animation
    init_stop.set()
    init_thread.join()

    # Handle “no folders inside” / no matches
    if not file_list:
        print(f"{Fore.YELLOW}  No files found with specified extensions. No folder inside contains matching files.{Style.RESET_ALL}")
        return copied_files, skipped_files

    # Informative hint when mirroring structure but no eligible subfolders
    if create_folders:
        subfolders_only = {d for d in eligible_dirs if os.path.normpath(d) != os.path.normpath(source_folder)}
        if not subfolders_only:
            if root_has_files:
                print(f"{Fore.YELLOW}  No subfolders with matching files. Only root-level files will be mirrored.{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}  No folder inside contains matching files.{Style.RESET_ALL}")

    # Progress setup
    use_rich = True
    try:
        from rich.console import Console
        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn
        from rich.live import Live
        console = Console()
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        )
    except ImportError:
        use_rich = False
        console = None

    def collision_safe_path(path):
        if not os.path.exists(path):
            return path
        p = Path(path)
        stem, suffix, parent = p.stem, p.suffix, p.parent
        i = 1
        while True:
            candidate = parent / f"{stem} ({i}){suffix}"
            if not candidate.exists():
                return str(candidate)
            i += 1

    def map_destination(root, name):
        src_path = os.path.join(root, name)
        if create_folders:
            # Mirror only where matching files exist; ensures no empty dirs.
            relative = os.path.relpath(root, source_folder)
            dest_dir = os.path.join(destination_folder, relative)
            dest_path = os.path.join(dest_dir, name)
        else:
            dest_dir = destination_folder
            dest_path = os.path.join(destination_folder, name)
        return src_path, dest_dir, dest_path

    def do_copy(src_path, dest_dir, dest_path):
        try:
            if not dry_run:
                Path(dest_dir).mkdir(parents=True, exist_ok=True)
            if os.path.exists(dest_path):
                if remove_duplicates:
                    if dry_run:
                        return "replace"
                    shutil.copy2(src_path, dest_path)
                    return "replaced"
                else:
                    if not create_folders and auto_rename_on_conflict:
                        new_path = collision_safe_path(dest_path)
                        if dry_run:
                            return f"rename->{Path(new_path).name}"
                        shutil.copy2(src_path, new_path)
                        return f"renamed->{Path(new_path).name}"
                    else:
                        return "skip"
            else:
                if dry_run:
                    return "copy"
                shutil.copy2(src_path, dest_path)
                return "copied"
        except (shutil.Error, OSError) as e:
            return f"error:{e}"

    iterable = (map_destination(root, name) for (root, name) in file_list)

    if use_rich:
        from rich.live import Live
        with Live(progress, console=console, refresh_per_second=10):
            task = progress.add_task("Processing files", total=len(file_list))
            if max_workers > 1:
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = {pool.submit(do_copy, *args): args for args in iterable}
                    for fut in as_completed(futures):
                        src_path, dest_dir, dest_path = futures[fut]
                        result = fut.result()
                        name = os.path.basename(src_path)
                        if result in ("copied", "replaced") or result.startswith("renamed"):
                            copied_files += 1
                            console.print(f"[green]  {result.capitalize()}: [blue]{src_path}[/blue] -> [purple]{dest_path}[/purple][/green]")
                        elif result == "copy":
                            console.print(f"[green]  Copy (dry run): [blue]{src_path}[/blue] -> [purple]{dest_path}[/purple][/green]")
                        elif result == "replace":
                            console.print(f"[yellow]  Replace (dry run): [cyan]{name}[/cyan][/yellow]")
                        elif result == "skip":
                            skipped_files += 1
                            console.print(f"[magenta]  Skipped duplicate: [cyan]{name}[/cyan][/magenta]")
                        elif result.startswith("error:"):
                            # FIX: index 1 not 21
                            console.print(f"[red]  Error copying {src_path}: {result.split(':',1)[1]}[/red]")
                        progress.advance(task)
            else:
                for src_path, dest_dir, dest_path in (map_destination(root, name) for (root, name) in file_list):
                    result = do_copy(src_path, dest_dir, dest_path)
                    name = os.path.basename(src_path)
                    if result in ("copied", "replaced") or result.startswith("renamed"):
                        copied_files += 1
                        console.print(f"[green]  {result.capitalize()}: [blue]{src_path}[/blue] -> [purple]{dest_path}[/purple][/green]")
                    elif result == "copy":
                        console.print(f"[green]  Copy (dry run): [blue]{src_path}[/blue] -> [purple]{dest_path}[/purple][/green]")
                    elif result == "replace":
                        console.print(f"[yellow]  Replace (dry run): [cyan]{name}[/cyan][/yellow]")
                    elif result == "skip":
                        skipped_files += 1
                        console.print(f"[magenta]  Skipped duplicate: [cyan]{name}[/cyan][/magenta]")
                    elif result.startswith("error:"):
                        # FIX: index 1 not 21
                        console.print(f"[red]  Error copying {src_path}: {result.split(':',1)[1]}[/red]")
                    progress.advance(task)
    else:
        print(f"{Fore.YELLOW}  Warning: 'rich' not installed. Progress bar disabled.{Style.RESET_ALL}")
        for root, name in file_list:
            src_path, dest_dir, dest_path = map_destination(root, name)
            result = do_copy(src_path, dest_dir, dest_path)
            fname = os.path.basename(src_path)
            if result in ("copied", "replaced") or result.startswith("renamed"):
                copied_files += 1
                print(f"{Fore.GREEN}Copied: {src_path} -> {dest_path}{Style.RESET_ALL}")
            elif result == "copy":
                print(f"{Fore.GREEN}Copy (dry run): {src_path} -> {dest_path}{Style.RESET_ALL}")
            elif result == "replace":
                print(f"{Fore.YELLOW}Replace (dry run): {fname}{Style.RESET_ALL}")
            elif result == "skip":
                skipped_files += 1
                print(f"{Fore.MAGENTA}Skipped duplicate: {fname}{Style.RESET_ALL}")
            elif result.startswith("error:"):
                # FIX: index 1 not 21
                print(f"{Fore.RED}Error copying {src_path}: {result.split(':',1)[1]}{Style.RESET_ALL}")

    # Summary
    print(f"\n{Fore.CYAN}{Style.BRIGHT}  {'⥦'*26}{reset}")
    print(f"{Fore.CYAN}{Style.BRIGHT}   File Extraction Complete{reset}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {'⥩'*26}{reset}")
    print(f"{Fore.RED}   Files Extracted{bold_arrow}{copied_files}")
    print(f"{Fore.RED}   Files Skipped{bold_arrow}{skipped_files}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {'⥫'*26}{reset}\n")

    return copied_files, skipped_files

# =========================
# Main
# =========================
def main():
    try:
        # Banner
        print("\n\n\n\n" + Style.BRIGHT + pyfiglet.figlet_format(" File Extractor", font="slant"))
        print(f"{' ' * 55}{Fore.YELLOW}By. HackByte\n")

        # Welcome
        print(f"\n\n{Style.BRIGHT}{Fore.YELLOW}  {'❉' * 54}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.YELLOW}  ❉    Welcome to File Extractor - Created By Afsal    ❉{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.YELLOW}  {'❉' * 54}{Style.RESET_ALL}\n")

        bold_arrow = f"{Fore.YELLOW}{Style.BRIGHT} ⥤ {Style.RESET_ALL}"

        # Inputs
        source_folder = prompt_existing_dir(f"{Fore.YELLOW}{Style.BRIGHT}  Enter the source folder path{Style.RESET_ALL}{bold_arrow}")
        source_abs = str(Path(source_folder).expanduser().resolve())
        destination_folder = prompt_destination_dir(f"{Fore.YELLOW}{Style.BRIGHT}  Enter the destination folder path{Style.RESET_ALL}{bold_arrow}", source_abs=source_abs)
        file_extensions = prompt_extensions(f"{Fore.YELLOW}{Style.BRIGHT}  Enter file extensions (e.g., .txt,.pdf){Style.RESET_ALL}{bold_arrow}")
        remove_duplicates = prompt_yes_no(f"{Fore.YELLOW}{Style.BRIGHT}  Remove duplicates if file exists? (yes/no){Style.RESET_ALL}{bold_arrow}")
        create_folders = prompt_yes_no(f"{Fore.YELLOW}{Style.BRIGHT}  Create same folder structure in destination? (yes/no){Style.RESET_ALL}{bold_arrow}")

        # Resolve final absolute paths
        src = str(Path(source_folder).expanduser().resolve())
        dst = str(Path(destination_folder).expanduser().resolve())

        # Final robust safety check (defense in depth)
        src_path = Path(src)
        dst_path = Path(dst)
        if dst_path == src_path or is_subpath(dst_path, src_path):
            print(f"{Fore.RED}  Error: Destination folder cannot be inside source folder.")
            print(f"{Style.BRIGHT}{Fore.CYAN}  Tip: Choose a path outside: e.g., /home/kali/Output-Files or ~/Desktop/Output-Files{Style.RESET_ALL}")
            return

        # Execute
        copy_filtered_files(
            src,
            dst,
            file_extensions,
            remove_duplicates,
            create_folders,
            dry_run=False,         # set True for preview
            max_workers=1,         # increase for I/O-bound speedup if needed
            auto_rename_on_conflict=True
        )
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}  Operation cancelled by user.")
    except Exception as e:
        print(f"{Fore.RED}  An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
