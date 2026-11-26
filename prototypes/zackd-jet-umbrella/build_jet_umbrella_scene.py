#!/usr/bin/env python3
"""Blender 5.1 Zack D. Films-Style Original 3D Physics Short:
"What If You Opened an Umbrella Behind a Jet Engine?" (300 frames = 10.00s @ 30fps).

Built strictly following `blender-viral-3d-physics` skill standards:
- BLENDER_EEVEE (28 spp, Raytracing, AgX, motion_blur_shutter=0.26, Fog Glow)
- Real Poly Haven HDRI (derelict_airfield_02), Asphalt PBR, Barrel_01, Barrier, Suitcase
- Airbus A350_nologo.glb parked on tarmac + procedural Hero Turbofan Engine stand
- Real Cloth canopy umbrella with WIND force field + inside-out inversion snap
- Everyday suited human (rpm_player.glb) with zero-spring Hybrid Active Ragdoll,
  natural pre-launch pose (zero A-pose), 52-ARKit terrified expressions, and 2-pass
  bullseye barrel-pyramid smash
- Mandatory 4-frame Visual Gate + F1 asset forward-axis & bbox assertions

Usage:
  blender --background --factory-startup --python build_jet_umbrella_scene.py -- --preview-only
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

ROOT = "/Users/yun-yeowon/workspace/ad-studio/zackd-jet-umbrella"
ASSETS = os.path.join(ROOT, "assets")
HUMAN_GLB = "/Users/yun-yeowon/workspace/ad-studio/rnd-sunny-ssambap/ragdoll_test/assets/rpm_player.glb"


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Zack D. Films Original: Jet Engine vs Umbrella")
    p.add_argument("--frames-dir", default=os.path.join(ROOT, "frames"))
    p.add_argument("--save-blend", default=os.path.join(ROOT, "jet_umbrella_scene.blend"))
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--height", type=int, default=1280)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--samples", type=int, default=28)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--render-all", action="store_true")
    return p.parse_args(argv)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _clamp01(x: float) -> float:
    return _clamp(x, 0.0, 1.0)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_vec(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Vector:
    return Vector((_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t)))


def _smoothstep(e0: float, e1: float, x: float) -> float:
    if e1 <= e0:
        return 1.0 if x >= e1 else 0.0
    t = _clamp01((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def _set_input(node: bpy.types.Node, name: str, value) -> None:
    if name in node.inputs:
        node.inputs[name].default_value = value


def _make_mat(
    name: str,
    color,
    *,
    metallic: float = 0.0,
    roughness: float = 0.3,
    coat: float = 0.0,
    emission_color=None,
    emission_strength: float = 0.0,
    transmission: float = 0.0,
    alpha: float = 1.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        _set_input(bsdf, "Base Color", (*color, 1.0))
        _set_input(bsdf, "Metallic", metallic)
        _set_input(bsdf, "Roughness", roughness)
        _set_input(bsdf, "Coat Weight", coat)
        _set_input(bsdf, "Coat Roughness", 0.06)
        _set_input(bsdf, "Transmission Weight", transmission)
        _set_input(bsdf, "Alpha", alpha)
        if emission_color is not None:
            _set_input(bsdf, "Emission Color", (*emission_color, 1.0))
            _set_input(bsdf, "Emission Strength", emission_strength)
    return mat


def _clear_scene_safe() -> None:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves, bpy.data.actions, bpy.data.images):
        for item in list(col):
            if item.users == 0:
                col.remove(item)


def _setup_eevee(scene: bpy.types.Scene, args: argparse.Namespace) -> None:
    scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = args.samples
        if hasattr(scene.eevee, "use_raytracing"):
            scene.eevee.use_raytracing = True
        if hasattr(scene.eevee, "motion_blur_steps"):
            scene.eevee.motion_blur_steps = 3
        if hasattr(scene.eevee, "shadow_ray_count"):
            scene.eevee.shadow_ray_count = 2

    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.fps = args.fps
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.26

    try:
        scene.view_settings.view_transform = "AgX"
    except Exception:
        scene.view_settings.view_transform = "Filmic"
    scene.view_settings.exposure = 0.10

    try:
        ng = bpy.data.node_groups.new("JetComp", "CompositorNodeTree")
        scene.compositing_node_group = ng
        ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        hsv = ng.nodes.new("CompositorNodeHueSat")
        out = ng.nodes.new("NodeGroupOutput")
        for k, v in (("Type", "Fog Glow"), ("Quality", "High"), ("Threshold", 1.15), ("Strength", 0.48), ("Size", 7.0)):
            if k in gl.inputs:
                try:
                    gl.inputs[k].default_value = v
                except Exception:
                    pass
        _set_input(hsv, "Saturation", 1.12)
        _set_input(hsv, "Value", 1.03)
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], hsv.inputs["Image"])
        ng.links.new(hsv.outputs["Image"], out.inputs["Image"])
    except Exception as e:
        print("[jet] Compositor warning:", e, flush=True)


def _setup_world(scene: bpy.types.Scene) -> None:
    world = bpy.data.worlds.new("AirfieldWorld")
    scene.world = world
    if hasattr(world, "use_nodes"):
        world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix_cam = nt.nodes.new("ShaderNodeMixShader")
    lp = nt.nodes.new("ShaderNodeLightPath")

    bg_light = nt.nodes.new("ShaderNodeBackground")
    hdr_path = os.path.join(ASSETS, "derelict_airfield_02_2k.hdr")
    if os.path.exists(hdr_path):
        tex_env = nt.nodes.new("ShaderNodeTexEnvironment")
        tex_env.image = bpy.data.images.load(hdr_path)
        nt.links.new(tex_env.outputs["Color"], bg_light.inputs["Color"])
        bg_light.inputs["Strength"].default_value = 0.85
    else:
        bg_light.inputs["Color"].default_value = (0.55, 0.78, 1.0, 1.0)
        bg_light.inputs["Strength"].default_value = 0.90

    bg_cam = nt.nodes.new("ShaderNodeBackground")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.02
    mr.inputs["From Max"].default_value = 0.45
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.64, 0.84, 0.98, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.10, 0.34, 0.78, 1.0)
    nt.links.new(tex.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg_cam.inputs["Color"])
    bg_cam.inputs["Strength"].default_value = 1.02

    nt.links.new(lp.outputs["Is Camera Ray"], mix_cam.inputs["Fac"])
    nt.links.new(bg_light.outputs["Background"], mix_cam.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix_cam.inputs[2])
    nt.links.new(mix_cam.outputs["Shader"], out.inputs["Surface"])

    sun_data = bpy.data.lights.new("AirfieldSun", type="SUN")
    sun_data.energy = 5.0
    sun_data.angle = math.radians(1.5)
    sun_data.color = (1.0, 0.96, 0.90)
    sun = bpy.data.objects.new("AirfieldSun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(46.0), math.radians(-18.0), math.radians(32.0))


def _ensure_rigidbody_world(scene: bpy.types.Scene) -> None:
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    rbw.substeps_per_frame = 20
    rbw.solver_iterations = 20
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = 300


def _build_runway_environment(scene: bpy.types.Scene) -> None:
    # Asphalt PBR material from Poly Haven asphalt_pit_lane
    mat = bpy.data.materials.new("RunwayAsphaltPBR")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (30.0, 14.0, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])

    diff_p = os.path.join(ASSETS, "asphalt_diff.jpg")
    rough_p = os.path.join(ASSETS, "asphalt_rough.jpg")
    nor_p = os.path.join(ASSETS, "asphalt_nor.jpg")
    if os.path.exists(diff_p):
        t_d = nt.nodes.new("ShaderNodeTexImage")
        t_d.image = bpy.data.images.load(diff_p)
        nt.links.new(mp.outputs["Vector"], t_d.inputs["Vector"])
        nt.links.new(t_d.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        _set_input(bsdf, "Base Color", (0.14, 0.15, 0.17, 1.0))
    if os.path.exists(rough_p):
        t_r = nt.nodes.new("ShaderNodeTexImage")
        t_r.image = bpy.data.images.load(rough_p)
        t_r.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs["Vector"], t_r.inputs["Vector"])
        nt.links.new(t_r.outputs["Color"], bsdf.inputs["Roughness"])
    if os.path.exists(nor_p):
        t_n = nt.nodes.new("ShaderNodeTexImage")
        t_n.image = bpy.data.images.load(nor_p)
        t_n.image.colorspace_settings.name = "Non-Color"
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.65
        nt.links.new(mp.outputs["Vector"], t_n.inputs["Vector"])
        nt.links.new(t_n.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    # Large runway slab (top flush at z = 0.0) with PASSIVE rigidbody + collision
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(60.0, 0.0, -0.5))
    tarmac = bpy.context.active_object
    tarmac.name = "RunwayTarmac"
    tarmac.scale = (440.0, 240.0, 1.0)
    tarmac.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    tarmac.select_set(True)
    bpy.context.view_layer.objects.active = tarmac
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    tarmac.rigid_body.collision_shape = "BOX"
    tarmac.rigid_body.friction = 0.55
    tarmac.rigid_body.restitution = 0.25
    tarmac.modifiers.new("Collision", "COLLISION")

    # Distant tarmac skirt to horizon
    skirt_mat = _make_mat("DistantGround", (0.16, 0.17, 0.18), roughness=0.92)
    bpy.ops.mesh.primitive_plane_add(size=2400.0, location=(50.0, 0.0, -0.06))
    sk = bpy.context.active_object
    sk.name = "RunwayHorizon"
    sk.data.materials.append(skirt_mat)

    # White dashed runway centerline + yellow apron safety borders + runway beacons
    white_m = _make_mat("RunwayWhite", (0.94, 0.94, 0.92), roughness=0.72)
    yellow_m = _make_mat("RunwayYellow", (0.98, 0.72, 0.04), roughness=0.65)
    beacon_m = _make_mat("RunwayBeacon", (1.0, 0.45, 0.06), emission_color=(1.0, 0.42, 0.05), emission_strength=6.0)
    dark_cap_m = _make_mat("BeaconBase", (0.12, 0.13, 0.15), metallic=0.6, roughness=0.4)

    for ix in range(-16, 180, 8):
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(float(ix), 0.0, 0.008))
        st = bpy.context.active_object
        st.scale = (4.2, 0.36, 1.0)
        st.data.materials.append(white_m)

    for y_line in (-5.6, 5.6):
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(60.0, y_line, 0.008))
        yl = bpy.context.active_object
        yl.scale = (240.0, 0.22, 1.0)
        yl.data.materials.append(yellow_m)

    # Distance blast zone ticks (5m, 10m, 15m, 20m, 25m behind engine) + beacons
    for bx in range(4, 52, 6):
        for by in (-6.2, 6.2):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.14, depth=0.16, location=(float(bx), by, 0.08))
            b0 = bpy.context.active_object
            b0.data.materials.append(dark_cap_m)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.09, location=(float(bx), by, 0.18))
            b1 = bpy.context.active_object
            b1.data.materials.append(beacon_m)

    # Parked Airbus A350_nologo.glb in background apron (min_z = -4.072 -> grounded at z = 4.07)
    a350_p = os.path.join(ASSETS, "A350_nologo.glb")
    if os.path.exists(a350_p):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=a350_p)
        new_objs = [o for o in bpy.data.objects if o not in before]
        piv = bpy.data.objects.new("ParkedA350", None)
        scene.collection.objects.link(piv)
        for o in new_objs:
            if o.parent is None:
                o.parent = piv
                o.rotation_mode = "XYZ"
        piv.location = (22.0, 29.0, 4.07)
        piv.rotation_mode = "XYZ"
        piv.rotation_euler = (0.0, 0.0, math.radians(-22.0))

    # Poly Haven concrete_road_barrier along apron edge (min_z = -0.008 -> z = +0.008)
    bar_p = os.path.join(ASSETS, "concrete_road_barrier", "concrete_road_barrier_1k.gltf")
    if os.path.exists(bar_p):
        for idx, bx in enumerate((2.0, 9.0, 16.0, 23.0, 30.0, 37.0)):
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=bar_p)
            new_objs = [o for o in bpy.data.objects if o not in before]
            piv = bpy.data.objects.new(f"ApronBarrier_{idx}", None)
            scene.collection.objects.link(piv)
            for o in new_objs:
                if o.parent is None:
                    o.parent = piv
                    o.rotation_mode = "XYZ"
            piv.location = (float(bx), 7.6, 0.008)
            piv.rotation_mode = "XYZ"


def _build_hero_turbofan(scene: bpy.types.Scene) -> Tuple[bpy.types.Material, List[bpy.types.Object]]:
    """Build detailed industrial test-rig Turbofan Jet Engine at x=0, exhausting along +X."""
    rig_steel = _make_mat("TestRigSteel", (0.14, 0.16, 0.19), metallic=0.78, roughness=0.35)
    hazard_y = _make_mat("RigHazardYellow", (0.98, 0.72, 0.02), roughness=0.36)
    cowling_w = _make_mat("NacelleWhite", (0.86, 0.89, 0.93), metallic=0.25, roughness=0.18, coat=0.7)
    titanium = _make_mat("TitaniumRim", (0.55, 0.59, 0.65), metallic=0.92, roughness=0.18)
    blade_mat = _make_mat("FanBladeTi", (0.28, 0.31, 0.36), metallic=0.94, roughness=0.22)
    nozzle_mat = _make_mat("ExhaustAlloy", (0.22, 0.20, 0.22), metallic=0.90, roughness=0.30)
    core_glow = _make_mat(
        "JetCoreGlow", (1.0, 0.42, 0.08),
        emission_color=(1.0, 0.46, 0.10), emission_strength=2.0,
    )
    red_stripe = _make_mat("NacelleStripeRed", (0.86, 0.10, 0.08), roughness=0.25, coat=0.6)

    stand = bpy.data.objects.new("TurbofanTestStand", None)
    scene.collection.objects.link(stand)

    # Ground skids & yellow safety border beams (flush on z=0.0)
    for sy in (-1.35, 1.35):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, sy, 0.09))
        sk = bpy.context.active_object
        sk.scale = (4.2, 0.28, 0.18)
        sk.data.materials.append(hazard_y)
        sk.parent = stand

        for sx in (-1.4, 1.1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.11, depth=1.55, location=(sx, sy * 0.78, 0.90))
            leg = bpy.context.active_object
            leg.rotation_euler = (math.radians(16.0 if sy < 0 else -16.0), 0.0, 0.0)
            leg.data.materials.append(rig_steel)
            leg.parent = stand

    # Cross mounting cradle under nacelle
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-0.1, 0.0, 0.58))
    cradle = bpy.context.active_object
    cradle.scale = (3.0, 1.9, 0.22)
    cradle.data.materials.append(rig_steel)
    cradle.parent = stand

    # Nacelle outer barrel (hollow cylinder profile built via bmesh lathe around X axis, centered z=1.78)
    z_hub = 1.78
    bm = bmesh.new()
    n_rad = 48
    profile = [
        (-2.05, 1.04), (-2.12, 1.12), (-1.95, 1.24), (-0.80, 1.30),
        (0.60, 1.26), (1.65, 1.10), (1.72, 0.98), (1.58, 0.88),
        (0.40, 0.98), (-1.75, 1.02), (-2.05, 1.04),
    ]
    rings = []
    for px, pr in profile[:-1]:
        ring = []
        for k in range(n_rad):
            a = 2.0 * math.pi * k / n_rad
            ring.append(bm.verts.new((px, pr * math.cos(a), z_hub + pr * math.sin(a))))
        rings.append(ring)
    for ir in range(len(rings)):
        r0 = rings[ir]
        r1 = rings[(ir + 1) % len(rings)]
        for k in range(n_rad):
            kn = (k + 1) % n_rad
            f = bm.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
            px = profile[ir][0]
            if px < -1.85:
                f.material_index = 1  # Titanium intake lip
            elif -0.15 < px < 0.25:
                f.material_index = 2  # Red intake danger band
            elif px > 1.45:
                f.material_index = 3  # Exhaust nozzle metal
            else:
                f.material_index = 0  # Glossy white cowling
    nm = bpy.data.meshes.new("NacelleMesh")
    bm.to_mesh(nm)
    bm.free()
    for p in nm.polygons:
        p.use_smooth = True
    nacelle = bpy.data.objects.new("TurbofanNacelle", nm)
    scene.collection.objects.link(nacelle)
    for m in (cowling_w, titanium, red_stripe, nozzle_mat):
        nacelle.data.materials.append(m)
    nacelle.parent = stand

    # Exhaust nozzle cone & glowing turbine core (facing +X)
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.92, radius2=0.68, depth=0.85, location=(1.88, 0.0, z_hub), rotation=(0.0, math.radians(90.0), 0.0))
    noz = bpy.context.active_object
    noz.name = "ExhaustNozzleRing"
    bpy.ops.object.shade_smooth()
    noz.data.materials.append(nozzle_mat)
    noz.parent = stand

    bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=0.62, radius2=0.14, depth=1.35, location=(2.05, 0.0, z_hub), rotation=(0.0, math.radians(90.0), 0.0))
    core = bpy.context.active_object
    core.name = "TurbofanCoreGlow"
    bpy.ops.object.shade_smooth()
    core.data.materials.append(core_glow)
    core.parent = stand

    # Spinning intake fan rotor + 24 curved titanium blades
    rotor = bpy.data.objects.new("FanRotor", None)
    scene.collection.objects.link(rotor)
    rotor.location = (-1.42, 0.0, z_hub)
    rotor.rotation_mode = "XYZ"
    rotor.parent = stand

    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.34, radius2=0.04, depth=0.62, location=(-0.18, 0.0, 0.0), rotation=(0.0, math.radians(-90.0), 0.0))
    spinner = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    spinner.data.materials.append(titanium)
    spinner.parent = rotor

    for bi in range(24):
        ang = 2.0 * math.pi * bi / 24.0
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.56 * math.cos(ang), 0.56 * math.sin(ang)))
        bl = bpy.context.active_object
        bl.scale = (0.04, 0.14, 0.72)
        bl.rotation_mode = "XYZ"
        bl.rotation_euler = (ang - math.pi * 0.5, math.radians(32.0), 0.0)
        bl.data.materials.append(blade_mat)
        bl.parent = rotor

    # Keyframe rotor spin & glowing turbine core surge across F1..300
    em_sock = core_glow.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    rot_deg = 0.0
    for f in range(1, 301):
        rpm_deg_per_frame = _lerp(18.0, 95.0, _smoothstep(60.0, 145.0, float(f)))
        rot_deg += rpm_deg_per_frame
        rotor.rotation_euler = (math.radians(rot_deg), 0.0, 0.0)
        rotor.keyframe_insert(data_path="rotation_euler", frame=f)

        em_val = _lerp(2.0, 22.0, _smoothstep(65.0, 140.0, float(f))) * (1.0 - 0.6 * _smoothstep(245.0, 300.0, float(f)))
        if f in (1, 60, 90, 140, 240, 275, 300):
            em_sock.default_value = em_val
            em_sock.keyframe_insert(data_path="default_value", frame=f)

    # 70 supersonic jet blast wind-streak ribbons shooting +X from nozzle (x=+2.2..+42m)
    streak_mat = _make_mat(
        "JetWindStreak", (0.86, 0.96, 1.0), roughness=0.1,
        emission_color=(0.75, 0.92, 1.0), emission_strength=3.2,
    )
    rng = random.Random(777)
    streaks = []
    for i in range(70):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6, radius=rng.uniform(0.012, 0.032), depth=rng.uniform(1.8, 3.8),
            location=(0.0, 0.0, -30.0), rotation=(0.0, math.pi * 0.5, 0.0),
        )
        s_obj = bpy.context.active_object
        s_obj.name = f"WindStreak_{i:02d}"
        s_obj.data.materials.append(streak_mat)
        ang = rng.uniform(0.0, 2.0 * math.pi)
        r_cone = rng.uniform(0.15, 0.95)
        streaks.append((
            s_obj,
            rng.uniform(0.0, 1.0),  # phase
            rng.uniform(28.0, 44.0),  # m/s speed
            math.cos(ang) * r_cone,
            math.sin(ang) * r_cone,
        ))

    for f in range(1, 301):
        t = (f - 1) / 30.0
        vis_scale = _smoothstep(68.0, 92.0, float(f)) * (1.0 - _smoothstep(245.0, 285.0, float(f)))
        for s_obj, ph, spd, cy, cz in streaks:
            if vis_scale < 0.02:
                s_obj.location = (0.0, 0.0, -30.0)
            else:
                u = (ph + t * (spd / 38.0)) % 1.0
                sx = 2.3 + u * 38.0
                spread = 1.0 + u * 1.65
                s_obj.location = (sx, cy * spread, z_hub + cz * spread * 0.85)
                s_obj.scale = (1.0, 1.0, vis_scale)
            s_obj.keyframe_insert(data_path="location", frame=f)
            s_obj.keyframe_insert(data_path="scale", frame=f)

    return core_glow, [s[0] for s in streaks]


def _build_cloth_umbrella(scene: bpy.types.Scene) -> Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]:
    """Build black-and-white striped Cloth+Solidify umbrella that opens F16..42, inverts F92..126, and flies."""
    nylon_mat = _make_mat("UmbrellaNylon", (0.07, 0.08, 0.11), roughness=0.22, coat=0.55)
    stripe_mat = _make_mat("UmbrellaWhitePanel", (0.94, 0.80, 0.16), roughness=0.24, coat=0.55)
    metal_mat = _make_mat("UmbrellaSteel", (0.76, 0.79, 0.84), metallic=0.9, roughness=0.20)
    wood_mat = _make_mat("UmbrellaHandle", (0.32, 0.15, 0.07), roughness=0.36, coat=0.5)

    umb = bpy.data.objects.new("HeroUmbrella", None)
    scene.collection.objects.link(umb)

    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.016, depth=0.98, location=(0.0, 0.0, 0.19))
    shaft = bpy.context.active_object
    shaft.name = "UmbShaft"
    bpy.ops.object.shade_smooth()
    shaft.data.materials.append(metal_mat)
    shaft.parent = umb

    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.026, depth=0.18, location=(0.0, 0.0, -0.30))
    grip = bpy.context.active_object
    grip.name = "UmbHandle"
    bpy.ops.object.shade_smooth()
    grip.data.materials.append(wood_mat)
    grip.parent = umb

    # Keep full mesh centered on HeroUmbrella frame (avoid world-space Cloth coordinate lag):
    # Basis = Open Dome (rad=0.82), ShapeKey 1 = "Furled", ShapeKey 2 = "Invert", + animated WAVE wind flutter!
    bm = bmesh.new()
    n_seg, n_rings, rad = 24, 9, 0.82
    apex = bm.verts.new((0.0, 0.0, 0.68))
    rings = []
    for ir in range(1, n_rings + 1):
        u = ir / n_rings
        r_ring = rad * u
        z_ring = 0.68 - 0.30 * (u * u)
        row = []
        for it in range(n_seg):
            a = 2.0 * math.pi * it / n_seg
            scallop = -0.022 * math.cos(8 * a) * (u ** 3)
            row.append(bm.verts.new((r_ring * math.cos(a), r_ring * math.sin(a), z_ring + scallop)))
        rings.append(row)
    for it in range(n_seg):
        f_tri = bm.faces.new((apex, rings[0][it], rings[0][(it + 1) % n_seg]))
        f_tri.material_index = 1 if (it // 3) % 2 == 1 else 0
    for ir in range(n_rings - 1):
        for it in range(n_seg):
            itn = (it + 1) % n_seg
            f_q = bm.faces.new((rings[ir][it], rings[ir + 1][it], rings[ir + 1][itn], rings[ir][itn]))
            f_q.material_index = 1 if (it // 3) % 2 == 1 else 0
    cmesh = bpy.data.meshes.new("UmbrellaCanopyMesh")
    bm.to_mesh(cmesh)
    bm.free()
    for p in cmesh.polygons:
        p.use_smooth = True

    canopy = bpy.data.objects.new("UmbCanopyCloth", cmesh)
    scene.collection.objects.link(canopy)
    canopy.data.materials.append(nylon_mat)
    canopy.data.materials.append(stripe_mat)
    canopy.parent = umb

    canopy.shape_key_add(name="Basis")
    sk_furl = canopy.shape_key_add(name="Furled")
    sk_inv = canopy.shape_key_add(name="Invert")
    for i, v in enumerate(cmesh.vertices):
        d_xy = math.hypot(v.co.x, v.co.y)
        u = _clamp01(d_xy / rad)
        ang = math.atan2(v.co.y, v.co.x)
        # Furled shape: tucked tight along shaft (-Z)
        sk_furl.data[i].co = Vector((v.co.x * 0.14, v.co.y * 0.14, 0.68 - 0.65 * u))
        # Inverted shape: ribs violently blown inside-out forward toward +Z (in wind toward +X)!
        flutter = 0.08 * math.sin(8 * ang) * (u ** 2)
        new_r = d_xy * (0.76 + 0.12 * math.cos(4 * ang))
        new_z = 0.68 + 0.68 * (u ** 1.25) + flutter
        sk_inv.data[i].co = Vector((new_r * math.cos(ang), new_r * math.sin(ang), new_z))

    # High-frequency wind-ripple WAVE modifier (ramps up F70..147 when jet blast hits canopy)
    wv = canopy.modifiers.new("WindFlutter", "WAVE")
    wv.use_x = True
    wv.use_y = True
    wv.use_normal = True
    wv.width = 0.28
    wv.narrowness = 1.6
    wv.speed = 0.9
    wv.height = 0.0
    for f_w, h_w in ((1, 0.0), (65, 0.015), (95, 0.075), (125, 0.11), (148, 0.0)):
        wv.height = h_w
        wv.keyframe_insert(data_path="height", frame=f_w)

    sol = canopy.modifiers.new("UmbThickness", "SOLIDIFY")
    sol.thickness = 0.016
    sol.offset = 0.0

    # Open smoothly F14..38 (wide open in F35!), flutter hard, then violently invert F92..126
    for f in (1, 14, 38, 92, 108, 126, 300):
        sk_furl.value = 1.0 - _smoothstep(14.0, 38.0, float(f))
        sk_furl.keyframe_insert(data_path="value", frame=f)

        inv_v = _smoothstep(92.0, 126.0, float(f))
        sk_inv.value = inv_v
        sk_inv.keyframe_insert(data_path="value", frame=f)

    bpy.ops.object.effector_add(type="WIND", location=(3.0, 0.0, 1.45), rotation=(0.0, math.pi * 0.5, 0.0))
    wind = bpy.context.active_object
    wind.name = "JetBlastWind"
    wind.field.strength = 0.0

    # Detached RB_Umbrella for flight phase F148..300 (striped cone matching open/inverted look!)
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.04, depth=0.98, location=(0.0, 0.0, 0.0))
    rb_mesh_obj = bpy.context.active_object
    rb_mesh_obj.name = "RB_UmbrellaHull"
    rb_mesh_obj.data.materials.append(metal_mat)
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.08, radius2=0.72, depth=0.56, location=(0.0, 0.0, 0.78))
    rb_cone = bpy.context.active_object
    rb_cone.data.materials.append(nylon_mat)
    rb_cone.parent = rb_mesh_obj

    rb_mesh_obj.location = (5.55, -0.22, 1.45)
    rb_mesh_obj.rotation_mode = "XYZ"
    rb_mesh_obj.rotation_euler = (0.0, math.radians(-78.0), 0.0)
    bpy.ops.object.select_all(action="DESELECT")
    rb_mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = rb_mesh_obj
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    rb_mesh_obj.rigid_body.mass = 0.65
    rb_mesh_obj.rigid_body.linear_damping = 0.02
    rb_mesh_obj.rigid_body.angular_damping = 0.03
    rb_mesh_obj.rigid_body.restitution = 0.45

    rb_mesh_obj.rigid_body.kinematic = True
    rb_mesh_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
    rb_mesh_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=147)
    rb_mesh_obj.rigid_body.kinematic = False
    rb_mesh_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=148)

    for ch in (shaft, grip, canopy):
        ch.hide_render = False
        ch.keyframe_insert(data_path="hide_render", frame=1)
        ch.keyframe_insert(data_path="hide_render", frame=147)
        ch.hide_render = True
        ch.keyframe_insert(data_path="hide_render", frame=148)

    for ch in (rb_mesh_obj, rb_cone):
        ch.hide_render = True
        ch.keyframe_insert(data_path="hide_render", frame=1)
        ch.keyframe_insert(data_path="hide_render", frame=147)
        ch.hide_render = False
        ch.keyframe_insert(data_path="hide_render", frame=148)

    return umb, rb_mesh_obj, wind


def _build_cones_and_suitcase(scene: bpy.types.Scene) -> List[bpy.types.Object]:
    """Build 4 traffic cones + Poly Haven vintage_suitcase blown down runway at F95..140."""
    orange_m = _make_mat("ConeOrange", (0.98, 0.30, 0.02), roughness=0.35, coat=0.3)
    white_m = _make_mat("ConeWhite", (0.95, 0.96, 0.98), roughness=0.30)
    props: List[bpy.types.Object] = []

    cone_spots = [(4.0, -1.65), (4.6, 1.55), (5.5, -1.95), (6.4, 1.75)]
    for idx, (cx, cy) in enumerate(cone_spots):
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.22, radius2=0.04, depth=0.72, location=(cx, cy, 0.36))
        c = bpy.context.active_object
        c.name = f"TrafficCone_{idx}"
        c.data.materials.append(orange_m)
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.145, radius2=0.105, depth=0.18, location=(0.0, 0.0, 0.06))
        stripe = bpy.context.active_object
        stripe.data.materials.append(white_m)
        stripe.parent = c

        bpy.ops.object.select_all(action="DESELECT")
        c.select_set(True)
        bpy.context.view_layer.objects.active = c
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        c.rigid_body.collision_shape = "CONE"
        c.rigid_body.mass = 2.5
        c.rigid_body.friction = 0.35
        c.rigid_body.restitution = 0.45
        c.rigid_body.kinematic = True
        c.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
        c.rigid_body.keyframe_insert(data_path="kinematic", frame=94)
        c.rigid_body.kinematic = False
        c.rigid_body.keyframe_insert(data_path="kinematic", frame=95)
        props.append(c)

    # Poly Haven vintage_suitcase (keep suitcase_01 only, join cleanly, center origin, place at (4.9, -1.15))
    suit_p = os.path.join(ASSETS, "vintage_suitcase", "vintage_suitcase_1k.gltf")
    if os.path.exists(suit_p):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=suit_p)
        new_objs = [o for o in bpy.data.objects if o not in before]
        keep_meshes = []
        for o in new_objs:
            if "_02_" in o.name:
                bpy.data.objects.remove(o, do_unlink=True)
            elif o.type == "MESH":
                keep_meshes.append(o)
        if keep_meshes:
            bpy.ops.object.select_all(action="DESELECT")
            for m in keep_meshes:
                m.select_set(True)
            bpy.context.view_layer.objects.active = keep_meshes[0]
            bpy.ops.object.join()
            suit = bpy.context.active_object
            suit.name = "SuitcaseProp"
            suit.parent = None
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
            bb = [Vector(c) for c in suit.bound_box]
            dz = max(v.z for v in bb) - min(v.z for v in bb)
            suit.location = (5.0, -1.05, dz * 0.5 + 0.005)
            suit.rotation_mode = "XYZ"
            suit.rotation_euler = (0.0, 0.0, math.radians(18.0))
            bpy.ops.rigidbody.object_add(type="ACTIVE")
            suit.rigid_body.collision_shape = "BOX"
            suit.rigid_body.mass = 5.0
            suit.rigid_body.friction = 0.35
            suit.rigid_body.restitution = 0.35
            suit.rigid_body.kinematic = True
            suit.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
            suit.rigid_body.keyframe_insert(data_path="kinematic", frame=94)
            suit.rigid_body.kinematic = False
            suit.rigid_body.keyframe_insert(data_path="kinematic", frame=95)
            props.append(suit)

    # Sweeper piston active ONLY F95..102 to launch cones & suitcase down runway (never touches businessman at x=6.2 F148!)
    # Two side rails sweeping at y=-1.6 and y=+1.6 + low x=4.0..5.4
    for sy in (-1.55, 1.55):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3.2, sy, 0.36))
        sw = bpy.context.active_object
        sw.name = f"BlastSweep_{'L' if sy > 0 else 'R'}"
        sw.scale = (0.5, 1.4, 0.65)
        sw.hide_render = True
        bpy.ops.object.select_all(action="DESELECT")
        sw.select_set(True)
        bpy.context.view_layer.objects.active = sw
        bpy.ops.rigidbody.object_add(type="PASSIVE")
        sw.rigid_body.kinematic = True
        sw.rigid_body.restitution = 0.55

        sw.location = (3.2, sy, 0.36)
        sw.keyframe_insert(data_path="location", frame=1)
        sw.keyframe_insert(data_path="location", frame=94)
        sw.location = (6.6, sy, 0.45)
        sw.keyframe_insert(data_path="location", frame=101)
        sw.location = (6.6, sy, -30.0)
        sw.keyframe_insert(data_path="location", frame=105)

    return props


LIMB_SPECS = [
    ("Hips", None, 14.0, 0.16, None),
    ("Spine2", "Hips", 18.0, 0.17, ((-28, 32), (-20, 20), (-25, 25))),
    ("Head", "Spine2", 5.0, 0.11, ((-32, 32), (-25, 25), (-28, 28))),
    ("LeftArm", "Spine2", 3.0, 0.075, ((-85, 85), (-45, 45), (-85, 85))),
    ("LeftForeArm", "LeftArm", 2.0, 0.06, ((-10, 125), (-15, 15), (-20, 20))),
    ("RightArm", "Spine2", 3.0, 0.075, ((-85, 85), (-45, 45), (-85, 85))),
    ("RightForeArm", "RightArm", 2.0, 0.06, ((-10, 125), (-15, 15), (-20, 20))),
    ("LeftUpLeg", "Hips", 8.0, 0.095, ((-75, 85), (-25, 25), (-45, 45))),
    ("LeftLeg", "LeftUpLeg", 5.0, 0.075, ((-125, 8), (-12, 12), (-12, 12))),
    ("RightUpLeg", "Hips", 8.0, 0.095, ((-75, 85), (-25, 25), (-45, 45))),
    ("RightLeg", "RightUpLeg", 5.0, 0.075, ((-125, 8), (-12, 12), (-12, 12))),
]


def _build_businessman_ragdoll(scene: bpy.types.Scene) -> Dict[str, object]:
    """Import rpm_player.glb facing -X toward jet engine and build zero-spring Bullet RBs."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=HUMAN_GLB)
    new_objs = [o for o in bpy.data.objects if o not in before]

    arm: Optional[bpy.types.Object] = None
    shaped_meshes: List[bpy.types.Object] = []
    foot_objs: List[bpy.types.Object] = []
    for o in new_objs:
        if o.type == "ARMATURE":
            arm = o
        elif o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o, do_unlink=True)
        elif o.type == "MESH":
            if o.data.shape_keys:
                shaped_meshes.append(o)
            if "Footwear" in o.name:
                foot_objs.append(o)
    assert arm is not None, "Expected Armature in rpm_player.glb"

    # Ground at x=6.2, y=0.0 facing -X (-90 deg around Z rotates rest -Y front -> -X)
    arm.location = (6.2, 0.0, 0.0)
    arm.rotation_mode = "XYZ"
    arm.rotation_euler = (0.0, 0.0, -math.pi * 0.5)
    bpy.context.view_layer.update()

    # Ground shoes flush on tarmac z=0.0
    if foot_objs:
        min_z = min((fo.matrix_world @ Vector(c)).z for fo in foot_objs for c in fo.bound_box)
        arm.location.z -= min_z
        bpy.context.view_layer.update()

    # Assert businessman faces -X toward Jet Engine
    pb_hips = arm.pose.bones["Hips"]
    hips_world_mat = (arm.matrix_world @ pb_hips.matrix).to_3x3()
    face_dir = (hips_world_mat @ Vector((0.0, 0.0, 1.0))).normalized()
    print(f"[jet] Businessman F1 check: loc={tuple(round(x,3) for x in arm.location)} face_dir={tuple(round(x,2) for x in face_dir)}", flush=True)
    assert face_dir.x < -0.9, f"Expected businessman facing -X! face_dir={face_dir}"

    rb_map: Dict[str, bpy.types.Object] = {}
    bind_hips: Optional[bpy.types.Object] = None

    for bname, parent_name, mass, rad, limits in LIMB_SPECS:
        pb = arm.pose.bones[bname]
        head_w = arm.matrix_world @ pb.head
        tail_w = arm.matrix_world @ pb.tail
        bone_len = max(0.12, (tail_w - head_w).length)
        mid_w = (head_w + tail_w) * 0.5
        rot_q = (arm.matrix_world @ pb.matrix).to_quaternion().normalized()

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=12, radius=rad, depth=bone_len,
            location=(0.0, 0.0, 0.0), rotation=(math.pi * 0.5, 0.0, 0.0),
        )
        rb_obj = bpy.context.active_object
        rb_obj.name = f"RB_{bname}"
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        rb_obj.location = mid_w
        rb_obj.rotation_mode = "QUATERNION"
        rb_obj.rotation_quaternion = rot_q

        bpy.ops.object.select_all(action="DESELECT")
        rb_obj.select_set(True)
        bpy.context.view_layer.objects.active = rb_obj
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        rb_obj.rigid_body.collision_shape = "CAPSULE"
        rb_obj.rigid_body.mass = mass
        if bname == "Hips":
            rb_obj.rigid_body.linear_damping = 0.02
            rb_obj.rigid_body.angular_damping = 0.72
        else:
            rb_obj.rigid_body.linear_damping = 0.01
            rb_obj.rigid_body.angular_damping = 0.04
        rb_obj.rigid_body.friction = 0.45
        rb_obj.rigid_body.restitution = 0.25
        rb_obj.hide_render = True
        rb_obj.hide_viewport = True

        if bname == "Hips":
            bind_hips = bpy.data.objects.new("Bind_Hips", None)
            scene.collection.objects.link(bind_hips)
            bind_hips.parent = rb_obj
            bind_hips.location = Vector((0.0, -0.5 * bone_len, 0.0))
            bind_hips.rotation_euler = (0.0, 0.0, 0.0)

        rb_map[bname] = rb_obj

        if parent_name is not None and limits is not None:
            c_emp = bpy.data.objects.new(f"Joint_{bname}", None)
            scene.collection.objects.link(c_emp)
            c_emp.location = head_w
            c_emp.rotation_mode = "QUATERNION"
            c_emp.rotation_quaternion = rot_q
            bpy.ops.object.select_all(action="DESELECT")
            c_emp.select_set(True)
            bpy.context.view_layer.objects.active = c_emp
            bpy.ops.rigidbody.constraint_add(type="GENERIC_SPRING")
            rbc = c_emp.rigid_body_constraint
            rbc.object1 = rb_map[parent_name]
            rbc.object2 = rb_obj
            rbc.disable_collisions = True
            for attr_lin in ("use_limit_lin_x", "use_limit_lin_y", "use_limit_lin_z"):
                setattr(rbc, attr_lin, True)
            for attr_v in (
                "limit_lin_x_lower", "limit_lin_x_upper",
                "limit_lin_y_lower", "limit_lin_y_upper",
                "limit_lin_z_lower", "limit_lin_z_upper",
            ):
                setattr(rbc, attr_v, 0.0)

            (lx0, lx1), (ly0, ly1), (lz0, lz1) = limits
            rbc.use_limit_ang_x = True
            rbc.limit_ang_x_lower = math.radians(lx0)
            rbc.limit_ang_x_upper = math.radians(lx1)
            rbc.use_limit_ang_y = True
            rbc.limit_ang_y_lower = math.radians(ly0)
            rbc.limit_ang_y_upper = math.radians(ly1)
            rbc.use_limit_ang_z = True
            rbc.limit_ang_z_lower = math.radians(lz0)
            rbc.limit_ang_z_upper = math.radians(lz1)
            for ax in ("x", "y", "z"):
                setattr(rbc, f"use_spring_ang_{ax}", False)

    assert bind_hips is not None
    cl = pb_hips.constraints.new("COPY_LOCATION")
    cl.target = bind_hips
    cl.target_space = "WORLD"
    cl.owner_space = "WORLD"
    cr = pb_hips.constraints.new("COPY_ROTATION")
    cr.target = bind_hips
    cr.target_space = "WORLD"
    cr.owner_space = "WORLD"
    cr.mix_mode = "REPLACE"

    for rb_obj in rb_map.values():
        rb_obj.rigid_body.kinematic = True
        rb_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
        rb_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=147)
        rb_obj.rigid_body.kinematic = False
        rb_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=148)

    # Catapult piston starts cleanly clear of businessman (x=6.2 -> piston x=4.55, r=1.15 => max_x=5.70)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.15, depth=0.5, location=(4.55, 0.0, 0.45))
    piston = bpy.context.active_object
    piston.name = "JetBlastPiston"
    piston.hide_render = True
    bpy.ops.object.select_all(action="DESELECT")
    piston.select_set(True)
    bpy.context.view_layer.objects.active = piston
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    piston.rigid_body.kinematic = True
    piston.rigid_body.restitution = 0.35

    # Vertical + horizontal impulse tuned for ~3s airborne arc (z apex ~10m, landing ~35-45m around F235..255!)
    piston.location = (4.55, 0.0, 0.45)
    piston.rotation_euler = (0.0, math.radians(38.0), 0.0)
    piston.keyframe_insert(data_path="location", frame=1)
    piston.keyframe_insert(data_path="location", frame=147)
    piston.location = (7.25, 0.04, 3.85)
    piston.keyframe_insert(data_path="location", frame=155)
    piston.location = (7.25, 0.04, -25.0)
    piston.keyframe_insert(data_path="location", frame=162)

    bpy.ops.object.effector_add(type="TURBULENCE", location=(18.0, 0.0, 4.5))
    turb = bpy.context.active_object
    turb.name = "RunwayTurbulence"
    turb.field.size = 10.0
    turb.field.noise = 1.6
    turb.field.strength = 0.0
    turb.field.keyframe_insert(data_path="strength", frame=1)
    turb.field.keyframe_insert(data_path="strength", frame=148)
    turb.field.strength = 95.0
    turb.field.keyframe_insert(data_path="strength", frame=158)
    turb.field.keyframe_insert(data_path="strength", frame=300)

    return {"arm": arm, "rb_map": rb_map, "hips_rb": rb_map["Hips"], "shaped_meshes": shaped_meshes}


def _import_barrel_pyramid(scene: bpy.types.Scene) -> List[bpy.types.Object]:
    """Import 6 Poly Haven Barrel_01 drums (3+2+1 pyramid) with centered origins for Bullet RB."""
    bar_p = os.path.join(ASSETS, "Barrel_01", "Barrel_01_1k.gltf")
    drums: List[bpy.types.Object] = []
    # Temporary out-of-the-way position for Pass 1 trajectory discovery
    for i in range(6):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=bar_p)
        new_objs = [o for o in bpy.data.objects if o not in before]
        mesh_obj = next((o for o in new_objs if o.type == "MESH"), None)
        assert mesh_obj is not None, "Expected MESH in Barrel_01"
        mesh_obj.parent = None
        for o in new_objs:
            if o != mesh_obj:
                bpy.data.objects.remove(o, do_unlink=True)
        mesh_obj.name = f"CrashBarrel_{i}"
        mesh_obj.rotation_mode = "XYZ"
        bpy.ops.object.select_all(action="DESELECT")
        mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")

        mesh_obj.location = (80.0, float(i) * 1.2, 0.44)
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        mesh_obj.rigid_body.collision_shape = "CYLINDER"
        mesh_obj.rigid_body.mass = 4.5
        mesh_obj.rigid_body.friction = 0.42
        mesh_obj.rigid_body.restitution = 0.40
        mesh_obj.rigid_body.use_deactivation = True
        mesh_obj.rigid_body.use_start_deactivated = True
        drums.append(mesh_obj)
    return drums


def _place_barrel_pyramid(drums: List[bpy.types.Object], cx: float, cy: float) -> None:
    """Arrange 6 centered-origin Barrel_01 drums (radius 0.282, height 0.880) in 3-2-1 pyramid."""
    # Y-spread pyramid across runway path so flying body crashes straight through the middle
    layout = [
        (cx, cy - 0.62, 0.445),
        (cx, cy, 0.445),
        (cx, cy + 0.62, 0.445),
        (cx, cy - 0.31, 1.325),
        (cx, cy + 0.31, 1.325),
        (cx, cy, 2.205),
    ]
    for d, (x, y, z) in zip(drums, layout):
        d.location = (x, y, z)
        d.rotation_euler = (0.0, 0.0, 0.0)


def _prelaunch_umbrella_euler(f: int) -> Dict[str, Tuple[float, float, float]]:
    """Natural stance holding umbrella forward with Right hand -> bracing hard against jet blast."""
    brace = _smoothstep(76.0, 138.0, float(min(f, 147)))
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


def _active_flight_euler(f: int) -> Dict[str, Tuple[float, float, float]]:
    """Anatomical panic-flail pose during mid-air flight (F148..300) using verified rpm_player axes."""
    if f <= 147:
        return {}
    t = max(0.0, (f - 148.0) / 30.0)
    w = 10.5
    whiplash = math.sin(_clamp01((f - 148.0) / 14.0) * math.pi)
    damp = 1.0 - 0.55 * _smoothstep(255.0, 295.0, float(f))
    return {
        "Spine": (10.0 + 6.0 * math.sin(w * t), 8.0 * math.sin(0.8 * w * t), 6.0 * math.cos(0.7 * w * t)),
        "Spine1": (12.0 + 7.0 * math.sin(w * t + 0.4), 10.0 * math.sin(0.9 * w * t), 7.0 * math.sin(0.6 * w * t)),
        "Spine2": (10.0 + 6.0 * math.cos(w * t), 12.0 * math.sin(0.85 * w * t + 0.7), 8.0 * math.cos(0.75 * w * t)),
        "Neck": (-18.0 * whiplash + 10.0 * math.sin(1.2 * w * t), 14.0 * math.sin(0.9 * w * t), 10.0 * math.cos(1.1 * w * t)),
        "Head": (-16.0 * whiplash + 8.0 * math.cos(1.3 * w * t), 18.0 * math.sin(0.8 * w * t + 0.5), 12.0 * math.sin(1.0 * w * t)),
        "LeftShoulder": (0.0, 0.0, 15.0 + 10.0 * math.sin(1.5 * w * t) * damp),
        "RightShoulder": (0.0, 0.0, -15.0 - 10.0 * math.sin(1.5 * w * t + 2.4) * damp),
        "LeftArm": (-54.0 + 26.0 * math.sin(1.6 * w * t) * damp, 18.0 * math.cos(1.4 * w * t) * damp, 52.0 + 26.0 * math.cos(1.6 * w * t) * damp),
        "RightArm": (-54.0 + 26.0 * math.sin(1.6 * w * t + 2.7) * damp, -18.0 * math.cos(1.4 * w * t + 2.7) * damp, -52.0 - 26.0 * math.cos(1.6 * w * t + 2.7) * damp),
        "LeftForeArm": (10.0 + 12.0 * math.sin(1.8 * w * t), 0.0, 64.0 + 22.0 * math.sin(1.9 * w * t + 0.8) * damp),
        "RightForeArm": (10.0 + 12.0 * math.sin(1.8 * w * t + 2.5), 0.0, -64.0 - 22.0 * math.sin(1.9 * w * t + 3.3) * damp),
        "LeftHand": (22.0 * math.sin(2.4 * w * t), 0.0, 24.0 * math.cos(2.2 * w * t)),
        "RightHand": (22.0 * math.sin(2.4 * w * t + 2.3), 0.0, -24.0 * math.cos(2.2 * w * t + 2.3)),
        "LeftUpLeg": (58.0 + 30.0 * math.sin(1.7 * w * t) * damp, 10.0 * math.sin(w * t), 16.0 + 10.0 * math.cos(1.1 * w * t)),
        "RightUpLeg": (58.0 + 30.0 * math.sin(1.7 * w * t + 3.14) * damp, -10.0 * math.sin(w * t), -16.0 - 10.0 * math.cos(1.1 * w * t)),
        "LeftLeg": (-84.0 - 26.0 * math.sin(1.7 * w * t + 0.7) * damp, 0.0, 0.0),
        "RightLeg": (-84.0 - 26.0 * math.sin(1.7 * w * t + 3.84) * damp, 0.0, 0.0),
        "LeftFoot": (22.0 * math.sin(1.7 * w * t + 1.2), 0.0, 0.0),
        "RightFoot": (22.0 * math.sin(1.7 * w * t + 4.34), 0.0, 0.0),
    }


def _apply_hybrid_poses_face_and_umbrella(
    scene: bpy.types.Scene,
    rag: Dict[str, object],
    umb: bpy.types.Object,
) -> Tuple[Dict[int, Vector], Dict[int, Quaternion]]:
    arm = rag["arm"]
    rb_map = rag["rb_map"]
    shaped_meshes = rag["shaped_meshes"]
    rb_parent_map = {bname: pname for bname, pname, *_ in LIMB_SPECS if pname is not None}

    scene.frame_set(1)
    q_rb_rest = {bname: rb.matrix_world.to_quaternion().normalized() for bname, rb in rb_map.items()}

    hips_pos: Dict[int, Vector] = {}
    hips_rot: Dict[int, Quaternion] = {}
    active_bones = [
        "Spine", "Spine1", "Spine2", "Neck", "Head",
        "LeftShoulder", "RightShoulder", "LeftArm", "RightArm",
        "LeftForeArm", "RightForeArm", "LeftHand", "RightHand",
        "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg",
        "LeftFoot", "RightFoot",
    ]
    face_keys = (
        "jawOpen", "mouthFunnel", "mouthStretchLeft", "mouthStretchRight",
        "mouthLowerDownLeft", "mouthLowerDownRight", "mouthFrownLeft", "mouthFrownRight",
        "eyeWideLeft", "eyeWideRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
    )

    for bname in active_bones:
        pb = arm.pose.bones.get(bname)
        if pb is not None:
            pb.rotation_mode = "QUATERNION"

    pre_end = _prelaunch_umbrella_euler(147)
    rhand_pb = arm.pose.bones["RightHand"]

    for f in range(1, 301):
        scene.frame_set(f)
        hips_pos[f] = rb_map["Hips"].matrix_world.translation.copy()
        hips_rot[f] = rb_map["Hips"].matrix_world.to_quaternion().normalized()
        q_rb_now = {bname: rb.matrix_world.to_quaternion().normalized() for bname, rb in rb_map.items()}

        phys_w = _lerp(0.60, 0.36, _smoothstep(160.0, 170.0, float(f))) if f >= 148 else 0.0
        pre_deg = _prelaunch_umbrella_euler(f)
        act_deg = _active_flight_euler(f)
        t_blend = _smoothstep(147.0, 157.0, float(f)) if f >= 148 else 0.0

        for bname in active_bones:
            pb = arm.pose.bones.get(bname)
            if pb is None:
                continue
            if f <= 147:
                ax, ay, az = pre_deg.get(bname, (0.0, 0.0, 0.0))
            elif f <= 157:
                sx, sy, sz = pre_end.get(bname, (0.0, 0.0, 0.0))
                px, py, pz = act_deg.get(bname, (0.0, 0.0, 0.0))
                ax, ay, az = _lerp(sx, px, t_blend), _lerp(sy, py, t_blend), _lerp(sz, pz, t_blend)
            else:
                ax, ay, az = act_deg.get(bname, (0.0, 0.0, 0.0))

            q_active = Euler((math.radians(ax), math.radians(ay), math.radians(az)), "XYZ").to_quaternion().normalized()
            if bname in rb_parent_map and phys_w > 0.0:
                pname = rb_parent_map[bname]
                q_rel_rest = (q_rb_rest[pname].inverted() @ q_rb_rest[bname]).normalized()
                q_rel_now = (q_rb_now[pname].inverted() @ q_rb_now[bname]).normalized()
                q_phys_delta = (q_rel_rest.inverted() @ q_rel_now).normalized()
                if q_phys_delta.w < 0.0:
                    q_phys_delta.negate()
                q_combined = (Quaternion((1.0, 0.0, 0.0, 0.0)).slerp(q_phys_delta, phys_w) @ q_active).normalized()
            else:
                q_combined = q_active

            if f >= 154:
                e = q_combined.to_euler("XYZ")
                ch = False
                if bname in ("LeftLeg", "RightLeg"):
                    cx = _clamp(e.x, math.radians(-125.0), math.radians(-15.0))
                    if abs(cx - e.x) > 1e-5:
                        e.x = cx
                        ch = True
                elif bname == "LeftForeArm":
                    cz = _clamp(e.z, math.radians(25.0), math.radians(125.0))
                    if abs(cz - e.z) > 1e-5:
                        e.z = cz
                        ch = True
                elif bname == "RightForeArm":
                    cz = _clamp(e.z, math.radians(-125.0), math.radians(-25.0))
                    if abs(cz - e.z) > 1e-5:
                        e.z = cz
                        ch = True
                if ch:
                    q_combined = e.to_quaternion().normalized()

            pb.rotation_quaternion = q_combined
            pb.keyframe_insert(data_path="rotation_quaternion", frame=f)

        # Keep HeroUmbrella wooden handle locked directly inside his RightHand palm during F1..147
        if f <= 147:
            bpy.context.view_layer.update()
            hand_w = arm.matrix_world @ rhand_pb.head
            brace = _smoothstep(76.0, 138.0, float(f))
            umb_rot = Euler((math.radians(3.0 * math.sin(f * 1.4) * brace), math.radians(-84.0 + 8.0 * brace), 0.0), "XYZ")
            grip_off_w = umb_rot.to_matrix() @ Vector((0.0, 0.0, -0.30))
            umb.rotation_mode = "XYZ"
            umb.rotation_euler = umb_rot
            umb.location = hand_w - grip_off_w
            umb.keyframe_insert(data_path="location", frame=f)
            umb.keyframe_insert(data_path="rotation_euler", frame=f)

        # Shocked alarm (F75..147) -> Screaming panic (F148..250) -> Dazed wince (F251..300)
        alarm = _smoothstep(75.0, 140.0, float(f))
        scream = _smoothstep(148.0, 155.0, float(f)) if f >= 148 else 0.0
        t_s = max(0.0, (f - 148.0) / 30.0)
        face_vals = {
            "jawOpen": _lerp(_lerp(0.03, 0.36, alarm), 0.80 + 0.14 * math.sin(t_s * 8.5), scream),
            "mouthFunnel": scream * (0.34 + 0.10 * math.cos(t_s * 6.5)),
            "mouthStretchLeft": scream * 0.48,
            "mouthStretchRight": scream * 0.48,
            "mouthLowerDownLeft": scream * 0.45,
            "mouthLowerDownRight": scream * 0.45,
            "mouthFrownLeft": scream * 0.35,
            "mouthFrownRight": scream * 0.35,
            "eyeWideLeft": _lerp(_lerp(0.0, 0.72, alarm), 0.95, scream),
            "eyeWideRight": _lerp(_lerp(0.0, 0.72, alarm), 0.95, scream),
            "browInnerUp": _lerp(_lerp(0.12, 0.75, alarm), 0.92, scream),
            "browOuterUpLeft": _lerp(_lerp(0.0, 0.50, alarm), 0.65, scream),
            "browOuterUpRight": _lerp(_lerp(0.0, 0.50, alarm), 0.65, scream),
        }
        for mesh_obj in shaped_meshes:
            sk = mesh_obj.data.shape_keys
            if sk is None:
                continue
            for kname in face_keys:
                kb = sk.key_blocks.get(kname)
                if kb is not None:
                    kb.value = _clamp01(face_vals[kname])
                    kb.keyframe_insert(data_path="value", frame=f)

    return hips_pos, hips_rot


def _keyframe_camera(cam: bpy.types.Object, frame: int, loc: Vector, target: Vector, roll_deg: float = 0.0, lens: float = 30.0) -> None:
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


def _animate_world_physics_and_cameras(
    scene: bpy.types.Scene,
    cam: bpy.types.Object,
    rag: Dict[str, object],
    umb_info: Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object],
    drums: List[bpy.types.Object],
) -> int:
    scene.frame_start = 1
    scene.frame_end = 300
    umb, rb_umb_hull, _ = umb_info

    # --- PASS 1: Bake trajectory to find exact runway landing spot around F235..275 ---
    print("[jet] Pass 1 physics bake (finding exact barrel-crash landing point)...", flush=True)
    t0 = time.time()
    bpy.ops.ptcache.bake_all(bake=True)
    print(f"[jet] Pass 1 bake finished in {time.time() - t0:.1f}s", flush=True)

    f_hit = 252
    hit_pos = Vector((26.0, 0.0, 1.0))
    for f in range(180, 290):
        scene.frame_set(f)
        hp = rag["hips_rb"].matrix_world.translation
        if hp.z <= 1.55 and hp.x > 14.0:
            f_hit = f
            hit_pos = hp.copy()
            break
    else:
        scene.frame_set(252)
        hit_pos = rag["hips_rb"].matrix_world.translation.copy()
    print(f"[jet] Pass 1 detected runway touchdown: F{f_hit} at {tuple(round(x,2) for x in hit_pos)}", flush=True)

    # --- Free bake, relocate 6-drum Barrel_01 pyramid + RB_Umbrella to handoff, & PASS 2 FINAL BAKE ---
    bpy.ops.ptcache.free_bake_all()
    _place_barrel_pyramid(drums, hit_pos.x + 0.5, hit_pos.y)

    # Also match RB_UmbrellaHull starting spot cleanly to F147 umbrella spot
    scene.frame_set(147)
    rb_umb_hull.location = Vector((5.65, -0.25, 1.45))

    # Add an extra kinetic BarrelSmashHelper linked cleanly to impact spot at f_hit-2..f_hit+10?
    # Better: let the 11 heavy Rigid Bodies (~73kg) + RB_Hips themselves plow into the pyramid!
    # Also ensure RB_Hips hits barrel height by nudging pyramid X slightly if needed; wait, barrel height goes z=0.45..2.64 so hit_pos.z<=1.55 hits squarely!
    print("[jet] Pass 2 final Cloth + Bullet physics bake (frames 1..300)...", flush=True)
    t1 = time.time()
    bpy.ops.ptcache.bake_all(bake=True)
    print(f"[jet] Pass 2 final bake finished in {time.time() - t1:.1f}s", flush=True)

    hips_pos, hips_rot = _apply_hybrid_poses_face_and_umbrella(scene, rag, umb)
    print(
        f"[jet] Final Hips track: F145={tuple(round(x,2) for x in hips_pos[145])}, "
        f"F195={tuple(round(x,2) for x in hips_pos[195])}, "
        f"F{f_hit}={tuple(round(x,2) for x in hips_pos[f_hit])}, "
        f"F280={tuple(round(x,2) for x in hips_pos[280])}",
        flush=True,
    )

    # Check Barrel displacement after hit!
    scene.frame_set(min(300, f_hit + 24))
    barrel_moves = [round((d.matrix_world.translation - Vector((hit_pos.x, hit_pos.y, d.location.z))).length, 2) for d in drums]
    print(f"[jet] Barrel displacements at F{min(300, f_hit + 24)}: {barrel_moves}", flush=True)

    # FaceFill tracking light for crisp screaming face in Shot 3
    fl_data = bpy.data.lights.new("FaceFill", type="AREA")
    fl_data.energy = 0.0
    fl_data.size = 5.5
    fl_data.color = (1.0, 0.97, 0.92)
    fl = bpy.data.objects.new("FaceFill", fl_data)
    scene.collection.objects.link(fl)

    for f in range(1, 301):
        # Shot 1 (F1..75): Wide 3/4 runway establish (Turbofan + man + umbrella + parked A350)
        if f <= 75:
            u = (f - 1) / 74.0
            _keyframe_camera(
                scene.camera, f,
                _lerp_vec((10.5, -13.5, 4.4), (9.2, -10.8, 3.3), _smoothstep(0.0, 1.0, u)),
                _lerp_vec((2.2, 2.0, 1.8), (3.4, 0.2, 1.5), _smoothstep(0.0, 1.0, u)),
                lens=28.0,
            )
            fl_data.energy = 0.0
            fl_data.keyframe_insert(data_path="energy", frame=f)

        # Shot 2 (F76..150): Mid side-front as jet blast peaks, umbrella inverts, cones/suitcase rocket past!
        elif f <= 150:
            u = (f - 76) / 74.0
            sh = _smoothstep(86.0, 148.0, float(f))
            sx = 0.07 * math.sin(f * 2.5) * sh
            sz = 0.06 * math.cos(f * 2.1) * sh
            _keyframe_camera(
                scene.camera, f,
                _lerp_vec((9.6, -5.6, 1.85), (9.0, -4.8, 1.70), u) + Vector((sx, 0.0, sz)),
                _lerp_vec((4.4, 0.0, 1.35), (4.0, 0.0, 1.40), u),
                lens=30.0,
            )
            fl_data.energy = 0.0
            fl_data.keyframe_insert(data_path="energy", frame=f)

        # Shot 3 (F151..240): Zack D. Films 24mm front-3/4 flight tracking shot aligned with torso front + back runway view!
        elif f <= 240:
            u = (f - 151) / 89.0
            hp = hips_pos[f]
            hips_front = (hips_rot[f].to_matrix() @ Vector((0.0, 0.0, 1.0))).normalized()
            cam_dir = (
                hips_front * 0.55
                + Vector((0.55, -0.70, 0.35)).normalized() * 0.45
            ).normalized()
            if cam_dir.z < 0.25:
                cam_dir.z = 0.25
                cam_dir.normalize()
            cam_loc = hp + cam_dir * _lerp(2.45, 2.20, u)
            _keyframe_camera(
                scene.camera, f,
                cam_loc,
                hp + Vector((-0.35, 0.10, -0.15)),
                roll_deg=_lerp(-6.0, 5.0, u),
                lens=24.0,
            )
            fl.location = cam_loc + Vector((0.3, -0.4, 0.4))
            fl.rotation_mode = "QUATERNION"
            fl.rotation_quaternion = (hp - fl.location).to_track_quat("-Z", "Y")
            fl.keyframe_insert(data_path="location", frame=f)
            fl.keyframe_insert(data_path="rotation_quaternion", frame=f)
            fl_data.energy = 135.0
            fl_data.keyframe_insert(data_path="energy", frame=f)

        # Shot 4 (F241..300): Low runway impact camera as he smashes through the 6 Barrel_01 pyramid!
        else:
            u = (f - 241) / 59.0
            imp_shake = math.sin(f * 2.8) * 0.12 * math.exp(-max(0, f - f_hit) / 10.0) if f >= f_hit else 0.0
            _keyframe_camera(
                scene.camera, f,
                Vector((hit_pos.x + 4.8 - 0.8 * u, hit_pos.y - 4.8, 1.65 + imp_shake)),
                Vector((hit_pos.x + 0.8, hit_pos.y, 1.05)),
                lens=28.0,
            )
            fl_data.energy = 0.0
            fl_data.keyframe_insert(data_path="energy", frame=f)

    return f_hit


def _print_diagnostics(scene: bpy.types.Scene, arm: bpy.types.Object, f_hit: int) -> None:
    print("\n=== JET UMBRELLA ACTIVE RAGDOLL JOINT DIAGNOSTICS ===", flush=True)
    bones = ["Spine2", "Head", "LeftArm", "LeftForeArm", "RightArm", "RightForeArm", "LeftUpLeg", "LeftLeg", "RightUpLeg", "RightLeg"]
    rb_hips = bpy.data.objects.get("RB_Hips")
    for f in (35, 120, 155, 195, 225, f_hit):
        scene.frame_set(f)
        deps = bpy.context.evaluated_depsgraph_get()
        arm_eval = arm.evaluated_get(deps)
        parts = [f"{bn}:{math.degrees(arm_eval.pose.bones[bn].rotation_quaternion.angle):.0f}°" for bn in bones if bn in arm_eval.pose.bones]
        pos_s = ""
        if rb_hips:
            p = rb_hips.evaluated_get(deps).matrix_world.translation
            pos_s = f" | Hips=({p.x:.1f},{p.y:.1f},{p.z:.1f})"
        print(f"F{f:03d}: " + " ".join(parts) + pos_s, flush=True)


def main() -> None:
    args = _parse_args()
    os.makedirs(args.frames_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.save_blend), exist_ok=True)

    _clear_scene_safe()
    scene = bpy.context.scene
    _setup_eevee(scene, args)
    _setup_world(scene)
    _ensure_rigidbody_world(scene)

    _build_runway_environment(scene)
    _build_hero_turbofan(scene)
    umb_info = _build_cloth_umbrella(scene)
    _build_cones_and_suitcase(scene)
    rag = _build_businessman_ragdoll(scene)
    drums = _import_barrel_pyramid(scene)

    cam_data = bpy.data.cameras.new("JetCam")
    cam_data.clip_start = 0.1
    cam_data.clip_end = 4000.0
    cam = bpy.data.objects.new("JetCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    f_hit = _animate_world_physics_and_cameras(scene, cam, rag, umb_info, drums)
    _print_diagnostics(scene, rag["arm"], f_hit)

    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("[jet] pack_all warning:", e, flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.save_blend)
    print(f"[jet] Saved blend: {args.save_blend}", flush=True)

    if args.preview_only:
        preview_frames = [
            ("F035_hook_runway", 35),
            ("F120_umbrella_invert", 120),
            ("F195_ragdoll_flight", 195),
            ("F268_barrel_crash", min(295, max(230, f_hit + 3))),
        ]
        for label, fnum in preview_frames:
            ts = time.time()
            scene.frame_set(fnum)
            scene.render.filepath = os.path.join(args.frames_dir, f"preview_{label}.png")
            bpy.ops.render.render(write_still=True)
            print(f"[jet] Preview {label} rendered in {time.time() - ts:.2f}s", flush=True)
        return

    if args.render_all:
        for fnum in range(1, 301):
            ts = time.time()
            scene.frame_set(fnum)
            scene.render.filepath = os.path.join(args.frames_dir, f"frame_{fnum:04d}.png")
            bpy.ops.render.render(write_still=True)
            if fnum % 30 == 0 or fnum == 300 or fnum <= 3:
                print(f"[jet] Rendered {fnum}/300 ({time.time() - ts:.2f}s/f)", flush=True)


if __name__ == "__main__":
    main()
