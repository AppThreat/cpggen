import os
import re
import shutil
from pathlib import Path

# Default ignore list
ignore_directories = [
    ".git",
    ".svn",
    ".mvn",
    ".idea",
    "backup",
    "docs",
    "tests",
    "test",
    "report",
    "reports",
    "node_modules",
    ".terraform",
    ".serverless",
    "venv",
    "examples",
    "tutorials",
    "samples",
    "migrations",
    "db_migrations",
    "unittests",
    "unittests_legacy",
    "stubs",
    "mock",
    "mocks",
]

ignore_files = [
    ".pyc",
    ".gz",
    ".tar",
    ".tar.gz",
    ".tar",
    ".log",
    ".tmp",
    ".gif",
    ".png",
    ".jpg",
    ".webp",
    ".webm",
    ".icns",
    ".pcm",
    ".wav",
    ".mp3",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".d.ts",
    ".min.js",
    ".min.css",
    ".eslintrc.js",
    ".babelrc.js",
    ".spec.js",
    ".spec.ts",
    ".component.spec.js",
    ".component.spec.ts",
    ".data.js",
    ".data.ts",
    ".bundle.js",
    ".snap",
    ".pb.go",
    ".tests.py",
    ".vdb",
    ".txt",
    ".strings",
    ".nib",
]


def is_ignored_file(file_name):
    """
    Method to find if the given file can be ignored
    :param file_name: File to compare
    :return: Boolean True if file can be ignored. False otherwise
    """
    if not file_name:
        return False
    file_name = file_name.lower()
    extn = "".join(Path(file_name).suffixes)
    if extn in ignore_files or file_name in ignore_files:
        return True
    for ie in ignore_files:
        if file_name.endswith(ie):
            return True
    return False


def filter_ignored_dirs(dirs):
    """
    Method to filter directory list to remove ignored directories
    :param dirs: Directories to ignore
    :return: Filtered directory list
    """
    [
        dirs.remove(d)
        for d in list(dirs)
        if d.lower() in ignore_directories or d.startswith(".")
    ]
    return dirs


def is_ignored_dir(base_dir, dir_name):
    """
    Method to find if the given directory is an ignored directory
    :param base_dir: Base directory
    :param dir_name: Directory to compare
    :return: Boolean True if directory can be ignored. False otherwise
    """
    base_dir = base_dir.lower()
    dir_name = dir_name.lower()
    if dir_name.startswith("."):
        return True
    elif dir_name.startswith("/" + base_dir):
        dir_name = re.sub(r"^/" + base_dir + "/", "", dir_name)
    elif dir_name.startswith(base_dir):
        dir_name = re.sub(r"^" + base_dir + "/", "", dir_name)
    for d in ignore_directories:
        if dir_name == d or dir_name.startswith(d) or ("/" + d + "/") in dir_name:
            return True
    return False


def find_files(src, src_ext_name, use_start=False, quick=False):
    """
    Method to find files with given extension
    :param src: Source directory
    :param src_ext_name: Extension
    :param use_start: Boolean to check for file prefix
    :return: List of files with full path
    """
    result = []
    for root, dirs, files in os.walk(src):
        filter_ignored_dirs(dirs)
        if not is_ignored_dir(src, root):
            for file in files:
                if is_ignored_file(src, file):
                    continue
                if file == src_ext_name or file.endswith(src_ext_name):
                    result.append(os.path.join(root, file))
                elif use_start and file.startswith(src_ext_name):
                    result.append(os.path.join(root, file))
                if quick and result:
                    return result
    return result


def find_java_artifacts(search_dir):
    """
    Method to find java artifacts in the given directory
    :param src: Directory to search
    :return: List of war or ear or jar files
    """
    result = [p.as_posix() for p in Path(search_dir).rglob("*.war")]
    if not result:
        result = [p.as_posix() for p in Path(search_dir).rglob("*.ear")]
    if not result:
        result = [p.as_posix() for p in Path(search_dir).rglob("*.jar")]
    # Zip up the target directory as a jar file for analysis
    if not result:
        is_empty = True
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jar", encoding="utf-8", delete=False
        ) as zfile:
            with zipfile.ZipFile(zfile.name, "w") as zf:
                for dirname, subdirs, files in os.walk(search_dir):
                    zf.write(dirname)
                    is_empty = False
                    for filename in files:
                        if not filename.endswith(".jar"):
                            zf.write(os.path.join(dirname, filename))
        return [] if is_empty else [zfile.name]
    return result


def find_csharp_artifacts(search_dir):
    """
    Method to find .Net solution and csproj files in the given directory
    :param src: Directory to search
    :return: List of war or ear or jar files
    """
    result = [p.as_posix() for p in Path(search_dir).rglob("*.sln")]
    if not result:
        result = [p.as_posix() for p in Path(search_dir).rglob("*.csproj")]
    return result


def check_command(cmd):
    """
    Method to check if command is available
    :return True if command is available in PATH. False otherwise
    """
    try:
        cpath = shutil.which(cmd, mode=os.F_OK | os.X_OK)
        return cpath is not None
    except Exception:
        return False


def is_binary_string(content):
    """
    Method to check if the given content is a binary string
    """
    textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})
    return bool(content.translate(None, textchars))


def is_exe(src):
    """Detect if the source is a binary file
    :param src: Source path
    :return True if binary file. False otherwise.
    """
    if os.path.isfile(src):
        try:
            return is_binary_string(open(src, "rb").read(1024))
        except Exception:
            return False
    return False


def find_exe_files(src):
    """
    Method to find files with given extenstion
    """
    result = []
    for root, dirs, files in os.walk(src):
        filter_ignored_dirs(dirs)
        for file in files:
            if is_ignored_file(file):
                continue
            fullPath = os.path.join(root, file)
            if is_exe(fullPath):
                result.append(fullPath)
    return result


def bomstrip(manifest):
    """
    Function to delete UTF-8 BOM character in "string"
    """
    utf8bom = b"\xef\xbb\xbf"
    if manifest[:3] == utf8bom:
        return manifest[3:]
    else:
        return manifest
