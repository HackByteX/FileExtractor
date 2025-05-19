import os
import shutil
from pathlib import Path
from colorama import init, Fore, Style
import sys
import pyfiglet
import threading
import time

# Initialize colorama for colored output
init(autoreset=True, strip=not sys.stdout.isatty())

def copy_filtered_files(source_folder, destination_folder, file_extensions, remove_duplicates, create_folders):
    """
    Copy files with specified extensions from source folder to destination folder.
    
    Args:
        source_folder (str): Path to the source folder.
        destination_folder (str): Path to the destination folder.
        file_extensions (list): List of file extensions to filter (e.g., ['.txt', '.pdf']).
        remove_duplicates (bool): If True, overwrite existing files; if False, skip them.
        create_folders (bool): If True, preserve folder structure; if False, copy files to destination root.
    """
    # Ensure destination folder exists
    Path(destination_folder).mkdir(parents=True, exist_ok=True)
    
    # Normalize file extensions to lowercase and ensure they start with a dot
    file_extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in file_extensions]
    
    copied_files = 0
    skipped_files = 0
    
    # Validate destination is not inside source
    if os.path.abspath(destination_folder).startswith(os.path.abspath(source_folder)):
        print(f"{Fore.RED}Error: Destination folder cannot be inside source folder.")
        return copied_files, skipped_files
    
    # Define the bold and prominent arrow (single ⥤)
    bold_arrow = f"{Fore.YELLOW}{Style.BRIGHT} ⥤ {Style.RESET_ALL}"
    
    # Print header
    print(f"\n{Fore.CYAN}{Style.BRIGHT}  {'⥦'*36}")
    print(f"{Fore.CYAN}   Starting File Extraction Operation")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {'⥩'*36}")
    print(f"{Fore.RED}  Source{bold_arrow}{source_folder}")
    print(f"{Fore.RED}  Destination{bold_arrow}{destination_folder}")
    print(f"{Fore.RED}  Extensions{bold_arrow}{', '.join(file_extensions)}")
    print(f"{Fore.RED}  Remove Duplicates{bold_arrow}{'Yes' if remove_duplicates else 'No'}")
    print(f"{Fore.RED}  Create Folder Structure{bold_arrow}{'Including Directory' if create_folders else 'Only Files'}\n")
    
    # Flag to control initialization message
    initializing = True
    
    def display_initializing():
        """Display 'Getting things ready, please wait...' with dots animation until stopped."""
        dots = 0
        while initializing:
            sys.stdout.write(f"\r{Fore.LIGHTBLUE_EX}  Getting things ready, please wait{'.' * (dots % 4)}   ")
            sys.stdout.flush()
            time.sleep(0.5)
            dots += 1
        # Clear the line after stopping
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()
    
    # Start the initializing message in a separate thread
    init_thread = threading.Thread(target=display_initializing)
    init_thread.daemon = True
    init_thread.start()
    
    # Collect all files to process
    file_list = []
    for root, _, files in os.walk(source_folder):
        for file in files:
            if any(file.lower().endswith(ext) for ext in file_extensions):
                file_list.append((root, file))
    
    # Stop initializing message if no files to process
    if not file_list:
        initializing = False
        init_thread.join()
        print(f"{Fore.YELLOW}  No files found with specified extensions.")
        return copied_files, skipped_files
    
    # Try to use rich for progress bar
    try:
        from rich.console import Console
        from rich.live import Live
        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn
        console = Console()
        
        # Initialize progress bar
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console
        )
        
        # Start live display for progress bar
        with Live(progress, console=console, refresh_per_second=10) as live:
            task = progress.add_task("Processing files", total=len(file_list))
            
            # Process files
            for root, file in file_list:
                # Stop initializing message on first file
                if initializing:
                    initializing = False
                    init_thread.join()
                
                source_path = os.path.join(root, file)
                if create_folders:
                    # Preserve folder structure
                    relative_path = os.path.relpath(root, source_folder)
                    dest_dir = os.path.join(destination_folder, relative_path)
                    dest_path = os.path.join(dest_dir, file)
                else:
                    # Copy directly to destination folder
                    dest_dir = destination_folder
                    dest_path = os.path.join(destination_folder, file)
                
                try:
                    if os.path.exists(dest_path):
                        if remove_duplicates:
                            console.print(f"[yellow]  Replacing: [cyan]{file}[/cyan] ([blue]{source_path}[/blue])[/yellow]")
                            if create_folders:
                                Path(dest_dir).mkdir(parents=True, exist_ok=True)
                            shutil.copy2(source_path, dest_path)
                            copied_files += 1
                        else:
                            console.print(f"[magenta]  Skipped duplicate: [cyan]{file}[/cyan][/magenta]")
                            skipped_files += 1
                            progress.advance(task)
                            continue
                    else:
                        console.print(f"[green]  Copied: [blue]{source_path}[/blue] -> [purple]{dest_path}[/purple][/green]")
                        if create_folders:
                            Path(dest_dir).mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                        copied_files += 1
                except (shutil.Error, OSError) as e:
                    console.print(f"[red]  Error copying {source_path}: {e}[/red]")
                
                progress.advance(task)
    
    except ImportError:
        print(f"{Fore.YELLOW}  Warning: 'rich' not installed. Progress bar disabled.")
        # Fallback: process files without progress bar
        for root, file in file_list:
            # Stop initializing message on first file
            if initializing:
                initializing = False
                init_thread.join()
            
            source_path = os.path.join(root, file)
            if create_folders:
                # Preserve folder structure
                relative_path = os.path.relpath(root, source_folder)
                dest_dir = os.path.join(destination_folder, relative_path)
                dest_path = os.path.join(dest_dir, file)
            else:
                # Copy directly to destination folder
                dest_dir = destination_folder
                dest_path = os.path.join(destination_folder, file)
            
            try:
                if os.path.exists(dest_path):
                    if remove_duplicates:
                        print(f"{Fore.YELLOW}Replacing: {file} ({source_path})")
                        sys.stdout.flush()
                        if create_folders:
                            Path(dest_dir).mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                        copied_files += 1
                    else:
                        print(f"{Fore.MAGENTA}Skipped duplicate: {file}")
                        sys.stdout.flush()
                        skipped_files += 1
                        continue
                else:
                    print(f"{Fore.GREEN}Copied: {source_path} -> {dest_path}")
                    sys.stdout.flush()
                    if create_folders:
                        Path(dest_dir).mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    copied_files += 1
            except (shutil.Error, OSError) as e:
                print(f"{Fore.RED}Error copying {source_path}: {e}")
    
    # Ensure initializing message is stopped
    initializing = False
    init_thread.join()
    
    # Print summary
    print(f"\n{Fore.CYAN}{Style.BRIGHT}  {'⥦'*26}")
    print(f"{Fore.CYAN}   File Extraction Complete")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {'⥩'*26}")
    print(f"{Fore.RED}   Files Extracted{bold_arrow}{copied_files}")
    print(f"{Fore.RED}   Files Skipped{bold_arrow}{skipped_files}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {'⥫'*26}\n")
    
    return copied_files, skipped_files

def main():
    try:
        print("\n\n\n\n" + Style.BRIGHT + pyfiglet.figlet_format(" File Extractor", font="slant"))
        print(f"{' ' * 55}{Fore.YELLOW}By. HackByte\n")
    
        # Print welcome message
        print(f"\n\n{Style.BRIGHT}  {'❉' * 54}")
        print(f"  ❉    Welcome to File Extractor - Created By Afsal    ❉")
        print(f"{Style.BRIGHT}  {'❉' * 54}\n")
        
        # Define the bold and prominent arrow for prompts
        bold_arrow = f"{Fore.YELLOW}{Style.BRIGHT} ⥤ {Style.RESET_ALL}"
        
        # Prompt for source and destination folders
        print(f"{Fore.YELLOW}  Enter the source folder path{bold_arrow}", end='')
        source_folder = input().strip()
        print(f"{Fore.YELLOW}  Enter the destination folder path{bold_arrow}", end='')
        destination_folder = input().strip()
        
        # Prompt for file extensions
        print(f"{Fore.YELLOW}  Enter file extensions (e.g., .txt,.pdf,...etc){bold_arrow}", end='')
        extensions_input = input().strip()
        file_extensions = [ext.strip() for ext in extensions_input.split(",") if ext.strip()]
        
        # Prompt for remove_duplicates
        while True:
            print(f"{Fore.YELLOW}  Remove duplicates if file exists? (yes/no){bold_arrow}", end='')
            remove_duplicates_input = input().strip().lower()
            if remove_duplicates_input in ['y', 'yes']:
                remove_duplicates = True
                break
            elif remove_duplicates_input in ['n', 'no']:
                remove_duplicates = False
                break
            else:
                print(f"{Fore.RED}  Invalid input. Please enter 'yes', 'no', 'y', or 'n'.")
        
        # Prompt for create_folders
        while True:
            print(f"{Fore.YELLOW}  Create folder structure in destination? (yes/no){bold_arrow}", end='')
            create_folders_input = input().strip().lower()
            if create_folders_input in ['y', 'yes']:
                create_folders = True
                break
            elif create_folders_input in ['n', 'no']:
                create_folders = False
                break
            else:
                print(f"{Fore.RED}  Invalid input. Please enter 'yes', 'no', 'y', or 'n'.")
        
        # Validate inputs
        if not os.path.exists(source_folder):
            print(f"{Fore.RED}  Error: Source folder '{source_folder}' does not exist.")
            return
        if not file_extensions:
            print(f"{Fore.RED}  Error: No valid file extensions provided.")
            return
        
        # Run the copy operation
        copy_filtered_files(source_folder, destination_folder, file_extensions, remove_duplicates, create_folders)
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}  Operation cancelled by user.")
    except Exception as e:
        print(f"{Fore.RED}  An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
