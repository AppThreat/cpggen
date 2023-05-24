# CPG Generator

```
 ██████╗██████╗  ██████╗
██╔════╝██╔══██╗██╔════╝
██║     ██████╔╝██║  ███╗
██║     ██╔═══╝ ██║   ██║
╚██████╗██║     ╚██████╔╝
 ╚═════╝╚═╝      ╚═════╝
```

CPG Generator is a python cli tool to generate [Code Property Graph](https://cpg.joern.io) for multiple languages. The generated CPG can be directly imported to [Joern](https://joern.io) or uploaded to [Qwiet.AI](https://docs.shiftleft.io/home) for analysis.

[![release](https://github.com/appthreat/cpggen/actions/workflows/pythonpublish.yml/badge.svg)](https://github.com/appthreat/cpggen/actions/workflows/pythonpublish.yml)
[![Downloads](https://static.pepy.tech/badge/cpggen)](https://pepy.tech/project/cpggen)
[![Discord](https://img.shields.io/badge/-Discord-lime?style=for-the-badge&logo=discord&logoColor=white&color=black)](https://discord.gg/tmmtjCEHNV)

## Pre-requisites

- JDK 11 or above
- Python 3.10
- Docker or podman (Windows, Linux or Mac) or
- [Atom](https://github.com/AppThreat/atom#installation) or [Joern](https://docs.joern.io/installation)

## Installation

cpggen is available as a single executable binary, [PyPI package](https://pypi.org/project/cpggen/) or as a [container image](https://github.com/AppThreat/cpggen/pkgs/container/cpggen).

### Single executable binaries

Download the executable binary for your operating system from the [releases page](https://github.com/appthreat/cpggen/releases). These binary bundle the following:

- Joern with all the CPG frontends
- cpggen with Python 3.10
- cdxgen with Node.js 18 - Generates SBoM

```bash
curl -LO https://github.com/AppThreat/cpggen/releases/latest/download/cpggen-linux-amd64
chmod +x cpggen-linux-amd64
./cpggen-linux-amd64 --help
```

OSS version without any Qwiet.AI binary frontends.

```bash
curl -LO https://github.com/AppThreat/cpggen/releases/latest/download/cpggen-oss-linux-amd64
chmod +x cpggen-oss-linux-amd64
./cpggen-oss-linux-amd64 --help
```

On Windows,

```powershell
curl -LO https://github.com/appthreat/cpggen/releases/latest/download/cpggen.exe
.\cpggen.exe --help
```

NOTE: On Windows, antivirus and antimalware could prevent this single executable from functioning properly. Depending on the system, administrative privileges might also be required. Use container-based execution as a fallback.

### OCI Artifacts via ORAS cli

Use [ORAS cli](https://oras.land/docs/cli/installation/) to download the cpggen binary on Linux and Windows.

```bash
VERSION="1.0.0"
curl -LO "https://github.com/oras-project/oras/releases/download/v${VERSION}/oras_${VERSION}_linux_amd64.tar.gz"
mkdir -p oras-install/
tar -zxf oras_${VERSION}_*.tar.gz -C oras-install/
sudo mv oras-install/oras /usr/local/bin/
rm -rf oras_${VERSION}_*.tar.gz oras-install/
```

```bash
oras pull ghcr.io/appthreat/cpggen-bin:v1
chmod +x cpggen-linux-amd64
./cpggen-linux-amd64 --help
```

On Windows

```powershell
set VERSION="1.0.0"
curl.exe -sLO  "https://github.com/oras-project/oras/releases/download/v%VERSION%/oras_%VERSION%_windows_amd64.zip"
tar.exe -xvzf oras_%VERSION%_windows_amd64.zip
mkdir -p %USERPROFILE%\bin\
copy oras.exe %USERPROFILE%\bin\
set PATH=%USERPROFILE%\bin\;%PATH%
```

```powershell
Invoke-WebRequest -Uri https://github.com/oras-project/oras/releases/download/v1.0.0/oras_1.0.0_windows_amd64.zip -UseBasicParsing -OutFile oras_1.0.0_windows_amd64.zip
Expand-Archive -Path oras_1.0.0_windows_amd64.zip -DestinationPath .
oras.exe pull ghcr.io/appthreat/cpggen-windows-bin:v1
```

### PyPI package

This would install the python cli tool with bundled [atom](https://github.com/AppThreat/atom) distribution.

```
pip install cpggen
```

With atom, CPG can be generated for the following languages:

- C/C++
- Java
- Jars
- JavaScript/TypeScript

Install joern and set the `JOERN_HOME` environment variable if you would like support for additional languages.

### Bundled container image

```
docker pull ghcr.io/appthreat/cpggen
# podman pull ghcr.io/appthreat/cpggen
```

Almalinux 9 requires the CPU to support SSE4.2. For kvm64 VM use the Almalinux 8 version instead.

```
docker pull ghcr.io/appthreat/cpggen-alma8
# podman pull ghcr.io/appthreat/cpggen-alma8
```

Or use the nightly to always get the latest joern and tools.

```
docker pull ghcr.io/appthreat/cpggen:nightly
# podman pull ghcr.io/appthreat/cpggen:nightly
```

To use the container image with only open-source CPG frontends without any Qwiet.AI support.

```
docker pull ghcr.io/appthreat/cpggen-oss
# podman pull ghcr.io/appthreat/cpggen-oss
```

## Usage

To auto detect the language from the current directory and generate CPG.

```
cpggen
```

To specify input and output directory.

```
cpggen -i <src directory> -o <CPG directory or file name>
```

You can even pass a git or a package url or CVE id as source

```
cpggen -i https://github.com/HooliCorp/vulnerable-aws-koa-app -o /tmp/cpg
```

```
cpggen -i "pkg:maven/org.apache.commons/commons-io@1.3.2" -o /tmp/cpg
```

```
export GITHUB_TOKEN=<token with read:packages scope>
cpggen -i CVE-2023-32681 -o /tmp/cpg

cpggen -i GHSA-j8r2-6x86-q33q -o /tmp/cpg
```

To specify language type.

```
cpggen -i <src directory> -o <CPG directory or file name> -l java

# Comma separated values are accepted for multiple languages
cpggen -i <src directory> -o <CPG directory or file name> -l java,js,python
```

Container based invocation

```
docker run --rm -it -v /tmp:/tmp -v $(pwd):/app:rw --cpus=4 --memory=16g -t ghcr.io/appthreat/cpggen cpggen -i <src directory> -o <CPG directory or file name>
```

### Export graphs

By passing `--export`, cpggen can export the various graphs to many formats using [joern-export](https://docs.joern.io/exporting/)

Example to export `cpg14` graphs in `dot` format

```bash
cpggen -i ~/work/sandbox/crAPI -o ~/work/sandbox/crAPI/cpg_out --build --export --export-out-dir ~/work/sandbox/crAPI/cpg_export
```

To export `cpg` in `neo4jcsv` format

```bash
cpggen -i ~/work/sandbox/crAPI -o ~/work/sandbox/crAPI/cpg_out --build --export --export-out-dir ~/work/sandbox/crAPI/cpg_export --export-repr cpg --export-format neo4jcsv
```

### Slicing graphs

Pass `--slice` argument to extract intra-procedural slices from the CPG. By default, slices would be based on `Usages`. Pass `--slice-mode DataFlow` to create a sliced CPG based on `DataFlow`.

```bash
cpggen -i ~/work/sandbox/crAPI -o ~/work/sandbox/crAPI/cpg_out --slice
```

### Creating vectors

Pass `--vectors` argument to extract vector representations of code from CPG in json format.

```bash
cpggen -i ~/work/sandbox/crAPI -o ~/work/sandbox/crAPI/cpg_out --vectors
```

### Artifacts produced

Upon successful completion, cpggen would produce the following artifacts in the directory specified under `out_dir`

- {name}-{lang}-cpg.bin.zip - Code Property Graph for the given language type
- {name}-{lang}-cpg.bom.xml - SBoM in CycloneDX XML format
- {name}-{lang}-cpg.bom.json - SBoM in CycloneDX json format
- {name}-{lang}-cpg.manifest.json - A json file listing the generated artifacts and the invocation commands

## Server mode

cpggen can run in server mode.

```
cpggen --server
```

You can invoke the endpoint `/cpg` to generate CPG from a path, http or package url. Parameters can be passed using GET or POST request.

```
curl "http://127.0.0.1:7072/cpg?src=/Volumes/Work/sandbox/vulnerable-aws-koa-app&out_dir=/tmp/cpg_out&lang=js"
```

```
curl "http://127.0.0.1:7072/cpg?url=https://github.com/HooliCorp/vulnerable-aws-koa-app&out_dir=/tmp/cpg_out&lang=js"
```

Package url with slicing.

```
curl "http://127.0.0.1:7072/cpg?url=pkg:maven/org.apache.commons/commons-io@1.3.2&out_dir=/tmp/cpg_out&slice=true"
```

## Languages supported

| Language    | Requires build | Maturity |
| ----------- | -------------- | -------- |
| C           | No             | High     |
| C++         | No             | High     |
| Java        | No (\*)        | Medium   |
| Scala       | Yes            | High     |
| Jsp         | Yes            | High     |
| Jar/War     | No             | High     |
| JavaScript  | No             | Medium   |
| TypeScript  | No             | Medium   |
| Kotlin      | No (\*)        | Low      |
| Php         | No             | Low      |
| Python      | No             | Low      |
| C# / dotnet | Yes            | High     |
| Go          | Yes            | High     |

(\*) - Precision could be improved with dependencies

## Full list of options

```
cpggen --help
usage: cpggen [-h] [-i SRC] [-o CPG_OUT_DIR] [-l LANGUAGE] [--use-container] [--build] [--joern-home JOERN_HOME] [--server] [--server-host SERVER_HOST] [--server-port SERVER_PORT] [--export]
              [--export-repr {ast,cfg,cdg,ddg,pdg,cpg,cpg14,all}] [--export-format {neo4jcsv,graphml,graphson,dot}] [--export-out-dir EXPORT_OUT_DIR] [--verbose] [--skip-sbom] [--slice] [--slice-mode {Usages,DataFlow}] [--use-parse]

CPG Generator

optional arguments:
  -h, --help            show this help message and exit
  -i SRC, --src SRC     Source directory or url or CVE or GHSA id
  -o CPG_OUT_DIR, --out-dir CPG_OUT_DIR
                        CPG output directory
  -l LANGUAGE, --lang LANGUAGE
                        Optional. CPG language frontend to use. Auto-detects by default.
  --use-container       Use cpggen docker image
  --build               Attempt to build the project automatically
  --joern-home JOERN_HOME
                        Joern installation directory
  --server              Run cpggen as a server
  --server-host SERVER_HOST
                        cpggen server host
  --server-port SERVER_PORT
                        cpggen server port
  --export              Export CPG as a graph
  --export-repr {ast,cfg,cdg,ddg,pdg,cpg,cpg14,all}
                        Graph representation to export
  --export-format {neo4jcsv,graphml,graphson,dot}
                        Export format
  --export-out-dir EXPORT_OUT_DIR
                        Export output directory
  --verbose             Run cpggen in verbose mode
  --skip-sbom           Do not generate SBoM
  --slice               Extract intra-procedural slices from the CPG
  --slice-mode {Usages,DataFlow}
                        Mode used for CPG slicing
  --use-atom            Use atom toolkit
  --vectors             Extract vector representations of code from CPG
```

## Environment variables

| Name                    | Purpose                                                                    |
| ----------------------- | -------------------------------------------------------------------------- |
| JOERN_HOME              | Joern installation directory                                               |
| CPGGEN_HOST             | cpggen server host. Default 127.0.0.1                                      |
| CPGGEN_PORT             | cpggen server port. Default 7072                                           |
| CPGGEN_CONTAINER_CPU    | CPU units to use in container execution mode. Default computed             |
| CPGGEN_CONTAINER_MEMORY | Memory units to use in container execution mode. Default computed          |
| CPGGEN_MEMORY           | Heap memory to use for frontends. Default computed                         |
| AT_DEBUG_MODE           | Set to debug to enable debug logging                                       |
| CPG_EXPORT              | Set to true to export CPG graphs in dot format                             |
| CPG_EXPORT_REPR         | Graph to export. Default all                                               |
| CPG_EXPORT_FORMAT       | Export format. Default dot                                                 |
| CPG_SLICE               | Set to true to slice CPG                                                   |
| CPG_SLICE_MODE          | Slice mode. Default Usages                                                 |
| CPG_VECTORS             | Set to true to generate vector representations of code from CPG            |
| SHIFTLEFT_ACCESS_TOKEN  | Set to automatically submit the CPG for analysis by Qwiet AI               |
| CDXGEN_ARGS             | Extra arguments to pass to cdxgen                                          |
| ENABLE_SBOM             | Enable SBoM generation using cdxgen                                        |
| JIMPLE_ANDROID_JAR      | Path to android.jar for use with jimple for .apk or .dex to CPG conversion |
| GITHUB_TOKEN            | Token with read:packages scope to analyze CVE or GitHub Advisory           |
| USE_ATOM                | Use AppThreat atom instead of joern frontends                              |

## GitHub actions

Use the marketplace [action](https://github.com/marketplace/actions/cpggen) to generate CPGs using GitHub actions. Optionally, the upload the generated CPGs as build artifacts use the below step.

```
- name: Upload cpg
  uses: actions/upload-artifact@v1.0.0
  with:
    name: cpg
    path: cpg_out
```

## License

Apache-2.0

## Developing / Contributing

```
git clone git@github.com:AppThreat/cpggen.git
cd cpggen

python -m pip install --upgrade pip
python -m pip install poetry
# Add poetry to the PATH environment variable
poetry install

poetry run cpggen -i <src directory>
```
