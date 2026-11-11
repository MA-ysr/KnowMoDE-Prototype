package org.xaikg.mde;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

/** JSON in/out for CLI reports and generated registries. */
public final class Json {

    public static final ObjectMapper MAPPER = new ObjectMapper()
        .enable(SerializationFeature.INDENT_OUTPUT)
        .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS);

    private Json() {}

    public static String write(Object o) {
        try {
            return MAPPER.writeValueAsString(o);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    public static void writeFile(Path file, Object o) throws IOException {
        Files.createDirectories(file.toAbsolutePath().getParent());
        Files.writeString(file, write(o) + System.lineSeparator());
    }

    /** Prints a report to stdout (the contract with the Python pipeline). */
    public static void print(Object report) {
        System.out.println(write(report));
    }
}
