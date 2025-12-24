# CloudCreator - Blender Add-on
# Copyright (C) 2024 plainprince
# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "CloudCreator",
    "author": "plainprince",
    "version": (1, 0, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > CloudCreator",
    "description": "CloudCreator by plainprince",
    "category": "3D View",
}

import bpy
import os
import random
from bpy.props import FloatProperty, IntProperty, BoolProperty, EnumProperty
from bpy.types import Panel, Operator, PropertyGroup


def get_addon_path():
    """Get the path to the addon directory."""
    return os.path.dirname(os.path.realpath(__file__))


def get_assets_path():
    """Get the path to the assets.blend file."""
    return os.path.join(get_addon_path(), "assets", "assets.blend")


class CloudCreatorProperties(PropertyGroup):
    """Properties for CloudCreator settings."""
    
    add_cloud: BoolProperty(
        name="Add Cloud",
        description="Add a cloud mesh",
        default=True,
    )
    
    seed: IntProperty(
        name="Seed",
        description="Random seed for cloud generation",
        default=0,
        min=0,
        max=9999,
    )
    
    multiple: BoolProperty(
        name="Multiple",
        description="Generate multiple clouds (cloud layer) instead of a single cloud",
        default=False,
    )
    
    cloud_type: EnumProperty(
        name="Cloud Type",
        description="Type of single cloud to generate",
        items=[
            ('single', "Single", "Flat single cloud"),
            ('sphere', "Sphere", "Spherical cloud"),
        ],
        default='single',
    )
    
    cloud_spread: FloatProperty(
        name="Cloud Spread",
        description="Size of the cloud layer in meters (WARNING: Large values with raytracing can be very slow)",
        default=100.0,
        min=1.0,
        max=1000.0,
        step=1000,
        precision=1,
        subtype='DISTANCE',
        unit='LENGTH',
    )
    
    shadow_spread: FloatProperty(
        name="Shadow Spread",
        description="Size of the cloud shadow plane in meters",
        default=100.0,
        min=10.0,
        max=1000.0,
        step=1000,
        precision=1,
        subtype='DISTANCE',
        unit='LENGTH',
    )
    
    cloud_height: FloatProperty(
        name="Cloud Height",
        description="Height of the clouds in meters",
        default=10.0,
        min=1.0,
        max=500.0,
        step=100,
        precision=1,
        subtype='DISTANCE',
        unit='LENGTH',
    )
    
    cloud_shadows: BoolProperty(
        name="Cloud Shadows",
        description="Enable shadows for clouds",
        default=True,
    )
    
    add_light: BoolProperty(
        name="Add Light",
        description="Add an area light above the shadow plane",
        default=False,
    )


def rename_material_nodes(material, prefix="CloudCreator"):
    """Rename all nodes in a material to have the CloudCreator prefix."""
    if not material or not material.use_nodes:
        return
    
    for node in material.node_tree.nodes:
        if not node.name.startswith(prefix):
            node.name = f"{prefix}_{node.name}"
            node.label = node.name


def set_random_mapping_locations(material, seed):
    """Set random mapping location values based on seed for all mapping nodes."""
    if not material or not material.use_nodes:
        return
    
    random.seed(seed)
    
    for node in material.node_tree.nodes:
        if node.type == 'MAPPING':
            node.inputs['Location'].default_value[0] = random.uniform(-1000, 1000)
            node.inputs['Location'].default_value[1] = random.uniform(-1000, 1000)
            node.inputs['Location'].default_value[2] = random.uniform(-1000, 1000)


def setup_cloud_visibility(obj):
    """Configure visibility settings for cloud objects (disable shadows for performance)."""
    obj.visible_shadow = False


def setup_shadow_plane_visibility(obj):
    """Configure visibility settings for shadow plane (invisible to camera)."""
    obj.visible_camera = False


def load_cloud_mesh(context, mesh_name):
    """Load a cloud mesh from the assets.blend file."""
    props = context.scene.cloudcreator
    assets_path = get_assets_path()
    
    if not os.path.exists(assets_path):
        return None, f"Assets file not found: {assets_path}"
    
    # Load the object from the blend file
    with bpy.data.libraries.load(assets_path, link=False) as (data_from, data_to):
        if mesh_name in data_from.objects:
            data_to.objects = [mesh_name]
        else:
            return None, f"Object '{mesh_name}' not found in assets.blend"
    
    # Link the object to the scene
    if data_to.objects and data_to.objects[0]:
        obj = data_to.objects[0]
        context.collection.objects.link(obj)
        
        # Rename to CloudCreator prefix
        if mesh_name == "cloud_layer":
            obj.name = "CloudCreator_Layer"
        elif mesh_name == "cloud_single":
            obj.name = "CloudCreator_Single"
        elif mesh_name == "cloud_sphere":
            obj.name = "CloudCreator_Sphere"
        else:
            obj.name = f"CloudCreator_{mesh_name}"
        
        # Set location to cloud height
        obj.location.z = props.cloud_height
        
        # If multiple (cloud_layer), scale based on cloud_spread (X and Y only)
        if props.multiple and mesh_name == "cloud_layer":
            # cloud_layer base size is 10m, calculate scale factor to reach target spread
            base_size = 10.0
            scale_factor = props.cloud_spread / base_size
            obj.scale = (scale_factor, scale_factor, 1.0)
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Configure visibility settings for performance
        setup_cloud_visibility(obj)
        
        # Process all materials on the object
        for mat in obj.data.materials:
            if mat:
                rename_material_nodes(mat, "CloudCreator")
                set_random_mapping_locations(mat, props.seed)
        
        return obj, None
    
    return None, "Failed to load object"


def create_cloud_shadow_plane(context):
    """Create a plane with cloud shadow material."""
    props = context.scene.cloudcreator
    
    # Initialize random with seed
    random.seed(props.seed)
    
    # Use shadow_spread for plane size
    plane_size = props.shadow_spread
    
    # Create plane
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, props.cloud_height))
    plane = context.active_object
    plane.name = "CloudCreator_Shadow"
    
    # Scale based on size and apply scale
    plane.scale = (plane_size, plane_size, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Configure visibility settings (invisible to camera)
    setup_shadow_plane_visibility(plane)
    
    # Create material
    mat = bpy.data.materials.new(name="CloudCreator_ShadowMaterial")
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    nodes.clear()
    
    # Create nodes
    # Output node
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    node_output.location = (600, 0)
    node_output.name = "CloudCreator_Output"
    
    # Principled BSDF
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.location = (300, 0)
    node_bsdf.name = "CloudCreator_BSDF"
    node_bsdf.inputs['Base Color'].default_value = (0, 0, 0, 1)
    
    # Color Ramp
    node_ramp = nodes.new(type='ShaderNodeValToRGB')
    node_ramp.location = (0, 0)
    node_ramp.name = "CloudCreator_ColorRamp"
    # Set color ramp stops: black at 0.4, white at 0.6
    node_ramp.color_ramp.elements[0].position = 0.4
    node_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    node_ramp.color_ramp.elements[1].position = 0.6
    node_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    
    # Noise Texture
    node_noise = nodes.new(type='ShaderNodeTexNoise')
    node_noise.location = (-200, 0)
    node_noise.name = "CloudCreator_Noise"
    node_noise.inputs['Scale'].default_value = 1.0
    node_noise.inputs['Detail'].default_value = 5.0
    
    # Mapping node
    node_mapping = nodes.new(type='ShaderNodeMapping')
    node_mapping.location = (-400, 0)
    node_mapping.name = "CloudCreator_Mapping"
    # Set seeded random location for each axis
    node_mapping.inputs['Location'].default_value[0] = random.uniform(-1000, 1000)
    node_mapping.inputs['Location'].default_value[1] = random.uniform(-1000, 1000)
    node_mapping.inputs['Location'].default_value[2] = random.uniform(-1000, 1000)
    
    # Texture Coordinate node
    node_texcoord = nodes.new(type='ShaderNodeTexCoord')
    node_texcoord.location = (-600, 0)
    node_texcoord.name = "CloudCreator_TexCoord"
    
    # Link nodes
    links.new(node_texcoord.outputs['Generated'], node_mapping.inputs['Vector'])
    links.new(node_mapping.outputs['Vector'], node_noise.inputs['Vector'])
    links.new(node_noise.outputs['Fac'], node_ramp.inputs['Fac'])
    links.new(node_ramp.outputs['Color'], node_bsdf.inputs['Alpha'])
    links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])
    
    # Assign material to plane
    plane.data.materials.append(mat)
    
    return plane


def create_cloud_light(context, shadow_plane):
    """Create an area light above the shadow plane."""
    import math
    props = context.scene.cloudcreator
    
    # Create area light slightly above the shadow plane
    light_height = props.cloud_height + 0.5
    bpy.ops.object.light_add(type='AREA', location=(0, 0, light_height))
    light = context.active_object
    light.name = "CloudCreator_Light"
    
    # Configure the light
    light.data.name = "CloudCreator_AreaLight"
    light.data.energy = 10000
    light.data.shape = 'SQUARE'
    light.data.size = props.shadow_spread
    light.data.spread = math.radians(20)  # 20 degrees beam spread
    
    # Parent light to shadow plane
    light.parent = shadow_plane
    light.matrix_parent_inverse = shadow_plane.matrix_world.inverted()
    
    return light


class CLOUDCREATOR_OT_create(Operator):
    """Create clouds based on current settings."""
    
    bl_idname = "cloudcreator.create"
    bl_label = "Create Clouds"
    bl_description = "Generate clouds with the current settings"
    bl_options = {'REGISTER', 'UNDO'}
    
    def invoke(self, context, event):
        props = context.scene.cloudcreator
        
        # Safety warning for large cloud spread with multiple clouds
        if props.add_cloud and props.multiple and props.cloud_spread > 10:
            return context.window_manager.invoke_confirm(self, event)
        
        return self.execute(context)
    
    def execute(self, context):
        props = context.scene.cloudcreator
        
        # Load cloud mesh if enabled
        if props.add_cloud:
            # Determine which mesh to load
            if props.multiple:
                mesh_name = "cloud_layer"
            else:
                mesh_name = f"cloud_{props.cloud_type}"
            
            # Load the cloud mesh
            cloud_obj, error = load_cloud_mesh(context, mesh_name)
            if error:
                self.report({'WARNING'}, f"CloudCreator: {error}")
            elif cloud_obj:
                self.report({'INFO'}, f"CloudCreator: Loaded '{cloud_obj.name}'")
        
        # Create cloud shadow plane if enabled
        shadow_plane = None
        if props.cloud_shadows:
            shadow_plane = create_cloud_shadow_plane(context)
            self.report({'INFO'}, f"CloudCreator: Created shadow plane '{shadow_plane.name}'")
            
            # Add light if enabled
            if props.add_light:
                light = create_cloud_light(context, shadow_plane)
                self.report({'INFO'}, f"CloudCreator: Created light '{light.name}'")
        
        return {'FINISHED'}
    
    @classmethod
    def description(cls, context, properties):
        props = context.scene.cloudcreator
        if props.add_cloud and props.multiple and props.cloud_spread > 10:
            return "WARNING: Large cloud spread (>10m) with raytracing can be very slow and may crash Cycles. Continue?"
        return "Generate clouds with the current settings"


class CLOUDCREATOR_PT_main_panel(Panel):
    """Main panel for CloudCreator in the N-panel."""
    
    bl_label = "CloudCreator"
    bl_idname = "CLOUDCREATOR_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CloudCreator"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cloudcreator
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        col = layout.column(align=True)
        col.prop(props, "seed")
        col.prop(props, "cloud_height")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.prop(props, "add_cloud")
        
        # Only show cloud options if add_cloud is enabled
        if props.add_cloud:
            col.prop(props, "multiple")
            
            # Show cloud_type if multiple is disabled, cloud_spread if enabled
            if props.multiple:
                col.prop(props, "cloud_spread")
                # Show warning for large spread
                if props.cloud_spread > 10:
                    box = layout.box()
                    box.alert = True
                    box.label(text="Warning: Large spread may crash Cycles!", icon='ERROR')
            else:
                col.prop(props, "cloud_type")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.prop(props, "cloud_shadows")
        
        # Only show shadow options if cloud_shadows is enabled
        if props.cloud_shadows:
            col.prop(props, "shadow_spread")
            col.prop(props, "add_light")
        
        layout.separator()
        
        layout.operator("cloudcreator.create", text="Create", icon='OUTLINER_OB_POINTCLOUD')


classes = (
    CloudCreatorProperties,
    CLOUDCREATOR_OT_create,
    CLOUDCREATOR_PT_main_panel,
)


def register():
    """Register the add-on classes and handlers."""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.cloudcreator = bpy.props.PointerProperty(type=CloudCreatorProperties)


def unregister():
    """Unregister the add-on classes and handlers."""
    del bpy.types.Scene.cloudcreator
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
