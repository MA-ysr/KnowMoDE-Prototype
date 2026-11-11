package org.xaikg.mde;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EAttribute;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.InternalEObject;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.util.EcoreUtil;
import org.eclipse.epsilon.emc.emf.InMemoryEmfModel;
import org.eclipse.epsilon.eol.models.IModel;

/**
 * The four (+1) interrelated M1 models of one use case, loaded into ONE ResourceSet so that
 * cross-file references (e.g. PromptTemplate.targetConcepts -> kg-schema.xmi#Drug) resolve to the
 * very same objects the Schema model exposes. Each file is exposed to Epsilon under a fixed alias
 * derived from its root element type.
 */
public final class ModelSet implements AutoCloseable {

    /** Root EClass name -> Epsilon model alias. */
    public static final Map<String, String> ALIASES = Map.of(
        "KGSchemaDefinition", "Schema",
        "LLMPipelineConfig", "Pipeline",
        "ValidationConfig", "Policy",
        "ExplainabilityConfig", "Explainability",
        "DecisionBindingConfig", "Decision");

    public record LoadedModel(String alias, Path file, String rootType, String sha256) {}
    public record UnresolvedReference(String model, String element, String feature, String proxyUri) {}

    private final ResourceSet resourceSet = new ResourceSetImpl();
    private final Map<String, Resource> byAlias = new LinkedHashMap<>();
    private final List<LoadedModel> loaded = new ArrayList<>();
    private final List<UnresolvedReference> unresolved = new ArrayList<>();
    private final List<IModel> epsilonModels = new ArrayList<>();
    private final Metamodels metamodels;

    private ModelSet(Metamodels metamodels) {
        this.metamodels = metamodels;
    }

    /** Loads every *.xmi in the given files/directories. */
    public static ModelSet load(Metamodels metamodels, List<Path> inputs) throws IOException {
        ModelSet ms = new ModelSet(metamodels);
        List<Path> files = new ArrayList<>();
        for (Path in : inputs) {
            if (Files.isDirectory(in)) {
                try (var s = Files.list(in)) {
                    s.filter(p -> p.toString().endsWith(".xmi")).sorted().forEach(files::add);
                }
            } else if (Files.isRegularFile(in)) {
                files.add(in);
            } else {
                throw new IOException("Model path not found: " + in);
            }
        }
        if (files.isEmpty()) {
            throw new IOException("No .xmi model files found in " + inputs);
        }
        for (Path f : files) {
            Resource r = ms.resourceSet.getResource(URI.createFileURI(f.toAbsolutePath().toString()), true);
            if (r.getContents().isEmpty()) {
                throw new IOException("Empty model: " + f);
            }
            EObject root = r.getContents().get(0);
            String rootType = root.eClass().getName();
            String alias = ALIASES.getOrDefault(rootType, rootType);
            // A second file with the same root type (e.g. a stray alternative schema) is loaded under a
            // numbered alias so that the constraint layer, not the loader, reports the inconsistency.
            for (int n = 2; ms.byAlias.containsKey(alias); n++) {
                alias = ALIASES.getOrDefault(rootType, rootType) + "_" + n;
            }
            ms.byAlias.put(alias, r);
            ms.loaded.add(new LoadedModel(alias, f, rootType, Hashing.sha256(f)));
        }
        EcoreUtil.resolveAll(ms.resourceSet);
        ms.collectUnresolved();
        for (var e : ms.byAlias.entrySet()) {
            InMemoryEmfModel m = new InMemoryEmfModel(e.getKey(), e.getValue(), metamodels.xaikgPackages());
            m.setExpand(false); // alias covers exactly its own file
            ms.epsilonModels.add(m);
        }
        return ms;
    }

    private void collectUnresolved() {
        for (var e : byAlias.entrySet()) {
            var it = e.getValue().getAllContents();
            while (it.hasNext()) {
                EObject o = it.next();
                for (var ref : o.eClass().getEAllReferences()) {
                    if (ref.isContainment() || ref.isDerived() || !o.eIsSet(ref)) continue;
                    Object v = o.eGet(ref, false);
                    if (v instanceof List<?> list) {
                        for (Object x : list) checkProxy(e.getKey(), o, ref.getName(), x);
                    } else {
                        checkProxy(e.getKey(), o, ref.getName(), v);
                    }
                }
            }
        }
    }

    private void checkProxy(String model, EObject owner, String feature, Object value) {
        if (value instanceof InternalEObject ieo && ieo.eIsProxy()) {
            unresolved.add(new UnresolvedReference(model, describe(owner), feature, String.valueOf(ieo.eProxyURI())));
        }
    }

    /** Human-readable identity of a model element: Type[idOrName]. */
    public static String describe(EObject o) {
        if (o == null) return "null";
        String id = null;
        EAttribute idAttr = o.eClass().getEIDAttribute();
        if (idAttr != null && o.eGet(idAttr) != null) {
            id = String.valueOf(o.eGet(idAttr));
        } else {
            var nameFeature = o.eClass().getEStructuralFeature("name");
            if (nameFeature == null) nameFeature = o.eClass().getEStructuralFeature("role");
            if (nameFeature == null) nameFeature = o.eClass().getEStructuralFeature("featureName");
            if (nameFeature != null && o.eGet(nameFeature) != null) {
                id = String.valueOf(o.eGet(nameFeature));
            }
        }
        if (id == null && o.eContainer() != null) {
            return o.eClass().getName() + " in " + describe(o.eContainer());
        }
        return o.eClass().getName() + "[" + (id == null ? "?" : id) + "]";
    }

    public List<IModel> epsilonModels() { return epsilonModels; }
    public List<LoadedModel> loaded() { return loaded; }
    public List<UnresolvedReference> unresolved() { return unresolved; }
    public ResourceSet resourceSet() { return resourceSet; }
    public Metamodels metamodels() { return metamodels; }

    public Resource resource(String alias) { return byAlias.get(alias); }

    public boolean has(String alias) { return byAlias.containsKey(alias); }

    /** alias -> file sha256, sorted, for stamping generated artefacts. */
    public Map<String, String> fingerprints() {
        Map<String, String> m = new TreeMap<>();
        for (LoadedModel lm : loaded) m.put(lm.alias() + ":" + lm.file().getFileName(), lm.sha256());
        return m;
    }

    @Override
    public void close() {
        for (IModel m : epsilonModels) {
            try { m.dispose(); } catch (RuntimeException ignored) { /* best effort */ }
        }
    }
}
