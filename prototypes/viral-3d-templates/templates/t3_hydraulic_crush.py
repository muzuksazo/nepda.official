"""Template T3: 500-Ton Hydraulic Press Crush & 48-Shard Bullet Fracture."""

from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Tuple

import bpy
from mathutils import Vector

from core.active_ragdoll import apply_face_weights, apply_pose_euler_dict, import_human_grounded
from core.scene_core import (
    ASSETS,
    clear_scene_safe,
    create_camera,
    ensure_rigidbody_world,
    import_centered_barrel,
    keyframe_camera,
    lerp,
    lerp_vec,
    make_mat,
    setup_eevee,
    setup_outdoor_hdri_world,
    smoothstep,
)


def _observer_pose(f: int, f_shatter: int) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, float]]:
    if f < f_shatter:
        watch = smoothstep(10.0, float(f_shatter - 10), float(f))
        pose = {
            "Spine": (4.0 * watch, 0.0, 0.0),
            "Head": (8.0 * watch, -10.0, 0.0),
            "Neck": (4.0 * watch, -6.0, 0.0),
            "LeftShoulder": (0.0, 0.0, -6.0),
            "RightShoulder": (0.0, 0.0, 6.0),
            "LeftArm": (32.0 - 18.0 * watch, 0.0, 8.0),
            "RightArm": (32.0 - 18.0 * watch, 0.0, -8.0),
            "LeftForeArm": (0.0, 0.0, 26.0 + 30.0 * watch),
            "RightForeArm": (0.0, 0.0, -26.0 - 30.0 * watch),
            "LeftUpLeg": (6.0, 0.0, 4.0),
            "RightUpLeg": (6.0, 0.0, -4.0),
            "LeftLeg": (-10.0, 0.0, 0.0),
            "RightLeg": (-10.0, 0.0, 0.0),
        }
        face = {"browInnerUp": 0.25 + 0.55 * watch, "eyeWideLeft": 0.4 * watch, "eyeWideRight": 0.4 * watch, "jawOpen": 0.08 + 0.25 * watch}
        return pose, face

    # Violent defensive flinch on explosive shatter!
    fl = smoothstep(float(f_shatter), float(f_shatter + 6), float(f))
    osc = math.sin((f - f_shatter) * 0.4) * 5.0
    pose = {
        "Spine": (-16.0 * fl, 0.0, 0.0),
        "Spine1": (-12.0 * fl, 0.0, 0.0),
        "Head": (-20.0 * fl, 14.0 * fl, 0.0),
        "Neck": (-10.0 * fl, 8.0 * fl, 0.0),
        "LeftShoulder": (0.0, 0.0, 12.0 * fl),
        "RightShoulder": (0.0, 0.0, -12.0 * fl),
        "LeftArm": (-58.0 * fl + osc, 0.0, 48.0 * fl),
        "RightArm": (-58.0 * fl - osc, 0.0, -48.0 * fl),
        "LeftForeArm": (10.0, 0.0, 96.0 * fl),
        "RightForeArm": (10.0, 0.0, -96.0 * fl),
        "LeftUpLeg": (18.0 * fl, 0.0, 8.0),
        "RightUpLeg": (10.0 * fl, 0.0, -8.0),
        "LeftLeg": (-28.0 * fl, 0.0, 0.0),
        "RightLeg": (-16.0 * fl, 0.0, 0.0),
    }
    face = {
        "jawOpen": 0.88 * fl, "mouthFunnel": 0.35 * fl,
        "mouthStretchLeft": 0.45 * fl, "mouthStretchRight": 0.45 * fl,
        "eyeWideLeft": 0.96 * fl, "eyeWideRight": 0.96 * fl,
        "browInnerUp": 0.95 * fl, "browOuterUpLeft": 0.7 * fl, "browOuterUpRight": 0.7 * fl,
    }
    return pose, face


def build_scene(spec: Dict, *, samples: int = 24) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    params = spec.get("params", {})
    total_frames = int(spec.get("total_frames", 150))
    f_shatter = int(params.get("fracture_frame", 97))

    clear_scene_safe()
    scene = bpy.context.scene
    setup_eevee(scene, width=int(spec.get("width", 720)), height=int(spec.get("height", 1280)),
                fps=int(spec.get("fps", 30)), samples=samples, total_frames=total_frames)
    setup_outdoor_hdri_world(scene, hdri_path=ASSETS["hdri_airfield"], horizon_color=(0.14, 0.16, 0.22), zenith_color=(0.04, 0.05, 0.08), sun_energy=2.2)
    ensure_rigidbody_world(scene, total_frames=total_frames)

    # Studio Workshop lighting
    for name, loc, rot, en, sz, col in (
        ("StudioKey", (3.5, -5.0, 5.0), (50.0, 0.0, 32.0), 480.0, 3.5, (1.0, 0.96, 0.90)),
        ("StudioRimCyan", (-3.5, 3.8, 3.8), (112.0, 0.0, -135.0), 420.0, 3.0, (0.45, 0.82, 1.0)),
        ("StudioRimAmber", (4.0, 2.5, 2.8), (95.0, 0.0, 125.0), 320.0, 3.0, (1.0, 0.68, 0.30)),
    ):
        ld = bpy.data.lights.new(name, type="AREA")
        ld.energy = en
        ld.size = sz
        ld.color = col
        lo = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = tuple(math.radians(a) for a in rot)

    # Concrete studio floor (top z=0.0, PASSIVE BOX)
    floor_m = make_mat("WorkshopConcrete", (0.14, 0.15, 0.17), roughness=0.58)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.5))
    fl = bpy.context.active_object
    fl.scale = (45.0, 45.0, 1.0)
    fl.data.materials.append(floor_m)
    bpy.ops.object.select_all(action="DESELECT")
    fl.select_set(True)
    bpy.context.view_layer.objects.active = fl
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    fl.rigid_body.collision_shape = "BOX"
    fl.rigid_body.friction = 0.6
    fl.rigid_body.restitution = 0.35

    # Industrial 500-Ton Hydraulic Press Frame
    press_dark = make_mat("PressFrame", (0.12, 0.14, 0.17), metallic=0.82, roughness=0.34)
    press_yellow = make_mat("PressYellow", (0.98, 0.72, 0.03), roughness=0.32, coat=0.4)
    chrome_m = make_mat("PressChrome", (0.88, 0.90, 0.94), metallic=0.98, roughness=0.08)
    glass_m = make_mat("SafetyShield", (0.78, 0.92, 1.0), roughness=0.05, transmission=0.85, ior=1.48)

    # Anvil Base (top strictly at z=0.85) with PASSIVE collider
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.425))
    anvil = bpy.context.active_object
    anvil.name = "PressAnvil"
    anvil.scale = (2.6, 1.8, 0.85)
    anvil.data.materials.append(press_dark)
    bpy.ops.object.select_all(action="DESELECT")
    anvil.select_set(True)
    bpy.context.view_layer.objects.active = anvil
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    anvil.rigid_body.collision_shape = "BOX"
    anvil.rigid_body.friction = 0.5
    anvil.rigid_body.restitution = 0.4

    # Twin columns + yellow top header
    for cx in (-1.05, 1.05):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, 0.0, 2.25))
        col = bpy.context.active_object
        col.scale = (0.34, 0.46, 3.0)
        col.data.materials.append(press_dark)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 3.55))
    hdr = bpy.context.active_object
    hdr.scale = (2.75, 1.5, 0.55)
    hdr.data.materials.append(press_yellow)

    # Transparent blast safety partition between press & observer
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.45, -0.35, 1.45))
    sh = bpy.context.active_object
    sh.scale = (0.04, 1.8, 2.6)
    sh.data.materials.append(glass_m)

    # Live glowing 3D pressure bar on front right column (green -> orange -> pulsing red)
    bar_mat = make_mat("PressureBar", (0.1, 0.95, 0.3), emission_color=(0.1, 0.95, 0.3), emission_strength=6.0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.05, -0.26, 2.15))
    pbar = bpy.context.active_object
    pbar.data.materials.append(bar_mat)
    bsdf_bar = bar_mat.node_tree.nodes["Principled BSDF"]
    for f in range(1, total_frames + 1):
        u = smoothstep(15.0, float(f_shatter), float(f))
        pbar.scale = (0.14, 0.06, 0.05 + 1.05 * u)
        pbar.location = (1.05, -0.26, 1.65 + 0.525 * u)
        pbar.keyframe_insert(data_path="scale", frame=f)
        pbar.keyframe_insert(data_path="location", frame=f)
        if f % 10 == 0 or f in (1, f_shatter - 1, f_shatter, total_frames):
            col = (lerp(0.1, 1.0, smoothstep(0.0, 0.7, u)), lerp(0.95, 0.10, smoothstep(0.35, 1.0, u)), 0.08, 1.0)
            bsdf_bar.inputs["Emission Color"].default_value = col
            bsdf_bar.inputs["Emission Color"].keyframe_insert(data_path="default_value", frame=f)

    # Descending Chrome Hydraulic Ram (bottom hits z=0.92 at f_shatter)
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.44, depth=1.6, location=(0.0, 0.0, 3.0))
    ram = bpy.context.active_object
    ram.name = "HydraulicRam"
    bpy.ops.object.shade_smooth()
    ram.data.materials.append(chrome_m)
    bpy.ops.object.select_all(action="DESELECT")
    ram.select_set(True)
    bpy.context.view_layer.objects.active = ram
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    ram.rigid_body.collision_shape = "CYLINDER"
    ram.rigid_body.kinematic = True
    ram.rigid_body.restitution = 0.55

    for f in range(1, total_frames + 1):
        if f < 15:
            z_bot = 2.25
        elif f < f_shatter:
            # F15..52 fast approach to touch top (1.73), F52..f_shatter slow crushing squeeze to 1.08!
            if f <= 52:
                z_bot = lerp(2.25, 1.73, smoothstep(15.0, 52.0, float(f)))
            else:
                z_bot = lerp(1.73, 1.08, (f - 52) / max(1, f_shatter - 52))
        elif f <= f_shatter + 4:
            # Violent downward snap slamming through fractured core!
            z_bot = lerp(1.08, 0.90, (f - f_shatter) / 4.0)
        else:
            z_bot = 0.90
        ram.location = (0.0, 0.0, z_bot + 0.80)
        ram.keyframe_insert(data_path="location", frame=f)

    # Intact Target: Poly Haven Barrel_01 drum (top z=1.73, base z=0.85) visibly buckling F52..f_shatter-1
    target_barrel = import_centered_barrel(scene, "TargetBarrel", (0.0, 0.0, 1.29), rigid=False)
    for f in range(1, total_frames + 1):
        if f <= 52:
            sx, sz = 1.0, 1.0
            vib = 0.0
        elif f < f_shatter:
            sq = (f - 52) / max(1, f_shatter - 52)
            sz = lerp(1.0, 0.26, sq)
            sx = 1.0 + 0.45 * sq
            vib = 0.015 * math.sin(f * 3.1) * sq
        else:
            sx, sz, vib = 1.45, 0.26, 0.0
        target_barrel.scale = (sx, sx, sz)
        target_barrel.location = (vib, 0.0, 0.85 + 0.44 * sz)
        target_barrel.keyframe_insert(data_path="scale", frame=f)
        target_barrel.keyframe_insert(data_path="location", frame=f)
        if f in (1, f_shatter - 1, f_shatter):
            target_barrel.hide_render = f >= f_shatter
            target_barrel.keyframe_insert(data_path="hide_render", frame=f)

    # 48 Bullet Rigid Body Shards (hidden until f_shatter) blasted outward by ram + 4 radial burst pistons!
    shard_red = make_mat("ShardMetalRed", (0.90, 0.14, 0.07), metallic=0.72, roughness=0.25)
    shard_glow = make_mat("ShardCoreGlow", (0.25, 0.90, 1.0), roughness=0.06, emission_color=(0.25, 0.90, 1.0), emission_strength=6.5)
    rng = random.Random(500)
    for idx in range(48):
        ang = rng.uniform(0.0, 2.0 * math.pi)
        rr = rng.uniform(0.24, 0.50)
        zz = rng.uniform(0.98, 1.34)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(0.095, 0.165), location=(rr * math.cos(ang), rr * math.sin(ang), zz))
        sh_obj = bpy.context.active_object
        sh_obj.name = f"Shard_{idx:02d}"
        sh_obj.scale = (rng.uniform(0.75, 1.55), rng.uniform(0.6, 1.3), rng.uniform(0.45, 1.0))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        sh_obj.data.materials.append(shard_glow if idx % 3 == 0 else shard_red)
        bpy.ops.object.select_all(action="DESELECT")
        sh_obj.select_set(True)
        bpy.context.view_layer.objects.active = sh_obj
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        sh_obj.rigid_body.collision_shape = "CONVEX_HULL"
        sh_obj.rigid_body.mass = rng.uniform(0.8, 1.8)
        sh_obj.rigid_body.restitution = 0.40
        sh_obj.rigid_body.linear_damping = 0.24
        sh_obj.rigid_body.angular_damping = 0.12
        sh_obj.rigid_body.kinematic = True
        sh_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
        sh_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=f_shatter - 1)
        sh_obj.rigid_body.kinematic = False
        sh_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=f_shatter)
        sh_obj.hide_render = True
        sh_obj.keyframe_insert(data_path="hide_render", frame=1)
        sh_obj.keyframe_insert(data_path="hide_render", frame=f_shatter - 1)
        sh_obj.hide_render = False
        sh_obj.keyframe_insert(data_path="hide_render", frame=f_shatter)

    # 4 radial burst pistons inside core to blast shards dramatically outward at f_shatter..f_shatter+6!
    for idx, (dx, dy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.22, depth=0.40, location=(0.0, 0.0, -10.0))
        bp = bpy.context.active_object
        bp.hide_render = True
        bpy.ops.object.select_all(action="DESELECT")
        bp.select_set(True)
        bpy.context.view_layer.objects.active = bp
        bpy.ops.rigidbody.object_add(type="PASSIVE")
        bp.rigid_body.kinematic = True
        bp.rigid_body.restitution = 0.50
        bp.location = (0.0, 0.0, -10.0)
        bp.keyframe_insert(data_path="location", frame=1)
        bp.location = (0.04 * dx, 0.04 * dy, 1.08)
        bp.keyframe_insert(data_path="location", frame=f_shatter - 1)
        bp.location = (0.95 * dx, 0.95 * dy, 1.24)
        bp.keyframe_insert(data_path="location", frame=f_shatter + 6)
        bp.location = (0.95 * dx, 0.95 * dy, -10.0)
        bp.keyframe_insert(data_path="location", frame=f_shatter + 10)

    # Everyday businessman observer behind safety glass
    human = import_human_grounded(scene, location=(2.15, -0.55, 0.0), yaw_deg=-72.0)
    for f in range(1, total_frames + 1):
        pose, face = _observer_pose(f, f_shatter)
        apply_pose_euler_dict(human["arm"], f, pose)
        apply_face_weights(human["shaped_meshes"], f, face)

    print("[T3] Baking 48-shard hydraulic fracture Bullet simulation...", flush=True)
    t0 = time.time()
    bpy.ops.ptcache.bake_all(bake=True)
    print(f"[T3] Bake finished in {time.time() - t0:.1f}s", flush=True)

    cam = create_camera(scene, "T3Cam")
    for f in range(1, total_frames + 1):
        if f <= 45:
            u = (f - 1) / 44.0
            keyframe_camera(cam, f, lerp_vec((2.8, -6.2, 2.4), (2.3, -5.2, 2.1), u), lerp_vec((0.5, 0.0, 1.5), (0.3, 0.0, 1.45), u), lens=30.0)
        elif f < f_shatter:
            u = (f - 46) / max(1.0, float(f_shatter - 46))
            vib = 0.018 * math.sin(f * 3.5) * u
            keyframe_camera(cam, f, lerp_vec((1.2, -3.2, 1.65), (0.95, -2.5, 1.38), u) + Vector((vib, 0.0, vib)), Vector((0.25, 0.0, 1.32)), lens=38.0)
        else:
            u = (f - f_shatter) / max(1.0, float(total_frames - f_shatter))
            shk = 0.11 * math.sin(f * 2.9) * math.exp(-(f - f_shatter) / 10.0)
            keyframe_camera(cam, f, lerp_vec((1.95, -6.3, 1.85), (2.25, -6.7, 1.95), u) + Vector((shk, 0.0, shk * 0.8)), Vector((0.85, -0.25, 1.30)), lens=23.0)

    return scene, [
        ("F025_press_ready", 25),
        ("F085_crush_buckle", max(50, f_shatter - 12)),
        ("F103_shard_burst", min(total_frames - 5, f_shatter + 6)),
        ("F138_reaction_after", total_frames - 12),
    ]
