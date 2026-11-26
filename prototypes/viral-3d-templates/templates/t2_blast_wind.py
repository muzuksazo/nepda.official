"""Template T2: Jet Blast Wind, Umbrella Invert & Active Ragdoll Barrel Crash."""

from __future__ import annotations

import math
import os
import random
import time
from typing import Dict, List, Tuple

import bmesh
import bpy
from mathutils import Euler, Vector

from core.active_ragdoll import (
    attach_zero_spring_ragdoll,
    compose_hybrid_active_ragdoll,
    import_human_grounded,
    print_ragdoll_diagnostics,
)
from core.scene_core import (
    ASSETS,
    build_asphalt_tarmac,
    clamp01,
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


def _prelaunch_umbrella_pose(f: int, f_rel: int) -> Dict[str, Tuple[float, float, float]]:
    brace = smoothstep(f_rel * 0.50, f_rel * 0.93, float(min(f, f_rel - 1)))
    shake = math.sin(f * 1.9) * 3.5 * brace
    return {
        "Spine": (6.0 + 18.0 * brace + 0.4 * shake, 0.0, 0.0),
        "Spine1": (6.0 + 14.0 * brace, 0.0, 0.0),
        "Spine2": (4.0 + 10.0 * brace, 0.0, 0.0),
        "Neck": (-8.0 + 14.0 * brace, 0.0, 0.0),
        "Head": (-6.0 + 10.0 * brace + 0.6 * shake, 0.0, 0.0),
        "LeftShoulder": (0.0, 0.0, -6.0 + 10.0 * brace),
        "RightShoulder": (0.0, 0.0, 8.0),
        "LeftArm": (32.0 - 52.0 * brace, 0.0, 8.0 + 20.0 * brace),
        "RightArm": (-38.0 - 22.0 * brace, 0.0, -24.0 - 12.0 * brace),
        "LeftForeArm": (0.0, 0.0, 22.0 + 55.0 * brace),
        "RightForeArm": (8.0, 0.0, -78.0 - 10.0 * brace),
        "LeftUpLeg": (8.0 + 16.0 * brace, 0.0, 4.0),
        "RightUpLeg": (8.0 + 6.0 * brace, 0.0, -4.0),
        "LeftLeg": (-14.0 - 18.0 * brace, 0.0, 0.0),
        "RightLeg": (-14.0 - 10.0 * brace, 0.0, 0.0),
    }


def build_scene(spec: Dict, *, samples: int = 24) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    params = spec.get("params", {})
    total_frames = int(spec.get("total_frames", 150))
    scale_t = total_frames / 300.0
    f_open = max(6, int(round(38 * scale_t)))
    f_inv0 = max(f_open + 10, int(round(92 * scale_t)))
    f_inv1 = max(f_inv0 + 12, int(round(126 * scale_t)))
    f_rel = max(f_inv1 + 6, int(round(148 * scale_t)))

    clear_scene_safe()
    scene = bpy.context.scene
    setup_eevee(scene, width=int(spec.get("width", 720)), height=int(spec.get("height", 1280)),
                fps=int(spec.get("fps", 30)), samples=samples, total_frames=total_frames)
    setup_outdoor_hdri_world(scene, hdri_path=ASSETS["hdri_airfield"])
    ensure_rigidbody_world(scene, total_frames=total_frames)
    build_asphalt_tarmac(scene)

    # Parked Airbus A350 & concrete road barriers
    if os.path.exists(ASSETS["a350"]):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=ASSETS["a350"])
        new_objs = [x for x in bpy.data.objects if x not in before]
        piv = bpy.data.objects.new("ParkedA350", None)
        scene.collection.objects.link(piv)
        for o in new_objs:
            if o.parent is None:
                o.parent = piv
                o.rotation_mode = "XYZ"
        piv.location = (22.0, 29.0, 4.07)
        piv.rotation_mode = "XYZ"
        piv.rotation_euler = (0.0, 0.0, math.radians(-22.0))

    if os.path.exists(ASSETS["barrier"]):
        for idx, bx in enumerate((2.0, 10.0, 18.0, 26.0, 34.0, 42.0)):
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=ASSETS["barrier"])
            new_objs = [x for x in bpy.data.objects if x not in before]
            piv = bpy.data.objects.new(f"ApronBarrier_{idx}", None)
            scene.collection.objects.link(piv)
            for o in new_objs:
                if o.parent is None:
                    o.parent = piv
                    o.rotation_mode = "XYZ"
            piv.location = (float(bx), 7.6, 0.008)

    # Hero Turbofan Jet Engine at x=0 exhausting +X
    rig_steel = make_mat("T2Steel", (0.14, 0.16, 0.19), metallic=0.78, roughness=0.35)
    hazard_y = make_mat("T2Hazard", (0.98, 0.72, 0.02), roughness=0.36)
    cowling_w = make_mat("T2Cowl", (0.86, 0.89, 0.93), metallic=0.25, roughness=0.18, coat=0.7)
    titanium = make_mat("T2Ti", (0.55, 0.59, 0.65), metallic=0.92, roughness=0.18)
    nozzle_m = make_mat("T2Nozzle", (0.22, 0.20, 0.22), metallic=0.90, roughness=0.30)
    core_glow = make_mat("T2Core", (1.0, 0.42, 0.08), emission_color=(1.0, 0.46, 0.10), emission_strength=4.0)

    stand = bpy.data.objects.new("TurbofanStand", None)
    scene.collection.objects.link(stand)
    for sy in (-1.35, 1.35):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, sy, 0.09))
        sk = bpy.context.active_object
        sk.scale = (4.2, 0.28, 0.18)
        sk.data.materials.append(hazard_y)
        sk.parent = stand
        for sx in (-1.4, 1.1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.11, depth=1.55, location=(sx, sy * 0.78, 0.90))
            lg = bpy.context.active_object
            lg.rotation_euler = (math.radians(16.0 if sy < 0 else -16.0), 0.0, 0.0)
            lg.data.materials.append(rig_steel)
            lg.parent = stand

    z_hub = 1.78
    bm = bmesh.new()
    prof = [(-2.05, 1.04), (-2.12, 1.12), (-1.95, 1.24), (-0.80, 1.30), (0.60, 1.26), (1.65, 1.10), (1.72, 0.98), (1.58, 0.88), (-1.75, 1.02)]
    rings = [[bm.verts.new((px, pr * math.cos(2 * math.pi * k / 40), z_hub + pr * math.sin(2 * math.pi * k / 40))) for k in range(40)] for px, pr in prof]
    for ir in range(len(rings)):
        r0, r1 = rings[ir], rings[(ir + 1) % len(rings)]
        mi = 1 if prof[ir][0] < -1.85 else (2 if prof[ir][0] > 1.45 else 0)
        for k in range(40):
            f_p = bm.faces.new((r0[k], r0[(k + 1) % 40], r1[(k + 1) % 40], r1[k]))
            f_p.material_index = mi
    nm = bpy.data.meshes.new("T2Nacelle")
    bm.to_mesh(nm)
    bm.free()
    for p in nm.polygons:
        p.use_smooth = True
    nac = bpy.data.objects.new("Nacelle", nm)
    scene.collection.objects.link(nac)
    for m in (cowling_w, titanium, nozzle_m):
        nac.data.materials.append(m)
    nac.parent = stand

    bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=0.62, radius2=0.14, depth=1.35, location=(2.05, 0.0, z_hub), rotation=(0.0, math.radians(90.0), 0.0))
    core = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    core.data.materials.append(core_glow)
    core.parent = stand
    em_s = core_glow.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for fn, ev in ((1, 3.0), (f_inv0 - 15, 6.0), (f_inv0 + 10, 22.0), (total_frames, 12.0)):
        em_s.default_value = ev
        em_s.keyframe_insert(data_path="default_value", frame=fn)

    # Wind streaks
    sm = make_mat("T2Streak", (0.86, 0.96, 1.0), emission_color=(0.75, 0.92, 1.0), emission_strength=3.2)
    rng = random.Random(777)
    streaks = []
    for _ in range(55):
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=rng.uniform(0.014, 0.03), depth=rng.uniform(1.8, 3.6), location=(0.0, 0.0, -30.0), rotation=(0.0, math.pi * 0.5, 0.0))
        so = bpy.context.active_object
        so.data.materials.append(sm)
        a = rng.uniform(0.0, 2.0 * math.pi)
        rc = rng.uniform(0.15, 0.95)
        streaks.append((so, rng.uniform(0.0, 1.0), rng.uniform(28.0, 44.0), math.cos(a) * rc, math.sin(a) * rc))
    for f in range(1, total_frames + 1):
        t = (f - 1) / 30.0
        vs = smoothstep(float(f_open), float(f_inv0), float(f)) * (1.0 - smoothstep(float(total_frames - 25), float(total_frames), float(f)))
        for so, ph, spd, cy, cz in streaks:
            if vs < 0.02:
                so.location = (0.0, 0.0, -30.0)
            else:
                u = (ph + t * (spd / 38.0)) % 1.0
                sp = 1.0 + u * 1.65
                so.location = (2.3 + u * 38.0, cy * sp, z_hub + cz * sp * 0.85)
                so.scale = (1.0, 1.0, vs)
            so.keyframe_insert(data_path="location", frame=f)
            so.keyframe_insert(data_path="scale", frame=f)

    # Striped Umbrella with WAVE wind flutter + Invert shape key
    accent = tuple(params.get("umbrella_accent_color", [0.94, 0.80, 0.16]))
    nylon_m = make_mat("T2UmbBlk", (0.07, 0.08, 0.11), roughness=0.22, coat=0.55)
    stripe_m = make_mat("T2UmbAcc", accent, roughness=0.24, coat=0.55)
    steel_m = make_mat("T2UmbStl", (0.76, 0.79, 0.84), metallic=0.9, roughness=0.20)
    wood_m = make_mat("T2UmbWood", (0.32, 0.15, 0.07), roughness=0.36, coat=0.5)

    umb = bpy.data.objects.new("HeroUmbrella", None)
    scene.collection.objects.link(umb)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.016, depth=0.98, location=(0.0, 0.0, 0.19))
    sh = bpy.context.active_object
    sh.data.materials.append(steel_m)
    sh.parent = umb
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.026, depth=0.18, location=(0.0, 0.0, -0.30))
    gp = bpy.context.active_object
    gp.data.materials.append(wood_m)
    gp.parent = umb

    bm = bmesh.new()
    n_seg, n_rings, rad = 24, 9, 0.82
    apex = bm.verts.new((0.0, 0.0, 0.68))
    rings = [[bm.verts.new((rad * (ir / n_rings) * math.cos(2 * math.pi * it / n_seg), rad * (ir / n_rings) * math.sin(2 * math.pi * it / n_seg), 0.68 - 0.30 * ((ir / n_rings) ** 2))) for it in range(n_seg)] for ir in range(1, n_rings + 1)]
    for it in range(n_seg):
        bm.faces.new((apex, rings[0][it], rings[0][(it + 1) % n_seg])).material_index = 1 if (it // 3) % 2 == 1 else 0
    for ir in range(n_rings - 1):
        for it in range(n_seg):
            itn = (it + 1) % n_seg
            bm.faces.new((rings[ir][it], rings[ir + 1][it], rings[ir + 1][itn], rings[ir][itn])).material_index = 1 if (it // 3) % 2 == 1 else 0
    cm = bpy.data.meshes.new("T2Canopy")
    bm.to_mesh(cm)
    bm.free()
    for p in cm.polygons:
        p.use_smooth = True
    canopy = bpy.data.objects.new("T2CanopyObj", cm)
    scene.collection.objects.link(canopy)
    canopy.data.materials.append(nylon_m)
    canopy.data.materials.append(stripe_m)
    canopy.parent = umb
    canopy.shape_key_add(name="Basis")
    sk_furl = canopy.shape_key_add(name="Furled")
    sk_inv = canopy.shape_key_add(name="Invert")
    for i, v in enumerate(cm.vertices):
        dxy = math.hypot(v.co.x, v.co.y)
        u = clamp01(dxy / rad)
        ang = math.atan2(v.co.y, v.co.x)
        sk_furl.data[i].co = Vector((v.co.x * 0.14, v.co.y * 0.14, 0.68 - 0.65 * u))
        sk_inv.data[i].co = Vector((dxy * 0.78 * math.cos(ang), dxy * 0.78 * math.sin(ang), 0.68 + 0.68 * (u ** 1.25) + 0.08 * math.sin(8 * ang) * (u ** 2)))

    wv = canopy.modifiers.new("WindFlutter", "WAVE")
    wv.use_x = True
    wv.use_y = True
    wv.use_normal = True
    wv.width = 0.28
    wv.speed = 0.9
    for fw, hw in ((1, 0.0), (f_open, 0.015), (f_inv0, 0.08), (f_inv1, 0.11), (f_rel, 0.0)):
        wv.height = hw
        wv.keyframe_insert(data_path="height", frame=fw)
    canopy.modifiers.new("UmbThick", "SOLIDIFY").thickness = 0.016

    for fn in (1, 10, f_open, f_inv0, f_inv1, total_frames):
        sk_furl.value = 1.0 - smoothstep(10.0, float(f_open), float(fn))
        sk_furl.keyframe_insert(data_path="value", frame=fn)
        sk_inv.value = smoothstep(float(f_inv0), float(f_inv1), float(fn))
        sk_inv.keyframe_insert(data_path="value", frame=fn)

    # Human facing -X + Zero-Spring Ragdoll
    human = import_human_grounded(scene, location=(6.2, 0.0, 0.0), yaw_deg=-90.0)
    hips_world_mat = (human["arm"].matrix_world @ human["arm"].pose.bones["Hips"].matrix).to_3x3()
    face_dir = (hips_world_mat @ Vector((0.0, 0.0, 1.0))).normalized()
    assert face_dir.x < -0.9, f"Expected human facing -X, got {face_dir}"
    rag = attach_zero_spring_ragdoll(scene, human, release_frame=f_rel, total_frames=total_frames, hips_ang_damping=0.72)

    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.15, depth=0.5, location=(4.55, 0.0, 0.45))
    piston = bpy.context.active_object
    piston.hide_render = True
    bpy.ops.object.select_all(action="DESELECT")
    piston.select_set(True)
    bpy.context.view_layer.objects.active = piston
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    piston.rigid_body.kinematic = True
    piston.rigid_body.restitution = 0.35
    piston.location = (4.55, 0.0, 0.45)
    piston.rotation_euler = (0.0, math.radians(38.0), 0.0)
    piston.keyframe_insert(data_path="location", frame=1)
    piston.keyframe_insert(data_path="location", frame=f_rel - 1)
    piston.location = (7.25, 0.04, 3.85)
    piston.keyframe_insert(data_path="location", frame=f_rel + 7)
    piston.location = (7.25, 0.04, -25.0)
    piston.keyframe_insert(data_path="location", frame=f_rel + 14)

    # 6 Barrels (2-pass target lock)
    b_mass = float(params.get("barrel_mass", 4.5))
    drums = [import_centered_barrel(scene, f"T2Barrel_{i}", (120.0, float(i) * 1.5, 0.445), mass=b_mass) for i in range(6)]

    # Pass 1 bake -> locate landing -> Pass 2 bake
    bpy.ops.ptcache.bake_all(bake=True)
    f_hit = min(total_frames - 18, f_rel + int(round(100 * scale_t)))
    hit_pos = Vector((42.0, -1.5, 0.8))
    for f in range(f_rel + 15, total_frames - 5):
        scene.frame_set(f)
        hp = rag["hips_rb"].matrix_world.translation
        if hp.z <= 1.55 and hp.x > 14.0:
            f_hit = f
            hit_pos = hp.copy()
            break
    bpy.ops.ptcache.free_bake_all()
    cx, cy = hit_pos.x + 0.5, hit_pos.y
    for d, (bx, by, bz) in zip(drums, [(cx, cy - 0.62, 0.445), (cx, cy, 0.445), (cx, cy + 0.62, 0.445), (cx, cy - 0.31, 1.325), (cx, cy + 0.31, 1.325), (cx, cy, 2.205)]):
        d.location = (bx, by, bz)
        d.rotation_euler = (0.0, 0.0, 0.0)
    print(f"[T2] Barrel crash target placed at F{f_hit} {tuple(round(x, 2) for x in hit_pos)}", flush=True)
    bpy.ops.ptcache.bake_all(bake=True)

    hips_pos, hips_rot = compose_hybrid_active_ragdoll(
        scene, rag, release_frame=f_rel, total_frames=total_frames,
        prelaunch_fn=lambda f: _prelaunch_umbrella_pose(f, f_rel), alarm_start_frame=f_open,
    )

    # Lock umbrella onto hand F1..f_rel-1 and hide F>=f_rel
    rhand = rag["arm"].pose.bones["RightHand"]
    for f in range(1, f_rel):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        hw = rag["arm"].matrix_world @ rhand.head
        br = smoothstep(float(f_open), float(f_rel - 2), float(f))
        ur = Euler((0.0, math.radians(-84.0 + 8.0 * br), 0.0), "XYZ")
        umb.rotation_mode = "XYZ"
        umb.rotation_euler = ur
        umb.location = hw - (ur.to_matrix() @ Vector((0.0, 0.0, -0.30)))
        umb.keyframe_insert(data_path="location", frame=f)
        umb.keyframe_insert(data_path="rotation_euler", frame=f)
    for ch in (sh, gp, canopy):
        ch.hide_render = False
        ch.keyframe_insert(data_path="hide_render", frame=1)
        ch.hide_render = True
        ch.keyframe_insert(data_path="hide_render", frame=f_rel)

    cam = create_camera(scene, "T2Cam")
    fl_d = bpy.data.lights.new("T2FaceFill", type="AREA")
    fl_d.size = 5.5
    fl = bpy.data.objects.new("T2FaceFill", fl_d)
    scene.collection.objects.link(fl)

    s1_end = int(round(75 * scale_t))
    s2_end = f_rel + 2
    s3_end = max(s2_end + 10, f_hit - 12)
    for f in range(1, total_frames + 1):
        if f <= s1_end:
            u = (f - 1) / max(1.0, float(s1_end - 1))
            keyframe_camera(cam, f, lerp_vec((10.5, -13.5, 4.4), (9.2, -10.8, 3.3), u), lerp_vec((2.2, 2.0, 1.8), (3.4, 0.2, 1.5), u), lens=28.0)
            fl_d.energy = 0.0
        elif f <= s2_end:
            u = (f - s1_end - 1) / max(1.0, float(s2_end - s1_end - 1))
            keyframe_camera(cam, f, lerp_vec((9.6, -5.6, 1.85), (9.0, -4.8, 1.70), u), lerp_vec((4.4, 0.0, 1.35), (4.0, 0.0, 1.40), u), lens=30.0)
            fl_d.energy = 0.0
        elif f <= s3_end:
            u = (f - s2_end - 1) / max(1.0, float(s3_end - s2_end - 1))
            hp = hips_pos[f]
            hf = (hips_rot[f].to_matrix() @ Vector((0.0, 0.0, 1.0))).normalized()
            cd = (hf * 0.55 + Vector((0.55, -0.70, 0.35)).normalized() * 0.45).normalized()
            if cd.z < 0.25:
                cd.z = 0.25
                cd.normalize()
            cl = hp + cd * lerp(2.45, 2.20, u)
            keyframe_camera(cam, f, cl, hp + Vector((-0.35, 0.10, -0.15)), roll_deg=lerp(-6.0, 5.0, u), lens=24.0)
            fl.location = cl + Vector((0.3, -0.4, 0.4))
            fl.rotation_mode = "QUATERNION"
            fl.rotation_quaternion = (hp - fl.location).to_track_quat("-Z", "Y")
            fl.keyframe_insert(data_path="location", frame=f)
            fl.keyframe_insert(data_path="rotation_quaternion", frame=f)
            fl_d.energy = 135.0
        else:
            u = (f - s3_end - 1) / max(1.0, float(total_frames - s3_end - 1))
            keyframe_camera(cam, f, Vector((hit_pos.x + 4.8 - 0.8 * u, hit_pos.y - 4.8, 1.65)), Vector((hit_pos.x + 0.8, hit_pos.y, 1.05)), lens=28.0)
            fl_d.energy = 0.0
        fl_d.keyframe_insert(data_path="energy", frame=f)

    print_ragdoll_diagnostics(scene, rag["arm"], (f_open, f_inv1, f_rel + 10, int(0.5 * (f_rel + f_hit)), f_hit))
    return scene, [
        ("F018_hook_runway", max(12, int(round(35 * scale_t)))),
        ("F060_umbrella_invert", max(25, f_inv1 - 3)),
        ("F100_ragdoll_flight", max(45, int(0.5 * (f_rel + f_hit)))),
        ("F135_barrel_crash", min(total_frames - 4, f_hit + 5)),
    ]
