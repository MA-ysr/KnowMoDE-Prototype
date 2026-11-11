"""Writes LLM extraction results as instances of the rawextraction metamodel (XMI), using pyecore
with the very same .ecore file the Java runtime registers. This is where M0 data is lifted to a
model so that T2 can be a model transformation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyecore.resources import URI, ResourceSet

from ..config import PATHS

RAW_NS = "http://www.xaikg.org/1.0/raw"


@dataclass
class RawEntityData:
    type: str
    id: str
    mention: str
    confidence: float
    start: int
    end: int
    chunk_index: int
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class RawRelationData:
    type: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    confidence: float
    evidence: str
    start: int
    end: int
    chunk_index: int


@dataclass
class RawChunkData:
    index: int
    start: int
    end: int
    status: str = "OK"
    error: str | None = None


@dataclass
class RawDocumentData:
    source_document: str
    source_uri: str
    source_sha256: str
    source_text: str
    extraction_task: str
    llm_model: str
    prompt_id: str
    prompt_hash: str
    timestamp: str
    chunks: list[RawChunkData] = field(default_factory=list)
    entities: list[RawEntityData] = field(default_factory=list)
    relations: list[RawRelationData] = field(default_factory=list)


def load_ecore(rset: ResourceSet, ecore: Path):
    """Loads an .ecore with pyecore. EMF tolerates XML comments inside the metamodel; pyecore does
    not, so the file is parsed comment-free into a temporary copy first (the model is unchanged)."""
    import tempfile

    from lxml import etree

    tree = etree.parse(str(ecore), parser=etree.XMLParser(remove_comments=True))
    tmp = Path(tempfile.gettempdir()) / f"xaikg-{ecore.stem}.ecore"
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8")
    res = rset.get_resource(URI(str(tmp)))
    pkg = res.contents[0]
    rset.metamodel_registry[pkg.nsURI] = pkg
    return pkg


class RawModelWriter:
    def __init__(self, metamodel_dir: Path | None = None):
        self.rset = ResourceSet()
        self.pkg = load_ecore(self.rset, (metamodel_dir or PATHS.metamodels) / "rawextraction.ecore")
        self.cls = {c.name: c for c in self.pkg.eClassifiers}

    def _new(self, name: str, **attrs):
        obj = self.cls[name]()
        for k, v in attrs.items():
            if v is not None:
                setattr(obj, k, v)
        return obj

    def write(self, doc: RawDocumentData, out: Path) -> Path:
        root = self._new("RawExtractionResult", sourceDocument=doc.source_document, sourceUri=doc.source_uri,
                         sourceSha256=doc.source_sha256, sourceText=doc.source_text, extractionTask=doc.extraction_task,
                         llmModel=doc.llm_model, promptId=doc.prompt_id, promptHash=doc.prompt_hash,
                         extractionTimestamp=doc.timestamp)
        for c in doc.chunks:
            root.chunks.append(self._new("RawChunk", index=c.index, charStart=c.start, charEnd=c.end,
                                         status=c.status, error=c.error))
        for e in doc.entities:
            ent = self._new("RawEntity", type=e.type, id=e.id, mention=e.mention, confidence=float(e.confidence),
                            sourceSpanStart=e.start, sourceSpanEnd=e.end, chunkIndex=e.chunk_index)
            for k, v in e.properties.items():
                ent.properties.append(self._new("RawProperty", key=str(k), value=str(v)))
            root.entities.append(ent)
        for r in doc.relations:
            root.relations.append(self._new("RawRelation", type=r.type, sourceType=r.source_type, sourceId=r.source_id,
                                            targetType=r.target_type, targetId=r.target_id, confidence=float(r.confidence),
                                            evidence=r.evidence, sourceSpanStart=r.start, sourceSpanEnd=r.end,
                                            chunkIndex=r.chunk_index))
        out.parent.mkdir(parents=True, exist_ok=True)
        resource = self.rset.create_resource(URI(str(out)))
        resource.append(root)
        resource.save()
        return out
