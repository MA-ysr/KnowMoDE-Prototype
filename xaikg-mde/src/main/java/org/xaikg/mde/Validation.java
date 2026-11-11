package org.xaikg.mde;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.emc.emf.InMemoryEmfModel;
import org.eclipse.epsilon.eol.models.IModel;
import org.eclipse.epsilon.evl.execute.UnsatisfiedConstraint;

/**
 * T2 "LLM output validation" (paper, Phases 3 and 4: T2a compiles the policy, T2b applies the validator), realised as a higher-order transformation:
 *   1. compile the Validation Policy model into an EVL validator (T2a, EGL),
 *   2. evaluate it on the RawExtraction models,
 *   3. materialise the verdicts into ValidatedKG models (T2b, ETL): accepted facts with full
 *      provenance, rejected items naming the failing rule, per-document statistics.
 */
public final class Validation {

    static final String T2A_FILE = "t2a_policy2evl.egl";
    static final String T2B_FILE = "t2b_raw2validated.etl";

    private Validation() {}

    /** Rule metadata read from the Policy model (name -> type, severity, scope). */
    record Rule(String name, String type, String severity, String scope) {}

    static List<Rule> rules(ModelSet ms) {
        EObject config = ms.resource("Policy").getContents().get(0);
        @SuppressWarnings("unchecked")
        List<EObject> rules = (List<EObject>) config.eGet(config.eClass().getEStructuralFeature("rules"));
        List<Rule> out = new ArrayList<>();
        for (EObject r : rules) {
            out.add(new Rule(str(r, "name"), str(r, "ruleType"), str(r, "severity"), str(r, "scope")));
        }
        return out;
    }

    static String str(EObject o, String feature) {
        Object v = o.eGet(o.eClass().getEStructuralFeature(feature));
        return v == null ? null : String.valueOf(v);
    }

    /** Loads every rawextraction .xmi under `rawDir` (recursively) into one expanded Epsilon model. */
    static InMemoryEmfModel loadRaw(Metamodels mm, Path rawDir, List<Path> filesOut) throws Exception {
        ResourceSet rs = new ResourceSetImpl();
        Resource first = null;
        try (var walk = Files.walk(rawDir)) {
            for (Path p : (Iterable<Path>) walk.filter(f -> f.toString().endsWith(".xmi")).sorted()::iterator) {
                Resource r = rs.getResource(URI.createFileURI(p.toAbsolutePath().toString()), true);
                if (first == null) first = r;
                filesOut.add(p);
            }
        }
        if (first == null) {
            throw new IllegalArgumentException("No raw extraction .xmi files under " + rawDir);
        }
        InMemoryEmfModel raw = new InMemoryEmfModel("Raw", first, List.of(mm.byNsUri(Metamodels.RAW_NS)));
        raw.setExpand(true);
        return raw;
    }

    public static void run(MdeHome home, ModelSet ms, Path rawDir, Path outDir, Map<String, Object> report) throws Exception {
        if (!ms.has("Schema") || !ms.has("Policy")) {
            throw new IllegalArgumentException("T2 needs the KG Schema and Validation Policy models");
        }
        Files.createDirectories(outDir);
        String policyVersion = ms.loaded().stream().filter(l -> l.alias().equals("Policy")).findFirst().orElseThrow().sha256();
        IModel schema = model(ms, "Schema");
        IModel policy = model(ms, "Policy");

        // --- T2a: compile the policy into an EVL validator ------------------------------------
        String evl = Epsilon.runEgl(home.transformations().resolve(T2A_FILE), List.of(policy, schema), Map.of("ids", new Ids()));
        Path evlFile = outDir.resolve("validation.evl");
        Files.writeString(evlFile, "// input: validation-policy.xmi sha256=" + policyVersion + "\n// generated-at: " + Instant.now() + "\n" + evl);
        List<Rule> rules = rules(ms);
        report.put("validator", Map.of("file", evlFile.toAbsolutePath().toString(), "rules", rules.size(),
            "policyVersion", policyVersion));

        // --- evaluate the generated validator on the raw extractions -------------------------
        List<Path> rawFiles = new ArrayList<>();
        InMemoryEmfModel raw = loadRaw(ms.metamodels(), rawDir, rawFiles);
        Epsilon.EvlRun run = Epsilon.evaluate(evlFile, List.of(raw, schema, policy));
        Map<EObject, Map<String, String>> failures = new HashMap<>();
        for (UnsatisfiedConstraint uc : run.unsatisfied()) {
            if (uc.getInstance() instanceof EObject eo) {
                failures.computeIfAbsent(eo, k -> new LinkedHashMap<>()).put(uc.getConstraint().getName(), uc.getMessage());
            }
        }
        // verdict per raw item: [ruleName, ruleType, severity, passed, message] for every applicable rule
        Map<EObject, List<List<Object>>> verdicts = new HashMap<>();
        Map<String, int[]> perRule = new TreeMap<>();
        int entities = 0, relations = 0;
        var it = raw.getResource().getResourceSet().getAllContents();
        while (it.hasNext()) {
            Object o = it.next();
            if (!(o instanceof EObject eo)) continue;
            String kind = eo.eClass().getName();
            String scope = kind.equals("RawEntity") ? "ENTITY" : kind.equals("RawRelation") ? "RELATION" : null;
            if (scope == null) continue;
            if (scope.equals("ENTITY")) entities++; else relations++;
            Map<String, String> failed = failures.getOrDefault(eo, Map.of());
            List<List<Object>> vs = new ArrayList<>();
            for (Rule r : rules) {
                if (!r.scope().equals(scope)) continue;
                boolean passed = !failed.containsKey(r.name());
                int[] c = perRule.computeIfAbsent(r.name(), k -> new int[2]);
                c[0]++;
                if (!passed) c[1]++;
                vs.add(List.of(r.name(), r.type(), r.severity(), passed, passed ? "" : failed.get(r.name())));
            }
            verdicts.put(eo, vs);
        }

        // --- T2b: materialise verdicts into ValidatedKG models --------------------------------
        Path vkgFile = outDir.resolve("validated-kg.xmi");
        Files.deleteIfExists(vkgFile);
        EmfModel vkg = Epsilon.newOutputModel("VKG", Metamodels.VALIDATED_NS, vkgFile);
        Map<String, Object> vars = new LinkedHashMap<>();
        vars.put("verdicts", verdicts);
        vars.put("policyVersion", policyVersion);
        vars.put("validatedAt", Instant.now().toString());
        vars.put("ids", new Ids());
        Epsilon.runEtl(home.transformations().resolve(T2B_FILE), List.of(raw, schema, policy, vkg), vars);
        vkg.store();
        vkg.dispose();
        raw.dispose();

        // --- reports --------------------------------------------------------------------------
        Map<String, Object> ruleStats = new LinkedHashMap<>();
        for (var e : perRule.entrySet()) {
            ruleStats.put(e.getKey(), Map.of("evaluated", e.getValue()[0], "failed", e.getValue()[1]));
        }
        List<Map<String, Object>> rejected = new ArrayList<>();
        int validEntities = 0, validRelations = 0;
        EmfModel reloaded = Epsilon.loadModel("VKG", Metamodels.VALIDATED_NS, vkgFile);
        for (EObject root : reloaded.getResource().getContents()) {
            validEntities += ((List<?>) root.eGet(root.eClass().getEStructuralFeature("validEntities"))).size();
            validRelations += ((List<?>) root.eGet(root.eClass().getEStructuralFeature("validRelations"))).size();
            @SuppressWarnings("unchecked")
            List<EObject> rej = (List<EObject>) root.eGet(root.eClass().getEStructuralFeature("rejected"));
            for (EObject r : rej) {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("document", str(root, "sourceDocument"));
                for (String f : List.of("kind", "originalType", "originalId", "mention", "confidence", "failedRule", "ruleType", "rejectionReason")) {
                    m.put(f, str(r, f));
                }
                rejected.add(m);
            }
        }
        reloaded.dispose();
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("documents", rawFiles.size());
        summary.put("rawEntities", entities);
        summary.put("rawRelations", relations);
        summary.put("validEntities", validEntities);
        summary.put("validRelations", validRelations);
        summary.put("rejected", rejected.size());
        summary.put("acceptanceRate", (entities + relations) == 0 ? 1.0
            : Math.round(1000.0 * (validEntities + validRelations) / (entities + relations)) / 1000.0);
        Json.writeFile(outDir.resolve("rejection-report.json"), Map.of(
            "policyVersion", policyVersion, "summary", summary, "perRule", ruleStats, "rejected", rejected));
        report.put("status", "ok");
        report.put("output", vkgFile.toAbsolutePath().toString());
        report.put("rejectionReport", outDir.resolve("rejection-report.json").toAbsolutePath().toString());
        report.put("summary", summary);
        report.put("perRule", ruleStats);
        report.put("sourceModels", ms.fingerprints());
    }

    static IModel model(ModelSet ms, String alias) {
        return ms.epsilonModels().stream().filter(m -> m.getName().equals(alias)).findFirst().orElseThrow();
    }
}
