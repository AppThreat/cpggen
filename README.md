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

## Pre-requisites

- JDK 11 or above
- Python 3.10
- Docker or podman (Windows, Linux or Mac) or
- Joern [natively installed](https://docs.joern.io/installation) (Linux only)

## Installation

cpggen is available as a [PyPI package](https://pypi.org/project/cpggen/) or as a [container image](https://github.com/AppThreat/cpggen/pkgs/container/cpggen).

```
pip install cpggen
```

Bundled container image

```
docker pull ghcr.io/appthreat/cpggen
# podman pull ghcr.io/appthreat/cpggen
```

Or use the nightly to always get the latest joern and tools.

```
docker pull ghcr.io/appthreat/cpggen:nightly
# podman pull ghcr.io/appthreat/cpggen:nightly
```

### Single executable binaries

Download the executable binary for your operating system from the [releases page](https://github.com/appthreat/cpggen/releases). These binary bundle the following:

- cpggen with Python 3.10
- cdxgen with Node.js 18
- cdxgen binary plugins

```bash
curl -LO https://github.com/AppThreat/cpggen/releases/download/v0.8.1/cpggen-linux-amd64
chmod +x cpggen-linux-amd64
./cpggen-linux-amd64 --help
```

On Windows,

```powershell
curl -LO https://github.com/appthreat/cpggen/releases/download/v0.8.1/cpggen.exe
.\cpggen.exe --help
```

### OCI Artifacts via ORAS cli

Use [ORAS cli](https://oras.land/cli/) to download the cpggen binary with Python and Node.js preinstalled.

```bash
oras pull ghcr.io/appthreat/cpggen-bin:v1
chmod +x cpggen-linux-amd64
./cpggen-linux-amd64 --help
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

You can even pass a git url as source

```
cpggen -i https://github.com/HooliCorp/vulnerable-aws-koa-app -o /tmp/cpg
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

Example to export `all` graphs in `dot` format

```bash
cpggen -i ~/work/sandbox/crAPI -o ~/work/sandbox/crAPI/cpg_out --build --export --export-out-dir ~/work/sandbox/crAPI/export_out
```

To export `pdg` in `neo4jcsv` format

```bash
cpggen -i ~/work/sandbox/crAPI -o ~/work/sandbox/crAPI/cpg_out --build --export --export-out-dir ~/work/sandbox/crAPI/export_out --export-repr pdg --export-format neo4jcsv
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

You can invoke the endpoint `/cpg` to generate CPG.

```
curl "http://127.0.0.1:7072/cpg?src=/Volumes/Work/sandbox/vulnerable-aws-koa-app&out_dir=/tmp/cpg_out&lang=js"
```

```
curl "http://127.0.0.1:7072/cpg?url=https://github.com/HooliCorp/vulnerable-aws-koa-app&out_dir=/tmp/cpg_out&lang=js"
```

## Languages supported

| Language    | Requires build |
| ----------- | -------------- |
| C           | No             |
| C++         | No             |
| Java        | No (\*)        |
| Scala       | Yes            |
| Jsp         | Yes            |
| Jar/War     | No             |
| JavaScript  | No             |
| TypeScript  | No             |
| Kotlin      | No (\*)        |
| Php         | No             |
| Python      | No             |
| C# / dotnet | Yes            |
| Go          | Yes            |

(\*) - Precision could be improved with dependencies

## Environment variables

| Name                    | Purpose                                                           |
| ----------------------- | ----------------------------------------------------------------- |
| JOERN_HOME              | Joern installation directory                                      |
| CPGGEN_HOST             | cpggen server host. Default 127.0.0.1                             |
| CPGGEN_PORT             | cpggen server port. Default 7072                                  |
| CPGGEN_CONTAINER_CPU    | CPU units to use in container execution mode. Default computed    |
| CPGGEN_CONTAINER_MEMORY | Memory units to use in container execution mode. Default computed |
| CPGGEN_MEMORY           | Heap memory to use for frontends. Default computed                |
| AT_DEBUG_MODE           | Set to debug to enable debug logging                              |
| CPG_EXPORT              | Set to true to export CPG graphs in dot format                    |
| CPG_EXPORT_REPR         | Graph to export. Default all                                      |
| CPG_EXPORT_FORMAT       | Export format. Default dot                                        |
| SHIFTLEFT_ACCESS_TOKEN  | Set to automatically submit the CPG for analysis by Qwiet AI      |

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
