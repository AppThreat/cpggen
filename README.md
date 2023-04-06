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
```

Container based invocation

```
docker run --rm -it -v /tmp:/tmp -v $(pwd):/app:rw --cpus=4 --memory=16g -t ghcr.io/appthreat/cpggen cpggen -i <src directory> -o <CPG directory or file name>
```

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
