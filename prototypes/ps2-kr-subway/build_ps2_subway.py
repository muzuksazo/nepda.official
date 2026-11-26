"""Part B v2: PS2 Low-Poly Korean Daily Life Ep.1
("출근길 2호선 왕십리역 지옥철 탑승 미션")
Zero voxel people — 100% real 3D humans with DECIMATE + UV-Snap PS2 pixelation,
curved Seoul Line 2 interior, beveled rounded-triangle green handles, EEVEE Raytracing @ 720x1280.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, "/Users/yun-yeowon/workspace/ad-studio/viral-3d-templates")

try:
    import bmesh
    import bpy
    from mathutils import Euler, Vector
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

if IN_BLENDER:
    from core.active_ragdoll import apply_pose_euler_dict, import_human_grounded
    from core.scene_core import (
        clear_scene_safe,
        create_camera,
        keyframe_camera,
        lerp,
        lerp_vec,
        make_mat,
        setup_eevee,
        smoothstep,
    )
else:
    from core.post_assemble import stitch_preview_grid

BLENDER_BIN = "/Applications/Blender.app/Contents/MacOS/Blender"
ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-kr-subway"
TEX_DIR = os.path.join(ROOT, "textures")
FRAMES_DIR = os.path.join(ROOT, "frames")
QA_PREVIEW = os.path.join(ROOT, "qa_preview_4frames.png")
MICHELLE_GLB = "/Users/yun-yeowon/workspace/ad-studio/rnd-sunny-ssambap/ragdoll_test/assets/Michelle.glb"

TOTAL_FRAMES = 240
FPS = 30
RENDER_W = 720
RENDER_H = 1280


def make_tex_mat(name: str, tex_path: str, *, emission: float = 0.0, roughness: float = 0.72) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(tex_path, check_existing=True)
    tex.interpolation = "Closest"
    bsdf.inputs["Roughness"].default_value = roughness
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if emission > 0.0:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def apply_ps2_pixel_shader(
    mat: bpy.types.Material,
    *,
    pixel_res: int = 72,
    tint: Optional[Tuple[float, float, float]] = None,
    blend_type: str = "MULTIPLY",
    tint_fac: float = 0.85,
    val_mul: float = 1.0,
    sat_mul: float = 1.0,
    roughness: Optional[float] = None,
) -> None:
    """Inject UV SNAP -> Closest texelation + color/roughness grading on glTF PBR materials."""
    if not mat or not getattr(mat, "use_nodes", False) or not mat.node_tree:
        return
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    uv_node = nodes.new("ShaderNodeTexCoord")
    snap_node = nodes.new("ShaderNodeVectorMath")
    snap_node.operation = "SNAP"
    step = 1.0 / max(16.0, float(pixel_res))
    snap_node.inputs[1].default_value = (step, step, 0.0)
    links.new(uv_node.outputs["UV"], snap_node.inputs[0])

    for n in list(nodes):
        if n.type == "TEX_IMAGE":
            n.interpolation = "Closest"
            if not n.inputs["Vector"].is_linked:
                links.new(snap_node.outputs["Vector"], n.inputs["Vector"])

    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        return
    if roughness is not None and "Roughness" in bsdf.inputs:
        for lk in list(links):
            if lk.to_node == bsdf and lk.to_socket.name == "Roughness":
                links.remove(lk)
        bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.25

    if tint is not None or abs(val_mul - 1.0) > 1e-3 or abs(sat_mul - 1.0) > 1e-3:
        bc_sock = bsdf.inputs["Base Color"]
        in_link = next((lk for lk in links if lk.to_node == bsdf and lk.to_socket == bc_sock), None)
        if in_link is not None:
            src_sock = in_link.from_socket
            links.remove(in_link)
            if abs(val_mul - 1.0) > 1e-3 or abs(sat_mul - 1.0) > 1e-3:
                hsv = nodes.new("ShaderNodeHueSaturation")
                hsv.inputs["Saturation"].default_value = sat_mul
                hsv.inputs["Value"].default_value = val_mul
                links.new(src_sock, hsv.inputs["Color"])
                src_sock = hsv.outputs["Color"]
            if tint is not None:
                mix = nodes.new("ShaderNodeMix")
                mix.data_type = "RGBA"
                mix.blend_type = blend_type
                mix.inputs["Factor"].default_value = tint_fac
                mix.inputs[7].default_value = (*tint, 1.0)
                links.new(src_sock, mix.inputs[6])
                src_sock = mix.outputs[2]
            links.new(src_sock, bc_sock)
        elif tint is not None:
            bc_sock.default_value = (tint[0] * val_mul, tint[1] * val_mul, tint[2] * val_mul, 1.0)


def apply_all_face_weights(shaped_meshes: List[bpy.types.Object], frame: int, face_vals: Dict[str, float]) -> None:
    """Animate any subset of all 52 ARKit shape keys without restrictive allowlist."""
    for m_obj in shaped_meshes:
        sk = m_obj.data.shape_keys
        if sk is None:
            continue
        for k, v in face_vals.items():
            kb = sk.key_blocks.get(k)
            if kb is not None:
                kb.value = max(0.0, min(1.0, v))
                kb.keyframe_insert(data_path="value", frame=frame)


def add_box(
    name: str,
    loc: Tuple[float, float, float],
    scale: Tuple[float, float, float],
    mat: bpy.types.Material,
    parent: Optional[bpy.types.Object] = None,
    *,
    bevel: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        bm = o.modifiers.new("Bevel", "BEVEL")
        bm.width = bevel
        bm.segments = 2
    o.data.materials.append(mat)
    if parent is not None:
        o.parent = parent
    return o


def add_cyl(
    name: str,
    loc: Tuple[float, float, float],
    radius: float,
    depth: float,
    rot_deg: Tuple[float, float, float],
    mat: bpy.types.Material,
    parent: Optional[bpy.types.Object] = None,
    *,
    verts: int = 16,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    if parent is not None:
        o.parent = parent
    return o


def add_sign_plane(
    name: str,
    loc: Tuple[float, float, float],
    size_wh: Tuple[float, float],
    rot_deg: Tuple[float, float, float],
    mat: bpy.types.Material,
    parent: Optional[bpy.types.Object] = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=loc)
    pl = bpy.context.active_object
    pl.name = name
    pl.scale = (size_wh[0], size_wh[1], 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    pl.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    pl.data.materials.append(mat)
    if parent is not None:
        pl.parent = parent
    return pl


def build_curved_ceiling(scene: bpy.types.Scene, mat: bpy.types.Material, parent: bpy.types.Object) -> None:
    """Build authentic barrel-vault subway ceiling with center A/C vent channel."""
    mesh = bpy.data.meshes.new("CurvedCarRoof")
    bm = bmesh.new()
    # Cross section profile in (Y, Z) extruded along X = [-6.0, +6.0]
    profile_yz = [
        (0.0, 2.08),
        (0.20, 2.24),
        (0.55, 2.38),
        (1.02, 2.47),
        (1.06, 2.43),
        (1.84, 2.43),
        (1.88, 2.47),
        (2.35, 2.38),
        (2.70, 2.24),
        (2.90, 2.08),
    ]
    r0 = [bm.verts.new((-6.0, y, z)) for y, z in profile_yz]
    r1 = [bm.verts.new((6.0, y, z)) for y, z in profile_yz]
    for i in range(len(profile_yz) - 1):
        bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("CurvedCarRoof", mesh)
    scene.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True


def build_green_line2_handle(
    scene: bpy.types.Scene,
    name: str,
    loc: Tuple[float, float, float],
    green_m: bpy.types.Material,
    strap_m: bpy.types.Material,
    chrome_m: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """Build authentic curved rounded-triangle Seoul Line 2 green grab handle."""
    piv = bpy.data.objects.new(name, None)
    scene.collection.objects.link(piv)
    piv.parent = parent
    piv.location = loc

    # Top metal rail clamp + vertical strap
    add_cyl(f"{name}_Clamp", (0.0, 0.0, 0.0), 0.022, 0.04, (0.0, 90.0, 0.0), chrome_m, piv, verts=12)
    add_box(f"{name}_Strap", (0.0, 0.0, -0.09), (0.026, 0.008, 0.16), strap_m, piv)

    # Rounded triangle plastic loop in (X, Z) plane using beveled Curve
    curve_data = bpy.data.curves.new(f"{name}_LoopCurve", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = 0.011
    curve_data.bevel_resolution = 3
    sp = curve_data.splines.new("BEZIER")
    # Rounded triangle vertices: top-center, bottom-right, bottom-left (loop closed)
    pts = [
        (0.0, 0.0, -0.165),
        (0.055, 0.0, -0.245),
        (0.062, 0.0, -0.275),
        (0.0, 0.0, -0.282),
        (-0.062, 0.0, -0.275),
        (-0.055, 0.0, -0.245),
    ]
    sp.bezier_points.add(len(pts) - 1)
    for i, co in enumerate(pts):
        bp = sp.bezier_points[i]
        bp.co = co
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    sp.use_cyclic_u = True

    loop_obj = bpy.data.objects.new(f"{name}_Ring", curve_data)
    scene.collection.objects.link(loop_obj)
    loop_obj.parent = piv
    loop_obj.data.materials.append(green_m)
    return piv


def add_glasses_to_head(arm: bpy.types.Object, idx: int, frame_mat: bpy.types.Material) -> None:
    """Attach slim curved PS2 black-rimmed glasses directly to Head bone."""
    pb_head = arm.pose.bones.get("Head")
    if pb_head is None:
        return
    # Bridge + twin thin rims in local bone space (rpm Head faces -Y? Wait: check head local bone space via object parent)
    for gname, gloc, gscale in (
        (f"GlBridge_{idx}", (0.0, 0.095, 0.085), (0.028, 0.012, 0.008)),
        (f"GlRimL_{idx}", (-0.032, 0.095, 0.085), (0.042, 0.012, 0.024)),
        (f"GlRimR_{idx}", (0.032, 0.095, 0.085), (0.042, 0.012, 0.024)),
    ):
        g = add_box(gname, (0.0, 0.0, 0.0), gscale, frame_mat)
        g.parent = arm
        g.parent_type = "BONE"
        g.parent_bone = "Head"
        g.location = gloc


def import_commuter_rpm(
    scene: bpy.types.Scene,
    idx: int,
    *,
    loc: Tuple[float, float, float],
    yaw_deg: float,
    scale_mul: float,
    suit_tint: Tuple[float, float, float],
    hair_val: float,
    skin_val: float,
    has_glasses: bool,
    glass_mat: bpy.types.Material,
    decimate_ratio: float = 0.45,
) -> Dict[str, object]:
    """Import real 3D human (rpm_player.glb), decimate to crisp PS2 polycount, apply pixelated shaders."""
    hum = import_human_grounded(scene, location=loc, yaw_deg=yaw_deg, ground_flush=True)
    arm: bpy.types.Object = hum["arm"]
    arm.name = f"NPC_RPM_{idx:02d}"
    arm.scale = (scale_mul, scale_mul, scale_mul)
    bpy.context.view_layer.update()

    # Re-ground after scaling
    foots = [o for o in bpy.data.objects if o.parent == arm and o.type == "MESH" and "Footwear" in o.name]
    if foots:
        min_z = min((fo.matrix_world @ Vector(c)).z for fo in foots for c in fo.bound_box)
        arm.location.z += (loc[2] - min_z)
        bpy.context.view_layer.update()

    for o in [ob for ob in bpy.data.objects if ob.parent == arm and ob.type == "MESH"]:
        # Copy materials uniquely per commuter so suits have varied realistic colors!
        for slot in o.material_slots:
            if slot.material is not None:
                m_copy = slot.material.copy()
                slot.material = m_copy
                if "Top" in o.name or "Bottom" in o.name or "Footwear" in o.name:
                    apply_ps2_pixel_shader(m_copy, pixel_res=68, tint=suit_tint, val_mul=0.78, roughness=0.86)
                elif "Hair" in o.name:
                    apply_ps2_pixel_shader(m_copy, pixel_res=60, val_mul=hair_val, sat_mul=0.5, roughness=0.88)
                elif "Head" in o.name or "Body" in o.name:
                    apply_ps2_pixel_shader(m_copy, pixel_res=72, val_mul=skin_val, sat_mul=1.10, roughness=0.72)

        # Organic PS2 low-poly decimation (clear shape keys cleanly on non-hero NPCs before Decimate!)
        if any(k in o.name for k in ("Head", "Outfit_Top", "Outfit_Bottom", "Hair", "Body")):
            if o.data.shape_keys:
                o.shape_key_clear()
            dec = o.modifiers.new("PS2Decimate", "DECIMATE")
            dec.ratio = decimate_ratio

    if has_glasses:
        add_glasses_to_head(arm, idx, glass_mat)

    return {"arm": arm, "base_z": arm.location.z, "base_loc": loc, "base_yaw": yaw_deg, "kind": "rpm"}


def import_commuter_michelle(
    scene: bpy.types.Scene,
    idx: int,
    *,
    loc: Tuple[float, float, float],
    yaw_deg: float,
    tint: Tuple[float, float, float],
) -> Optional[Dict[str, object]]:
    """Import real female commuter from Michelle.glb (cleaned & decimated to PS2 polycount)."""
    if not os.path.exists(MICHELLE_GLB):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=MICHELLE_GLB)
    new_objs = [o for o in bpy.data.objects if o not in before]
    arm: Optional[bpy.types.Object] = None
    meshes: List[bpy.types.Object] = []
    for o in new_objs:
        if o.type == "ARMATURE":
            arm = o
        elif o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o, do_unlink=True)
        elif o.type == "MESH":
            meshes.append(o)
    if arm is None or not meshes:
        return None

    # Clear embedded animation data so commuter stands upright
    for o in [arm, *meshes]:
        if o.animation_data:
            o.animation_data_clear()
    arm.name = f"NPC_Fem_{idx:02d}"
    arm.location = loc
    arm.rotation_mode = "XYZ"
    arm.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    arm.scale = (1.04, 1.04, 1.04)
    bpy.context.view_layer.update()

    min_z = min((m.matrix_world @ Vector(c)).z for m in meshes for c in m.bound_box)
    arm.location.z += (loc[2] - min_z)
    bpy.context.view_layer.update()

    for m_obj in meshes:
        for slot in m_obj.material_slots:
            if slot.material is not None:
                mc = slot.material.copy()
                slot.material = mc
                apply_ps2_pixel_shader(mc, pixel_res=72, tint=tint, val_mul=0.82, roughness=0.84)
        dec = m_obj.modifiers.new("PS2Decimate", "DECIMATE")
        dec.ratio = 0.22

    return {"arm": arm, "base_z": arm.location.z, "base_loc": loc, "base_yaw": yaw_deg, "kind": "michelle"}


def hero_pose_and_face(f: int) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, float]]:
    if f <= 45:
        # Standing naturally on platform watching train doors open
        breathe = math.sin(f * 0.22) * 2.0
        pose = {
            "Spine": (4.0, 0.0, 0.0),
            "Head": (-4.0, 0.0, 0.0),
            "LeftShoulder": (0.0, 0.0, -5.0),
            "RightShoulder": (0.0, 0.0, 5.0),
            "LeftArm": (64.0 + breathe, 0.0, 10.0),
            "RightArm": (64.0 - breathe, 0.0, -10.0),
            "LeftForeArm": (0.0, 0.0, 18.0),
            "RightForeArm": (0.0, 0.0, -18.0),
            "LeftUpLeg": (3.0, 0.0, 4.0),
            "RightUpLeg": (3.0, 0.0, -4.0),
            "LeftLeg": (-6.0, 0.0, 0.0),
            "RightLeg": (-6.0, 0.0, 0.0),
        }
        face = {"browInnerUp": 0.25, "eyeSquintLeft": 0.15, "eyeSquintRight": 0.15, "jawOpen": 0.04}
        return pose, face

    if f <= 145:
        # Act 2: Reaching FORWARD (+Z on LeftArm / -Z on RightArm!) to push into packed crowd!
        u = smoothstep(45.0, 62.0, float(f))
        push_wave = max(0.0, math.sin((f - 50) * 0.22))
        stride = math.sin((f - 45) * 0.35) * 14.0 * (1.0 - smoothstep(125.0, 142.0, float(f)))
        pose = {
            "Spine": (18.0 * u + 7.0 * push_wave, 0.0, 0.0),
            "Spine1": (10.0 * u, 0.0, 0.0),
            "Head": (-18.0 * u, 0.0, 0.0),
            "Neck": (-8.0 * u, 0.0, 0.0),
            "LeftShoulder": (0.0, 0.0, 16.0 * u),
            "RightShoulder": (0.0, 0.0, -16.0 * u),
            # Positive Z on LeftArm / Negative Z on RightArm brings arms straight FORWARD in front of chest!
            "LeftArm": (lerp(64.0, -18.0, u), 0.0, lerp(10.0, 64.0 + 12.0 * push_wave, u)),
            "RightArm": (lerp(64.0, -18.0, u), 0.0, lerp(-10.0, -64.0 - 12.0 * push_wave, u)),
            "LeftForeArm": (0.0, 0.0, lerp(18.0, 34.0 * (1.0 - 0.55 * push_wave), u)),
            "RightForeArm": (0.0, 0.0, lerp(-18.0, -34.0 * (1.0 - 0.55 * push_wave), u)),
            "LeftUpLeg": (12.0 + stride, 0.0, 5.0),
            "RightUpLeg": (12.0 - stride, 0.0, -5.0),
            "LeftLeg": (-22.0 - 0.4 * abs(stride), 0.0, 0.0),
            "RightLeg": (-22.0 - 0.4 * abs(stride), 0.0, 0.0),
        }
        face = {
            "browDownLeft": 0.65,
            "browDownRight": 0.65,
            "eyeSquintLeft": 0.65,
            "eyeSquintRight": 0.65,
            "jawOpen": 0.30 + 0.25 * push_wave,
            "mouthStretchLeft": 0.55,
            "mouthStretchRight": 0.55,
        }
        return pose, face

    # Act 3: Wedged tightly facing camera with arms pinned down & intense crying/grimacing Slide-0 face!
    sq = smoothstep(146.0, 162.0, float(f))
    sway = math.sin((f - 150) * 0.48) * 3.0
    pose = {
        "Spine": (2.0, sway * 0.4, 0.0),
        "Head": (-5.0 - 4.0 * sq, sway, 0.0),
        "Neck": (-3.0, sway * 0.3, 0.0),
        "LeftShoulder": (0.0, 0.0, -6.0),
        "RightShoulder": (0.0, 0.0, 6.0),
        "LeftArm": (66.0, 0.0, 12.0),
        "RightArm": (66.0, 0.0, -12.0),
        "LeftForeArm": (0.0, 0.0, 28.0),
        "RightForeArm": (0.0, 0.0, -28.0),
        "LeftUpLeg": (4.0, 0.0, 3.0),
        "RightUpLeg": (4.0, 0.0, -3.0),
        "LeftLeg": (-6.0, 0.0, 0.0),
        "RightLeg": (-6.0, 0.0, 0.0),
    }
    wince = 0.85 + 0.15 * math.sin((f - 150) * 0.35)
    face = {
        "browDownLeft": 0.82 * sq,
        "browDownRight": 0.82 * sq,
        "browInnerUp": 0.95 * sq,
        "eyeSquintLeft": 0.82 * wince * sq,
        "eyeSquintRight": 0.82 * wince * sq,
        "cheekSquintLeft": 0.78 * sq,
        "cheekSquintRight": 0.78 * sq,
        "noseSneerLeft": 0.78 * sq,
        "noseSneerRight": 0.78 * sq,
        "mouthFrownLeft": 1.0 * sq,
        "mouthFrownRight": 1.0 * sq,
        "mouthLowerDownLeft": 0.72 * sq,
        "mouthLowerDownRight": 0.72 * sq,
        "mouthShrugLower": 0.65 * sq,
        "mouthPucker": 0.35 * sq,
        "jawOpen": 0.32 * sq,
        "mouthStretchLeft": 0.38 * sq,
        "mouthStretchRight": 0.38 * sq,
    }
    return pose, face


def build_scene(samples: int = 24) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    clear_scene_safe()
    scene = bpy.context.scene

    # Full 720x1280 EEVEE Raytracing + AgX + Fog Glow Compositor
    setup_eevee(
        scene,
        width=RENDER_W,
        height=RENDER_H,
        fps=FPS,
        samples=samples,
        total_frames=TOTAL_FRAMES,
        exposure=0.08,
        glare_strength=0.35,
    )
    scene.render.use_motion_blur = False
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    w = bpy.data.worlds.new("PS2SubwayMood")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.035, 0.042, 0.048, 1.0)
        bg.inputs["Strength"].default_value = 0.35

    # Architectural Materials
    plat_m = make_mat("PlatformConcrete", (0.20, 0.21, 0.23), roughness=0.88)
    tactile_m = make_mat("TactileYellow", (0.88, 0.68, 0.06), roughness=0.72)
    car_floor_m = make_mat("CarFloor", (0.26, 0.28, 0.30), roughness=0.72)
    car_wall_m = make_mat("CarWall", (0.64, 0.67, 0.66), roughness=0.58, metallic=0.12)
    car_trim_m = make_mat("CarTrim", (0.14, 0.16, 0.18), roughness=0.45, metallic=0.45)
    steel_m = make_mat("SubwayChrome", (0.72, 0.75, 0.78), metallic=0.88, roughness=0.22)
    green_m = make_mat("Line2GreenHandle", (0.05, 0.56, 0.20), roughness=0.28, coat=0.55)
    strap_m = make_mat("HandleStrapWhite", (0.78, 0.80, 0.78), roughness=0.65)
    door_glass_m = make_mat("DoorGlass", (0.10, 0.14, 0.16), roughness=0.12, transmission=0.55, alpha=0.60)
    fluor_m = make_mat("FluorescentTube", (0.94, 0.99, 0.94), emission_color=(0.92, 1.0, 0.92), emission_strength=4.2)
    win_tunnel_m = make_mat("TunnelDark", (0.015, 0.018, 0.024), roughness=0.9)
    glass_frame_m = make_mat("NPCGlassRim", (0.02, 0.02, 0.03), roughness=0.35)

    wangsimni_mat = make_tex_mat("WangsimniLED", os.path.join(TEX_DIR, "wangsimni_led.png"), emission=1.45, roughness=0.3)
    routemap_mat = make_tex_mat("Line2RouteMap", os.path.join(TEX_DIR, "line2_routemap.png"), emission=0.40, roughness=0.4)
    psd_mat = make_tex_mat("PSDDecal", os.path.join(TEX_DIR, "psd_decal.png"), emission=0.22, roughness=0.5)

    # Moody Overhead Subway Fluorescent Lighting (natural top-down shadows, lifted suit separation)
    for name, loc, rot, en, sz, col in (
        ("CarFluorFront", (0.0, 0.75, 2.38), (0.0, 0.0, 0.0), 48.0, 2.4, (0.92, 1.0, 0.93)),
        ("CarFluorBack", (0.0, 2.05, 2.38), (0.0, 0.0, 0.0), 48.0, 2.4, (0.92, 1.0, 0.93)),
        ("PlatformOverhead", (0.0, -2.1, 3.3), (12.0, 0.0, 0.0), 95.0, 4.0, (0.90, 0.95, 1.0)),
        ("FaceSoftBounce", (0.0, 0.28, 1.48), (85.0, 0.0, 0.0), 7.5, 1.4, (0.95, 0.98, 1.0)),
    ):
        ld = bpy.data.lights.new(name, type="AREA")
        ld.energy = en
        ld.size = sz
        ld.color = col
        lo = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = tuple(math.radians(a) for a in rot)

    # Platform slab + yellow tactile line
    add_box("PlatformSlab", (0.0, -2.85, -0.25), (14.0, 5.4, 0.50), plat_m)
    add_box("TactileStrip", (0.0, -0.56, 0.004), (14.0, 0.28, 0.012), tactile_m)

    train_root = bpy.data.objects.new("SubwayTrain", None)
    scene.collection.objects.link(train_root)

    # Car Floor, Curved Barrel-Vault Roof + A/C Diffuser Louvers
    add_box("CarFloor", (0.0, 1.45, -0.05), (12.0, 3.1, 0.10), car_floor_m, train_root)
    build_curved_ceiling(scene, car_wall_m, train_root)
    for lx in (-2.4, -1.2, 0.0, 1.2, 2.4):
        add_box(f"ACVent_{lx}", (lx, 1.45, 2.43), (0.95, 0.58, 0.025), car_trim_m, train_root)

    # Back wall with windows + pillars
    add_box("BackWallLow", (0.0, 2.95, 0.50), (12.0, 0.14, 1.0), car_wall_m, train_root)
    add_box("BackWallTop", (0.0, 2.95, 2.18), (12.0, 0.14, 0.52), car_wall_m, train_root)
    add_box("BackWindowDark", (0.0, 2.98, 1.45), (11.6, 0.06, 0.92), win_tunnel_m, train_root)
    for px in (-4.2, -2.1, 0.0, 2.1, 4.2):
        add_box(f"BackPillar_{px}", (px, 2.91, 1.45), (0.34, 0.16, 0.96), car_wall_m, train_root)

    # Front wall (y=0.0) + central doorway opening + vertical door frame rubber gaskets
    add_box("FrontWallLeft", (-3.4, 0.0, 1.24), (5.24, 0.12, 2.48), car_wall_m, train_root)
    add_box("FrontWallRight", (3.4, 0.0, 1.24), (5.24, 0.12, 2.48), car_wall_m, train_root)
    add_box("FrontDoorHeader", (0.0, 0.0, 2.28), (1.60, 0.14, 0.42), car_wall_m, train_root)
    add_box("FrontDoorGreenTrim", (0.0, -0.075, 2.09), (1.64, 0.04, 0.05), green_m, train_root)
    for gx in (-0.79, 0.79):
        add_box(f"DoorGasket_{gx}", (gx, -0.05, 1.04), (0.04, 0.10, 2.08), car_trim_m, train_root)

    # Overhead Stainless Wire Luggage Racks (y=0.22 & y=2.70, z=1.98)
    for ry, sgn in ((0.22, 1.0), (2.70, -1.0)):
        for wy in range(4):
            add_cyl(f"RackWire_{ry}_{wy}", (0.0, ry + sgn * (0.05 * wy), 1.98), 0.008, 10.5, (0.0, 90.0, 0.0), steel_m, train_root, verts=8)
        for bx in (-3.0, -1.5, 0.0, 1.5, 3.0):
            add_cyl(f"RackBracket_{ry}_{bx}", (bx, ry + sgn * 0.08, 1.98), 0.012, 0.22, (90.0, 0.0, 0.0), steel_m, train_root, verts=8)

    # Platform Screen Door (PSD)
    for sx in (-1.45, 1.45):
        add_box(f"PSDPillar_{sx}", (sx, -0.22, 1.22), (0.58, 0.10, 2.44), steel_m)
    add_box("PSDTopBeam", (0.0, -0.22, 2.34), (8.0, 0.12, 0.28), steel_m)
    add_sign_plane("PSD_Sign", (0.0, -0.29, 2.32), (1.45, 0.24), (90.0, 0.0, 0.0), psd_mat)

    # Sliding Doors + Window Glass
    train_door_l = add_box("TrainDoorL", (-0.40, -0.05, 1.04), (0.80, 0.06, 2.08), steel_m, train_root)
    train_door_r = add_box("TrainDoorR", (0.40, -0.05, 1.04), (0.80, 0.06, 2.08), steel_m, train_root)
    add_box("DoorWinL", (-0.40, -0.06, 1.38), (0.46, 0.08, 0.85), door_glass_m, train_door_l)
    add_box("DoorWinR", (0.40, -0.06, 1.38), (0.46, 0.08, 0.85), door_glass_m, train_door_r)

    psd_door_l = add_box("PSDDoorL", (-0.40, -0.18, 1.06), (0.78, 0.05, 2.12), door_glass_m)
    psd_door_r = add_box("PSDDoorR", (0.40, -0.18, 1.06), (0.78, 0.05, 2.12), door_glass_m)

    # Ceiling Fluorescent Tubes + Brushed Chrome Rails + 18 Glossy Green Triangular Handles!
    for fx in (-3.2, -1.0, 1.2, 3.4):
        for fy in (0.90, 2.00):
            add_box(f"Fluor_{fx}_{fy}", (fx, fy, 2.42), (1.45, 0.16, 0.03), fluor_m, train_root)

    handle_pivots: List[bpy.types.Object] = []
    for ry in (0.72, 2.04):
        add_cyl(f"Rail_{ry:.2f}", (0.0, ry, 2.25), 0.018, 10.5, (0.0, 90.0, 0.0), steel_m, train_root, verts=12)
        for bx in (-2.4, -1.2, 0.0, 1.2, 2.4):
            add_cyl(f"RailStem_{ry:.2f}_{bx}", (bx, ry, 2.34), 0.012, 0.18, (0.0, 0.0, 0.0), steel_m, train_root, verts=10)
        for hx in (-2.5, -1.9, -1.35, -0.85, -0.45, 0.0, 0.45, 0.85, 1.35, 1.9):
            hp = build_green_line2_handle(scene, f"Handle_{ry:.1f}_{hx:.2f}", (hx, ry, 2.25), green_m, strap_m, steel_m, train_root)
            handle_pivots.append(hp)

    # Hanging 왕십리역 Ceiling LCD Monitor suspended cleanly on dual chrome pipes
    add_box("LCDBox", (0.0, 1.98, 2.08), (0.94, 0.14, 0.42), car_trim_m, train_root, bevel=0.015)
    for sx in (-0.30, 0.30):
        add_cyl(f"LCDPipe_{sx}", (sx, 1.98, 2.36), 0.014, 0.24, (0.0, 0.0, 0.0), steel_m, train_root, verts=10)
    add_sign_plane("WangsimniScreenFront", (0.0, 1.905, 2.08), (0.88, 0.38), (90.0, 0.0, 0.0), wangsimni_mat, train_root)
    add_sign_plane("RouteMapSign", (0.0, 0.075, 2.24), (1.35, 0.24), (90.0, 0.0, 180.0), routemap_mat, train_root)

    # Animate doors & train shudder/handle sway
    for f in range(1, TOTAL_FRAMES + 1):
        open_w = 1.0 - smoothstep(126.0, 146.0, float(f))
        if f <= 18:
            open_w = smoothstep(1.0, 16.0, float(f))
        if 140 <= f <= 145:
            open_w = max(open_w, 0.14 * math.sin((f - 140) * 0.6))
        shift = 0.76 * open_w
        train_door_l.location.x = -0.40 - shift
        train_door_r.location.x = 0.40 + shift
        psd_door_l.location.x = -0.40 - shift
        psd_door_r.location.x = 0.40 + shift
        for o in (train_door_l, train_door_r, psd_door_l, psd_door_r):
            o.keyframe_insert(data_path="location", frame=f)

        dep = smoothstep(150.0, 185.0, float(f))
        vib_z = 0.010 * math.sin(f * 1.1) * dep
        train_root.location = (0.0, 0.0, vib_z)
        train_root.keyframe_insert(data_path="location", frame=f)
        for j, hp in enumerate(handle_pivots):
            sw = (8.0 * dep + 3.0 * math.sin(f * 0.35 + j * 0.7)) * dep
            hp.rotation_euler = (0.0, math.radians(sw), 0.0)
            hp.keyframe_insert(data_path="rotation_euler", frame=f)

    # Passing tunnel pillar lights behind back windows F150..240
    pass_post_m = make_mat("TunnelPost", (0.95, 0.65, 0.25), emission_color=(0.95, 0.65, 0.25), emission_strength=3.5)
    for k in range(4):
        tp = add_box(f"TunnelLight_{k}", (-6.0 + k * 4.5, 4.2, 1.5), (0.18, 0.18, 1.4), pass_post_m)
        for f in range(1, TOTAL_FRAMES + 1):
            dep = max(0.0, (f - 150) / 30.0)
            tp.location.x = ((k * 4.5 - 6.0 - 18.0 * dep) % 18.0) - 9.0
            tp.keyframe_insert(data_path="location", frame=f)

    # 12 Real 3D Low-Poly Commuters (ZERO cube/voxel people!)
    rpm_specs = [
        # (x, y, yaw_deg, scale, suit_tint, hair_val, skin_val, has_glasses)
        (-0.34, 0.78, 175.0, 0.99, (0.14, 0.15, 0.18), 0.18, 0.75, True),    # #0 Doorway front-left (pushed back)
        (0.36, 0.80, -172.0, 1.01, (0.12, 0.15, 0.24), 0.16, 0.78, False),   # #1 Doorway front-right (pushed back)
        (-0.34, 0.62, 162.0, 1.05, (0.14, 0.16, 0.20), 0.16, 0.78, True),    # #2 Act-3 Foreground left commuter (dark suit + glasses!)
        (0.34, 0.64, -162.0, 1.04, (0.18, 0.20, 0.26), 0.18, 0.76, False),   # #3 Act-3 Foreground right commuter (navy suit!)
        (-0.82, 1.28, 165.0, 0.97, (0.24, 0.25, 0.27), 0.20, 0.76, False),   # #4 Mid-left
        (0.84, 1.24, -162.0, 1.02, (0.18, 0.19, 0.21), 0.15, 0.78, True),    # #5 Mid-right
        (-0.42, 1.56, 178.0, 0.98, (0.13, 0.16, 0.24), 0.16, 0.72, False),   # #6 Back row left
        (0.44, 1.54, -176.0, 1.03, (0.26, 0.21, 0.18), 0.18, 0.75, True),    # #7 Back row right
        (-1.18, 0.88, 145.0, 0.96, (0.22, 0.23, 0.25), 0.19, 0.74, False),   # #8 Far left
    ]
    npcs: List[Dict[str, object]] = []
    for idx, (nx, ny, nyaw, sc, tint, hv, sv, gl) in enumerate(rpm_specs):
        npc = import_commuter_rpm(
            scene, idx, loc=(nx, ny, 0.0), yaw_deg=nyaw, scale_mul=sc,
            suit_tint=tint, hair_val=hv, skin_val=sv, has_glasses=gl, glass_mat=glass_frame_m,
        )
        # Set relaxed standing commuter arm pose on frame 1 (arms down at sides)
        arm_n: bpy.types.Object = npc["arm"]
        apply_pose_euler_dict(arm_n, 1, {
            "Spine": (2.0, 0.0, 0.0),
            "Head": (4.0, (idx % 3 - 1) * 6.0, 0.0),
            "LeftArm": (66.0, 0.0, 10.0),
            "RightArm": (66.0, 0.0, -10.0),
            "LeftForeArm": (0.0, 0.0, 18.0),
            "RightForeArm": (0.0, 0.0, -18.0),
        })
        npcs.append(npc)

    # 3 Female Commuters from Michelle.glb (neutral beige & charcoal coats)
    for m_idx, (mx, my, myaw, mtint) in enumerate((
        (-0.02, 1.88, 175.0, (0.62, 0.56, 0.48)),
        (1.16, 0.92, -148.0, (0.28, 0.30, 0.34)),
        (-0.86, 1.82, 168.0, (0.36, 0.32, 0.30)),
    )):
        fm = import_commuter_michelle(scene, m_idx, loc=(mx, my, 0.0), yaw_deg=myaw, tint=mtint)
        if fm is not None:
            npcs.append(fm)

    # Keyframe commuter crowd compression wave + Act 3 framing squeeze + train sway
    for f in range(1, TOTAL_FRAMES + 1):
        if f not in (1, 45, 55, 70, 88, 105, 120, 138, 146, 154, 175, 195, 215, 240):
            # Smooth wave interpolation every 4 frames keeps curve clean & super fast
            if f % 4 != 0:
                continue
        push_wave = max(0.0, math.sin((f - 52) * 0.22)) * smoothstep(48.0, 60.0, float(f)) * (1.0 - smoothstep(130.0, 145.0, float(f)))
        pack_in = smoothstep(144.0, 152.0, float(f))
        dep = smoothstep(150.0, 185.0, float(f))
        for idx, npc in enumerate(npcs):
            arm_n = npc["arm"]
            bx, by, _ = npc["base_loc"]
            byaw = npc["base_yaw"]
            bz = npc["base_z"]
            if idx in (2, 3):
                # Left/right foreground commuters close in naturally beside Hero in Act 3
                sx = lerp(bx * 2.15, bx, pack_in)
                sy = lerp(0.95, by, pack_in)
            elif idx in (0, 1):
                sx = bx * (1.0 + 0.55 * pack_in)
                sy = by + 0.22 * push_wave + 0.42 * pack_in
            else:
                sx = bx
                sy = by + 0.16 * push_wave * (1.0 / (1.0 + idx * 0.12))
            sway_x = 0.012 * math.sin(f * 0.45 + idx) * dep
            sway_z = (0.010 * math.sin(f * 1.1) * dep) if f >= 150 else 0.0
            arm_n.location = (sx + sway_x, sy, bz + sway_z)
            arm_n.rotation_euler = (math.radians(-4.5 * push_wave), math.radians(2.0 * math.sin(f * 0.4 + idx) * dep), math.radians(byaw))
            arm_n.keyframe_insert(data_path="location", frame=f)
            arm_n.keyframe_insert(data_path="rotation_euler", frame=f)

    # Original PS2 Hero ("민수") using rpm_player.glb (keep all 53 shape keys intact!)
    hero = import_human_grounded(scene, location=(0.0, -1.25, 0.0), yaw_deg=180.0, ground_flush=True)
    arm: bpy.types.Object = hero["arm"]
    base_z = arm.location.z

    for o in [ob for ob in bpy.data.objects if ob.parent == arm and ob.type == "MESH"]:
        for slot in o.material_slots:
            if slot.material is not None:
                m = slot.material.copy()
                slot.material = m
                if "Top" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=76, tint=(0.82, 0.84, 0.82), blend_type="MIX", tint_fac=0.72, val_mul=1.55, sat_mul=0.25, roughness=0.88)
                elif "Bottom" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=72, tint=(0.18, 0.34, 0.62), blend_type="MIX", tint_fac=0.72, val_mul=1.35, roughness=0.90)
                elif "Hair" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=64, val_mul=0.14, sat_mul=0.4, roughness=0.88)
                elif "Head" in o.name or "Body" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=84, val_mul=0.72, sat_mul=1.18, roughness=0.66)
                elif "Footwear" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=64, val_mul=0.5, roughness=0.82)

    for f in range(1, TOTAL_FRAMES + 1):
        if f <= 45:
            hy = lerp(-1.25, -0.78, smoothstep(8.0, 44.0, float(f)))
            hyaw = 180.0
        elif f <= 144:
            u = smoothstep(45.0, 128.0, float(f))
            push_bob = 0.045 * max(0.0, math.sin((f - 50) * 0.22))
            hy = lerp(-0.78, 0.35, u) + push_bob
            hyaw = 180.0
        else:
            turn = smoothstep(144.0, 152.0, float(f))
            hy = lerp(0.35, 1.05, smoothstep(144.0, 154.0, float(f)))
            hyaw = lerp(180.0, 0.0, turn)
        dep = smoothstep(150.0, 185.0, float(f))
        hx = 0.012 * math.sin(f * 0.55) * dep
        hz = base_z + (0.010 * math.sin(f * 1.1) * dep if f >= 150 else 0.0)
        arm.location = (hx, hy, hz)
        arm.rotation_euler = (0.0, 0.0, math.radians(hyaw))
        arm.keyframe_insert(data_path="location", frame=f)
        arm.keyframe_insert(data_path="rotation_euler", frame=f)

        pose, face = hero_pose_and_face(f)
        apply_pose_euler_dict(arm, f, pose)
        apply_all_face_weights(hero["shaped_meshes"], f, face)

    # 3-Act Camera Choreography
    cam = create_camera(scene, "PS2Cam")
    for f in range(1, TOTAL_FRAMES + 1):
        if f <= 48:
            u = (f - 1) / 47.0
            loc = lerp_vec((0.55, -2.65, 1.62), (0.48, -2.05, 1.54), u)
            tgt = lerp_vec((0.0, 0.5, 1.38), (0.0, 0.78, 1.34), u)
            lens = 28.0
        elif f <= 145:
            u = (f - 49) / 96.0
            shk = 0.025 * abs(math.sin((f - 50) * 0.25)) if f >= 55 else 0.0
            if 141 <= f <= 145:
                shk += 0.04 * math.sin(f * 3.1)
            loc = lerp_vec((0.56, -1.92, 1.56), (0.44, -1.52, 1.54), u) + Vector((shk, 0.0, shk * 0.7))
            tgt = lerp_vec((0.0, -0.05, 1.32), (0.0, 0.48, 1.36), u)
            lens = 29.0
        else:
            # Slide-0 iconic interior composition inside closed car!
            u = smoothstep(146.0, 235.0, float(f))
            rattle = 0.008 * math.sin(f * 1.15) * smoothstep(150.0, 175.0, float(f))
            loc = Vector((0.01 + rattle * 0.5, lerp(0.06, 0.14, u), 1.60 + rattle))
            tgt = Vector((0.0, 1.12, 1.72))
            lens = lerp(26.0, 31.0, u)
        keyframe_camera(cam, f, loc, tgt, lens=lens)

    return scene, [
        ("F020_platform_doors", 20),
        ("F088_doorway_push", 88),
        ("F142_door_slam", 142),
        ("F195_squished_closeup", 195),
    ]


def _blender_main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--render-all", action="store_true")
    args = p.parse_args(argv)

    os.makedirs(FRAMES_DIR, exist_ok=True)
    scene, previews = build_scene(samples=args.samples)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "ps2_kr_subway.blend"))

    if args.preview_only:
        for label, fnum in previews:
            scene.frame_set(fnum)
            scene.render.filepath = os.path.join(FRAMES_DIR, f"preview_{label}.png")
            bpy.ops.render.render(write_still=True)
    elif args.render_all:
        for fnum in range(1, TOTAL_FRAMES + 1):
            scene.frame_set(fnum)
            scene.render.filepath = os.path.join(FRAMES_DIR, f"frame_{fnum:04d}.png")
            bpy.ops.render.render(write_still=True)
            if fnum % 30 == 0 or fnum == TOTAL_FRAMES or fnum == 1:
                print(f"[ps2] Rendered {fnum}/{TOTAL_FRAMES}", flush=True)


def _host_main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--render-all", action="store_true")
    args = p.parse_args()

    mode_flag = "--preview-only" if args.preview_only else "--render-all"
    subprocess.run([
        BLENDER_BIN, "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", os.path.abspath(__file__), "--", "--samples", str(args.samples), mode_flag,
    ], check=True)

    if args.preview_only:
        prev_imgs = sorted(glob.glob(os.path.join(FRAMES_DIR, "preview_*.png")))
        stitch_preview_grid(prev_imgs, QA_PREVIEW)
        print(f"[ps2] Saved 4-frame Visual Gate sheet: {QA_PREVIEW}", flush=True)


if __name__ == "__main__":
    if IN_BLENDER:
        _blender_main()
    else:
        _host_main()
