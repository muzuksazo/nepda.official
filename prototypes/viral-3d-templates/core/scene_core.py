"""Shared Blender 5.1 scene, material, glTF orientation/grounding, and physics helpers."""

from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

ASSETS = {
    "human": "/Users/yun-yeowon/workspace/ad-studio/rnd-sunny-ssambap/ragdoll_test/assets/rpm_player.glb",
    "ferrari": "/Users/yun-yeowon/workspace/ad-studio/rnd-sunny-ssambap/hq_test/assets/ferrari.glb",
    "a350": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/A350_nologo.glb",
    "hdri_airfield": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/derelict_airfield_02_2k.hdr",
    "asphalt_diff": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/asphalt_diff.jpg",
    "asphalt_rough": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/asphalt_rough.jpg",
    "asphalt_nor": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/asphalt_nor.jpg",
    "barrel": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/Barrel_01/Barrel_01_1k.gltf",
    "barrier": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/concrete_road_barrier/concrete_road_barrier_1k.gltf",
    "suitcase": "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella/assets/vintage_suitcase/vintage_suitcase_1k.gltf",
    "master_blend": "/Users/yun-yeowon/workspace/ad-studio/rnd-sunny-ssambap/waterblob_mcp_master.blend",
}


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def clamp01(x: float) -> float:
    return clamp(x, 0.0, 1.0)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_vec(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Vector:
    return Vector((lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)))


def smoothstep(e0: float, e1: float, x: float) -> float:
    if e1 <= e0:
        return 1.0 if x >= e1 else 0.0
    t = clamp01((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def set_input(node: bpy.types.Node, name: str, value) -> None:
    if name in node.inputs:
        node.inputs[name].default_value = value


def make_mat(
    name: str,
    color,
    *,
    metallic: float = 0.0,
    roughness: float = 0.28,
    coat: float = 0.0,
    subsurface: float = 0.0,
    transmission: float = 0.0,
    ior: float = 1.45,
    alpha: float = 1.0,
    emission_color=None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        set_input(bsdf, "Base Color", (*color, 1.0))
        set_input(bsdf, "Metallic", metallic)
        set_input(bsdf, "Roughness", roughness)
        set_input(bsdf, "Coat Weight", coat)
        set_input(bsdf, "Coat Roughness", 0.05)
        set_input(bsdf, "Subsurface Weight", subsurface)
        set_input(bsdf, "Transmission Weight", transmission)
        set_input(bsdf, "IOR", ior)
        set_input(bsdf, "Alpha", alpha)
        if emission_color is not None:
            set_input(bsdf, "Emission Color", (*emission_color, 1.0))
            set_input(bsdf, "Emission Strength", emission_strength)
    return mat


def clear_scene_safe(keep_sand: bool = False) -> Dict[str, object]:
    kept_sand = bpy.data.materials.get("sand_03") if keep_sand else None
    kept_world = bpy.context.scene.world if keep_sand else None
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves, bpy.data.actions):
        for item in list(col):
            if item.users == 0 and item != kept_sand:
                col.remove(item)
    return {"sand_mat": kept_sand, "world": kept_world}


def setup_eevee(
    scene: bpy.types.Scene,
    *,
    width: int = 720,
    height: int = 1280,
    fps: int = 30,
    samples: int = 24,
    total_frames: int = 150,
    exposure: float = 0.10,
    glare_strength: float = 0.45,
) -> None:
    scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = samples
        if hasattr(scene.eevee, "use_raytracing"):
            scene.eevee.use_raytracing = True
        if hasattr(scene.eevee, "motion_blur_steps"):
            scene.eevee.motion_blur_steps = 3
        if hasattr(scene.eevee, "shadow_ray_count"):
            scene.eevee.shadow_ray_count = 2

    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.26

    try:
        scene.view_settings.view_transform = "AgX"
    except Exception:
        scene.view_settings.view_transform = "Filmic"
    scene.view_settings.exposure = exposure

    try:
        ng = bpy.data.node_groups.new("ViralComp", "CompositorNodeTree")
        scene.compositing_node_group = ng
        ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        hsv = ng.nodes.new("CompositorNodeHueSat")
        out = ng.nodes.new("NodeGroupOutput")
        for k, v in (("Type", "Fog Glow"), ("Quality", "High"), ("Threshold", 1.15), ("Strength", glare_strength), ("Size", 7.0)):
            if k in gl.inputs:
                try:
                    gl.inputs[k].default_value = v
                except Exception:
                    pass
        set_input(hsv, "Saturation", 1.12)
        set_input(hsv, "Value", 1.03)
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], hsv.inputs["Image"])
        ng.links.new(hsv.outputs["Image"], out.inputs["Image"])
    except Exception as e:
        print("[core] Compositor warning:", e, flush=True)


def ensure_rigidbody_world(scene: bpy.types.Scene, total_frames: int = 150, substeps: int = 20) -> None:
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    rbw.substeps_per_frame = substeps
    rbw.solver_iterations = 20
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = total_frames


def setup_outdoor_hdri_world(
    scene: bpy.types.Scene,
    *,
    hdri_path: Optional[str] = None,
    preserved_world: Optional[bpy.types.World] = None,
    horizon_color=(0.60, 0.82, 0.99),
    zenith_color=(0.08, 0.30, 0.76),
    sun_energy: float = 5.0,
) -> None:
    hdri_img = None
    if preserved_world and getattr(preserved_world, "node_tree", None):
        for n in preserved_world.node_tree.nodes:
            if n.type == "TEX_ENVIRONMENT" and n.image is not None:
                hdri_img = n.image
                break

    world = preserved_world or bpy.data.worlds.new("ViralWorld")
    scene.world = world
    if hasattr(world, "use_nodes"):
        world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix_cam = nt.nodes.new("ShaderNodeMixShader")
    lp = nt.nodes.new("ShaderNodeLightPath")

    bg_light = nt.nodes.new("ShaderNodeBackground")
    if hdri_img is None and hdri_path and os.path.exists(hdri_path):
        hdri_img = bpy.data.images.load(hdri_path)
    if hdri_img is not None:
        tex_env = nt.nodes.new("ShaderNodeTexEnvironment")
        tex_env.image = hdri_img
        nt.links.new(tex_env.outputs["Color"], bg_light.inputs["Color"])
        bg_light.inputs["Strength"].default_value = 0.85
    else:
        bg_light.inputs["Color"].default_value = (0.55, 0.78, 1.0, 1.0)
        bg_light.inputs["Strength"].default_value = 0.85

    bg_cam = nt.nodes.new("ShaderNodeBackground")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.02
    mr.inputs["From Max"].default_value = 0.48
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*horizon_color, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (*zenith_color, 1.0)
    nt.links.new(tex.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg_cam.inputs["Color"])
    bg_cam.inputs["Strength"].default_value = 1.04

    nt.links.new(lp.outputs["Is Camera Ray"], mix_cam.inputs["Fac"])
    nt.links.new(bg_light.outputs["Background"], mix_cam.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix_cam.inputs[2])
    nt.links.new(mix_cam.outputs["Shader"], out.inputs["Surface"])

    sun_data = bpy.data.lights.new("SceneSun", type="SUN")
    sun_data.energy = sun_energy
    sun_data.angle = math.radians(1.6)
    sun_data.color = (1.0, 0.96, 0.90)
    sun = bpy.data.objects.new("SceneSun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(46.0), math.radians(-18.0), math.radians(30.0))


def build_asphalt_tarmac(
    scene: bpy.types.Scene,
    *,
    size_x: float = 420.0,
    size_y: float = 240.0,
    center_x: float = 55.0,
    friction: float = 0.55,
    restitution: float = 0.25,
    with_markings: bool = True,
) -> bpy.types.Object:
    mat = bpy.data.materials.new("TarmacAsphaltPBR")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (30.0, 14.0, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])

    if os.path.exists(ASSETS["asphalt_diff"]):
        td = nt.nodes.new("ShaderNodeTexImage")
        td.image = bpy.data.images.load(ASSETS["asphalt_diff"])
        nt.links.new(mp.outputs["Vector"], td.inputs["Vector"])
        nt.links.new(td.outputs["Color"], bsdf.inputs["Base Color"])
    if os.path.exists(ASSETS["asphalt_rough"]):
        tr = nt.nodes.new("ShaderNodeTexImage")
        tr.image = bpy.data.images.load(ASSETS["asphalt_rough"])
        tr.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs["Vector"], tr.inputs["Vector"])
        nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
    if os.path.exists(ASSETS["asphalt_nor"]):
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = bpy.data.images.load(ASSETS["asphalt_nor"])
        tn.image.colorspace_settings.name = "Non-Color"
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.65
        nt.links.new(mp.outputs["Vector"], tn.inputs["Vector"])
        nt.links.new(tn.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(center_x, 0.0, -0.5))
    tarmac = bpy.context.active_object
    tarmac.name = "RunwayTarmac"
    tarmac.scale = (size_x, size_y, 1.0)
    tarmac.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    tarmac.select_set(True)
    bpy.context.view_layer.objects.active = tarmac
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    tarmac.rigid_body.collision_shape = "BOX"
    tarmac.rigid_body.friction = friction
    tarmac.rigid_body.restitution = restitution
    tarmac.modifiers.new("Collision", "COLLISION")

    skirt_mat = make_mat("HorizonGround", (0.16, 0.17, 0.18), roughness=0.92)
    bpy.ops.mesh.primitive_plane_add(size=2400.0, location=(center_x, 0.0, -0.06))
    bpy.context.active_object.data.materials.append(skirt_mat)

    if with_markings:
        white_m = make_mat("RunwayWhite", (0.94, 0.94, 0.92), roughness=0.72)
        yellow_m = make_mat("RunwayYellow", (0.98, 0.72, 0.04), roughness=0.65)
        for ix in range(-16, int(center_x + size_x * 0.4), 8):
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(float(ix), 0.0, 0.008))
            st = bpy.context.active_object
            st.scale = (4.2, 0.36, 1.0)
            st.data.materials.append(white_m)
        for yl_y in (-5.6, 5.6):
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(center_x, yl_y, 0.008))
            yl = bpy.context.active_object
            yl.scale = (size_x * 0.75, 0.22, 1.0)
            yl.data.materials.append(yellow_m)

    return tarmac


def create_camera(scene: bpy.types.Scene, name: str = "TemplateCam") -> bpy.types.Object:
    cam_data = bpy.data.cameras.new(name)
    cam_data.clip_start = 0.1
    cam_data.clip_end = 5000.0
    cam = bpy.data.objects.new(name, cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def keyframe_camera(
    cam: bpy.types.Object,
    frame: int,
    loc: Vector,
    target: Vector,
    roll_deg: float = 0.0,
    lens: float = 30.0,
) -> None:
    cam.location = loc
    cam.keyframe_insert(data_path="location", frame=frame)
    cam.data.lens = lens
    cam.data.keyframe_insert(data_path="lens", frame=frame)
    direction = target - loc
    if direction.length < 1e-6:
        direction = Vector((1.0, 0.0, 0.0))
    quat = direction.to_track_quat("-Z", "Y")
    if abs(roll_deg) > 1e-4:
        quat = quat @ Euler((0.0, 0.0, math.radians(roll_deg)), "XYZ").to_quaternion()
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = quat
    cam.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def import_ferrari_oriented_x(
    scene: bpy.types.Scene,
    *,
    body_color=(0.98, 0.72, 0.02),
    add_cloth_collider: bool = False,
) -> Tuple[bpy.types.Object, List[bpy.types.Object]]:
    """Import ferrari.glb, switch QUATERNION->XYZ BEFORE rotating +Y nose onto +X, and collect wheels."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ASSETS["ferrari"])
    new_objs = [o for o in bpy.data.objects if o not in before]

    body_mat = bpy.data.materials.get("Body_Color")
    if body_mat and body_mat.use_nodes:
        bsdf = body_mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            set_input(bsdf, "Base Color", (*body_color, 1.0))
            set_input(bsdf, "Metallic", 0.22)
            set_input(bsdf, "Roughness", 0.07)
            set_input(bsdf, "Coat Weight", 1.0)
            set_input(bsdf, "Coat Roughness", 0.03)

    piv = bpy.data.objects.new("CarPivot", None)
    scene.collection.objects.link(piv)
    for o in new_objs:
        if o.parent is None:
            o.parent = piv
            o.rotation_mode = "XYZ"
            o.rotation_euler = (0.0, 0.0, -math.pi * 0.5)

    spin_wheels: List[bpy.types.Object] = []
    for ch in piv.children_recursive:
        if ch.type == "MESH" and "wheel" in ch.name.lower():
            bb_l = [Vector(c) for c in ch.bound_box]
            center_l = sum(bb_l, Vector((0.0, 0.0, 0.0))) / 8.0
            if center_l.length < 0.10:
                ch.rotation_mode = "XYZ"
                spin_wheels.append(ch)

    if add_cloth_collider:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=1.0, location=(0.0, 0.0, 0.55))
        col = bpy.context.active_object
        col.name = "CarCollider"
        col.scale = (2.1, 1.1, 0.85)
        col.parent = piv
        col.hide_render = True
        col.modifiers.new("Collision", "COLLISION")
        col.collision.thickness_outer = 0.14

    return piv, spin_wheels


def assert_car_oriented_x(car_piv: bpy.types.Object) -> None:
    bpy.context.view_layer.update()
    body_obj = next((c for c in car_piv.children_recursive if c.type == "MESH" and c.name.startswith("body")), None)
    lights_obj = next((c for c in car_piv.children_recursive if c.type == "MESH" and c.name == "lights"), None)
    assert body_obj is not None and lights_obj is not None, "Expected Ferrari body & lights"
    bb_b = [body_obj.matrix_world @ Vector(c) for c in body_obj.bound_box]
    bb_l = [lights_obj.matrix_world @ Vector(c) for c in lights_obj.bound_box]
    dx = max(v.x for v in bb_b) - min(v.x for v in bb_b)
    lx = sum(v.x for v in bb_l) / 8.0 - car_piv.matrix_world.translation.x
    print(f"[core] Ferrari +X check: body_dx={dx:.2f}m, lights_rel_x={lx:+.2f}m", flush=True)
    assert lx > 1.2 and dx > 4.0, f"Ferrari not oriented +X! lights_rel_x={lx}, body_dx={dx}"


def import_centered_barrel(
    scene: bpy.types.Scene,
    name: str,
    location: Tuple[float, float, float],
    *,
    mass: float = 4.5,
    rigid: bool = True,
    deactivated: bool = True,
) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ASSETS["barrel"])
    new_objs = [o for o in bpy.data.objects if o not in before]
    mesh_obj = next((o for o in new_objs if o.type == "MESH"), None)
    assert mesh_obj is not None, "Expected MESH in Barrel_01"
    mesh_obj.parent = None
    for o in new_objs:
        if o != mesh_obj:
            bpy.data.objects.remove(o, do_unlink=True)
    mesh_obj.name = name
    mesh_obj.rotation_mode = "XYZ"
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    mesh_obj.location = location
    if rigid:
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        mesh_obj.rigid_body.collision_shape = "CYLINDER"
        mesh_obj.rigid_body.mass = mass
        mesh_obj.rigid_body.friction = 0.45
        mesh_obj.rigid_body.restitution = 0.35
        mesh_obj.rigid_body.use_deactivation = deactivated
        mesh_obj.rigid_body.use_start_deactivated = deactivated
    return mesh_obj
