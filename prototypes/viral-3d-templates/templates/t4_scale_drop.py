"""Template T4: 3-Stage Scale Escalation Drop (Bowling Ball -> Ferrari -> 11m Magma Asteroid)."""

from __future__ import annotations

import math
import os
import random
import time
from typing import Dict, List, Tuple

import bmesh
import bpy
from mathutils import Vector

from core.active_ragdoll import apply_face_weights, apply_pose_euler_dict, import_human_grounded
from core.scene_core import (
    ASSETS,
    assert_car_oriented_x,
    build_asphalt_tarmac,
    clear_scene_safe,
    create_camera,
    ensure_rigidbody_world,
    import_centered_barrel,
    import_ferrari_oriented_x,
    keyframe_camera,
    lerp,
    lerp_vec,
    make_mat,
    setup_eevee,
    setup_outdoor_hdri_world,
    smoothstep,
)


def _human_scale_reaction(f: int) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, float]]:
    # Looks steadily higher as Stage 1 (F22) -> Stage 2 (F72) -> Stage 3 (F122) escalate
    up = smoothstep(5.0, 118.0, float(f))
    flinch = smoothstep(122.0, 128.0, float(f))
    pose = {
        "Spine": (-8.0 * up - 14.0 * flinch, 0.0, 0.0),
        "Neck": (-10.0 - 12.0 * up, 0.0, 0.0),
        "Head": (-14.0 - 16.0 * up, 0.0, 0.0),
        "LeftShoulder": (0.0, 0.0, -6.0 + 14.0 * flinch),
        "RightShoulder": (0.0, 0.0, 6.0 - 14.0 * flinch),
        "LeftArm": (32.0 - 82.0 * flinch, 0.0, 8.0 + 42.0 * flinch),
        "RightArm": (32.0 - 82.0 * flinch, 0.0, -8.0 - 42.0 * flinch),
        "LeftForeArm": (0.0, 0.0, 22.0 + 68.0 * flinch),
        "RightForeArm": (0.0, 0.0, -22.0 - 68.0 * flinch),
        "LeftUpLeg": (8.0 + 14.0 * flinch, 0.0, 4.0),
        "RightUpLeg": (8.0 + 6.0 * flinch, 0.0, -4.0),
        "LeftLeg": (-12.0 - 20.0 * flinch, 0.0, 0.0),
        "RightLeg": (-12.0 - 10.0 * flinch, 0.0, 0.0),
    }
    awe = smoothstep(18.0, 75.0, float(f))
    shock = smoothstep(75.0, 125.0, float(f))
    face = {
        "jawOpen": lerp(0.05, 0.45, awe) + 0.45 * shock,
        "mouthFunnel": 0.30 * shock,
        "mouthStretchLeft": 0.40 * shock,
        "mouthStretchRight": 0.40 * shock,
        "eyeWideLeft": lerp(0.10, 0.96, max(awe * 0.6, shock)),
        "eyeWideRight": lerp(0.10, 0.96, max(awe * 0.6, shock)),
        "browInnerUp": lerp(0.15, 0.94, max(awe * 0.65, shock)),
    }
    return pose, face


def _build_magma_asteroid(scene: bpy.types.Scene, radius: float = 5.5) -> bpy.types.Object:
    mat = bpy.data.materials.new("T4MagmaAsteroid")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.85

    tex = nt.nodes.new("ShaderNodeTexCoord")
    ns = nt.nodes.new("ShaderNodeTexNoise")
    ns.inputs["Scale"].default_value = 3.2
    ns.inputs["Detail"].default_value = 6.0
    nt.links.new(tex.outputs["Object"], ns.inputs["Vector"])

    # Rock color vs glowing lava cracks
    col_ramp = nt.nodes.new("ShaderNodeValToRGB")
    col_ramp.color_ramp.elements[0].position = 0.36
    col_ramp.color_ramp.elements[0].color = (0.95, 0.25, 0.02, 1.0)
    col_ramp.color_ramp.elements[1].position = 0.46
    col_ramp.color_ramp.elements[1].color = (0.09, 0.08, 0.08, 1.0)
    nt.links.new(ns.outputs["Fac"], col_ramp.inputs["Fac"])
    nt.links.new(col_ramp.outputs["Color"], bsdf.inputs["Base Color"])

    em_ramp = nt.nodes.new("ShaderNodeValToRGB")
    em_ramp.color_ramp.elements[0].position = 0.33
    em_ramp.color_ramp.elements[0].color = (1.0, 0.32, 0.04, 1.0)
    em_ramp.color_ramp.elements[1].position = 0.42
    em_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    nt.links.new(ns.outputs["Fac"], em_ramp.inputs["Fac"])
    nt.links.new(em_ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 9.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=radius, location=(13.5, 0.0, 50.0))
    ast = bpy.context.active_object
    ast.name = "Stage3Asteroid"
    rng = random.Random(404)
    for v in ast.data.vertices:
        v.co *= rng.uniform(0.86, 1.14)
    ast.data.materials.append(mat)
    return ast


def _make_shockwave_ring(scene: bpy.types.Scene, name: str, loc: Tuple[float, float, float], hit_f: int, max_r: float) -> None:
    m = make_mat(f"{name}_Mat", (0.95, 0.72, 0.35), emission_color=(1.0, 0.65, 0.25), emission_strength=4.5)
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.08, location=(loc[0], loc[1], 0.08))
    ring = bpy.context.active_object
    ring.name = name
    ring.data.materials.append(m)
    for f in (1, hit_f - 1, hit_f, hit_f + 16, hit_f + 22, 150):
        fn = max(1, min(150, f))
        if f < hit_f or f >= hit_f + 20:
            ring.scale = (0.01, 0.01, 0.01)
            ring.hide_render = True
        else:
            u = (f - hit_f) / 18.0
            s = max(0.1, max_r * u)
            ring.scale = (s, s, max(0.1, 1.2 - u))
            ring.hide_render = False
        ring.keyframe_insert(data_path="scale", frame=fn)
        ring.keyframe_insert(data_path="hide_render", frame=fn)


def build_scene(spec: Dict, *, samples: int = 24) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    params = spec.get("params", {})
    total_frames = int(spec.get("total_frames", 150))
    clear_scene_safe()
    scene = bpy.context.scene
    setup_eevee(scene, width=int(spec.get("width", 720)), height=int(spec.get("height", 1280)),
                fps=int(spec.get("fps", 30)), samples=samples, total_frames=total_frames)
    setup_outdoor_hdri_world(scene, hdri_path=ASSETS["hdri_airfield"])
    ensure_rigidbody_world(scene, total_frames=total_frames)
    build_asphalt_tarmac(scene, size_x=420.0, size_y=240.0, center_x=25.0)

    if os.path.exists(ASSETS["barrier"]):
        for idx, bx in enumerate((-2.0, 6.0, 14.0, 22.0, 30.0)):
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=ASSETS["barrier"])
            new_objs = [x for x in bpy.data.objects if x not in before]
            piv = bpy.data.objects.new(f"T4Barrier_{idx}", None)
            scene.collection.objects.link(piv)
            for o in new_objs:
                if o.parent is None:
                    o.parent = piv
                    o.rotation_mode = "XYZ"
            piv.location = (float(bx), 9.5, 0.008)

    # Human standing at x=-4.0 facing +X toward the 3 drops
    human = import_human_grounded(scene, location=(-4.0, 0.0, 0.0), yaw_deg=90.0)
    hips_wm = (human["arm"].matrix_world @ human["arm"].pose.bones["Hips"].matrix).to_3x3()
    face_dir = (hips_wm @ Vector((0.0, 0.0, 1.0))).normalized()
    assert face_dir.x > 0.9, f"Expected human facing +X! face_dir={face_dir}"
    for f in range(1, total_frames + 1):
        pose, face = _human_scale_reaction(f)
        apply_pose_euler_dict(human["arm"], f, pose)
        apply_face_weights(human["shaped_meshes"], f, face)

    # Stage 1 (F1..45): Red Bowling Ball (hit F22 at x=0.0) + 3 Bullet cones
    ball_m = make_mat("BowlingRed", (0.92, 0.06, 0.08), roughness=0.08, coat=1.0)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.16, location=(0.0, 0.0, 12.0))
    ball = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(ball_m)
    bpy.ops.object.select_all(action="DESELECT")
    ball.select_set(True)
    bpy.context.view_layer.objects.active = ball
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    ball.rigid_body.collision_shape = "SPHERE"
    ball.rigid_body.kinematic = True
    for f in range(1, total_frames + 1):
        if f <= 22:
            u = (f - 1) / 21.0
            z = lerp(12.0, 0.16, u * u)
        elif f <= 34:
            u = (f - 22) / 12.0
            z = 0.16 + 0.85 * math.sin(u * math.pi)
        else:
            z = 0.16
        ball.location = (0.0, 0.0, z)
        ball.keyframe_insert(data_path="location", frame=f)

    cone_m = make_mat("T4Cone", (0.98, 0.34, 0.04), roughness=0.35)
    for i, (cx, cy) in enumerate(((0.18, -0.22), (0.20, 0.22), (-0.18, 0.12))):
        bpy.ops.mesh.primitive_cone_add(vertices=14, radius1=0.18, radius2=0.04, depth=0.62, location=(cx, cy, 0.31))
        co = bpy.context.active_object
        co.data.materials.append(cone_m)
        bpy.ops.object.select_all(action="DESELECT")
        co.select_set(True)
        bpy.context.view_layer.objects.active = co
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        co.rigid_body.collision_shape = "CONE"
        co.rigid_body.mass = 1.5
        co.rigid_body.use_deactivation = True
        co.rigid_body.use_start_deactivated = True

    # Stage 2 (F46..95): Dropping Yellow Ferrari at x=4.2 hitting F72 + scattering 6 Barrel_01 drums!
    car, _ = import_ferrari_oriented_x(scene, body_color=tuple(params.get("car_color", [0.98, 0.72, 0.02])))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.6))
    car_rb = bpy.context.active_object
    car_rb.scale = (4.2, 1.9, 1.0)
    car_rb.hide_render = True
    car_rb.parent = car
    bpy.ops.object.select_all(action="DESELECT")
    car_rb.select_set(True)
    bpy.context.view_layer.objects.active = car_rb
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    car_rb.rigid_body.collision_shape = "BOX"
    car_rb.rigid_body.kinematic = True
    car_rb.rigid_body.restitution = 0.45

    for f in range(1, total_frames + 1):
        if f < 46:
            car.location = (4.2, 0.0, 32.0)
            car.rotation_euler = (0.0, math.radians(-12.0), 0.0)
        elif f <= 72:
            u = (f - 46) / 26.0
            car.location = (4.2, 0.0, lerp(24.0, 0.14, u * u))
            car.rotation_euler = (math.radians(4.0 * math.sin(u * math.pi)), math.radians(lerp(-14.0, 4.0, u)), 0.0)
        elif f <= 84:
            u = (f - 72) / 12.0
            car.location = (4.2, 0.0, 0.14 + 0.55 * math.sin(u * math.pi))
            car.rotation_euler = (0.0, math.radians(4.0 * (1.0 - u)), 0.0)
        else:
            car.location = (4.2, 0.0, 0.12)
            car.rotation_euler = (0.0, 0.0, 0.0)
        car.keyframe_insert(data_path="location", frame=f)
        car.keyframe_insert(data_path="rotation_euler", frame=f)

    scene.frame_set(75)
    assert_car_oriented_x(car)

    # 6 Barrels waiting around x=4.2
    for i, (bx, by) in enumerate(((3.4, -0.7), (3.4, 0.7), (4.2, -1.05), (4.2, 1.05), (5.0, -0.7), (5.0, 0.7))):
        import_centered_barrel(scene, f"T4Barrel_{i}", (bx, by, 0.445), mass=4.5, deactivated=True)
    _make_shockwave_ring(scene, "RingStage2", (4.2, 0.0, 0.1), 72, 4.2)

    # Stage 3 (F96..150): Colossal 11m-diameter Magma Asteroid hitting x=13.5 at F122 + 20 Bullet debris rocks!
    ast = _build_magma_asteroid(scene, radius=float(params.get("asteroid_radius", 5.5)))
    bpy.ops.object.select_all(action="DESELECT")
    ast.select_set(True)
    bpy.context.view_layer.objects.active = ast
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    ast.rigid_body.collision_shape = "SPHERE"
    ast.rigid_body.kinematic = True
    ast.rigid_body.restitution = 0.35

    for f in range(1, total_frames + 1):
        if f < 95:
            ast.location = (13.5, 0.0, 62.0)
            ast.rotation_euler = (0.0, 0.0, 0.0)
        elif f <= 122:
            u = (f - 95) / 27.0
            ast.location = (13.5, 0.0, lerp(46.0, 4.8, u * u))
            ast.rotation_euler = (u * 0.5, u * 0.7, u * 0.3)
        elif f <= 134:
            u = (f - 122) / 12.0
            ast.location = (13.5, 0.0, 4.8 + 0.55 * math.sin(u * math.pi))
            ast.rotation_euler = (0.5, 0.7, 0.3)
        else:
            ast.location = (13.5, 0.0, 4.8)
            ast.rotation_euler = (0.5, 0.7, 0.3)
        ast.keyframe_insert(data_path="location", frame=f)
        ast.keyframe_insert(data_path="rotation_euler", frame=f)

    rock_m = make_mat("T4DebrisRock", (0.14, 0.12, 0.12), roughness=0.88)
    rng = random.Random(88)
    for i in range(20):
        a = 2.0 * math.pi * i / 20.0
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(0.28, 0.55), location=(13.5 + 3.2 * math.cos(a), 3.2 * math.sin(a), 0.35))
        rk = bpy.context.active_object
        rk.data.materials.append(rock_m)
        bpy.ops.object.select_all(action="DESELECT")
        rk.select_set(True)
        bpy.context.view_layer.objects.active = rk
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        rk.rigid_body.mass = 8.0
        rk.rigid_body.use_deactivation = True
        rk.rigid_body.use_start_deactivated = True
    _make_shockwave_ring(scene, "RingStage3", (13.5, 0.0, 0.1), 122, 9.5)

    print("[T4] Baking 3-Stage Scale Escalation physics...", flush=True)
    t0 = time.time()
    bpy.ops.ptcache.bake_all(bake=True)
    print(f"[T4] Bake finished in {time.time() - t0:.1f}s", flush=True)

    # Dynamic continuous zoom-out camera (human + cones -> Ferrari -> giant 11m Asteroid!)
    cam = create_camera(scene, "T4Cam")
    for f in range(1, total_frames + 1):
        if f <= 45:
            u = (f - 1) / 44.0
            shk = 0.03 * math.sin(f * 3.0) * math.exp(-max(0, f - 22) / 5.0) if f >= 22 else 0.0
            keyframe_camera(cam, f, lerp_vec((-1.8, -6.4, 2.2), (-1.2, -7.8, 2.5), u) + Vector((0, 0, shk)), lerp_vec((-1.2, 0.0, 1.0), (-0.8, 0.0, 1.2), u), lens=32.0)
        elif f <= 95:
            u = (f - 46) / 49.0
            shk = 0.14 * math.sin(f * 2.8) * math.exp(-max(0, f - 72) / 8.0) if f >= 72 else 0.0
            keyframe_camera(cam, f, lerp_vec((0.5, -11.5, 3.2), (1.8, -14.5, 3.8), u) + Vector((0, 0, shk)), lerp_vec((0.8, 0.0, 2.2), (1.5, 0.0, 1.8), u), lens=28.0)
        else:
            u = (f - 96) / max(1.0, float(total_frames - 96))
            shk = 0.34 * math.sin(f * 2.7) * math.exp(-max(0, f - 122) / 9.0) if f >= 122 else 0.0
            keyframe_camera(cam, f, lerp_vec((2.2, -19.0, 4.8), (3.8, -26.5, 6.2), u) + Vector((shk, 0.0, shk * 0.9)), lerp_vec((3.5, 0.0, 3.5), (5.5, 0.0, 3.2), u), lens=24.0)

    return scene, [
        ("F022_bowling_hit", 22),
        ("F074_ferrari_smash", 74),
        ("F116_asteroid_drop", 116),
        ("F130_giant_impact", 130),
    ]
