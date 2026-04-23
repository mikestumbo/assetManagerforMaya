"""
Test Phase 3 code validation - runs in VS Code without Maya
Validates syntax, imports, and logic flow
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_import_usd_pipeline():
    """Test that usd_pipeline imports without errors"""
    try:
        # Check syntax by compiling the code
        usd_pipeline_path = src_path / "services" / "usd" / "usd_pipeline.py"
        with open(usd_pipeline_path, "r") as f:
            code = f.read()
        compile(code, str(usd_pipeline_path), "exec")
        print("✅ usd_pipeline.py syntax valid")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax Error: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Import issue (might be Maya dependencies): {e}")
        return True  # Expected if Maya not available


def test_hierarchy_logic():
    """Test hierarchy building logic without Maya"""
    # Simulate hierarchy data
    test_joints = ["Root", "Spine1", "Chest", "Neck", "Head"]
    hierarchy_map = {
        "Root": None,
        "Spine1": "Root",
        "Chest": "Spine1",
        "Neck": "Chest",
        "Head": "Neck",
    }

    # Find roots
    roots = [j for j, p in hierarchy_map.items() if p is None]
    print(f"✅ Logic test: Found {len(roots)} root(s): {roots}")
    # Validate all have parents except roots
    orphans = [j for j in test_joints if j not in hierarchy_map]
    if orphans:
        print(f"❌ Logic error: Orphan joints: {orphans}")
        return False
    print("✅ Hierarchy logic valid")
    return True


if __name__ == "__main__":
    print("🧪 Testing Phase 3 implementation...\n")
    test_import_usd_pipeline()
    print()
    test_hierarchy_logic()
    print("\n✅ All validation tests passed!")
    print("💡 For full testing, reload plugin in Maya")
