"""Phase 4: for each extraction task of the pipeline model (as described by its generated
side-car), chunk every document of its source collection, call the LLM with the generated prompt,
and write one rawextraction.xmi per document.

Span handling. The prompt asks for offsets relative to the chunk; they are mapped to document
offsets here. LLMs are unreliable at counting characters, so when the reported span does not match
the verbatim mention, the mention is located in the chunk by exact search (first occurrence after
the previous mention). The number of repaired spans is reported, because this is a measurable
weakness of the LLM, not of the pipeline. Mentions that cannot be located keep the LLM's span and
are left for the span-grounding rule of T2 to reject.
Reproduction. Every response is cached by (provider, model, prompt, chunk). When a document is not
cached for the model named in the pipeline model, the extractor first looks for a complete cached run
of the same prompt and chunks under another model of the same provider (the corpus was extracted
across several free-tier models) and records THAT model in the raw model's provenance, so a rebuilt
graph carries the same ExtractionRun nodes as the original and no document already processed costs a
new LLM call (with or without credentials; --force re-extracts with the configured model).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from ..config import PATHS
from ..manifest import load_manifest, now_iso, sha256_text
from ..mde_bridge import prompt_registry, prompt_sidecar
from .chunking import Chunk, chunk_document
from .client import DailyQuotaExhausted, LLMClient
from .raw_model import RawChunkData, RawDocumentData, RawEntityData, RawModelWriter, RawRelationData

def _manifest_name(collection: str) -> str | None:
    """`corpus/<source>[/<subset>]` (ExtractionTask.sourceCollection) -> manifest datasets/manifests/<source>.manifest.json."""
    parts = collection.split("/")
    if len(parts) not in (2, 3) or parts[0] != "corpus" or not all(parts):
        return None
    return parts[1] if (PATHS.manifests / f"{parts[1]}.manifest.json").exists() else None


def _locate(chunk: Chunk, mention: str, span: dict | None, search_from: int) -> tuple[int, int, bool]:
    """Returns (doc_start, doc_end, repaired)."""
    text = chunk.text
    if span and isinstance(span.get("start"), int) and isinstance(span.get("end"), int):
        s, e = span["start"], span["end"]
        if 0 <= s < e <= len(text) and text[s:e].lower() == mention.lower():
            return chunk.start + s, chunk.start + e, False
    idx = text.lower().find(mention.lower(), search_from)
    if idx < 0:
        idx = text.lower().find(mention.lower())
    if idx >= 0:
        return chunk.start + idx, chunk.start + idx + len(mention), True
    if span and isinstance(span.get("start"), int) and isinstance(span.get("end"), int):
        return chunk.start + span["start"], chunk.start + span["end"], True
    return -1, -1, True


def _documents(collections: str) -> list[tuple[str, Path, dict]]:
    """Documents of one or more collections (space/comma separated in ExtractionTask.sourceCollection).
    `corpus/<source>` selects the documents whose manifest entry belongs to that collection;
    `corpus/<source>/<subset>` the documents tagged with the subset (manifest `collection` / `alsoIn`).
    Files live in corpus/<source>/ in both cases."""
    docs = []
    for collection in [c for c in collections.replace(",", " ").split() if c]:
        name = _manifest_name(collection)
        if name is None:
            raise SystemExit(f"unknown source collection {collection!r} (expected corpus/<source>[/<subset>] with a manifest; run `make corpus`)")
        folder = PATHS.corpus / name
        manifest = load_manifest(PATHS.manifests, name, folder)
        for rel, entry in sorted(manifest.entries.items()):
            member = manifest.collections_of(rel) or {f"corpus/{name}"}
            if collection not in member:
                continue
            path = folder / rel
            if path.exists():
                docs.append((f"{name}/{rel}", path, entry))
    return docs


def _user_message(doc_id: str, chunk: Chunk, n_chunks: int) -> str:
    return f"Document: {doc_id}\nChunk {chunk.index + 1} of {n_chunks} (characters {chunk.start}-{chunk.end}).\n\n{chunk.text}"


def _fully_cached(client: LLMClient, prompt: str, users: list[str]) -> bool:
    return all((client.cache_dir / f"{client.cache_key(prompt, u)}.json").exists() for u in users)


def cached_alternative(client: LLMClient, prompt: str, sidecar: dict, doc_id: str, path: Path) -> LLMClient | None:
    """Cache-only runs: a client for another model of the same provider whose cache holds every chunk of
    this document, or None when the configured model is already fully cached (or nothing else is)."""
    text = path.read_text(encoding="utf-8")
    cs = sidecar["chunking"]
    chunks = chunk_document(text, cs["chunkSize"], cs["overlap"], cs["splitter"])
    users = [_user_message(doc_id, ch, len(chunks)) for ch in chunks]
    if _fully_cached(client, prompt, users):
        return None
    for d in sorted(p for p in client.cache_dir.parent.iterdir() if p.is_dir() and p != client.cache_dir):
        alt = LLMClient(f"{client.provider}/{d.name}", rpm=60, temperature=client.temperature, max_tokens=client.max_tokens)
        if _fully_cached(alt, prompt, users):
            return alt
    return None


def extract_document(client: LLMClient, prompt: str, sidecar: dict, doc_id: str, path: Path, entry: dict,
                     stats: dict) -> RawDocumentData:
    text = path.read_text(encoding="utf-8")
    cs = sidecar["chunking"]
    chunks = chunk_document(text, cs["chunkSize"], cs["overlap"], cs["splitter"])
    doc = RawDocumentData(source_document=doc_id, source_uri=entry.get("uri", ""), source_sha256=sha256_text(text),
                          source_text=text, extraction_task=sidecar["task"], llm_model=sidecar["llmModel"],
                          prompt_id=sidecar["promptId"], prompt_hash=sidecar["promptHash"], timestamp=now_iso())
    local_ids: dict[tuple[str, str], str] = {}
    for chunk in chunks:
        comp = client.complete_json(prompt, _user_message(doc_id, chunk, len(chunks)))
        if comp.error and comp.error.startswith("cache miss"):
            stats["cache_misses_without_key"] = stats.get("cache_misses_without_key", 0) + 1
        else:
            stats["calls"] += 0 if comp.cached else 1
        stats["cached"] += 1 if comp.cached else 0
        stats["input_tokens"] += comp.usage.get("input", 0)
        stats["output_tokens"] += comp.usage.get("output", 0)
        if comp.error or comp.data is None:
            status = "LLM_ERROR" if comp.error and "JSON" not in comp.error else "UNPARSEABLE"
            doc.chunks.append(RawChunkData(chunk.index, chunk.start, chunk.end, status, comp.error))
            stats["chunks_failed"] += 1
            continue
        doc.chunks.append(RawChunkData(chunk.index, chunk.start, chunk.end))
        stats["chunks_ok"] += 1
        cursor = 0
        for e in comp.data.get("entities", []) or []:
            if not isinstance(e, dict) or not e.get("type") or not e.get("id"):
                stats["malformed_items"] += 1
                continue
            mention = str(e.get("mention") or "").strip()
            s, t, repaired = _locate(chunk, mention, e.get("span"), cursor) if mention else (-1, -1, True)
            if repaired:
                stats["spans_repaired"] += 1
            if s >= 0:
                cursor = max(cursor, s - chunk.start)
            props = e.get("properties") or {}
            doc.entities.append(RawEntityData(type=str(e["type"]), id=str(e["id"]), mention=mention,
                                              confidence=float(e.get("confidence", 0.0) or 0.0), start=s, end=t,
                                              chunk_index=chunk.index,
                                              properties={str(k): str(v) for k, v in props.items() if v is not None}))
            local_ids[(str(e["type"]), str(e["id"]))] = mention
        for r in comp.data.get("relations", []) or []:
            if not isinstance(r, dict) or not r.get("type") or not isinstance(r.get("source"), dict) \
                    or not isinstance(r.get("target"), dict):
                stats["malformed_items"] += 1
                continue
            evidence = str(r.get("evidence") or "").strip()
            s, t, repaired = _locate(chunk, evidence, r.get("span"), 0) if evidence else (-1, -1, True)
            if repaired:
                stats["spans_repaired"] += 1
            doc.relations.append(RawRelationData(type=str(r["type"]), source_type=str(r["source"].get("type", "")),
                                                 source_id=str(r["source"].get("id", "")),
                                                 target_type=str(r["target"].get("type", "")),
                                                 target_id=str(r["target"].get("id", "")),
                                                 confidence=float(r.get("confidence", 0.0) or 0.0), evidence=evidence,
                                                 start=s, end=t, chunk_index=chunk.index))
    return doc


def run_extraction(task: str | None = None, limit: int | None = None, model_override: str | None = None,
                   rpm: int = 8, force: bool = False) -> dict:
    registry = prompt_registry()
    tasks = [p["task"] for p in registry["prompts"]]
    if task:
        if task not in tasks:
            raise SystemExit(f"unknown task {task!r}; generated tasks: {tasks}")
        tasks = [task]
    writer = RawModelWriter()
    report: dict = {"tasks": {}, "startedAt": now_iso()}
    for t in tasks:
        sidecar = prompt_sidecar(t)
        prompt = (PATHS.prompts / sidecar["promptFile"]).read_text(encoding="utf-8")
        model_spec = model_override or sidecar["llmModel"]
        client = LLMClient(model_spec, rpm=rpm, temperature=sidecar["temperature"], max_tokens=sidecar["maxTokens"])
        if model_override:
            sidecar = {**sidecar, "llmModel": model_override}
        docs = _documents(sidecar["sourceCollection"])
        if limit:
            docs = docs[:limit]
        out_dir = PATHS.raw / t
        stats = {"documents": 0, "skipped_existing": 0, "chunks_ok": 0, "chunks_failed": 0, "calls": 0, "cached": 0,
                 "input_tokens": 0, "output_tokens": 0, "entities": 0, "relations": 0, "spans_repaired": 0,
                 "malformed_items": 0, "seconds": 0.0}
        t0 = time.perf_counter()
        for doc_id, path, entry in docs:
            out = out_dir / (Path(doc_id).stem + ".xmi")
            if out.exists() and not force:
                stats["skipped_existing"] += 1
                continue
            doc_client, doc_sidecar = client, sidecar
            if not force:
                # a document already processed under another model is served from that model's cache
                # (no new LLM call); --force re-extracts with the configured model
                alt = cached_alternative(client, prompt, sidecar, doc_id, path)
                if alt is not None:
                    doc_client, doc_sidecar = alt, {**sidecar, "llmModel": f"{alt.provider}/{alt.model}"}
                    fb = stats.setdefault("cache_fallback_models", {})
                    fb[doc_sidecar["llmModel"]] = fb.get(doc_sidecar["llmModel"], 0) + 1
            try:
                doc = extract_document(doc_client, prompt, doc_sidecar, doc_id, path, entry, stats)
            except DailyQuotaExhausted as e:
                stats["stopped"] = f"daily quota exhausted at {doc_id}: {e}"
                print(f"[extract] {stats['stopped']}", file=sys.stderr, flush=True)
                break
            writer.write(doc, out)
            stats["documents"] += 1
            stats["entities"] += len(doc.entities)
            stats["relations"] += len(doc.relations)
            print(f"[extract] {t}: {doc_id} -> {len(doc.entities)} entities, {len(doc.relations)} relations "
                  f"({stats['documents']}/{len(docs) - stats['skipped_existing']})", file=sys.stderr, flush=True)
        stats["seconds"] = round(time.perf_counter() - t0, 1)
        stats["model"] = model_spec
        stats["promptId"] = sidecar["promptId"]
        report["tasks"][t] = stats
        if stats.get("stopped"):
            break
    report["finishedAt"] = now_iso()
    (PATHS.results / "extraction-runs.jsonl").parent.mkdir(exist_ok=True)
    with (PATHS.results / "extraction-runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(report) + "\n")
    return report
