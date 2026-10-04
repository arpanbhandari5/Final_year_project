"""Compatibility entry point for the historical model evaluation audit.

The previous evaluator depended on a removed trainer helper and could silently
encourage a newly retrained approximation. The artifact-only audit preserves
production artifacts and reports whether exact historical metrics are recoverable.
"""

from scripts.evaluate_historical_baseline import main


if __name__ == "__main__":
    main()
