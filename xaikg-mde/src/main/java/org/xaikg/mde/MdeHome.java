package org.xaikg.mde;

import java.io.IOException;
import java.io.InputStream;
import java.net.URISyntaxException;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Enumeration;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

/**
 * Locates the framework assets (metamodels/, constraints/, transformations/).
 *
 * Resolution order:
 *  1. explicit --mde-home option,
 *  2. XAIKG_MDE_HOME environment variable,
 *  3. the assets bundled inside the jar (extracted once to a temporary directory).
 *
 * Options 1 and 2 let you edit .evl/.etl/.egl files and re-run without rebuilding the jar.
 */
public final class MdeHome {

    private static final String[] ASSET_DIRS = { "metamodels", "constraints", "transformations" };

    private final Path root;

    private MdeHome(Path root) {
        this.root = root;
    }

    public static MdeHome resolve(Path explicit) throws IOException {
        if (explicit != null) {
            return validated(explicit.toAbsolutePath().normalize());
        }
        String env = System.getenv("XAIKG_MDE_HOME");
        if (env != null && !env.isBlank()) {
            return validated(Path.of(env).toAbsolutePath().normalize());
        }
        return new MdeHome(extractBundledAssets());
    }

    private static MdeHome validated(Path p) throws IOException {
        for (String d : ASSET_DIRS) {
            if (!Files.isDirectory(p.resolve(d))) {
                throw new IOException("MDE home " + p + " has no '" + d + "' directory");
            }
        }
        return new MdeHome(p);
    }

    public Path root() { return root; }
    public Path metamodels() { return root.resolve("metamodels"); }
    public Path constraints() { return root.resolve("constraints"); }
    public Path transformations() { return root.resolve("transformations"); }

    /** Copies the bundled asset directories out of the jar (or classes dir) into a temp folder. */
    private static Path extractBundledAssets() throws IOException {
        Path tmp = Files.createTempDirectory("xaikg-mde-");
        tmp.toFile().deleteOnExit();
        URL location = MdeHome.class.getProtectionDomain().getCodeSource().getLocation();
        Path source;
        try {
            source = Path.of(location.toURI());
        } catch (URISyntaxException e) {
            throw new IOException("Cannot locate own code source: " + location, e);
        }
        if (Files.isDirectory(source)) {
            // running from target/classes
            for (String d : ASSET_DIRS) {
                Path from = source.resolve(d);
                if (Files.isDirectory(from)) {
                    copyTree(from, tmp.resolve(d));
                }
            }
        } else {
            try (JarFile jar = new JarFile(source.toFile())) {
                Enumeration<JarEntry> entries = jar.entries();
                while (entries.hasMoreElements()) {
                    JarEntry entry = entries.nextElement();
                    String name = entry.getName();
                    for (String d : ASSET_DIRS) {
                        if (name.startsWith(d + "/") && !entry.isDirectory()) {
                            Path target = tmp.resolve(name);
                            Files.createDirectories(target.getParent());
                            try (InputStream in = jar.getInputStream(entry)) {
                                Files.copy(in, target, StandardCopyOption.REPLACE_EXISTING);
                            }
                        }
                    }
                }
            }
        }
        return validated(tmp).root;
    }

    private static void copyTree(Path from, Path to) throws IOException {
        try (var walk = Files.walk(from)) {
            for (Path p : (Iterable<Path>) walk::iterator) {
                Path target = to.resolve(from.relativize(p).toString());
                if (Files.isDirectory(p)) {
                    Files.createDirectories(target);
                } else {
                    Files.createDirectories(target.getParent());
                    Files.copy(p, target, StandardCopyOption.REPLACE_EXISTING);
                }
            }
        }
    }
}
