package org.xaikg.mde;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EPackage;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.xmi.impl.EcoreResourceFactoryImpl;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;

/**
 * Loads the .ecore metamodels (dynamic EMF, no generated Java) and registers every EPackage,
 * including sub-packages, in the global registry by nsURI. Epsilon and XMI loading both rely on
 * that registry.
 */
public final class Metamodels {

    public static final String XAIKG_NS = "http://www.xaikg.org/1.0";
    public static final String GRAPHSCHEMA_NS = "http://www.xaikg.org/1.0/graphschema";
    public static final String RAW_NS = "http://www.xaikg.org/1.0/raw";
    public static final String VALIDATED_NS = "http://www.xaikg.org/1.0/validated";

    private final List<EPackage> xaikgPackages = new ArrayList<>();
    private final List<EPackage> allPackages = new ArrayList<>();

    private Metamodels() {}

    public static Metamodels registerAll(MdeHome home) throws IOException {
        installFactories();
        Metamodels mm = new Metamodels();
        ResourceSet rs = new ResourceSetImpl();
        try (var files = Files.list(home.metamodels())) {
            for (Path ecore : (Iterable<Path>) files.filter(p -> p.toString().endsWith(".ecore")).sorted()::iterator) {
                Resource r = rs.getResource(URI.createFileURI(ecore.toAbsolutePath().toString()), true);
                for (var root : r.getContents()) {
                    if (root instanceof EPackage pkg) {
                        mm.register(pkg, ecore.getFileName().toString().equals("xaikg.ecore"));
                    }
                }
            }
        }
        if (mm.xaikgPackages.isEmpty()) {
            throw new IOException("xaikg.ecore not found in " + home.metamodels());
        }
        return mm;
    }

    /** Registers XMI/Ecore resource factories once (needed outside Eclipse). */
    public static void installFactories() {
        var map = Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap();
        map.putIfAbsent("ecore", new EcoreResourceFactoryImpl());
        map.putIfAbsent("xmi", new XMIResourceFactoryImpl());
        map.putIfAbsent("*", new XMIResourceFactoryImpl());
    }

    private void register(EPackage pkg, boolean isXaikg) {
        EPackage.Registry.INSTANCE.put(pkg.getNsURI(), pkg);
        allPackages.add(pkg);
        if (isXaikg) {
            xaikgPackages.add(pkg);
        }
        for (EPackage sub : pkg.getESubpackages()) {
            register(sub, isXaikg);
        }
    }

    /** xaikg root package and its five sub-packages. */
    public List<EPackage> xaikgPackages() { return xaikgPackages; }

    /** Every registered package (xaikg + auxiliary metamodels). */
    public List<EPackage> allPackages() { return allPackages; }

    public EPackage byNsUri(String nsUri) {
        return EPackage.Registry.INSTANCE.getEPackage(nsUri);
    }
}
