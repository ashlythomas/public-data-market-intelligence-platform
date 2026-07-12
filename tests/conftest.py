import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "packages" / "schemas" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "database" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "messaging" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "observability" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "source-licensing" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "model-client" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "test-fixtures" / "src"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "services" / "enrichment-worker" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signal-engine" / "src"))
sys.path.insert(0, str(ROOT / "services" / "normalizer" / "src"))
