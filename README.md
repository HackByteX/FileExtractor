Sure! Here's a cleaned-up and completed version of your `README.md` file for the **File Extractor** project:

---

# 📁 File Extractor

> Extract files with specific extensions from a source directory to a destination directory.
> Supports duplicate handling, folder structure preservation, and visual CLI output.

---

## ✨ Features

* ✅ Filter by file extension (e.g., `.pdf`, `.jpg`, `.docx` , `etc...`)
* ✅ Preserve or flatten folder structure
* ✅ Skip or overwrite duplicate files
* ✅ Terminal progress bar using [`rich`](https://github.com/Textualize/rich)
* ✅ Clean UI with [`colorama`](https://pypi.org/project/colorama/) and [`pyfiglet`](https://github.com/pwaller/pyfiglet)

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/HackByteX/file-extractor.git
cd file-extractor
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python File-Extractor.py
```

You'll be prompted for:

* Source folder
* Destination folder
* File extensions to filter (e.g.,  `.pdf`, `.jpg`, `.docx` , `etc...`)
* Overwrite existing files (yes/no)
* Preserve folder structure (yes/no)

---

## ✅ Step-by-Step Example: Run from Anywhere

### 1. Create a Wrapper Script

Create a simple shell script that acts like a shortcut:

```bash
sudo nano /usr/local/bin/fileextractor
```

Paste the following into the file:

```bash
#!/bin/bash
python3 /home/Afsal/Activity-Folder/Tools/File-Extractor.py "$@"
```

> 🔹 Replace the path with the actual location of your `File-Extractor.py`.

### 2. Make it executable

```bash
sudo chmod +x /usr/local/bin/fileextractor
```

---

### ✅ Now test it

Anywhere in your terminal, simply run:

```bash
fileextractor
```

Your script will execute globally, just like a normal command-line tool.

---

## Example

```
Source path             ⥤ /home/user/Downloads
Destination path        ⥤ /home/user/Documents/Extracted
File extensions         ⥤ .pdf,.jpg,.docx
Remove duplicates?      ⥤ yes
Preserve structure?     ⥤ no
```

---

## Requirements

* Python 3.7+
* Dependencies:

  * `colorama`
  * `pyfiglet`
  * `rich`

Install via:

```bash
pip install -r requirements.txt
```

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to propose.

---

## License

[MIT](LICENSE)

---

## Author

**Muhammed Afsal C**
[GitHub](https://github.com/your-username) • [LinkedIn](https://linkedin.com/in/your-link)

```

---

✅ Let me know if you want this in a downloadable ZIP or if you want help creating a GitHub Release/Tag (`v1.0.0`).
```
