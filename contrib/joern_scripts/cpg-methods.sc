@main def printCpgMethods(payload: String, resultFile: String) : Boolean = {
    importCpg(payload)
    if(!workspace.cpgExists(payload)) {
        printf("[-] Failed to create CPG for %s\n", payload)
        return false
    }
    cpg.method.toJsonPretty |> resultFile
    return true
}
