#include <stdio.h>
#include <string.h>

static int path_is_absolute(const char *path) {
#ifdef _WIN32
    return (path[0] != '\0' && path[1] == ':' && (path[2] == '\\' || path[2] == '/'))
        || (path[0] == '\\' && path[1] == '\\');
#else
    return path[0] == '/';
#endif
}

int main(int argc, char **argv) {
    const char *sarif_path = NULL;
    FILE *sarif_file;
    int index;

    if (!path_is_absolute(argv[0])) {
        return 67;
    }
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts("Verilator 5.040-native-fake");
        return 0;
    }
    for (index = 1; index + 1 < argc; ++index) {
        if (strcmp(argv[index], "--diagnostics-sarif-output") == 0) {
            sarif_path = argv[index + 1];
            break;
        }
    }
    if (sarif_path == NULL) {
        return 64;
    }
    sarif_file = fopen(sarif_path, "wb");
    if (sarif_file == NULL) {
        return 66;
    }
    fputs(
        "{\"version\":\"2.1.0\",\"runs\":[{\"tool\":{\"driver\":{"
        "\"name\":\"Verilator\",\"version\":\"5.040-native-fake\"}},"
        "\"results\":[{\"ruleId\":\"WIDTH\",\"level\":\"warning\","
        "\"message\":{\"text\":\"native wrapper invoked\"},\"locations\":[{"
        "\"physicalLocation\":{\"artifactLocation\":{\"uri\":\"rtl/top.sv\"},"
        "\"region\":{\"startLine\":1,\"startColumn\":1}}}]}]}]}",
        sarif_file
    );
    fclose(sarif_file);
    return 0;
}
