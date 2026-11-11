"""Corpus and dataset acquisition. Every fetcher writes files into datasets/<folder>/ and records
them in datasets/manifests/<folder>.manifest.json (URI, licence, SHA-256). Fetchers are idempotent:
a file whose manifest entry matches is not downloaded again, so runs are reproducible offline."""
