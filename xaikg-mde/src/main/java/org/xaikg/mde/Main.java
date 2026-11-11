package org.xaikg.mde;

import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.Callable;

import org.eclipse.emf.ecore.EcorePackage;
import org.eclipse.epsilon.egl.EgxModule;
import org.eclipse.epsilon.eol.EolModule;
import org.eclipse.epsilon.etl.EtlModule;
import org.eclipse.epsilon.evl.EvlModule;

import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

/**
 * Entry point of the XAI-KG MDE runtime (the M1 -> M0 side of the paper's six-phase workflow, Section 4).
 *
 * Every sub-command prints exactly one JSON report on stdout (the contract with the Python
 * pipeline) and uses the exit code to signal the outcome:
 *   0 = success, 2 = models violate a blocking constraint / unresolved references, 1 = failure.
 */
@Command(name = "xaikg-mde",
         mixinStandardHelpOptions = true,
         version = "xaikg-mde 0.1.0",
         description = "Model-driven runtime for LLM-assisted KG construction in XAI systems.",
         subcommands = { Main.Doctor.class, Commands.Check.class, Commands.T1.class, Commands.T2.class,
                         Commands.T3.class, Commands.T4.class, Commands.T5.class, Commands.T6.class, Commands.Generate.class })
public final class Main implements Callable<Integer> {

    public static final int EXIT_OK = 0;
    public static final int EXIT_FAILURE = 1;
    public static final int EXIT_MODEL_INVALID = 2;

    public static void main(String[] args) {
        int exit = new CommandLine(new Main())
            .setExecutionExceptionHandler((ex, cmd, parseResult) -> {
                Json.print(java.util.Map.of(
                    "command", cmd.getCommandName(),
                    "status", "failure",
                    "error", ex.getClass().getSimpleName() + ": " + String.valueOf(ex.getMessage())));
                if (System.getenv("XAIKG_DEBUG") != null) ex.printStackTrace(System.err);
                return EXIT_FAILURE;
            })
            .execute(args);
        System.exit(exit);
    }

    @Override
    public Integer call() {
        CommandLine.usage(this, System.out);
        return EXIT_OK;
    }

    /** Options shared by every command that needs the framework assets. */
    public static class HomeOptions {
        @Option(names = "--mde-home",
                description = "Folder holding metamodels/, constraints/, transformations/ (default: bundled in the jar; env XAIKG_MDE_HOME).")
        Path mdeHome;

        MdeHome home() throws Exception { return MdeHome.resolve(mdeHome); }
    }

    /** Options shared by every command that reads the M1 models of a use case. */
    public static class ModelOptions extends HomeOptions {
        @Option(names = { "-m", "--models" }, required = true, arity = "1..*",
                description = "M1 model files or directories (all *.xmi in a directory are loaded).")
        List<Path> models;
    }

    /** Verifies that EMF and every Epsilon engine are on the classpath of the shaded jar. */
    @Command(name = "doctor", description = "Check that EMF and the Epsilon engines load correctly.")
    static final class Doctor implements Callable<Integer> {
        @Override
        public Integer call() {
            Json.print(new java.util.TreeMap<>(java.util.Map.of(
                "command", "doctor",
                "status", "ok",
                "emf.ecore", EcorePackage.eNS_URI,
                "epsilon.eol", new EolModule().getClass().getName(),
                "epsilon.evl", new EvlModule().getClass().getName(),
                "epsilon.etl", new EtlModule().getClass().getName(),
                "epsilon.egx", new EgxModule().getClass().getName(),
                "java", System.getProperty("java.version"))));
            return EXIT_OK;
        }
    }
}
