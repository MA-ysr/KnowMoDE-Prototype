package org.xaikg.mde;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Set;

import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.common.module.IModule;
import org.eclipse.epsilon.common.parse.problem.ParseProblem;
import org.eclipse.epsilon.egl.EglFileGeneratingTemplateFactory;
import org.eclipse.epsilon.egl.EglTemplateFactory;
import org.eclipse.epsilon.egl.EglTemplateFactoryModuleAdapter;
import org.eclipse.epsilon.egl.EgxModule;
import org.eclipse.epsilon.emc.emf.EmfModel;
import org.eclipse.epsilon.eol.IEolModule;
import org.eclipse.epsilon.eol.models.IModel;
import org.eclipse.epsilon.etl.EtlModule;
import org.eclipse.epsilon.evl.EvlModule;
import org.eclipse.epsilon.evl.dom.Constraint;
import org.eclipse.epsilon.evl.execute.UnsatisfiedConstraint;

/** Thin wrappers around the Epsilon engines (EVL, ETL, EGL, EGX) with uniform error handling. */
public final class Epsilon {

    private Epsilon() {}

    public record Violation(String constraint, String family, boolean critique, String context,
                            String element, String model, String message) {}

    public record EvlResult(int constraintsDefined, List<Violation> violations) {
        public long errors() { return violations.stream().filter(v -> !v.critique()).count(); }
        public long warnings() { return violations.stream().filter(Violation::critique).count(); }
    }

    /** Runs an EVL module over the given models. */
    public static EvlResult runEvl(Path evlFile, Collection<IModel> models) throws Exception {
        EvlModule module = new EvlModule();
        parse(module, evlFile);
        module.getContext().getModelRepository().addModels(models);
        Set<UnsatisfiedConstraint> unsatisfied = module.execute();
        List<Violation> violations = new ArrayList<>();
        for (UnsatisfiedConstraint uc : unsatisfied) {
            Constraint c = uc.getConstraint();
            String name = c.getName();
            String family = name.contains("_") ? name.substring(0, name.indexOf('_')) : "";
            String context = c.getConstraintContext().getTypeName();
            String model = context.contains("!") ? context.substring(0, context.indexOf('!')) : "";
            String element = uc.getInstance() instanceof EObject eo ? ModelSet.describe(eo) : String.valueOf(uc.getInstance());
            violations.add(new Violation(name, family, c.isCritique(), context, element, model, uc.getMessage()));
        }
        violations.sort((a, b) -> {
            int s = Boolean.compare(a.critique(), b.critique());
            return s != 0 ? s : a.constraint().compareTo(b.constraint());
        });
        int defined = module.getConstraints().size();
        // Do NOT dispose the repository here: it would unload the shared M1 resources that later
        // transformations (T1..T6) still navigate. ModelSet.close() disposes them at the end.
        return new EvlResult(defined, violations);
    }

    /** Runs an ETL module; the caller is responsible for storing/disposing the target model. */
    public static void runEtl(Path etlFile, Collection<IModel> models) throws Exception {
        runEtl(etlFile, models, java.util.Map.of());
    }

    /** Runs an ETL module with extra read-only global variables visible to the program. */
    public static void runEtl(Path etlFile, Collection<IModel> models, java.util.Map<String, Object> variables) throws Exception {
        EtlModule module = new EtlModule();
        parse(module, etlFile);
        module.getContext().getModelRepository().addModels(models);
        for (var e : variables.entrySet()) {
            module.getContext().getFrameStack().putGlobal(
                org.eclipse.epsilon.eol.execute.context.Variable.createReadOnlyVariable(e.getKey(), e.getValue()));
        }
        module.execute();
    }

    /** Result of an EVL run when the caller needs the unsatisfied constraints themselves. */
    public record EvlRun(List<Constraint> constraints, Set<UnsatisfiedConstraint> unsatisfied) {}

    /** Runs an EVL module and returns the raw unsatisfied constraints (instances kept). */
    public static EvlRun evaluate(Path evlFile, Collection<IModel> models) throws Exception {
        EvlModule module = new EvlModule();
        parse(module, evlFile);
        module.getContext().getModelRepository().addModels(models);
        Set<UnsatisfiedConstraint> unsatisfied = module.execute();
        return new EvlRun(module.getConstraints(), unsatisfied);
    }

    /** Runs a single EGL template and returns the generated text. */
    public static String runEgl(Path eglFile, Collection<IModel> models) throws Exception {
        return runEgl(eglFile, models, java.util.Map.of());
    }

    /** Runs a single EGL template with extra read-only global variables; returns the generated text. */
    public static String runEgl(Path eglFile, Collection<IModel> models, java.util.Map<String, Object> variables) throws Exception {
        EglTemplateFactoryModuleAdapter module = new EglTemplateFactoryModuleAdapter(new EglTemplateFactory());
        parse(module, eglFile);
        module.getContext().getModelRepository().addModels(models);
        for (var e : variables.entrySet()) {
            module.getContext().getFrameStack().putGlobal(
                org.eclipse.epsilon.eol.execute.context.Variable.createReadOnlyVariable(e.getKey(), e.getValue()));
        }
        Object out = module.execute();
        return out == null ? "" : out.toString();
    }

    /** Runs an EGX co-ordination module, writing the generated files under outputRoot. */
    public static void runEgx(Path egxFile, Collection<IModel> models, Path outputRoot) throws Exception {
        runEgx(egxFile, models, outputRoot, java.util.Map.of());
    }

    /** Runs an EGX module with extra read-only global variables visible to the rules and templates. */
    public static void runEgx(Path egxFile, Collection<IModel> models, Path outputRoot,
                              java.util.Map<String, Object> variables) throws Exception {
        EglFileGeneratingTemplateFactory factory = new EglFileGeneratingTemplateFactory();
        factory.setOutputRoot(outputRoot.toAbsolutePath().toString());
        EgxModule module = new EgxModule(factory);
        parse(module, egxFile);
        module.getContext().getModelRepository().addModels(models);
        for (var e : variables.entrySet()) {
            module.getContext().getFrameStack().putGlobal(
                org.eclipse.epsilon.eol.execute.context.Variable.createReadOnlyVariable(e.getKey(), e.getValue()));
        }
        module.execute();
    }

    /** Creates an empty, writable EMF model for a registered metamodel URI, stored at `file`. */
    public static EmfModel newOutputModel(String name, String metamodelUri, Path file) throws Exception {
        EmfModel m = new EmfModel();
        m.setName(name);
        m.setMetamodelUri(metamodelUri);
        m.setModelFile(file.toAbsolutePath().toString());
        m.setReadOnLoad(false);
        m.setStoredOnDisposal(true);
        m.load();
        return m;
    }

    /** Loads an existing EMF model file for a registered metamodel URI (read-only). */
    public static EmfModel loadModel(String name, String metamodelUri, Path file) throws Exception {
        EmfModel m = new EmfModel();
        m.setName(name);
        m.setMetamodelUri(metamodelUri);
        m.setModelFile(file.toAbsolutePath().toString());
        m.setReadOnLoad(true);
        m.setStoredOnDisposal(false);
        m.load();
        return m;
    }

    private static void parse(IEolModule module, Path file) throws Exception {
        File f = file.toFile();
        if (!f.isFile()) {
            throw new IllegalArgumentException("Epsilon program not found: " + file);
        }
        ((IModule) module).parse(f);
        List<ParseProblem> problems = module.getParseProblems();
        if (!problems.isEmpty()) {
            StringBuilder sb = new StringBuilder("Parse problems in " + file.getFileName() + ":");
            for (ParseProblem p : problems) sb.append("\n  ").append(p);
            throw new IllegalStateException(sb.toString());
        }
    }
}
