import json
import os
import re
import shutil
import tempfile
import tarfile
import zipfile
from pathlib import Path
from sys import platform

import httpx
import rich.progress
from packageurl import PackageURL
from packageurl.contrib import purl2url
from rich.progress import Progress

from cpggen.source import ghsa

GIT_AVAILABLE = False
try:
    import git

    GIT_AVAILABLE = True
except ImportError:
    pass

MAVEN_CENTRAL_URL = "https://repo1.maven.org/maven2/"
ANDROID_MAVEN = "https://maven.google.com/"

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
    "instancemode-tests",
    "integration-tests",
    "oauth2-tests",
    "twofactor-tests",
    "gradle",
    "buildSrc",
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
    if platform != "win32":
        if dir_name.startswith("."):
            return True
        elif dir_name.startswith(os.path.sep + base_dir):
            dir_name = re.sub(r"^" + os.path.sep + base_dir + os.path.sep, "", dir_name)
        elif dir_name.startswith(base_dir):
            dir_name = re.sub(r"^" + base_dir + os.path.sep, "", dir_name)
    for d in ignore_directories:
        if (
            dir_name == d
            or dir_name.startswith(d)
            or (os.path.sep + d + os.path.sep) in dir_name
        ):
            return True
    return False


def find_files(src, src_ext_name, use_start=False, quick=False):
    """
    Method to find files with given extension
    :param src: Source directory
    :param src_ext_name: Extension
    :param use_start: Boolean to check for file prefix
    :param quick: Quick search mode to return after a single hit
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
                    result.append(os.path.abspath(os.path.join(root, file)))
                elif use_start and file.startswith(src_ext_name):
                    result.append(os.path.abspath(os.path.join(root, file)))
                if quick and result:
                    return result
    return result


def find_java_artifacts(search_dir):
    """
    Method to find java artifacts in the given directory
    :param search_dir: Directory to search
    :return: List of war or ear or jar files
    """
    jlist = []
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jar", encoding="utf-8", delete=False
    ) as zfile:
        with zipfile.ZipFile(zfile.name, "w") as zf:
            for dirname, subdirs, files in os.walk(search_dir):
                filter_ignored_dirs(subdirs)
                if not is_ignored_dir(search_dir, dirname):
                    for filename in files:
                        if (
                            filename.endswith(".jar")
                            or filename.endswith(".war")
                            or filename.endswith(".ear")
                        ):
                            jlist.append(
                                os.path.abspath(os.path.join(dirname, filename))
                            )
                            zf.write(os.path.join(dirname, filename))
    return jlist if len(jlist) == 1 else [os.path.abspath(zfile.name)]


def find_csharp_artifacts(search_dir):
    """
    Method to find .Net solution and csproj files in the given directory
    :param search_dir: Directory to search
    :return: List of .sln or .csharp files
    """
    result = [p.as_posix() for p in Path(search_dir).absolute().rglob("*.sln")]
    if not result:
        result = [p.as_posix() for p in Path(search_dir).absolute().rglob("*.csproj")]
    return result


def find_go_mods(search_dir):
    return find_files(search_dir, "go.mod", False, False)


def find_makefiles(search_dir):
    return find_files(search_dir, "Makefile", False, False)


def find_gradle_files(search_dir):
    return find_files(search_dir, "build.gradle", False, False)


def find_pom_files(search_dir):
    return find_files(search_dir, "pom.xml", False, False)


def find_sbt_files(search_dir):
    return find_files(search_dir, "build.sbt", False, False)


def check_command(cmd):
    """
    Method to check if command is available
    :return True if command is available in PATH. False otherwise
    """
    cpath = shutil.which(cmd, mode=os.F_OK | os.X_OK)
    return cpath is not None


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
        except OSError:
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
            full_path = os.path.join(root, file)
            if is_exe(full_path):
                result.append(full_path)
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
    is_java_like = False
    home_dir = str(Path.home())
    maven_cache = os.path.join(home_dir, ".m2")
    gradle_cache = os.path.join(home_dir, ".gradle", "caches", "modules-2", "files-2.1")
    maven_cache_exists = os.path.exists(maven_cache)
    gradle_cache_exists = os.path.exists(gradle_cache)
    project_types = []
    # Is this a package url
    if src_dir.startswith("pkg:"):
        purl_data = PackageURL.from_string(src_dir)
        if purl_data and purl_data.type:
            return [purl_data.type]
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
        is_java_like = True
        if os.getenv("SHIFTLEFT_ACCESS_TOKEN"):
            project_types.append("jar")
        else:
            if os.path.exists(str(Path.home() / ".m2")):
                project_types.append("java-with-deps")
            elif os.path.exists(
                str(Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1")
            ):
                project_types.append("java-with-gradle-deps")
            else:
                project_types.append("java")
    if find_files(src_dir, ".bzl", False, True) or find_files(
        src_dir, "BUILD", False, True
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
        or find_files(src_dir, ".cc", False, True)
        or find_files(src_dir, ".h", False, True)
        or find_files(src_dir, ".hpp", False, True)
        or find_files(src_dir, ".hh", False, True)
    ):
        project_types.append("c")
    if find_files(src_dir, ".bc", False, True) or find_files(
        src_dir, ".ll", False, True
    ):
        project_types.append("llvm")
    if is_exe(src_dir):
        project_types.append("binary")
    # Directory contains just a bunch of jar then try jimple
    if not is_java_like:
        if find_files(src_dir, ".jar", False, True):
            if os.getenv("SHIFTLEFT_ACCESS_TOKEN"):
                project_types.append("jar")
            else:
                project_types.append("jimple")
        elif (
            find_files(src_dir, ".apk", False, True)
            or find_files(src_dir, ".zip", False, True)
            or find_files(src_dir, ".dex", False, True)
            or find_files(src_dir, ".class", False, True)
            or find_files(src_dir, ".jimple", False, True)
        ):
            project_types.append("jimple")
    return project_types


def clone_repo(repo_url, clone_dir, depth=1):
    """Method to clone a git repo"""
    if not GIT_AVAILABLE:
        return None
    git.Repo.clone_from(repo_url, clone_dir, depth=depth)
    return clone_dir


def build_maven_download_url(purl):
    """
    Return a maven download URL from the `purl` string.
    """
    url_prefix = MAVEN_CENTRAL_URL

    purl_data = PackageURL.from_string(purl)
    group = purl_data.namespace.replace(".", "/")
    name = purl_data.name
    version = purl_data.version

    if "android" in group:
        url_prefix = ANDROID_MAVEN

    if name and version:
        return f"{url_prefix}{group}/{name}/{version}/{name}-{version}.jar"


def build_pypi_download_url(purl):
    """
    Return a PyPI download URL from the `purl` string.
    """
    url_prefix = "https://pypi.io/packages/source/"
    purl_data = PackageURL.from_string(purl)
    name = purl_data.name
    version = purl_data.version
    if name and version:
        return f"{url_prefix}{name[0]}/{name}/{name}-{version}.tar.gz"


def build_golang_download_url(purl):
    """
    Return a golang download URL from the `purl` string.
    """
    purl_data = PackageURL.from_string(purl)
    namespace = purl_data.namespace
    name = purl_data.name
    version = purl_data.version
    qualifiers = purl_data.qualifiers
    download_url = qualifiers.get("download_url")
    if download_url:
        return download_url
    if not (namespace and name and version):
        return
    version_prefix = qualifiers.get("version_prefix", "v")
    version = f"{version_prefix}{version}"
    return f"https://{namespace}/{name}/archive/refs/tags/{version}.zip"


def build_ghsa_download_url(cve_or_ghsa):
    """Method to get download urls for the packages belonging to the CVE"""
    return ghsa.get_download_urls(cve_or_ghsa=cve_or_ghsa)


def get_download_url(purl_str):
    """Build download urls from a purl or CVE or GHSA id"""
    if purl_str.startswith("GHSA") or purl_str.startswith("CVE"):
        return build_ghsa_download_url(purl_str)
    if purl_str.startswith("pkg:maven"):
        return build_maven_download_url(purl_str)
    if purl_str.startswith("pkg:pypi"):
        return build_pypi_download_url(purl_str)
    if purl_str.startswith("pkg:golang"):
        return build_golang_download_url(purl_str)
    return purl2url.get_download_url(purl_str)


def unzip_unsafe(zf, to_dir):
    """Method to unzip the file in an unsafe manne"""
    with zipfile.ZipFile(zf, "r") as zip_ref:
        zip_ref.extractall(to_dir)
    shutil.rmtree(zf, ignore_errors=True)


def untar_unsafe(tf, to_dir):
    """Method to untar .tar or .tar.gz files in an unsafe manner"""
    if tf.endswith("tar.gz") or tf.endswith(".tgz"):
        tar = tarfile.open(tf, "r:gz")
        tar.extractall(to_dir)
        tar.close()
    elif tf.endswith(".tar"):
        tar = tarfile.open(tf, "r:")
        tar.extractall(to_dir)
        tar.close()
    shutil.rmtree(tf, ignore_errors=True)


def download_package_unsafe(purl_str, download_dir, expand_archive=True):
    """Method to download the package from the given purl or CVE id"""
    if not purl_str:
        return
    durl = get_download_url(purl_str)
    if not durl:
        return
    if isinstance(durl, str):
        durl = [durl]
    for aurl in durl:
        if isinstance(aurl, dict) and aurl.get("purl"):
            aurl = get_download_url(aurl.get("purl"))
        with open(
            os.path.join(download_dir, os.path.basename(aurl)), mode="wb"
        ) as download_file:
            with httpx.stream("GET", aurl, follow_redirects=True) as response:
                total = int(response.headers["Content-Length"])
                with Progress(
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    rich.progress.BarColumn(bar_width=None),
                    rich.progress.DownloadColumn(),
                    rich.progress.TransferSpeedColumn(),
                ) as progress:
                    download_task = progress.add_task("Download", total=total)
                    for chunk in response.iter_bytes():
                        download_file.write(chunk)
                        progress.update(
                            download_task, completed=response.num_bytes_downloaded
                        )
            download_file.close()
            if expand_archive:
                if download_file.name.endswith(".zip"):
                    unzip_unsafe(download_file.name, download_dir)
                elif (
                    download_file.name.endswith(".tar")
                    or download_file.name.endswith(".tar.gz")
                    or download_file.name.endswith(".tgz")
                ):
                    untar_unsafe(download_file.name, download_dir)
    return download_dir


def purl_to_friendly_name(purl_str):
    """Convert package url to a friendly name"""
    purl_data = PackageURL.from_string(purl_str)
    name = purl_data.name
    version = purl_data.version
    return f"{name}-{version}"


def collect_cpg_manifests(cpg_out_dir):
    """Utility method to collect all the CPG manifests created in a directory"""
    cpg_manifests = []
    if os.path.isfile(cpg_out_dir):
        cpg_out_dir = os.path.dirname(cpg_out_dir)
    mfiles = find_files(cpg_out_dir, ".manifest.json") if cpg_out_dir else []
    for amanifest in mfiles:
        with open(amanifest, encoding="utf-8") as mfp:
            manifest_obj = json.load(mfp)
            cpg_manifests.append(manifest_obj)
    return cpg_manifests
