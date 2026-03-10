"""Remove redundant 'pass' statements after docstrings in interface/exception files."""
import re
import pathlib

ROOT = pathlib.Path(__file__).parent
TARGETS = [
    "src/core/exceptions.py",
    "src/core/interfaces/asset_repository.py",
    "src/core/interfaces/event_publisher.py",
    "src/core/interfaces/iplugin_service.py",
    "src/core/interfaces/library_service.py",
    "src/core/interfaces/maya_integration.py",
    "src/core/interfaces/maya_scene_parser.py",
    "src/core/interfaces/metadata_extractor.py",
    "src/core/interfaces/usd_export_service.py",
    "src/core/interfaces/usd_import_service.py",
    "src/core/interfaces/usd_material_converter.py",
    "src/core/interfaces/usd_rig_converter.py",
]

# Match a docstring closing quotes followed immediately by a pass line
PATTERN = re.compile(r'([ \t]*"""[ \t]*\n)([ \t]+pass[ \t]*\n)', re.MULTILINE)

total = 0
for rel in TARGETS:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    new, count = PATTERN.subn(r"\1", text)
    if count:
        path.write_text(new, encoding="utf-8")
        print(f"  {rel}: removed {count} pass statement(s)")
        total += count

print(f"\nTotal removed: {total}")
