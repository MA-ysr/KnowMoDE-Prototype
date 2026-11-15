# xaikg-mde: the model-driven side of KnowMoDE

Java 17 project (Maven) that contains everything model-driven: the metamodels (M2), the constraint layer and the transformations, executed by Eclipse Epsilon from a standalone command-line tool. It never calls an LLM or a database.

| Folder | Content | Documentation |
|---|---|---|
| [`metamodels/`](metamodels/) | `xaikg.ecore` (XAI-KG metamodel, five packages) and the auxiliary metamodels `graphschema`, `rawextraction`, `validatedkg` | [metamodel.md](../docs/metamodel.md), [transformations.md](../docs/transformations.md) |
| [`constraints/xaikg.evl`](constraints/xaikg.evl) | the constraint layer C1–C5 (113 invariants) | [constraints.md](../docs/constraints.md) |
| [`transformations/`](transformations/) | T1–T6 in ETL, EGL and EGX | [transformations.md](../docs/transformations.md) |
| [`src/main/java/`](src/main/java/org/xaikg/mde/) | CLI (`Main`, `Commands`), model loading (`Metamodels`, `ModelSet`), Epsilon runner, T2 (`Validation`), T5 (`Loader`), T6 (`Service`), fingerprints (`Hashing`) | [framework.md](../docs/framework.md) |
| [`src/test/java/`](src/test/java/org/xaikg/mde/) | acceptance tests (models, chain, mutants) | |

Dependencies (see [`pom.xml`](pom.xml)): EMF (Ecore, XMI), Epsilon 2.8 (EOL, EVL, ETL, EGL), picocli, Jackson, JUnit 5. `mvn package` builds the shaded `target/xaikg-mde.jar`.

```bash
java -jar target/xaikg-mde.jar check    --mde-home . -m ../models/diabetes-readmission        # Phase 2
java -jar target/xaikg-mde.jar generate --mde-home . -m ../models/diabetes-readmission -o ../generated   # Phases 2-3
java -jar target/xaikg-mde.jar t2 --mde-home . -m ../models/diabetes-readmission --raw ../datasets/raw -o ../generated/validated
```

Every command prints one JSON report on standard output; exit code 2 means that a blocking invariant failed and nothing was generated.
