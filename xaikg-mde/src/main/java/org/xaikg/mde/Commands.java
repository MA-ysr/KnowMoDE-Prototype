package org.xaikg.mde;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.eol.models.IModel;

import com.fasterxml.jackson.databind.node.ObjectNode;

import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

/** The workflow commands: check (C1-C5), t1, t3, t4 and generate (= check + t1 + t3 + t4). */
public final class Commands {

    private Commands() {}

    static final String EVL_FILE = "xaikg.evl";
    static final String T1_FILE = "t1_schema2graph.etl";
    static final String T3_FILE = "t3_graph2ddl.egl";
    static final String T4_FILE = "t4_prompts.egx";

    // ------------------------------------------------------------------------------------------
    // check
    // ------------------------------------------------------------------------------------------
    @Command(name = "check", description = "Evaluate constraints C1-C5 on the M1 models (Phase 2).")
    public static final class Check extends Main.ModelOptions implements Callable<Integer> {

        @Option(names = "--allow-partial", description = "Do not require all five M1 models to be present.")
        boolean allowPartial;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels mm = Metamodels.registerAll(home);
            try (ModelSet ms = ModelSet.load(mm, models)) {
                Map<String, Object> report = new LinkedHashMap<>();
                report.put("command", "check");
                int code = runCheck(home, ms, allowPartial, report);
                Json.print(report);
                return code;
            }
        }
    }

    /** Shared by check and generate. Fills `report`, returns the exit code. */
    static int runCheck(MdeHome home, ModelSet ms, boolean allowPartial, Map<String, Object> report) throws Exception {
        report.put("models", ms.loaded());
        List<String> missing = new ArrayList<>();
        for (String alias : ModelSet.ALIASES.values()) {
            if (!ms.has(alias)) missing.add(alias);
        }
        report.put("missingModels", missing);
        report.put("unresolvedReferences", ms.unresolved());
        if (!missing.isEmpty() && !allowPartial) {
            report.put("status", "error");
            report.put("error", "Missing M1 models: " + missing + " (the constraint layer is evaluated over the combination of all models)");
            return Main.EXIT_MODEL_INVALID;
        }
        if (!ms.unresolved().isEmpty()) {
            report.put("status", "error");
            report.put("error", "Unresolved cross-model references (dangling links violate C5 traceability)");
            return Main.EXIT_MODEL_INVALID;
        }
        Epsilon.EvlResult result = Epsilon.runEvl(home.constraints().resolve(EVL_FILE), ms.epsilonModels());
        report.put("constraintsDefined", result.constraintsDefined());
        report.put("summary", Map.of("errors", result.errors(), "warnings", result.warnings()));
        report.put("violations", result.violations());
        boolean ok = result.errors() == 0;
        report.put("status", ok ? "ok" : "error");
        return ok ? Main.EXIT_OK : Main.EXIT_MODEL_INVALID;
    }

    // ------------------------------------------------------------------------------------------
    // t1
    // ------------------------------------------------------------------------------------------
    @Command(name = "t1", description = "T1: KG Schema model -> graph schema model (M2M).")
    public static final class T1 extends Main.ModelOptions implements Callable<Integer> {

        @Option(names = { "-o", "--out" }, required = true, description = "Output model file (graph-schema.xmi).")
        Path out;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels mm = Metamodels.registerAll(home);
            try (ModelSet ms = ModelSet.load(mm, models)) {
                Map<String, Object> report = new LinkedHashMap<>();
                report.put("command", "t1");
                runT1(home, ms, out, report);
                Json.print(report);
                return Main.EXIT_OK;
            }
        }
    }

    static void runT1(MdeHome home, ModelSet ms, Path out, Map<String, Object> report) throws Exception {
        if (!ms.has("Schema")) throw new IllegalArgumentException("T1 needs the KG Schema model");
        Files.createDirectories(out.toAbsolutePath().getParent());
        Files.deleteIfExists(out);
        EmfModel graph = Epsilon.newOutputModel("Graph", Metamodels.GRAPHSCHEMA_NS, out);
        List<IModel> inputs = new ArrayList<>();
        inputs.add(ms.epsilonModels().stream().filter(m -> m.getName().equals("Schema")).findFirst().orElseThrow());
        inputs.add(graph);
        Epsilon.runEtl(home.transformations().resolve(T1_FILE), inputs);
        graph.store();
        graph.dispose();
        Map<String, Object> counts = new LinkedHashMap<>();
        EmfModel reloaded = Epsilon.loadModel("Graph", Metamodels.GRAPHSCHEMA_NS, out);
        EObject root = reloaded.getResource().getContents().get(0);
        for (String f : List.of("nodeLabels", "relationshipTypes", "constraints", "indexes", "storedQueries")) {
            counts.put(f, ((List<?>) root.eGet(root.eClass().getEStructuralFeature(f))).size());
        }
        reloaded.dispose();
        report.put("status", "ok");
        report.put("output", out.toAbsolutePath().toString());
        report.put("sourceModels", ms.fingerprints());
        report.put("counts", counts);
    }

    // ------------------------------------------------------------------------------------------
    // t3
    // ------------------------------------------------------------------------------------------
    @Command(name = "t3", description = "T3: graph schema model -> Cypher DDL (M2T).")
    public static final class T3 extends Main.HomeOptions implements Callable<Integer> {

        @Option(names = { "-g", "--graph-schema" }, required = true, description = "Input graph-schema.xmi (output of t1).")
        Path graphSchema;

        @Option(names = { "-o", "--out" }, required = true, description = "Output Cypher file (schema.cypher).")
        Path out;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels.registerAll(home);
            Map<String, Object> report = new LinkedHashMap<>();
            report.put("command", "t3");
            runT3(home, graphSchema, out, Map.of("graph-schema.xmi", Hashing.sha256(graphSchema)), report);
            Json.print(report);
            return Main.EXIT_OK;
        }
    }

    static void runT3(MdeHome home, Path graphSchema, Path out, Map<String, String> fingerprints,
                      Map<String, Object> report) throws Exception {
        EmfModel graph = Epsilon.loadModel("Graph", Metamodels.GRAPHSCHEMA_NS, graphSchema);
        String body = Epsilon.runEgl(home.transformations().resolve(T3_FILE), List.of(graph));
        graph.dispose();
        StringBuilder sb = new StringBuilder();
        sb.append("// Generated by xaikg-mde (T1 -> T3). DO NOT EDIT: regenerate from the KG schema model.\n");
        sb.append("// generated-at: ").append(Instant.now()).append('\n');
        for (var e : fingerprints.entrySet()) {
            sb.append("// input: ").append(e.getKey()).append(" sha256=").append(e.getValue()).append('\n');
        }
        sb.append(body);
        Files.createDirectories(out.toAbsolutePath().getParent());
        Files.writeString(out, sb.toString());
        report.put("status", "ok");
        report.put("output", out.toAbsolutePath().toString());
        report.put("statements", body.lines().filter(l -> l.startsWith("CREATE ")).count());
        report.put("inputs", fingerprints);
    }

    // ------------------------------------------------------------------------------------------
    // t4
    // ------------------------------------------------------------------------------------------
    @Command(name = "t4", description = "T4: KG Schema + LLM Pipeline models -> schema-aware prompts (M2T).")
    public static final class T4 extends Main.ModelOptions implements Callable<Integer> {

        @Option(names = { "-o", "--out" }, required = true, description = "Output root (prompts/ is created inside).")
        Path out;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels mm = Metamodels.registerAll(home);
            try (ModelSet ms = ModelSet.load(mm, models)) {
                Map<String, Object> report = new LinkedHashMap<>();
                report.put("command", "t4");
                runT4(home, ms, out, report);
                Json.print(report);
                return Main.EXIT_OK;
            }
        }
    }

    static void runT4(MdeHome home, ModelSet ms, Path outRoot, Map<String, Object> report) throws Exception {
        if (!ms.has("Schema") || !ms.has("Pipeline")) {
            throw new IllegalArgumentException("T4 needs the KG Schema and LLM Pipeline models");
        }
        Path prompts = outRoot.resolve("prompts");
        Files.createDirectories(prompts);
        Epsilon.runEgx(home.transformations().resolve(T4_FILE), ms.epsilonModels(), outRoot);

        // Runtime kernel part of T4: stamp each side-car with the prompt hash and the model fingerprints,
        // and build the prompt registry used for provenance (promptId -> authoring models).
        String generatedAt = Instant.now().toString();
        List<Map<String, Object>> registry = new ArrayList<>();
        try (var files = Files.list(prompts)) {
            for (Path json : (Iterable<Path>) files.filter(p -> p.toString().endsWith(".json") && !p.getFileName().toString().equals("prompt-registry.json")).sorted()::iterator) {
                ObjectNode node = (ObjectNode) Json.MAPPER.readTree(Files.readString(json));
                Path promptFile = prompts.resolve(node.get("promptFile").asText());
                String hash = Hashing.sha256(promptFile);
                String promptId = node.get("task").asText() + "@" + hash.substring(0, 12);
                node.put("promptId", promptId);
                node.put("promptHash", hash);
                node.put("generatedAt", generatedAt);
                node.set("sourceModels", Json.MAPPER.valueToTree(ms.fingerprints()));
                Files.writeString(json, Json.write(node) + System.lineSeparator());
                registry.add(Map.of(
                    "promptId", promptId, "task", node.get("task").asText(), "promptHash", hash,
                    "promptFile", promptFile.getFileName().toString(), "sidecar", json.getFileName().toString(),
                    "llmModel", node.get("llmModel").asText()));
            }
        }
        Json.writeFile(prompts.resolve("prompt-registry.json"),
            Map.of("generatedAt", generatedAt, "sourceModels", ms.fingerprints(), "prompts", registry));
        report.put("status", "ok");
        report.put("output", prompts.toAbsolutePath().toString());
        report.put("prompts", registry);
        report.put("sourceModels", ms.fingerprints());
    }

    // ------------------------------------------------------------------------------------------
    // t2
    // ------------------------------------------------------------------------------------------
    @Command(name = "t2", description = "T2: Validation Policy -> generated validator, applied to the raw extractions -> ValidatedKG (T2a in Phase 3, T2b in Phase 4).")
    public static final class T2 extends Main.ModelOptions implements Callable<Integer> {

        @Option(names = "--raw", required = true, description = "Folder with rawextraction .xmi files (searched recursively).")
        Path raw;

        @Option(names = { "-o", "--out" }, required = true, description = "Output folder (validation.evl, validated-kg.xmi, rejection-report.json).")
        Path out;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels mm = Metamodels.registerAll(home);
            try (ModelSet ms = ModelSet.load(mm, models)) {
                Map<String, Object> report = new LinkedHashMap<>();
                report.put("command", "t2");
                Map<String, Object> check = new LinkedHashMap<>();
                int code = runCheck(home, ms, false, check);
                if (code != Main.EXIT_OK) {
                    report.put("check", check);
                    report.put("status", "error");
                    report.put("error", "Constraint check failed; T2 not invoked");
                    Json.print(report);
                    return code;
                }
                Validation.run(home, ms, raw, out, report);
                Json.print(report);
                return Main.EXIT_OK;
            }
        }
    }

    // ------------------------------------------------------------------------------------------
    // t5
    // ------------------------------------------------------------------------------------------
    @Command(name = "t5", description = "T5: ValidatedKG model -> Cypher loader script (Phase 4).")
    public static final class T5 extends Main.ModelOptions implements Callable<Integer> {

        @Option(names = "--validated", required = true, description = "validated-kg.xmi file or folder (output of t2).")
        Path validated;

        @Option(names = { "-o", "--out" }, required = true, description = "Output Cypher file (load.cypher).")
        Path out;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels mm = Metamodels.registerAll(home);
            try (ModelSet ms = ModelSet.load(mm, models)) {
                Map<String, Object> report = new LinkedHashMap<>();
                report.put("command", "t5");
                Loader.run(home, ms, validated, out, report);
                Json.print(report);
                return Main.EXIT_OK;
            }
        }
    }

    // ------------------------------------------------------------------------------------------
    // t6
    // ------------------------------------------------------------------------------------------
    @Command(name = "t6", description = "T6: Explainability model -> explanation service (router, templates, contract) (Phase 3).")
    public static final class T6 extends Main.ModelOptions implements Callable<Integer> {

        @Option(names = { "-o", "--out" }, required = true, description = "Output folder (generated/service).")
        Path out;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels mm = Metamodels.registerAll(home);
            try (ModelSet ms = ModelSet.load(mm, models)) {
                Map<String, Object> report = new LinkedHashMap<>();
                report.put("command", "t6");
                Map<String, Object> check = new LinkedHashMap<>();
                int code = runCheck(home, ms, false, check);
                if (code != Main.EXIT_OK) {
                    report.put("check", check);
                    report.put("status", "error");
                    report.put("error", "Constraint check failed; T6 not invoked");
                    Json.print(report);
                    return code;
                }
                Service.run(home, ms, out, report);
                Json.print(report);
                return Main.EXIT_OK;
            }
        }
    }

    // ------------------------------------------------------------------------------------------
    // generate = check + t1 + t3 + t4 + t6 (Phases 2 and 3); refuses to generate if check fails
    // ------------------------------------------------------------------------------------------
    @Command(name = "generate", description = "check, then T1, T3, T4 and T6 (stops if a blocking constraint fails).")
    public static final class Generate extends Main.ModelOptions implements Callable<Integer> {

        @Option(names = { "-o", "--out" }, required = true, description = "Output root (generated/).")
        Path out;

        @Override
        public Integer call() throws Exception {
            MdeHome home = home();
            Metamodels mm = Metamodels.registerAll(home);
            try (ModelSet ms = ModelSet.load(mm, models)) {
                Map<String, Object> report = new LinkedHashMap<>();
                report.put("command", "generate");
                Map<String, Object> check = new LinkedHashMap<>();
                int code = runCheck(home, ms, false, check);
                report.put("check", check);
                if (code != Main.EXIT_OK) {
                    report.put("status", "error");
                    report.put("error", "Constraint check failed; transformations not invoked (Phase 2)");
                    Json.print(report);
                    return code;
                }
                Map<String, Object> t1 = new LinkedHashMap<>();
                Path graphSchema = out.resolve("graph-schema.xmi");
                runT1(home, ms, graphSchema, t1);
                report.put("t1", t1);
                Map<String, Object> t3 = new LinkedHashMap<>();
                Map<String, String> fp = new LinkedHashMap<>(ms.fingerprints());
                fp.put("graph-schema.xmi", Hashing.sha256(graphSchema));
                runT3(home, graphSchema, out.resolve("schema.cypher"), fp, t3);
                report.put("t3", t3);
                Map<String, Object> t4 = new LinkedHashMap<>();
                runT4(home, ms, out, t4);
                report.put("t4", t4);
                Map<String, Object> t6 = new LinkedHashMap<>();
                Service.run(home, ms, out.resolve("service"), t6);
                report.put("t6", t6);
                report.put("status", "ok");
                Json.print(report);
                return Main.EXIT_OK;
            }
        }
    }

    static String readOrEmpty(Path p) {
        try { return Files.readString(p); } catch (IOException e) { return ""; }
    }
}
