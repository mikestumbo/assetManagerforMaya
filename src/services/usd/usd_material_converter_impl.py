# -*- coding: utf-8 -*-
"""
USD Material Converter Implementation
Converts Maya materials (including RenderMan) to USD

Compatibility:
- Maya 2026.3
- MayaUSD 0.34.5
- RenderMan 27 (Pixar)

Author: Mike Stumbo
Version: 1.5.0
"""

from pathlib import Path
from typing import Optional, Dict, Any
import logging

from src.core.interfaces.usd_material_converter import IUSDMaterialConverter

# Conditional USD import
try:
    from pxr import Usd, Sdf, UsdShade, Gf  # type: ignore

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    Usd: Any = None  # type: ignore


class USDMaterialConverterImpl(IUSDMaterialConverter):
    """
    USD Material Converter Implementation

    Clean Code: Single Responsibility - Convert materials to USD
    Disney/Pixar Critical: RenderMan material preservation
    """

    def __init__(self):
        """Initialize material converter"""
        self.logger = logging.getLogger(__name__)

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use in USD paths"""
        # Replace invalid USD path characters
        safe_name = name.replace("|", "_").replace(":", "_").replace(" ", "_")
        # Ensure name doesn't start with a digit
        if safe_name and safe_name[0].isdigit():
            safe_name = f"mat_{safe_name}"
        return safe_name

    def convert_to_preview_surface(
        self, material_name: str, material_data: Dict[str, Any], usd_stage: Any  # pxr.Usd.Stage
    ) -> Optional[Any]:  # pxr.UsdShade.Material
        """
        Convert Maya material to UsdPreviewSurface with robust error handling

        Args:
            material_name: Name for USD material
            material_data: Material properties from Maya
            usd_stage: USD stage to create material in

        Returns:
            Created UsdShade.Material or None if failed
        """
        if not USD_AVAILABLE:
            self.logger.error("USD libraries not available")
            return None

        # Sanitize material name for USD path compliance
        safe_name = self._sanitize_name(material_name)
        material_path = f"/Materials/{safe_name}"

        try:
            # Validate stage - catch exceptions from invalid stages
            try:
                if usd_stage is None:
                    self.logger.error(f"USD stage is None for {safe_name}")
                    return None
                pseudo_root = usd_stage.GetPseudoRoot()
                if not pseudo_root or not pseudo_root.IsValid():
                    self.logger.error(f"Invalid pseudo root for {safe_name}")
                    return None
            except Exception as stage_err:
                self.logger.error(f"Stage validation failed for {safe_name}: {stage_err}")
                return None

            # Check if material path already exists
            existing_prim = usd_stage.GetPrimAtPath(material_path)
            if existing_prim and existing_prim.IsValid():
                self.logger.debug(f"Material {safe_name} already exists, reusing")
                return UsdShade.Material(existing_prim)

            # Create material
            usd_material = UsdShade.Material.Define(usd_stage, material_path)
            if not usd_material:
                self.logger.error(f"Material.Define returned None for {safe_name}")
                return None

            material_prim = usd_material.GetPrim()
            if not material_prim or not material_prim.IsValid():
                self.logger.error(f"Material prim invalid for {safe_name}")
                return None

            # Create shader
            shader_path = f"{material_path}/PreviewSurface"
            shader = UsdShade.Shader.Define(usd_stage, shader_path)
            if not shader:
                self.logger.error(f"Shader.Define returned None for {safe_name}")
                return None

            shader_prim = shader.GetPrim()
            if not shader_prim or not shader_prim.IsValid():
                self.logger.error(f"Shader prim invalid for {safe_name}")
                return None

            # Set shader ID
            shader.CreateIdAttr("UsdPreviewSurface")

            # Set basic properties with safe value handling
            if "diffuse_color" in material_data and material_data["diffuse_color"]:
                color = material_data["diffuse_color"]
                if isinstance(color, (list, tuple)) and len(color) >= 3:
                    try:
                        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                            Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))
                        )
                    except Exception as e:
                        self.logger.debug(f"Failed to set diffuse color: {e}")

            if "metallic" in material_data and material_data["metallic"] is not None:
                try:
                    metallic = float(material_data["metallic"])
                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
                except Exception as e:
                    self.logger.debug(f"Failed to set metallic: {e}")

            if "roughness" in material_data and material_data["roughness"] is not None:
                try:
                    roughness = float(material_data["roughness"])
                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
                except Exception as e:
                    self.logger.debug(f"Failed to set roughness: {e}")

            # Validate prims are still valid before connecting
            if not usd_material.GetPrim().IsValid() or not shader.GetPrim().IsValid():
                self.logger.error(f"Prims became invalid during creation for {safe_name}")
                return None

            # Create shader output and connect to material
            shader_output = shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
            if not shader_output:
                self.logger.error(f"Failed to create shader output for {safe_name}")
                return None

            # Create material surface output and connect
            material_surface = usd_material.CreateSurfaceOutput()
            if not material_surface:
                self.logger.error(f"Failed to create material surface output for {safe_name}")
                return None

            # Connect with error handling
            try:
                material_surface.ConnectToSource(shader_output)
            except Exception as conn_err:
                self.logger.error(f"ConnectToSource failed for {safe_name}: {conn_err}")
                return None

            self.logger.info(f"Created USD Preview Surface material: {safe_name}")
            return usd_material

        except Exception as e:
            self.logger.error(
                f"Failed to create USD Preview Surface material {material_name}: {e}"
            )
            import traceback

            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    def convert_renderman_material(
        self,
        material_name: str,
        renderman_params: Dict[str, Any],
        usd_stage: Any,
        usd_service: Optional[Any] = None,  # Kept for API compatibility, not used
    ) -> Optional[Any]:
        """
        Convert RenderMan material to USD using native RenderMan-USD shaders

        Both RenderMan and USD are Pixar products - they work together natively!
        Creates ri:PxrSurface, ri:PxrDisneyBsdf, etc. shaders directly in USD.

        Args:
            material_name: Name for USD material
            renderman_params: RenderMan shader parameters
            usd_stage: USD stage to create material in
            usd_service: Unused (kept for API compatibility)

        Returns:
            Created UsdShade.Material with RenderMan shader
        """
        if not USD_AVAILABLE:
            self.logger.error("USD libraries not available")
            return None

        try:
            # Use native RenderMan-USD conversion
            return self._convert_renderman_native(material_name, renderman_params, usd_stage)

        except Exception as e:
            self.logger.error(f"Failed to create RenderMan USD material {material_name}: {e}")
            return None

    def _convert_renderman_native(
        self, material_name: str, renderman_params: Dict[str, Any], usd_stage: Any
    ) -> Optional[Any]:
        """
        Convert RenderMan material to native USD RenderMan shaders

        Both RenderMan and USD are Pixar products - they share the same shader
        ecosystem. This creates ri:PxrSurface, ri:PxrDisneyBsdf, etc. directly.

        Args:
            material_name: Name for USD material
            renderman_params: RenderMan shader parameters
            usd_stage: USD stage to create material in

        Returns:
            Created UsdShade.Material with RenderMan shader
        """
        try:
            # Validate stage
            if not usd_stage or not usd_stage.GetPseudoRoot():
                self.logger.error(f"Invalid USD stage provided for {material_name}")
                return None

            # Sanitize material name
            safe_name = self._sanitize_name(material_name)
            material_path = f"/Materials/{safe_name}"

            # Check if material path already exists
            existing_prim = usd_stage.GetPrimAtPath(material_path)
            if existing_prim and existing_prim.IsValid():
                self.logger.debug(f"Material {safe_name} already exists, reusing")
                return UsdShade.Material(existing_prim)

            # Create material
            usd_material = UsdShade.Material.Define(usd_stage, material_path)
            if not usd_material or not usd_material.GetPrim().IsValid():
                self.logger.error(f"Failed to create USD material prim for {safe_name}")
                return None

            # Determine RenderMan shader type from parameters
            shader_type = self._determine_renderman_shader_type(material_name, renderman_params)

            # Create RenderMan shader
            shader = UsdShade.Shader.Define(usd_stage, f"{material_path}/Shader")
            if not shader or not shader.GetPrim().IsValid():
                self.logger.error(f"Failed to create USD shader prim for {safe_name}")
                return None

            # Set RenderMan shader ID (ri: prefix for RenderMan)
            shader.CreateIdAttr(f"ri:{shader_type}")

            # Create shader output (RenderMan uses "out")
            shader_output = shader.CreateOutput("out", Sdf.ValueTypeNames.Token)

            # Set RenderMan parameters
            self._set_renderman_parameters_safe(shader, renderman_params)

            # Connect shader to material surface output (ri context)
            surface_output = usd_material.CreateSurfaceOutput("ri")
            surface_output.ConnectToSource(shader_output)

            self.logger.info(f"[OK] Created RenderMan USD material: {safe_name} ({shader_type})")
            return usd_material

        except Exception as e:
            self.logger.error(f"Failed to create RenderMan USD material {material_name}: {e}")
            return None

    # LEGACY: Keep as backup conversion method
    def _convert_renderman_manual(
        self, material_name: str, renderman_params: Dict[str, Any], usd_stage: Any
    ) -> Optional[Any]:
        """
        Convert RenderMan material using manual parameter mapping

        Args:
            material_name: Name for USD material
            renderman_params: RenderMan shader parameters
            usd_stage: USD stage to create material in

        Returns:
            Created UsdShade.Material with RenderMan shader
        """
        try:
            # Validate stage
            if not usd_stage or not usd_stage.GetPseudoRoot():
                self.logger.error(f"Invalid USD stage provided for {material_name}")
                return None

            # Check if material path already exists
            material_path = f"/Materials/{material_name}"
            existing_prim = usd_stage.GetPrimAtPath(material_path)
            if existing_prim and existing_prim.IsValid():
                self.logger.warning(
                    f"Material path {material_path} already exists, skipping {material_name}"
                )
                return existing_prim

            # Note: Materials scope is created by the caller (usd_export_service_impl)

            # Create material with unique path to avoid conflicts
            usd_material = UsdShade.Material.Define(usd_stage, material_path)

            # Validate material was created successfully
            if not usd_material or not usd_material.GetPrim().IsValid():
                self.logger.error(f"Failed to create valid USD material prim for {material_name}")
                return None

            # Determine RenderMan shader type from material name and parameters
            shader_type = self._determine_renderman_shader_type(material_name, renderman_params)

            # Create RenderMan shader
            shader = UsdShade.Shader.Define(usd_stage, f"{material_path}/Shader")

            # Validate shader was created successfully
            if not shader or not shader.GetPrim().IsValid():
                self.logger.error(f"Failed to create valid USD shader prim for {material_name}")
                return None

            # Set RenderMan shader ID
            shader.CreateIdAttr(f"ri:{shader_type}")

            # Create output for RenderMan shader - this must be done BEFORE connecting
            # RenderMan shaders use "out" as their standard output
            shader_output = shader.CreateOutput("out", Sdf.ValueTypeNames.Token)

            # Set RenderMan parameters with better error handling
            self._set_renderman_parameters_safe(shader, renderman_params)

            # Connect shader to material surface output
            surface_output = usd_material.CreateSurfaceOutput("ri")
            surface_output.ConnectToSource(shader_output)

            # Validate the connection worked
            if not surface_output.IsValid():
                self.logger.error(
                    f"Failed to create valid surface output connection for {material_name}"
                )
                return None

            # Final validation - check that everything is still valid
            if not usd_material.GetPrim().IsValid() or not shader.GetPrim().IsValid():
                self.logger.error(
                    f"USD prims became invalid after material creation for {material_name}"
                )
                return None

            self.logger.info(f"Created RenderMan USD material: {material_name} ({shader_type})")
            return usd_material

        except Exception as e:
            self.logger.error(f"Failed to create RenderMan USD material {material_name}: {e}")
            return None

    def _determine_renderman_shader_type(self, material_name: str, params: Dict[str, Any]) -> str:
        """Determine RenderMan shader type from material name and parameters"""
        # Check material name for shader type hints
        name_lower = material_name.lower()

        if "bsdf" in name_lower:
            return "PxrBsdf"
        elif "surface" in name_lower:
            return "PxrSurface"
        elif "disney" in name_lower:
            return "PxrDisneyBsdf"
        elif "hair" in name_lower:
            return "PxrHair"
        elif "volume" in name_lower:
            return "PxrVolume"
        elif "light" in name_lower:
            return "PxrLight"

        # Check parameters for shader type hints
        if any(key in params for key in ["diffuseColor", "diffuseTint", "specularColor"]):
            return "PxrSurface"
        elif any(key in params for key in ["hairColor", "melanin"]):
            return "PxrHair"
        elif any(key in params for key in ["density", "scatterColor"]):
            return "PxrVolume"

        # Default to PxrSurface for general materials
        return "PxrSurface"

    def _set_renderman_parameters_safe(self, shader: Any, params: Dict[str, Any]) -> None:
        """Safely set RenderMan parameters on USD shader"""
        for param_name, param_value in params.items():
            try:
                # Skip complex or unsupported parameter types
                if self._is_supported_renderman_param(param_name, param_value):
                    usd_param_name = self._convert_renderman_param_name(param_name)
                    usd_type = self._get_usd_type_for_renderman_param(param_name, param_value)

                    if usd_type:
                        shader_input = shader.CreateInput(usd_param_name, usd_type)
                        # Handle different data types appropriately
                        processed_value = self._process_renderman_param_value(param_value)
                        shader_input.Set(processed_value)
                        self.logger.debug(
                            f"Set RenderMan parameter: {param_name} = {processed_value}"
                        )
                    else:
                        self.logger.debug(f"Skipping parameter {param_name}: unsupported type")
                else:
                    self.logger.debug(f"Skipping parameter {param_name}: not supported")

            except Exception as e:
                self.logger.warning(f"Failed to set RenderMan parameter {param_name}: {e}")

    def _is_supported_renderman_param(self, param_name: str, param_value: Any) -> bool:
        """Check if a RenderMan parameter is supported for USD conversion"""
        # Skip connection-related parameters
        if param_name.endswith("Connection") or "connection" in param_name.lower():
            return False

        # Skip complex data types that USD can't handle
        if isinstance(param_value, (list, tuple)) and len(param_value) > 4:
            return False

        # Skip None values
        if param_value is None:
            return False

        return True

    def _process_renderman_param_value(self, value: Any) -> Any:
        """Process RenderMan parameter value for USD compatibility"""
        if isinstance(value, (list, tuple)):
            # Convert tuples to lists for USD
            if len(value) == 3:
                return list(value)  # RGB colors
            elif len(value) == 4:
                return list(value)  # RGBA colors
            else:
                return value
        elif isinstance(value, (int, float, str, bool)):
            return value
        else:
            # For unsupported types, try to convert to string
            return str(value)

    def _convert_renderman_param_name(self, param_name: str) -> str:
        """Convert RenderMan parameter name to USD-compatible name"""
        # RenderMan uses camelCase, USD uses camelCase too
        # Just ensure it's valid
        return param_name

    def _find_renderman_shader_output(self, shader: Any) -> Optional[Any]:
        """Find a valid output on a RenderMan shader"""
        output_names = ["out", "surface", "bxdf_out", "result", "output", "bxdf", "shader"]

        for output_name in output_names:
            try:
                shader_output = shader.GetOutput(output_name)
                if shader_output and shader_output.IsValid():
                    self.logger.debug(f"Found valid RenderMan output: {output_name}")
                    return shader_output
            except Exception as e:
                self.logger.debug(f"Output {output_name} not found: {e}")
                continue

        return None

    def _get_usd_type_for_renderman_param(
        self, param_name: str, param_value: Any
    ) -> Optional[Any]:
        """Get USD type for RenderMan parameter with better type detection"""
        try:
            if isinstance(param_value, (list, tuple)):
                if len(param_value) == 3:
                    # Check if it's a color (values between 0-1)
                    if all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in param_value):
                        return Sdf.ValueTypeNames.Color3f
                    else:
                        return Sdf.ValueTypeNames.Vector3f
                elif len(param_value) == 4:
                    # Check if it's a color with alpha
                    if all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in param_value):
                        return Sdf.ValueTypeNames.Color4f
                    else:
                        return Sdf.ValueTypeNames.Vector4f
                else:
                    return None
            elif isinstance(param_value, float):
                return Sdf.ValueTypeNames.Float
            elif isinstance(param_value, int):
                return Sdf.ValueTypeNames.Int
            elif isinstance(param_value, bool):
                return Sdf.ValueTypeNames.Bool
            elif isinstance(param_value, str):
                return Sdf.ValueTypeNames.String
            else:
                return None
        except Exception as e:
            self.logger.debug(f"Error determining USD type for {param_name}: {e}")
            return None

    def map_texture_inputs(
        self, maya_texture_path: Path, usd_output_path: Path, copy_textures: bool = False
    ) -> str:
        """
        Map Maya texture file path to USD texture reference

        Args:
            maya_texture_path: Original Maya texture path
            usd_output_path: USD file output location
            copy_textures: Whether to copy textures to USD location

        Returns:
            USD texture path (relative or absolute)
        """
        if copy_textures:
            # Copy texture to USD directory
            usd_texture_dir = usd_output_path.parent / "textures"
            usd_texture_dir.mkdir(exist_ok=True)

            usd_texture_path = usd_texture_dir / maya_texture_path.name
            try:
                import shutil

                shutil.copy2(maya_texture_path, usd_texture_path)
                # Return relative path
                return f"textures/{maya_texture_path.name}"
            except Exception as e:
                self.logger.warning(f"Failed to copy texture {maya_texture_path}: {e}")
                return str(maya_texture_path)
        else:
            # Return absolute path
            return str(maya_texture_path)

    def bind_material_to_geometry(
        self, geometry_prim: Any, material: Any  # pxr.Usd.Prim  # pxr.UsdShade.Material
    ) -> bool:
        """
        Bind material to geometry

        Args:
            geometry_prim: USD geometry prim
            material: USD material to bind

        Returns:
            True if successful
        """
        if not USD_AVAILABLE:
            self.logger.error("USD libraries not available")
            return False

        try:
            # Bind material to geometry
            UsdShade.MaterialBindingAPI.Apply(geometry_prim)
            UsdShade.MaterialBindingAPI(geometry_prim).Bind(material)

            self.logger.debug(f"Bound material to geometry: {geometry_prim.GetPath()}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to bind material to geometry: {e}")
            return False

    def get_supported_maya_shaders(self) -> list[str]:
        """
        Get list of supported Maya shader types

        Returns:
            List of shader type names supported by this converter (RenderMan 27 compatible)
        """
        return [
            # Standard Maya shaders
            "lambert",
            "blinn",
            "phong",
            "phongE",
            "anisotropic",
            "layeredShader",
            "rampShader",
            "shadingMap",
            "surfaceShader",
            "useBackground",
            # RenderMan 27 Surface Shaders
            "PxrSurface",  # Primary physically-based surface shader
            "PxrMarschnerHair",  # Hair and fur shader
            "PxrVolume",  # Volume shader
            "PxrLMDiffuse",  # LightMixer diffuse
            "PxrLMGlass",  # LightMixer glass
            "PxrLMMetal",  # LightMixer metal
            "PxrLMPlastic",  # LightMixer plastic
            "PxrLMSkin",  # LightMixer skin (subsurface)
            "PxrLMSubsurface",  # LightMixer subsurface
            "PxrDisplace",  # Displacement shader
            # RenderMan 27 Patterns & Textures
            "PxrTexture",  # Primary texture lookup
            "PxrPtexture",  # Ptex texture lookup
            "PxrMultiTexture",  # Multi-texture blending
            "PxrBump",  # Bump mapping
            "PxrNormalMap",  # Normal mapping
            "PxrRoundCube",  # Procedural rounded cube
            "PxrFractal",  # Fractal noise
            "PxrWorley",  # Worley/cellular noise
            "PxrVoronoise",  # Voronoi noise
            "PxrChecker",  # Checker pattern
            "PxrRamp",  # Color ramp
            "PxrHairColor",  # Hair color generator
            "PxrDirt",  # Ambient occlusion/dirt
            "PxrFlakes",  # Metallic flakes
            # RenderMan 27 Utility Nodes
            "PxrBlend",  # Blend between inputs
            "PxrLayerSurface",  # Layer surface shader
            "PxrLayerMixer",  # Mix shader layers
            "PxrMatteID",  # Matte ID for compositing
            "PxrVariable",  # Custom variable
            "PxrToFloat",  # Convert to float
            "PxrToFloat3",  # Convert to float3
            "PxrHSL",  # HSL color adjustment
            "PxrColorCorrect",  # Color correction
            "PxrExposure",  # Exposure control
            "PxrGamma",  # Gamma correction
            "PxrInvert",  # Invert values
            "PxrClamp",  # Clamp values
            "PxrMix",  # Mix/lerp utility
            "PxrRemap",  # Remap value ranges
            "PxrThreshold",  # Threshold values
            # RenderMan 27 Light Filters
            "PxrIntMultLightFilter",  # Intensity multiplier
            "PxrBlockerLightFilter",  # Light blocker
            "PxrRodLightFilter",  # Rod light filter
            "PxrCookieLightFilter",  # Cookie/gobo
            "PxrGoboLightFilter",  # Gobo projection
            "PxrRampLightFilter",  # Light ramp
            "PxrBarnLightFilter",  # Barn door filter
            # RenderMan 27 Lights
            "PxrDomeLight",  # Environment/HDRI light
            "PxrRectLight",  # Rectangular area light
            "PxrDiskLight",  # Disk area light
            "PxrSphereLight",  # Sphere area light
            "PxrCylinderLight",  # Cylinder area light
            "PxrDistantLight",  # Directional/distant light
            "PxrPortalLight",  # Portal light for indoor scenes
            "PxrMeshLight",  # Mesh-based light
        ]

    def validate_texture_paths(self, texture_paths: list[Path]) -> tuple[list[Path], list[Path]]:
        """
        Validate texture file paths exist

        Args:
            texture_paths: List of texture paths to validate

        Returns:
            (valid_paths, invalid_paths)
        """
        valid_paths = []
        invalid_paths = []

        for texture_path in texture_paths:
            try:
                # Convert to Path if not already
                path = Path(texture_path) if not isinstance(texture_path, Path) else texture_path

                # Check if file exists
                if path.exists() and path.is_file():
                    valid_paths.append(path)
                else:
                    invalid_paths.append(path)
                    self.logger.warning(f"Texture file not found: {path}")

            except Exception as e:
                invalid_paths.append(texture_path)
                self.logger.warning(f"Error validating texture path {texture_path}: {e}")

        return valid_paths, invalid_paths
