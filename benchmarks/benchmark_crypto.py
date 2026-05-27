"""Benchmark cryptographic operations for TSB signing and verification."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path

from teaagent.tsb_format import TSBBuilder, TSBMetadata


def benchmark_tsb_build() -> dict[str, float]:
    """Benchmark TSB build operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create test skill
        skill_path = tmp_path / "skill"
        skill_path.mkdir()
        
        # Create files of various sizes
        (skill_path / "small.txt").write_text("x" * 100, encoding="utf-8")
        (skill_path / "medium.txt").write_text("x" * 10_000, encoding="utf-8")
        (skill_path / "large.txt").write_text("x" * 1_000_000, encoding="utf-8")
        
        # Create audit log (simple JSONL)
        audit_log_path = tmp_path / "audit.jsonl"
        audit_events = [
            {"event_id": str(i), "event_type": "tool_call", "run_id": "test", "created_at": f"2024-01-01T00:{i:02d}:00Z", "payload": {"tool": "test"}, "prev_hash": "genesis" if i == 0 else f"hash{i-1}"}
            for i in range(100)
        ]
        audit_log_content = "\n".join(json.dumps(event) for event in audit_events)
        audit_log_path.write_text(audit_log_content, encoding="utf-8")
        
        # Benchmark build
        metadata = TSBMetadata(
            skill_name="benchmark-skill",
            skill_version="1.0.0",
            skill_author="benchmark",
            created_at="2024-01-01T00:00:00Z",
        )
        
        builder = TSBBuilder(
            skill_path=skill_path,
            audit_log_path=audit_log_path,
            author_key_path=None,
        )
        
        output_path = tmp_path / "benchmark.tsb"
        
        start = time.perf_counter()
        builder.build_tsb(output_path, metadata, skip_audit_verification=True)
        build_time = time.perf_counter() - start
        
        # Benchmark hash calculation
        start = time.perf_counter()
        bundle_hash = hashlib.sha256()
        for file_path in sorted(skill_path.rglob("*")):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(skill_path))
                bundle_hash.update(rel_path.encode("utf-8"))
                bundle_hash.update(file_path.read_bytes())
        hash_time = time.perf_counter() - start
        
        # Benchmark tarball creation
        import tarfile
        start = time.perf_counter()
        with tarfile.open(tmp_path / "test.tar.gz", "w:gz") as tar:
            tar.add(skill_path, arcname="skill")
        tar_time = time.perf_counter() - start
        
        return {
            "build_time": build_time,
            "hash_time": hash_time,
            "tar_time": tar_time,
            "total_size": output_path.stat().st_size,
        }


def benchmark_hash_calculation_sizes() -> dict[str, dict[str, float]]:
    """Benchmark hash calculation for different file sizes."""
    results = {}
    
    sizes = [100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000]
    
    for size in sizes:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "test.txt"
            test_file.write_text("x" * size, encoding="utf-8")
            
            start = time.perf_counter()
            hashlib.sha256(test_file.read_bytes()).hexdigest()
            hash_time = time.perf_counter() - start
            
            results[f"{size}_bytes"] = {
                "hash_time": hash_time,
                "throughput_mb_s": (size / 1_000_000) / hash_time if hash_time > 0 else 0,
            }
    
    return results


def print_benchmark_results() -> None:
    """Print benchmark results."""
    print("=" * 80)
    print("TSB Build Performance Benchmark")
    print("=" * 80)
    
    build_results = benchmark_tsb_build()
    print(f"\nTSB Build:")
    print(f"  Build time: {build_results['build_time']:.4f}s")
    print(f"  Hash time: {build_results['hash_time']:.4f}s")
    print(f"  Tar time: {build_results['tar_time']:.4f}s")
    print(f"  Total size: {build_results['total_size'] / 1024:.2f} KB")
    
    print("\n" + "=" * 80)
    print("Hash Calculation Performance by File Size")
    print("=" * 80)
    
    hash_results = benchmark_hash_calculation_sizes()
    for size_key, metrics in hash_results.items():
        print(f"\n{size_key}:")
        print(f"  Hash time: {metrics['hash_time']:.6f}s")
        print(f"  Throughput: {metrics['throughput_mb_s']:.2f} MB/s")


if __name__ == "__main__":
    print_benchmark_results()
