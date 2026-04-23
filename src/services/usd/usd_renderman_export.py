"""
Unified USD Export with RenderMan Materials.
Creates unified hierarchy (mesh + skeleton under one SkelRoot),
then exports with RenderMan-compatible material shading mode.
"""

import maya.cmds as cmds
from pathlib import Path

OUTPUT_DIR = Path("C:/Users/ChEeP/OneDrive/Documents/maya/projects/default/USD_Test_Output")
OUTPUT_FILE = OUTPUT_DIR / "Veteran_RenderMan.usdc"
BODY_SHAPE = "Body_GeoShapeDeformed"
BODY_SKINCLUSTER = "skinCluster1"
EXPORT_GROUP = "USD_Export_Grp"


def find_root_joint(skin_cluster):
    """Walk up from the first influence joint to find the skeleton root."""
    joints = cmds.skinCluster(skin_cluster, query=True, influence=True)
    if not joints:
        raise RuntimeError(f"No joints found on {skin_cluster}")

    joint = joints[0]
    while True:
        parent = cmds.listRelatives(joint, parent=True, type="joint")
        if not parent:
            return joint
        joint = parent[0]


def create_unified_hierarchy():
    """Duplicate body mesh and skeleton under a single group for clean export."""
    if cmds.objExists(EXPORT_GROUP):
        cmds.delete(EXPORT_GROUP)

    root_joint = find_root_joint(BODY_SKINCLUSTER)
    print(f"Root joint: {root_joint}")

    # Get original mesh transform
    body_transform = cmds.listRelatives(BODY_SHAPE, parent=True)[0]

    # Duplicate mesh and skeleton
    mesh_dup = cmds.duplicate(body_transform, name="Body_USD")[0]
    skel_dup = cmds.duplicate(root_joint, name="Skeleton_USD", returnRootsOnly=True)[0]

    # Parent under unified group
    grp = cmds.group(empty=True, name=EXPORT_GROUP)
    cmds.parent(mesh_dup, grp)
    cmds.parent(skel_dup, grp)

    # Use long names to avoid ambiguity with original skeleton
    grp_long = cmds.ls(grp, long=True)[0]
    skel_long = cmds.ls(f"{grp_long}|{skel_dup}", long=True)[0]
    mesh_long = cmds.ls(f"{grp_long}|{mesh_dup}", long=True)[0]

    # Bind duplicated mesh to duplicated skeleton
    dup_joints = (
        cmds.listRelatives(skel_long, allDescendents=True, type="joint", fullPath=True) or []
    )
    dup_joints.insert(0, skel_long)
    print(f"Total joints: {len(dup_joints)}")

    new_skin = cmds.skinCluster(
        dup_joints, mesh_long, toSelectedBones=True, name="USD_skinCluster"
    )[0]

    # Copy weights from original
    cmds.copySkinWeights(
        sourceSkin=BODY_SKINCLUSTER,
        destinationSkin=new_skin,
        noMirror=True,
        surfaceAssociation="closestPoint",
        influenceAssociation=["name", "closestJoint", "oneToOne"],
    )
    print("Skin weights copied")
    return grp


def apply_renderman_material(export_group):
    """Connect the RenderMan PxrDisneyBsdf material to the export mesh."""
    mesh_dup = f"{export_group}|Body_USD"
    if not cmds.objExists(mesh_dup):
        print(f"WARNING: {mesh_dup} not found, skipping material assignment")
        return

    # The body mesh uses PxrDisneyBsdf1SG which has the RenderMan material
    # Assign the same shading group to the duplicate
    original_sg = "PxrDisneyBsdf1SG"
    if cmds.objExists(original_sg):
        cmds.sets(mesh_dup, edit=True, forceElement=original_sg)
        print(f"Assigned {original_sg} to {mesh_dup}")
    else:
        print(f"WARNING: {original_sg} not found")


def export_usd_with_renderman():
    """Export USD with RenderMan-compatible shading mode."""
    cmds.select(EXPORT_GROUP, hierarchy=True)

    # Try RenderMan shading mode first, fall back to alternatives
    shading_modes = [
        {"shadingMode": "useRegistry", "convertMaterialsTo": ["rendermanForMaya"]},
        {"shadingMode": "useRegistry", "convertMaterialsTo": ["UsdPreviewSurface"]},
        {"shadingMode": "displayColor"},
    ]

    for mode_kwargs in shading_modes:
        mode_desc = str(mode_kwargs)
        try:
            cmds.mayaUSDExport(
                file=str(OUTPUT_FILE),
                selection=True,
                exportSkels="auto",
                exportSkin="auto",
                exportBlendShapes=False,
                stripNamespaces=True,
                **mode_kwargs,
            )
            print(f"SUCCESS: Exported with {mode_desc}")
            return True
        except Exception as e:
            print(f"Mode {mode_desc} failed: {e}")
            continue

    # Last resort: export with basic materials flag
    try:
        cmds.mayaUSDExport(
            file=str(OUTPUT_FILE),
            selection=True,
            exportSkels="auto",
            exportSkin="auto",
            exportMaterials=True,
            exportBlendShapes=False,
            stripNamespaces=True,
        )
        print("SUCCESS: Exported with exportMaterials=True (fallback)")
        return True
    except Exception as e:
        print(f"All export modes failed: {e}")
        return False


def create_proxy():
    """Create a USD proxy in the scene for viewport/render testing."""
    proxy_transform = cmds.createNode("transform", name="Veteran_RenderMan_Proxy")
    proxy_shape = cmds.createNode("mayaUsdProxyShape", parent=proxy_transform)
    cmds.setAttr(proxy_shape + ".filePath", str(OUTPUT_FILE), type="string")
    cmds.setAttr(proxy_shape + ".primPath", "/", type="string")
    cmds.select(proxy_transform, replace=True)
    print(f"Created proxy: {proxy_transform} -> {proxy_shape}")
    return proxy_transform


# --- Main ---
print("=" * 60)
print("USD EXPORT WITH RENDERMAN MATERIALS")
print("=" * 60)

print("\n[1/4] Creating unified hierarchy...")
grp = create_unified_hierarchy()

print("\n[2/4] Applying RenderMan material...")
apply_renderman_material(grp)

print("\n[3/4] Exporting USD...")
exported = export_usd_with_renderman()

print("\n[4/4] Cleaning up and creating proxy...")
cmds.delete(EXPORT_GROUP)
if exported:
    proxy = create_proxy()
    file_size = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"\nOutput: {OUTPUT_FILE} ({file_size:.1f} MB)")
    print("Proxy created and selected - test RenderMan IPR now!")
else:
    print("Export failed - no proxy created")

print("\n" + "=" * 60)
