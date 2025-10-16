# USD Pipeline System - Technical Specification v1.4.0

> **Critical Feature**: Intelligent Maya → USD Conversion Pipeline  
> **Target User**: Character Riggers (Disney/Pixar Pipeline)  
> **Problem**: Maya's native USD export breaks rigs, materials, and geometry  
> **Solution**: Custom USD converter preserving ALL rigging data

---

## 🎯 **The Problem Statement**

### **Current Maya → USD Export Failures**

When exporting Maya (.mb/.ma) files to USD (.usd), **critical data is lost**:

1. **Skin Clusters** ❌
   - Entire skinning system disappears
   - Skin weights lost
   - Joint bindings broken
   - **Result**: Unusable character rig

2. **Mesh Geometry** ❌
   - Meshes corrupt or vanish
   - Topology breaks
   - UVs can be lost
   - **Result**: No geometry to animate

3. **RenderMan Materials** ❌
   - Shaders don't transfer
   - Textures missing
   - Material networks broken
   - **Result**: Grey untextured models

4. **Rig Controls** ❌
   - Control curves disappear
   - Custom attributes lost
   - Constraints broken
   - **Result**: No animation controls

### **Why This Matters**

- **Disney/Pixar** use USD throughout their pipeline
- **No tools exist** to solve this properly
- **Critical gap** for riggers entering the industry
- **Portfolio gold** for studio employment
- **Real production problem** affecting professionals

---

## 🛠️ **Technical Solution Architecture**

### **Three-Phase Conversion Pipeline**

```text
Maya Scene (.mb/.ma)
    ↓
[Phase 1: Maya Data Extraction]
    ↓
[Phase 2: USD Stage Construction]
    ↓
[Phase 3: Material Conversion]
    ↓
USD File (.usd/.usda/.usdc)
```

---

## 📊 **Phase 1: Maya Data Extraction**

### **1.1 Skin Cluster Data**

**Extract from Maya:**

```python
# Pseudocode for skin cluster extraction
for mesh in selected_meshes:
    skin_cluster = get_skin_cluster(mesh)
    if skin_cluster:
        # Extract joint influences
        joints = skin_cluster.get_influence_objects()
        
        # Extract skin weights per vertex
        for vertex_index in range(mesh.num_vertices):
            weights = skin_cluster.get_weights(vertex_index)
            joint_indices = skin_cluster.get_joint_indices(vertex_index)
            
        # Extract bind pose
        bind_pose = skin_cluster.get_bind_pre_matrix()
```

**Required Maya API:**

- `MFnSkinCluster` - Access skin cluster data
- `MItGeometry` - Iterate over vertices
- `MFnMesh` - Access mesh geometry
- `MDagPath` - Track joint hierarchy

**Data to Capture:**

- Joint names and hierarchy
- Skin weights per vertex (joint index + weight)
- Bind pose matrices
- Max influences per vertex
- Normalization mode

---

### **1.2 Mesh Geometry**

**Extract from Maya:**

```python
# Geometry data extraction
mesh_data = {
    'vertices': mesh.get_points(),  # 3D positions
    'normals': mesh.get_normals(),  # Vertex normals
    'uvs': mesh.get_uvs(),          # Texture coordinates
    'faces': mesh.get_face_vertex_indices(),
    'vertex_colors': mesh.get_vertex_colors() if exists
}
```

**Required Maya API:**

- `MFnMesh.getPoints()` - Vertex positions
- `MFnMesh.getNormals()` - Normal vectors
- `MFnMesh.getUVs()` - UV coordinates
- `MFnMesh.getTriangles()` - Face data

---

### **1.3 RenderMan Material Data**

**Extract from Maya:**

```python
# RenderMan shader network extraction
for material in scene_materials:
    if is_renderman_material(material):
        # Extract shader nodes
        shader_network = {
            'surface_shader': get_surface_shader(material),
            'displacement_shader': get_displacement_shader(material),
            'parameters': extract_shader_parameters(material),
            'textures': find_connected_textures(material),
            'connections': map_shader_connections(material)
        }
```

**RenderMan Specific:**

- PxrSurface shader parameters
- PxrDisplace shader data
- Texture file paths
- Shader network connections
- OSL shader code (if custom)

---

### **1.4 Rig Control Data**

**Extract from Maya:**

```python
# Rig control extraction
for control in rig_controls:
    control_data = {
        'curve_geometry': get_nurbs_curve_cvs(control),
        'transform': get_world_transform(control),
        'custom_attributes': get_custom_attrs(control),
        'constraints': get_constraints(control),
        'connections': get_attribute_connections(control),
        'color': get_override_color(control)
    }
```

**Required Data:**

- NURBS curve CVs (control shape)
- Transform matrices
- Custom attributes (float, enum, etc.)
- Constraint types and targets
- Driven key connections
- SDK (Set Driven Key) data

---

## 🏗️ **Phase 2: USD Stage Construction**

### **2.1 UsdSkel Structure**

**USD Skeletal Hierarchy:**

```text
/Character (SkelRoot)
    ├── /Skeleton (Skeleton)
    │   ├── joints (array of joint paths)
    │   ├── bindTransforms (bind pose matrices)
    │   └── restTransforms (rest pose matrices)
    ├── /Mesh (Mesh with skinning)
    │   ├── primvars:skel:jointIndices (per-vertex joint indices)
    │   ├── primvars:skel:jointWeights (per-vertex weights)
    │   └── skel:skeleton (relationship to /Character/Skeleton)
    ├── /Animation (SkelAnimation - if animated)
    │   ├── joints (matching skeleton joints)
    │   ├── translations (per-joint translations)
    │   ├── rotations (per-joint rotations)
    │   └── scales (per-joint scales)
    └── /Controls (Rig controls as separate layer)
        ├── /Control_01 (control curve geometry)
        ├── /Control_02
        └── ...
```

**Implementation:**

```python
from pxr import Usd, UsdGeom, UsdSkel, Sdf

# Create USD stage
stage = Usd.Stage.CreateNew(output_path)

# Create SkelRoot
skel_root = UsdSkel.Root.Define(stage, '/Character')

# Create Skeleton
skeleton = UsdSkel.Skeleton.Define(stage, '/Character/Skeleton')
skeleton.CreateJointsAttr(joint_names)
skeleton.CreateBindTransformsAttr(bind_matrices)
skeleton.CreateRestTransformsAttr(rest_matrices)

# Create skinned mesh
mesh = UsdGeom.Mesh.Define(stage, '/Character/Mesh')
mesh.CreatePointsAttr(vertices)
mesh.CreateFaceVertexIndicesAttr(face_indices)
mesh.CreateNormalsAttr(normals)

# Add skinning data
mesh.CreatePrimvar('skel:jointIndices', Sdf.ValueTypeNames.IntArray)
mesh.CreatePrimvar('skel:jointWeights', Sdf.ValueTypeNames.FloatArray)
binding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
binding.CreateSkeletonRel().SetTargets([skeleton.GetPath()])
```

---

### **2.2 Mesh with Skinning**

**USD Mesh Attributes:**

```python
# Mesh geometry
mesh.CreatePointsAttr(vertex_positions)  # 3D points
mesh.CreateNormalsAttr(normals)          # Normals
mesh.CreateFaceVertexCountsAttr(face_counts)  # Vertices per face
mesh.CreateFaceVertexIndicesAttr(indices)     # Face indices

# UV coordinates (primvar)
uv_primvar = mesh.CreatePrimvar(
    'st', 
    Sdf.ValueTypeNames.TexCoord2fArray,
    UsdGeom.Tokens.varying
)
uv_primvar.Set(uv_coordinates)

# Skinning primvars
joint_indices = mesh.CreatePrimvar(
    'skel:jointIndices',
    Sdf.ValueTypeNames.IntArray,
    UsdGeom.Tokens.vertex
)
joint_indices.SetElementSize(4)  # Max 4 influences per vertex
joint_indices.Set(flattened_joint_indices)

joint_weights = mesh.CreatePrimvar(
    'skel:jointWeights',
    Sdf.ValueTypeNames.FloatArray,
    UsdGeom.Tokens.vertex
)
joint_weights.SetElementSize(4)
joint_weights.Set(flattened_weights)
```

---

### **2.3 Rig Controls Preservation**

**Strategy**: Store rig controls as separate USD geometry

```python
# Create controls group
controls_xform = UsdGeom.Xform.Define(stage, '/Character/Controls')

for control_name, control_data in rig_controls.items():
    # Create curve geometry
    control_curve = UsdGeom.BasisCurves.Define(
        stage, 
        f'/Character/Controls/{control_name}'
    )
    
    # Set curve data
    control_curve.CreatePointsAttr(control_data['cvs'])
    control_curve.CreateCurveVertexCountsAttr(control_data['vertex_counts'])
    control_curve.CreateTypeAttr(UsdGeom.Tokens.cubic)
    control_curve.CreateBasisAttr(UsdGeom.Tokens.bspline)
    
    # Store custom attributes as USD metadata
    prim = control_curve.GetPrim()
    for attr_name, attr_value in control_data['custom_attrs'].items():
        prim.CreateAttribute(
            f'userProperties:{attr_name}',
            get_usd_type(attr_value)
        ).Set(attr_value)
```

---

## 🎨 **Phase 3: Material Conversion**

### **3.1 RenderMan → USD Material Translation**

#### Strategy 1: UsdPreviewSurface (Universal)

```python
from pxr import UsdShade

# Create material
material = UsdShade.Material.Define(stage, '/Materials/Character_Mat')

# Create PBR shader (UsdPreviewSurface)
pbr_shader = UsdShade.Shader.Define(
    stage, 
    '/Materials/Character_Mat/PBRShader'
)
pbr_shader.CreateIdAttr('UsdPreviewSurface')

# Map RenderMan parameters to PBR
pbr_shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(
    extract_diffuse_from_renderman(rman_shader)
)
pbr_shader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(
    extract_metallic_from_renderman(rman_shader)
)
pbr_shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(
    extract_roughness_from_renderman(rman_shader)
)

# Connect textures
texture_shader = create_texture_shader(stage, texture_path)
pbr_shader.CreateInput('diffuseColor').ConnectToSource(
    texture_shader.ConnectableAPI(),
    'rgb'
)
```

#### Strategy 2: Preserve RenderMan (Disney-specific)

```python
# Keep RenderMan shader network as UsdRi
rman_shader = UsdShade.Shader.Define(
    stage,
    '/Materials/Character_Mat/PxrSurface'
)
rman_shader.CreateIdAttr('PxrSurface')

# Preserve all RenderMan-specific parameters
for param_name, param_value in rman_parameters.items():
    rman_shader.CreateInput(param_name, get_type(param_value)).Set(param_value)
```

---

### **3.2 Texture Path Preservation**

**Challenge**: Maintain texture paths across pipeline

```python
# Strategy: Use asset paths with resolvers
texture_input = shader.CreateInput('file', Sdf.ValueTypeNames.Asset)

# Option 1: Relative paths
texture_input.Set(Sdf.AssetPath('textures/character_diffuse.png'))

# Option 2: Absolute paths (with pipeline resolver)
texture_input.Set(Sdf.AssetPath('/project/assets/character/textures/diffuse.png'))

# Option 3: USD Asset Resolver (Disney/Pixar style)
texture_input.Set(Sdf.AssetPath('asset://character/textures/diffuse'))
```

---

## 🎯 **UI Design: USD Pipeline Tab**

### **Location in Asset Manager**

```text
Asset Manager Window
├── Asset Library (tab)
├── Collections (tab)
├── USD Pipeline (tab) ← NEW!
└── Help (tab)
```

---

### **USD Pipeline Tab Layout**

```text
╔═══════════════════════════════════════════════════════════╗
║                 USD PIPELINE CREATOR                      ║
╠═══════════════════════════════════════════════════════════╣
║                                                            ║
║  [Section 1: Source Selection]                           ║
║  ┌────────────────────────────────────────────────────┐  ║
║  │ Source Maya Scene: [________________] [Browse...]  │  ║
║  │ ☑ Include Geometry                                 │  ║
║  │ ☑ Include Rigging (Skin Clusters)                 │  ║
║  │ ☑ Include Materials (RenderMan)                   │  ║
║  │ ☑ Include Rig Controls                            │  ║
║  └────────────────────────────────────────────────────┘  ║
║                                                            ║
║  [Section 2: USD Options]                                ║
║  ┌────────────────────────────────────────────────────┐  ║
║  │ USD Format: ● .usda (ASCII)  ○ .usdc (Binary)     │  ║
║  │ Output Path: [________________] [Browse...]        │  ║
║  │                                                     │  ║
║  │ Material Conversion:                               │  ║
║  │   ● UsdPreviewSurface (Universal)                 │  ║
║  │   ○ Preserve RenderMan (Disney/Pixar)            │  ║
║  │                                                     │  ║
║  │ Rigging Options:                                   │  ║
║  │   ☑ Create UsdSkel structure                      │  ║
║  │   ☑ Preserve skin weights                         │  ║
║  │   ☑ Include bind pose                             │  ║
║  │   Max Influences: [4▼]                            │  ║
║  └────────────────────────────────────────────────────┘  ║
║                                                            ║
║  [Section 3: Validation]                                 ║
║  ┌────────────────────────────────────────────────────┐  ║
║  │ Pre-Export Checks:                                 │  ║
║  │   ✓ Skin clusters detected: 3                     │  ║
║  │   ✓ Meshes found: 12                              │  ║
║  │   ✓ Materials found: 5 (RenderMan)               │  ║
║  │   ✓ Rig controls found: 47                        │  ║
║  │   ✓ No duplicate names                            │  ║
║  │   ⚠ Warning: Some UVs missing                     │  ║
║  └────────────────────────────────────────────────────┘  ║
║                                                            ║
║  [   Convert to USD   ]  [ Validate Only ]  [ Cancel ]   ║
║                                                            ║
╠═══════════════════════════════════════════════════════════╣
║  Progress: [████████████████████─────] 75%               ║
║  Status: Converting materials...                          ║
╚═══════════════════════════════════════════════════════════╝
```

---

## 🚀 **Implementation Roadmap**

### **Milestone 1: Core USD Export (Week 1-2)**

- [ ] Maya scene parsing
- [ ] Basic USD stage creation
- [ ] Mesh geometry export
- [ ] UV and normal preservation

### **Milestone 2: Rigging Support (Week 3-4)**

- [ ] Skin cluster extraction
- [ ] UsdSkel structure creation
- [ ] Bind pose preservation
- [ ] Skin weight export

### **Milestone 3: Material Conversion (Week 5-6)**

- [ ] RenderMan shader detection
- [ ] UsdPreviewSurface conversion
- [ ] Texture path handling
- [ ] Material network reconstruction

### **Milestone 4: Rig Controls (Week 7-8)**

- [ ] Control curve extraction
- [ ] Custom attribute preservation
- [ ] Constraint mapping
- [ ] USD control layer creation

### **Milestone 5: UI Integration (Week 9-10)**

- [ ] USD Pipeline tab creation
- [ ] Source selection UI
- [ ] Options configuration
- [ ] Progress feedback
- [ ] Validation system

### **Milestone 6: Testing & Polish (Week 11-12)**

- [ ] Test with various rig types
- [ ] RenderMan material testing
- [ ] Performance optimization
- [ ] Documentation
- [ ] Disney-style workflow validation

---

## 📚 **Required Technologies**

### **Maya API**

- `maya.OpenMaya` - Core Maya API
- `maya.OpenMayaAnim` - Animation/Rigging API
- `maya.cmds` - Command-based access

### **USD (Pixar)**

- `pxr.Usd` - Core USD API
- `pxr.UsdGeom` - Geometry schemas
- `pxr.UsdSkel` - Skeletal animation
- `pxr.UsdShade` - Material/Shader schemas
- `pxr.Sdf` - Scene description foundation

### **RenderMan (Optional)**

- RenderMan for Maya plugin
- RIS shader network access

---

## 🎯 **Success Metrics**

### **Technical Success**

- ✅ 100% skin weight preservation
- ✅ 100% mesh topology preservation
- ✅ 90%+ material conversion accuracy
- ✅ All rig controls preserved
- ✅ No data loss in conversion

### **Portfolio Success**

- ✅ Demonstrates USD pipeline expertise
- ✅ Shows Maya API mastery
- ✅ Solves REAL production problem
- ✅ Unique tool - no competitors
- ✅ Disney-ready portfolio piece

---

## 💼 **Career Impact Statement**

> **"I built a production-ready Maya → USD conversion pipeline that preserves character rigging data, addressing a critical gap in Disney/Pixar workflows. The tool maintains skin clusters, rig controls, and RenderMan materials through intelligent USD stage construction using UsdSkel and UsdShade schemas. This demonstrates my understanding of modern animation pipelines and technical problem-solving for industry-standard workflows."**

**Interview Talking Points:**

1. "Solved Maya→USD rigging conversion that native tools can't handle"
2. "Implemented UsdSkel pipeline preserving 100% of skin weight data"
3. "Built RenderMan→USD material converter for Disney pipeline compatibility"
4. "Created first-of-its-kind rig control preservation system in USD"
5. "Developed production tool addressing real rigger pain points"

---

## 📖 **References**

### **USD Documentation**

- [Official USD Documentation](https://openusd.org/)
- [UsdSkel Schema](https://openusd.org/release/api/usd_skel_page_front.html)
- [UsdShade Schema](https://openusd.org/release/api/usd_shade_page_front.html)

### **Maya Documentation**

- [Maya Python API](https://help.autodesk.com/view/MAYAUL/2025/ENU/)
- [MFnSkinCluster](https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=Maya_SDK_py_ref_class_open_maya_anim_1_1_m_fn_skin_cluster_html)

### **Industry Standards**

- [Disney Animation Studios - USD Workflow](https://www.disneyanimation.com/technology/innovations/universal-scene-description)
- [Pixar USD Forum](https://groups.google.com/g/usd-interest)

---

**Version**: 1.0  
**Date**: October 15, 2025  
**Author**: Mike Stumbo (ChEeP)  
**Target Release**: Asset Manager v1.4.0
