@main def printCpgMethods(payload: String, projectName: String, resultFile: String) : Boolean = {
    workspace.reset
    importCpg(payload, projectName)
    cpg.method.toJsonPretty |> resultFile
    return true
}
