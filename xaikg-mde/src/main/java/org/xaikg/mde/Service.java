package org.xaikg.mde;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** T6: Explainability (+ Schema, Decision) models -> explanation service artefacts (paper, Phase 3). */
public final class Service {

    static final String T6_FILE = "t6_service.egx";

    private Service() {}

    public static void run(MdeHome home, ModelSet ms, Path outRoot, Map<String, Object> report) throws Exception {
        for (String alias : List.of("Schema", "Explainability", "Decision")) {
            if (!ms.has(alias)) throw new IllegalArgumentException("T6 needs the " + alias + " model");
        }
        Files.createDirectories(outRoot.resolve("templates"));
        Epsilon.runEgx(home.transformations().resolve(T6_FILE), ms.epsilonModels(), outRoot, Map.of("ids", new Ids()));
        Map<String, Object> manifest = new LinkedHashMap<>();
        manifest.put("generatedAt", Instant.now().toString());
        manifest.put("sourceModels", ms.fingerprints());
        List<String> files;
        try (var walk = Files.walk(outRoot)) {
            files = walk.filter(Files::isRegularFile).map(p -> outRoot.relativize(p).toString()).sorted().toList();
        }
        manifest.put("files", files);
        Json.writeFile(outRoot.resolve("generation-manifest.json"), manifest);
        report.put("status", "ok");
        report.put("output", outRoot.toAbsolutePath().toString());
        report.put("files", files);
        report.put("sourceModels", ms.fingerprints());
    }
}
