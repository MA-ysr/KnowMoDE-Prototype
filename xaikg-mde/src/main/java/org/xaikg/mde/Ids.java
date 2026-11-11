package org.xaikg.mde;

/** Stable identifiers for facts; exposed to EOL programs as the `ids` variable. */
public final class Ids {

    public String factId(String key) {
        return "f_" + Hashing.sha256(key).substring(0, 16);
    }

    public String sha256(String text) {
        return Hashing.sha256(text);
    }

    /** JSON string literal (double-quoted, escaped). */
    public String json(String text) {
        try {
            return Json.MAPPER.writeValueAsString(text == null ? "" : text);
        } catch (java.io.IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Python string literal (double-quoted, escaped). */
    public String py(String text) {
        return json(text);
    }

    /** lower_snake_case identifier from an UpperCamelCase or free-text name. */
    public String snake(String text) {
        String s = text == null ? "" : text.trim();
        s = s.replaceAll("([a-z0-9])([A-Z])", "$1_$2").replaceAll("[^A-Za-z0-9]+", "_").toLowerCase();
        return s.replaceAll("^_+|_+$", "");
    }

    /** Single-quoted Cypher string literal. */
    public String cypher(String text) {
        String s = text == null ? "" : text;
        s = s.replace("\\", "\\\\").replace("'", "\\'").replace("\r", "").replace("\n", "\\n");
        return "'" + s + "'";
    }

    /** Double-quoted EOL/Java string literal of the given text (one line). */
    public String quote(String text) {
        String s = text == null ? "" : text;
        s = s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\r", " ").replace("\n", " ");
        return "\"" + s + "\"";
    }
}
