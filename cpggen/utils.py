import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import git

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
    "vendor",
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
                if is_ignored_file(file):
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
    is_empty = True
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jar", encoding="utf-8", delete=False
    ) as zfile:
        with zipfile.ZipFile(zfile.name, "w") as zf:
            for dirname, subdirs, files in os.walk(search_dir):
                is_empty = False
                for filename in files:
                    if (
                        filename.endswith(".jar")
                        or filename.endswith(".war")
                        or filename.endswith(".ear")
                    ):
                        zf.write(os.path.join(dirname, filename), filename)
    return [] if is_empty else [zfile.name]


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


def find_go_mods(search_dir):
    return find_files(search_dir, "go.mod", False, False)


def find_makefiles(search_dir):
    return find_files(search_dir, "Makefile", False, False)


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


def find_python_reqfiles(path):
    """
    Method to find python requirements files
    Args:
      path Project dir
    Returns:
      List of python requirement files
    """
    result = []
    req_files = ["requirements.txt", "Pipfile", "Pipfile.lock", "conda.yml"]
    for root, dirs, files in os.walk(path):
        filter_ignored_dirs(dirs)
        if not is_ignored_dir(path, root):
            for name in req_files:
                if name in files:
                    result.append(os.path.join(root, name))
    return result


def detect_project_type(src_dir):
    """Detect project type by looking for certain files
    :param src_dir: Source directory
    :return List of detected types
    """
    home_dir = str(Path.home())
    maven_cache = os.path.join(home_dir, ".m2")
    gradle_cache = os.path.join(home_dir, ".gradle", "caches", "modules-2", "files-2.1")
    maven_cache_exists = os.path.exists(maven_cache)
    gradle_cache_exists = os.path.exists(gradle_cache)
    project_types = []
    if find_python_reqfiles(src_dir) or find_files(src_dir, ".py", False, True):
        project_types.append("python")
    if find_files(src_dir, "composer.json", False, True) or find_files(
        src_dir, ".php", False, True
    ):
        project_types.append("php")
    if find_files(src_dir, ".sbt", False, True) or find_files(
        src_dir, ".scala", False, True
    ):
        project_types.append("scala")
    if find_files(src_dir, ".kt", False, True):
        if maven_cache_exists or gradle_cache_exists:
            project_types.append("kotlin-with-classpath")
        else:
            project_types.append("kotlin")
    if (
        find_files(src_dir, "pom.xml", False, True)
        or find_files(src_dir, ".gradle", False, True)
        or find_files(src_dir, ".java", False, True)
    ):
        project_types.append("java")
    if find_files(src_dir, ".jsp", False, True):
        project_types.append("jsp")
    if (
        find_files(src_dir, "package.json", False, True)
        or find_files(src_dir, "yarn.lock", False, True)
        or find_files(src_dir, ".js", False, True)
        or find_files(src_dir, ".ts", False, True)
    ):
        project_types.append("js")
    if find_files(src_dir, ".csproj", False, True) or find_files(
        src_dir, ".sln", False, True
    ):
        project_types.append("csharp")
    if (
        find_files(src_dir, "go.mod", False, True)
        or find_files(src_dir, "Gopkg.lock", False, True)
        or find_files(src_dir, ".go", False, True)
    ):
        project_types.append("go")
    if (
        find_files(src_dir, "conan.lock", False, True)
        or find_files(src_dir, "conanfile.txt", False, True)
        or find_files(src_dir, ".c", False, True)
        or find_files(src_dir, ".cpp", False, True)
    ):
        project_types.append("c")

    if is_exe(src_dir):
        project_types.append("binary")
    return project_types


def clone_repo(repo_url, clone_dir, depth=1):
    git.Repo.clone_from(repo_url, clone_dir, depth=depth)
    return clone_dir
