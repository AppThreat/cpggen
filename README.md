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

## Environment variables

| Name                    | Purpose                                                      |
| ----------------------- | ------------------------------------------------------------ |
| JOERN_HOME              | Joern installation directory                                 |
| CPGGEN_HOST             | cpggen server host. Default 127.0.0.1                        |
| CPGGEN_PORT             | cpggen server port. Default 7072                             |
| CPGGEN_CONTAINER_CPU    | CPU units to use in container execution mode. Default 2      |
| CPGGEN_CONTAINER_MEMORY | Memory units to use in container execution mode. Default 32g |
| CPGGEN_MEMORY           | Heap memory to use for frontends. Default 32G                |
| AT_DEBUG_MODE           | Set to debug to enable debug logging                         |
