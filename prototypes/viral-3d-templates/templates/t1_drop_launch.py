"""Template T1: Drop Impact & Catapult Active Ragdoll (Cloth Pressure blob + Ocean 4x4 + Ferrari)."""

from __future__ import annotations

import math
import os
import random
import time
from typing import Dict, List, Tuple

import bmesh
import bpy
from mathutils import Matrix, Vector

from core.active_ragdoll import (
    attach_zero_spring_ragdoll,
    compose_hybrid_active_ragdoll,
    import_human_grounded,
    print_ragdoll_diagnostics,
)
from core.scene_core import (
    ASSETS,
    assert_car_oriented_x,
    clear_scene_safe,
    create_camera,
    ensure_rigidbody_world,
    import_ferrari_oriented_x,
    keyframe_camera,
    lerp,
    lerp_vec,
    make_mat,
    setup_eevee,
    setup_outdoor_hdri_world,
    smoothstep,
)


def _build_ocean_and_coast(scene: bpy.types.Scene, sand_mat, total_frames: int) -> None:
    ocean_mat = bpy.data.materials.new("T1OceanMat")
    ocean_mat.use_nodes = True
    nt = ocean_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.04
    bsdf.inputs["IOR"].default_value = 1.333
    bsdf.inputs["Coat Weight"].default_value = 0.85
    bsdf.inputs["Coat Roughness"].default_value = 0.025

    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Foam"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.004, 0.044, 0.21, 1.0)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (0.14, 0.40, 0.72, 1.0)
    nt.links.new(attr.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(-10.0, 45.0, 0.0))
    ocean = bpy.context.active_object
    ocean.name = "OceanWaves"
    om = ocean.modifiers.new("Ocean", "OCEAN")
    om.geometry_mode = "GENERATE"
    om.resolution = 8
    om.spatial_size = 110
    om.repeat_x = 4
    om.repeat_y = 4
    om.choppiness = 1.45
    om.wave_scale = 0.95
    om.wave_scale_min = 0.05
    om.wind_velocity = 15.0
    om.use_foam = True
    om.foam_layer_name = "Foam"
    om.foam_coverage = -0.22
    ocean.data.materials.append(ocean_mat)
    for f in ocean.data.polygons:
        f.use_smooth = True
    for fn in range(1, total_frames + 1, 10):
        om.time = 1.0 + 0.045 * (fn - 1)
        om.keyframe_insert(data_path="time", frame=fn)
    om.time = 1.0 + 0.045 * (total_frames - 1)
    om.keyframe_insert(data_path="time", frame=total_frames)

    skirt_mat = make_mat("OceanSkirt", (0.004, 0.044, 0.21), roughness=0.08, coat=0.7)
    bpy.ops.mesh.primitive_plane_add(size=4200.0, location=(0.0, 0.0, -0.35))
    bpy.context.active_object.data.materials.append(skirt_mat)

    coast_mat = sand_mat if sand_mat is not None else make_mat("CoastSand", (0.72, 0.60, 0.42), roughness=0.82)
    bm = bmesh.new()
    nx, ny = 40, 10
    vg = []
    for iy in range(ny):
        v = iy / (ny - 1)
        y = 420.0 + v * 320.0
        row = []
        for ix in range(nx):
            u = ix / (nx - 1)
            x = -900.0 + u * 1800.0
            z = -2.5 if iy == 0 else -2.0 + v * (22.0 + 18.0 * (0.5 + 0.5 * math.sin(u * 9.0)))
            row.append(bm.verts.new((x, y + 32.0 * math.sin(u * math.pi * 1.4), z)))
        vg.append(row)
    for iy in range(ny - 1):
        for ix in range(nx - 1):
            bm.faces.new((vg[iy][ix], vg[iy][ix + 1], vg[iy + 1][ix + 1], vg[iy + 1][ix]))
    cm = bpy.data.meshes.new("T1Coast")
    bm.to_mesh(cm)
    bm.free()
    for f in cm.polygons:
        f.use_smooth = True
    coast = bpy.data.objects.new("Coastline", cm)
    scene.collection.objects.link(coast)
    coast.data.materials.append(coast_mat)


def _build_cloth_blob(scene: bpy.types.Scene, colors: List[List[float]], total_frames: int) -> None:
    mats = [make_mat(f"T1Blob_{i}", tuple(c), roughness=0.09, coat=1.0, subsurface=0.06) for i, c in enumerate(colors)]
    mesh = bpy.data.meshes.new("T1BlobMesh")
    obj = bpy.data.objects.new("WaterBlobHQ", mesh)
    scene.collection.objects.link(obj)
    for m in mats:
        obj.data.materials.append(m)

    bm = bmesh.new()
    n_seg, half_len, r_max, cap_rings, body_rings = 40, 5.6, 1.98, 12, 52
    rings = []
    tip_l = bm.verts.new((-half_len - r_max * 0.95, 0.0, 0.0))
    for ic in range(1, cap_rings):
        ac = (ic / cap_rings) * (math.pi * 0.5)
        x = -half_len - r_max * 0.95 * math.cos(ac)
        rr = r_max * math.sin(ac)
        rings.append([bm.verts.new((x, rr * math.cos(2 * math.pi * it / n_seg), rr * math.sin(2 * math.pi * it / n_seg) * 0.88)) for it in range(n_seg)])
    for ib in range(body_rings):
        x = -half_len + (ib / max(1, body_rings - 1)) * (2.0 * half_len)
        rings.append([bm.verts.new((x, r_max * math.cos(2 * math.pi * it / n_seg), r_max * math.sin(2 * math.pi * it / n_seg) * 0.88)) for it in range(n_seg)])
    for ic in range(1, cap_rings):
        ac = (ic / cap_rings) * (math.pi * 0.5)
        x = half_len + r_max * 0.95 * math.sin(ac)
        rr = r_max * math.cos(ac)
        rings.append([bm.verts.new((x, rr * math.cos(2 * math.pi * it / n_seg), rr * math.sin(2 * math.pi * it / n_seg) * 0.88)) for it in range(n_seg)])
    tip_r = bm.verts.new((half_len + r_max * 0.95, 0.0, 0.0))

    def bidx(xv: float) -> int:
        t = (xv + half_len + r_max) / (2.0 * (half_len + r_max))
        return min(len(mats) - 1, int(t * len(mats)))

    for it in range(n_seg):
        itn = (it + 1) % n_seg
        bm.faces.new((tip_l, rings[0][itn], rings[0][it])).material_index = 0
        bm.faces.new((tip_r, rings[-1][it], rings[-1][itn])).material_index = len(mats) - 1
    for ix in range(len(rings) - 1):
        mi = bidx(0.5 * (rings[ix][0].co.x + rings[ix + 1][0].co.x))
        for it in range(n_seg):
            itn = (it + 1) % n_seg
            bm.faces.new((rings[ix][it], rings[ix][itn], rings[ix + 1][itn], rings[ix + 1][it])).material_index = mi
    bm.to_mesh(mesh)
    bm.free()
    for f in mesh.polygons:
        f.use_smooth = True
    obj.location = (0.0, 0.0, 1.35)

    vg = obj.vertex_groups.new(name="PinBottom")
    for v in mesh.vertices:
        if v.co.z < -1.15:
            vg.add([v.index], 1.0, "REPLACE")
        elif v.co.z < -0.75:
            vg.add([v.index], 0.35, "REPLACE")

    cloth = obj.modifiers.new("ClothBlob", "CLOTH")
    cloth.settings.quality = 10
    cloth.settings.mass = 0.6
    cloth.settings.vertex_group_mass = "PinBottom"
    cloth.settings.pin_stiffness = 1.6
    cloth.settings.use_pressure = True
    cloth.settings.uniform_pressure_force = 3.8
    cloth.settings.pressure_factor = 1.6
    cloth.settings.tension_stiffness = 24.0
    cloth.settings.compression_stiffness = 24.0
    cloth.settings.shear_stiffness = 18.0
    cloth.settings.bending_stiffness = 2.2
    cloth.settings.tension_damping = 10.0
    cloth.settings.bending_damping = 1.5
    cloth.collision_settings.use_collision = True
    cloth.collision_settings.distance_min = 0.06
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = total_frames
    sub = obj.modifiers.new("SmoothPost", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1


def _build_truss_tower(scene: bpy.types.Scene) -> None:
    steel_mat = make_mat("T1Steel", (0.78, 0.82, 0.88), metallic=0.88, roughness=0.22)
    deck_mat = make_mat("T1Deck", (0.16, 0.19, 0.23), metallic=0.65, roughness=0.38)
    hazard_mat = make_mat("T1Hazard", (0.98, 0.75, 0.02), roughness=0.35)
    bm = bmesh.new()

    def strut(p1: Vector, p2: Vector, r: float = 0.09):
        vec = p2 - p1
        if vec.length < 1e-4:
            return
        mat = Matrix.Translation((p1 + p2) * 0.5) @ vec.to_track_quat("Z", "Y").to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8, radius1=r, radius2=r, depth=vec.length, matrix=mat)

    x0, x1, y0, y1, z_top, levels = -16.5, -8.5, -3.4, 3.4, 26.5, 7
    dz = z_top / levels
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for cx, cy in corners:
        strut(Vector((cx, cy, -1.0)), Vector((cx, cy, z_top)), r=0.14)
    for lv in range(levels + 1):
        z = lv * dz
        pts = [Vector((cx, cy, z)) for cx, cy in corners]
        for k in range(4):
            strut(pts[k], pts[(k + 1) % 4], r=0.11)
        if lv < levels:
            pts_u = [Vector((cx, cy, (lv + 1) * dz)) for cx, cy in corners]
            for k in range(4):
                strut(pts[k], pts_u[(k + 1) % 4], r=0.075)
                strut(pts[(k + 1) % 4], pts_u[k], r=0.075)
    mesh = bpy.data.meshes.new("T1TrussMesh")
    bm.to_mesh(mesh)
    bm.free()
    tower = bpy.data.objects.new("HQTrussTower", mesh)
    scene.collection.objects.link(tower)
    tower.data.materials.append(steel_mat)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-11.5, 0.0, z_top + 0.25))
    deck = bpy.context.active_object
    deck.scale = (11.5, 7.6, 0.45)
    deck.data.materials.append(deck_mat)
    deck.parent = tower

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-5.85, 0.0, z_top + 0.48))
    curb = bpy.context.active_object
    curb.scale = (0.35, 7.6, 0.08)
    curb.data.materials.append(hazard_mat)
    curb.parent = tower


def _prelaunch_lookup_pose(f: int) -> Dict[str, Tuple[float, float, float]]:
    look_t = smoothstep(15.0, 38.0, float(min(f, 44)))
    return {
        "Neck": (-14.0 * look_t, -14.0 * look_t, 0.0),
        "Head": (-22.0 * look_t, -24.0 * look_t, 0.0),
        "LeftShoulder": (0.0, 0.0, -6.0),
        "RightShoulder": (0.0, 0.0, 6.0),
        "LeftArm": (34.0, 0.0, 8.0),
        "RightArm": (34.0, 0.0, -8.0),
        "LeftForeArm": (0.0, 0.0, 22.0),
        "RightForeArm": (0.0, 0.0, -22.0),
        "LeftUpLeg": (8.0, 0.0, 4.0),
        "RightUpLeg": (8.0, 0.0, -4.0),
        "LeftLeg": (-14.0, 0.0, 0.0),
        "RightLeg": (-14.0, 0.0, 0.0),
    }


def build_scene(spec: Dict, *, samples: int = 24) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    params = spec.get("params", {})
    total_frames = int(spec.get("total_frames", 150))
    width = int(spec.get("width", 720))
    height = int(spec.get("height", 1280))
    fps = int(spec.get("fps", 30))

    kept = clear_scene_safe(keep_sand=True)
    scene = bpy.context.scene
    setup_eevee(scene, width=width, height=height, fps=fps, samples=samples, total_frames=total_frames)
    setup_outdoor_hdri_world(scene, hdri_path=ASSETS["hdri_airfield"], preserved_world=kept["world"])
    ensure_rigidbody_world(scene, total_frames=total_frames)

    fill_d = bpy.data.lights.new("T1Fill", type="AREA")
    fill_d.energy = 240.0
    fill_d.size = 24.0
    fill_o = bpy.data.objects.new("T1Fill", fill_d)
    scene.collection.objects.link(fill_o)
    fill_o.location = (6.0, -28.0, 22.0)
    fill_o.rotation_euler = (math.radians(52.0), 0.0, math.radians(10.0))

    _build_ocean_and_coast(scene, kept["sand_mat"], total_frames)
    colors = params.get("blob_colors", [[0.04, 0.44, 0.96], [0.88, 0.06, 0.08], [0.98, 0.74, 0.04], [0.03, 0.36, 0.88]])
    _build_cloth_blob(scene, colors, total_frames)
    _build_truss_tower(scene)

    car_color = tuple(params.get("car_color", [0.98, 0.72, 0.02]))
    car, wheels = import_ferrari_oriented_x(scene, body_color=car_color, add_cloth_collider=True)

    # Spray droplets
    drop_m = make_mat("T1Spray", (0.90, 0.97, 1.0), roughness=0.05, transmission=0.32, coat=1.0)
    rng = random.Random(909)
    drops = []
    for i in range(85):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rng.uniform(0.07, 0.16), location=(0.0, 0.0, -40.0))
        d = bpy.context.active_object
        bpy.ops.object.shade_smooth()
        d.data.materials.append(drop_m)
        ang = rng.uniform(0.0, 2.0 * math.pi)
        sr = rng.uniform(2.5, 9.0)
        drops.append((d, Vector((rng.uniform(-1.1, 1.1), rng.uniform(-0.9, 0.9), rng.uniform(0.2, 0.8))), Vector((sr * math.cos(ang), sr * math.sin(ang), rng.uniform(7.5, 16.0)))))

    human = import_human_grounded(scene, location=(3.6, 0.0, 2.98), yaw_deg=-18.0, pitch_deg=-4.0, ground_flush=False)
    rag = attach_zero_spring_ragdoll(scene, human, release_frame=45, total_frames=total_frames, hips_ang_damping=0.65)

    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=1.9, depth=0.6, location=(3.6, 0.0, 2.2))
    piston = bpy.context.active_object
    piston.name = "T1Piston"
    piston.hide_render = True
    bpy.ops.object.select_all(action="DESELECT")
    piston.select_set(True)
    bpy.context.view_layer.objects.active = piston
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    piston.rigid_body.kinematic = True
    piston.rigid_body.restitution = 0.35
    piston.location = (3.6, 0.0, 2.2)
    piston.rotation_euler = (math.radians(8.0), math.radians(-5.0), 0.0)
    piston.keyframe_insert(data_path="location", frame=1)
    piston.keyframe_insert(data_path="location", frame=44)
    piston.location = (4.2, -1.2, 6.2)
    piston.keyframe_insert(data_path="location", frame=50)
    piston.location = (4.2, -1.2, -20.0)
    piston.keyframe_insert(data_path="location", frame=56)

    bpy.ops.object.effector_add(type="TURBULENCE", location=(4.5, -4.0, 24.0))
    turb = bpy.context.active_object
    turb.field.size = 6.0
    turb.field.noise = 1.5
    turb.field.strength = 0.0
    turb.field.keyframe_insert(data_path="strength", frame=1)
    turb.field.keyframe_insert(data_path="strength", frame=50)
    turb.field.strength = 85.0
    turb.field.keyframe_insert(data_path="strength", frame=58)

    prev_x = -14.2
    spin = 0.0
    for f in range(1, total_frames + 1):
        if f <= 18:
            u = (f - 1) / 17.0
            car.location = (lerp(-14.2, -6.2, u), 0.0, 26.90)
            car.rotation_euler = (0.0, math.radians(10.0 * smoothstep(0.7, 1.0, u)), 0.0)
        elif f <= 45:
            u = (f - 18) / 27.0
            car.location = (lerp(-6.2, -3.7, u), 0.0, 26.90 - 26.05 * (u * u))
            car.rotation_euler = (0.0, math.radians(lerp(10.0, 54.0, u)), 0.0)
        elif f <= 80:
            u = (f - 45) / 35.0
            car.location = (-3.7 - 0.6 * u, 0.0, 0.85 + 0.45 * math.sin(u * math.pi))
            car.rotation_euler = (math.radians(8.0 * u), math.radians(lerp(54.0, 26.0, u)), 0.0)
        else:
            car.location = (-4.3, 0.0, 0.85)
            car.rotation_euler = (math.radians(8.0), math.radians(26.0), 0.0)
        car.keyframe_insert(data_path="location", frame=f)
        car.keyframe_insert(data_path="rotation_euler", frame=f)

        dx = max(0.0, car.location.x - prev_x) if f <= 45 else 0.0
        prev_x = car.location.x
        spin += dx / 0.28
        for w_o in wheels:
            w_o.rotation_euler = (-spin, 0.0, 0.0)
            w_o.keyframe_insert(data_path="rotation_euler", frame=f)

        for d, off, vel in drops:
            if f < 45 or f > 95:
                d.location = (0.0, 0.0, -40.0)
            else:
                dt = (f - 45) / 30.0
                d.location = Vector((-3.7, 0.0, 1.5)) + off + vel * dt + Vector((0.0, 0.0, -14.0 * dt * dt))
            d.keyframe_insert(data_path="location", frame=f)

    scene.frame_set(1)
    assert_car_oriented_x(car)

    print("[T1] Baking Cloth + Bullet physics...", flush=True)
    t0 = time.time()
    bpy.ops.ptcache.bake_all(bake=True)
    print(f"[T1] Bake finished in {time.time() - t0:.1f}s", flush=True)

    hips_pos, hips_rot = compose_hybrid_active_ragdoll(
        scene, rag, release_frame=45, total_frames=total_frames, prelaunch_fn=_prelaunch_lookup_pose
    )

    cam = create_camera(scene, "T1Cam")
    fl_d = bpy.data.lights.new("FaceFill", type="AREA")
    fl_d.size = 6.0
    fl = bpy.data.objects.new("FaceFill", fl_d)
    scene.collection.objects.link(fl)

    for f in range(1, total_frames + 1):
        if f <= 36:
            u = (f - 1) / 35.0
            keyframe_camera(cam, f, lerp_vec((-8.0, -31.0, 36.0), (-5.5, -24.0, 26.0), smoothstep(0.15, 1.0, u)),
                            lerp_vec((-6.5, 0.0, 14.0), (-2.0, 0.0, 4.5), smoothstep(0.15, 1.0, u)), roll_deg=-18.0 * (1.0 - 0.5 * u), lens=28.0)
            fl_d.energy = 0.0
        elif f <= 80:
            u = (f - 37) / 43.0
            sx = 0.16 * math.sin(f * 2.1) if 44 <= f <= 62 else 0.0
            sz = 0.14 * math.cos(f * 1.9) if 44 <= f <= 62 else 0.0
            tgt = lerp_vec((-0.2, 0.0, 2.5), tuple(hips_pos[f] + Vector((0.0, 0.0, -1.0))), smoothstep(45.0, 76.0, float(f)) * 0.78)
            keyframe_camera(cam, f, Vector((5.2 + sx, -19.5 + 1.5 * u, 3.6 + sz)), tgt, lens=26.0)
            fl_d.energy = 0.0
        else:
            u = (f - 81) / max(1.0, float(total_frames - 81))
            hp = hips_pos[f]
            hf = (hips_rot[f].to_matrix() @ Vector((0.0, 0.0, 1.0))).normalized()
            br = (hp - Vector((0.0, 0.0, 1.35))).normalized()
            cd = (hf * 0.42 + Vector((0.28, -0.82, 0.42)).normalized() * 0.42 + Vector((br.x, br.y, 0.55)).normalized() * 0.16).normalized()
            if cd.z < 0.28:
                cd.z = 0.28
                cd.normalize()
            cloc = hp + cd * lerp(2.45, 2.25, u) + Vector((0.15, -0.30, 0.30))
            keyframe_camera(cam, f, cloc, hp + Vector((-0.15, 0.12, -0.35)), roll_deg=lerp(-7.0, 5.0, u), lens=24.0)
            fl.location = cloc + Vector((0.4, -0.4, 0.5))
            fl.rotation_mode = "QUATERNION"
            fl.rotation_quaternion = (hp - fl.location).to_track_quat("-Z", "Y")
            fl.keyframe_insert(data_path="location", frame=f)
            fl.keyframe_insert(data_path="rotation_quaternion", frame=f)
            fl_d.energy = 120.0
        fl_d.keyframe_insert(data_path="energy", frame=f)

    print_ragdoll_diagnostics(scene, rag["arm"], (15, 45, 65, 95, 115, 140))
    return scene, [("F012_car_drive", 12), ("F040_dive_and_look", 40), ("F054_launch_whip", 54), ("F115_air_active", 115)]
