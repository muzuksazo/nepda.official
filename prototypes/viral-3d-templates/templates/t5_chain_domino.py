"""Template T5: Exponential Giant Domino Chain Reaction (10 Bullet Rigid Body Monoliths)."""

from __future__ import annotations

import math
import os
import time
from typing import Dict, List, Tuple

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


def _watcher_pose(f: int, f_end_smash: int) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, float]]:
    turn = smoothstep(15.0, float(f_end_smash), float(f))
    wow = smoothstep(float(f_end_smash - 15), float(f_end_smash + 8), float(f))
    pose = {
        "Spine": (8.0 * (1.0 - turn) - 10.0 * wow, 0.0, 0.0),
        "Head": (-6.0 - 20.0 * wow, -18.0 + 36.0 * turn, 0.0),
        "Neck": (-4.0 - 10.0 * wow, -10.0 + 22.0 * turn, 0.0),
        "LeftShoulder": (0.0, 0.0, -6.0 + 12.0 * wow),
        "RightShoulder": (0.0, 0.0, 6.0 - 12.0 * wow),
        "LeftArm": (32.0 - 78.0 * wow, 0.0, 8.0 + 36.0 * wow),
        "RightArm": (32.0 - 78.0 * wow, 0.0, -8.0 - 36.0 * wow),
        "LeftForeArm": (0.0, 0.0, 22.0 + 62.0 * wow),
        "RightForeArm": (0.0, 0.0, -22.0 - 62.0 * wow),
        "LeftUpLeg": (8.0, 0.0, 4.0),
        "RightUpLeg": (8.0, 0.0, -4.0),
        "LeftLeg": (-14.0, 0.0, 0.0),
        "RightLeg": (-14.0, 0.0, 0.0),
    }
    face = {
        "jawOpen": 0.05 + 0.78 * wow,
        "mouthFunnel": 0.30 * wow,
        "eyeWideLeft": 0.15 + 0.80 * wow,
        "eyeWideRight": 0.15 + 0.80 * wow,
        "browInnerUp": 0.20 + 0.72 * wow,
    }
    return pose, face


def build_scene(spec: Dict, *, samples: int = 24) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    params = spec.get("params", {})
    total_frames = int(spec.get("total_frames", 150))
    n_dom = int(params.get("count", 10))
    h0 = float(params.get("base_height", 0.48))
    growth = float(params.get("growth_ratio", 1.35))

    clear_scene_safe()
    scene = bpy.context.scene
    setup_eevee(scene, width=int(spec.get("width", 720)), height=int(spec.get("height", 1280)),
                fps=int(spec.get("fps", 30)), samples=samples, total_frames=total_frames)
    setup_outdoor_hdri_world(scene, hdri_path=ASSETS["hdri_airfield"])
    # Higher substeps + high tarmac friction + 1.55x timescale so giant 7m domino smashes barrels cleanly inside 5s!
    ensure_rigidbody_world(scene, total_frames=total_frames, substeps=30)
    scene.rigidbody_world.time_scale = 1.55
    build_asphalt_tarmac(scene, size_x=420.0, size_y=240.0, center_x=25.0, friction=0.90, restitution=0.02)

    if os.path.exists(ASSETS["barrier"]):
        for idx, bx in enumerate((-1.0, 6.0, 13.0, 20.0, 27.0)):
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=ASSETS["barrier"])
            new_objs = [x for x in bpy.data.objects if x not in before]
            piv = bpy.data.objects.new(f"T5Barrier_{idx}", None)
            scene.collection.objects.link(piv)
            for o in new_objs:
                if o.parent is None:
                    o.parent = piv
                    o.rotation_mode = "XYZ"
            piv.location = (float(bx), 9.0, 0.008)

    mat_cyan = make_mat("DominoCyan", (0.04, 0.56, 0.96), roughness=0.14, coat=0.9)
    mat_amber = make_mat("DominoAmber", (0.98, 0.34, 0.04), roughness=0.14, coat=0.9)
    mat_band = make_mat("DominoWhiteBar", (0.94, 0.96, 0.98), roughness=0.22)

    dominoes: List[bpy.types.Object] = []
    dom_xs: List[float] = []
    dom_hs: List[float] = []
    cur_x = 0.0
    for i in range(n_dom):
        h = h0 * (growth ** i)
        w = 0.50 * h
        thick = 0.10 * h
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cur_x, 0.0, 0.5 * h + 0.002))
        d = bpy.context.active_object
        d.name = f"Domino_{i:02d}"
        d.scale = (thick, w, h)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.modifier_add(type="BEVEL")
        d.modifiers["Bevel"].width = max(0.006, 0.02 * thick)
        d.modifiers["Bevel"].segments = 2
        d.data.materials.append(mat_cyan if i % 2 == 0 else mat_amber)

        # Crisp white center stripe on each domino
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
        bar = bpy.context.active_object
        bar.scale = (thick * 1.03, w * 0.88, h * 0.045)
        bar.data.materials.append(mat_band)
        bar.parent = d

        bpy.ops.object.select_all(action="DESELECT")
        d.select_set(True)
        bpy.context.view_layer.objects.active = d
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        d.rigid_body.collision_shape = "BOX"
        d.rigid_body.mass = max(1.0, 12.0 * (h ** 1.35))
        d.rigid_body.friction = 0.80
        d.rigid_body.restitution = 0.12
        d.rigid_body.linear_damping = 0.0
        d.rigid_body.angular_damping = 0.0

        dominoes.append(d)
        dom_xs.append(cur_x)
        dom_hs.append(h)
        # Spacing ~0.64 * h hits next domino around ~32 deg tilt (past COM threshold!)
        cur_x += 0.64 * h

    # Steel Pusher Ball hits Domino_00 top cleanly F5..15
    ball_m = make_mat("TriggerSteel", (0.78, 0.82, 0.88), metallic=0.95, roughness=0.14)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=18, ring_count=12, radius=0.14, location=(-0.6, 0.0, h0 * 0.82))
    trig = bpy.context.active_object
    trig.data.materials.append(ball_m)
    bpy.ops.object.select_all(action="DESELECT")
    trig.select_set(True)
    bpy.context.view_layer.objects.active = trig
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    trig.rigid_body.collision_shape = "SPHERE"
    trig.rigid_body.kinematic = True
    for f in range(1, total_frames + 1):
        if f <= 8:
            x = lerp(-0.45, 0.55, (f - 1) / 7.0)
        elif f <= 16:
            x = lerp(0.55, -2.0, (f - 8) / 8.0)
        else:
            x = -2.0
        trig.location = (x, 0.0, h0 * 0.82)
        trig.keyframe_insert(data_path="location", frame=f)

    # Target stack right where Domino #9 falls (x_last + 0.45 * h_last)
    x_last, h_last = dom_xs[-1], dom_hs[-1]
    x_tgt = x_last + 0.45 * h_last
    for idx, (bx, by, bz) in enumerate((
        (x_tgt, -0.62, 0.445), (x_tgt, 0.0, 0.445), (x_tgt, 0.62, 0.445),
        (x_tgt, -0.31, 1.325), (x_tgt, 0.31, 1.325), (x_tgt, 0.0, 2.205),
    )):
        import_centered_barrel(scene, f"T5Barrel_{idx}", (bx, by, bz), mass=4.5, deactivated=True)

    car, _ = import_ferrari_oriented_x(scene, body_color=(0.98, 0.72, 0.02))
    car.location = (x_tgt + 3.2, 0.0, 0.04)
    scene.frame_set(1)
    assert_car_oriented_x(car)

    print("[T5] Baking 10-Domino exponential Bullet chain...", flush=True)
    t0 = time.time()
    bpy.ops.ptcache.bake_all(bake=True)
    print(f"[T5] Bake finished in {time.time() - t0:.1f}s", flush=True)

    # Verify all dominoes actually tipped AND find wave front trajectory!
    wave_x: Dict[int, float] = {}
    fall_frame_last = 120
    for f in range(1, total_frames + 1):
        scene.frame_set(f)
        cur_wx = dom_xs[0]
        for idx, d in enumerate(dominoes):
            tilt = abs(math.degrees(d.matrix_world.to_euler().y))
            if tilt > 18.0:
                cur_wx = max(cur_wx, dom_xs[idx])
                if idx == len(dominoes) - 1 and fall_frame_last == 120:
                    fall_frame_last = f
        wave_x[f] = cur_wx

    scene.frame_set(total_frames - 3)
    final_tilts = [round(abs(math.degrees(d.matrix_world.to_euler().y)), 1) for d in dominoes]
    print(f"[T5] Domino tilts @F{total_frames-3}: {final_tilts} (last tip F{fall_frame_last})", flush=True)

    human = import_human_grounded(scene, location=(-1.1, -1.6, 0.0), yaw_deg=115.0)
    f_end_smash = min(total_frames - 10, fall_frame_last + 18)
    for f in range(1, total_frames + 1):
        pose, face = _watcher_pose(f, f_end_smash)
        apply_pose_euler_dict(human["arm"], f, pose)
        apply_face_weights(human["shaped_meshes"], f, face)

    cam = create_camera(scene, "T5Cam")
    for f in range(1, total_frames + 1):
        u = (f - 1) / max(1.0, float(total_frames - 1))
        wx = wave_x[f]
        shk = 0.25 * math.sin(f * 2.8) * math.exp(-max(0, f - f_end_smash) / 9.0) if f >= f_end_smash else 0.0
        # Smooth pull-out from close trigger (x=0.5, y=-3.8, z=1.5) out to giant 8m domino monolith & barrel crash!
        loc = lerp_vec((0.2, -3.6, 1.45), (x_last + 1.5, -18.5, 6.8), smoothstep(0.05, 0.92, u)) + Vector((shk, 0.0, shk * 0.8))
        tgt = lerp_vec((0.5, -0.3, 0.9), (wx * 0.4 + x_tgt * 0.6, 0.0, 2.2), smoothstep(0.05, 0.92, u))
        keyframe_camera(cam, f, loc, tgt, lens=lerp(32.0, 24.0, smoothstep(0.1, 0.9, u)))

    return scene, [
        ("F016_trigger_first", 16),
        ("F065_mid_dominoes", 65),
        ("F105_giant_monolith", min(total_frames - 20, max(85, fall_frame_last - 4))),
        ("F138_barrel_crush", min(total_frames - 5, max(120, f_end_smash + 6))),
    ]
