"""Generators for contracts whose consumer file is derived, not copied.

A generator is `(producer_bytes) -> consumer_bytes` and must be
deterministic: `pull` produces the consumer file with it, and `status`
reproduces the file to verify it, so any nondeterminism reads as drift.
"""
