#!/usr/bin/env python3
"""Procedural Blender 5.1 3D Universal A-Hook Template Renderer.

Generates 100% product-agnostic 9:16 cold-opener templates (0 credits) designed
around pure Zeigarnik retention mechanics without visual/category product clues.

Usage:
  blender --background --python libraries/media-tools/ad_hook_template_blender.py -- \
    --frames-dir /path/to/frames --width 1080 --height 1920 --fps 30 --duration 7.24
"""

from __future__ import annotations

import argparse
import colorsys
import math
import os
import sys

import bpy
from mathutils import Vector


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Blender Universal A-Hook Template T1")
    p.add_argument("--frames-dir", required=True, help="Output directory for PNG frames")
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--height", type=int, default=1920)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--duration", type=float, default=7.24)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--preview-only", action="store_true", help="Render only 2 spot frames (mid + end)")
    return p.parse_args(argv)


def _clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _set_input(node: bpy.types.Node, name: str, value) -> None:
    if name in node.inputs:
        node.inputs[name].default_value = value


def _make_principled_mat(
    name: str,
    base_color,
    *,
    metallic: float = 0.0,
    roughness: float = 0.25,
    coat_weight: float = 0.0,
    emission_color=None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is not None:
        _set_input(bsdf, "Base Color", (*base_color, 1.0))
        _set_input(bsdf, "Metallic", metallic)
        _set_input(bsdf, "Roughness", roughness)
        _set_input(bsdf, "Coat Weight", coat_weight)
        _set_input(bsdf, "Coat Roughness", 0.08)
        if emission_color is not None and emission_strength > 0:
            _set_input(bsdf, "Emission Color", (*emission_color, 1.0))
            _set_input(bsdf, "Emission Strength", emission_strength)
    return mat


def _pick_render_engine(scene: bpy.types.Scene) -> str:
    enum_items = [
        item.identifier
        for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ]
    for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        if cand in enum_items:
            scene.render.engine = cand
            return cand
    return scene.render.engine


def _setup_world_and_lights(scene: bpy.types.Scene) -> None:
    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    if bg is not None:
        bg.inputs["Color"].default_value = (0.015, 0.020, 0.042, 1.0)
        bg.inputs["Strength"].default_value = 0.85

    def add_area(name: str, loc, rot_deg, energy: float, size: float, color):
        ld = bpy.data.lights.new(name=name, type="AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        return lo

    # Key warm light front-right
    add_area("KeyLight", (4.5, -5.0, 5.2), (55.0, 0.0, 42.0), 420.0, 3.2, (1.0, 0.94, 0.88))
    # Cool cyan rim light back-left
    add_area("RimLightCyan", (-4.2, 4.8, 3.8), (118.0, 0.0, -35.0), 380.0, 3.8, (0.58, 0.84, 1.0))
    # Soft violet fill left
    add_area("FillLightViolet", (-4.8, -3.5, 2.2), (72.0, 0.0, -52.0), 180.0, 4.0, (0.76, 0.72, 1.0))
    # Subtle top strip light for metallic arch + specular highlights
    add_area("TopStrip", (0.0, 0.0, 6.2), (0.0, 0.0, 0.0), 220.0, 2.5, (1.0, 0.98, 0.95))


def _build_scene(args: argparse.Namespace) -> None:
    _clear_scene()
    scene = bpy.context.scene
    engine = _pick_render_engine(scene)
    print(f"[blender] Using engine={engine} {args.width}x{args.height}@{args.fps}fps dur={args.duration}s", flush=True)

    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.fps = args.fps
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    if hasattr(scene, "eevee"):
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = args.samples
        if hasattr(scene.eevee, "use_bloom"):
            scene.eevee.use_bloom = True
            scene.eevee.bloom_intensity = 0.08
    if engine == "CYCLES":
        scene.cycles.samples = max(16, args.samples)
        scene.cycles.use_adaptive_sampling = True

    try:
        scene.view_settings.view_transform = "AgX"
    except Exception:
        scene.view_settings.view_transform = "Filmic"
    scene.view_settings.exposure = 0.15

    _setup_world_and_lights(scene)

    # Studio floor plinth + subtle alignment glow rail
    floor_mat = _make_principled_mat("FloorMatte", (0.018, 0.024, 0.052), metallic=0.28, roughness=0.14, coat_weight=0.55)
    bpy.ops.mesh.primitive_plane_add(size=36.0, location=(0.0, 0.0, -0.45))
    floor_obj = bpy.context.active_object
    floor_obj.data.materials.append(floor_mat)

    rail_mat = _make_principled_mat(
        "CenterGuideRail",
        (0.98, 0.84, 0.36),
        metallic=0.25,
        roughness=0.18,
        emission_color=(1.0, 0.85, 0.35),
        emission_strength=3.2,
    )
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.445))
    rail = bpy.context.active_object
    rail.scale = (0.04, 6.2, 0.014)
    rail.data.materials.append(rail_mat)

    # Cantilevered champagne brushed-gold gantry (rear portal + top twin rail; front is open so camera view is unobstructed)
    gold_mat = _make_principled_mat("BrushedChampagneGold", (0.88, 0.74, 0.46), metallic=0.92, roughness=0.22)
    rod_mat = _make_principled_mat("ThinSteelRod", (0.76, 0.80, 0.88), metallic=0.95, roughness=0.16)

    y_min, y_max = -2.75, 2.75
    z_top = 3.25
    for x_off in (-0.16, 0.16):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.036, depth=6.20, location=(x_off, 0.10, z_top), rotation=(math.radians(90.0), 0.0, 0.0))
        bar = bpy.context.active_object
        bar.data.materials.append(gold_mat)

    for x_side in (-1.65, 1.65):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.055, depth=3.75, location=(x_side, 3.15, 1.40))
        post = bpy.context.active_object
        post.data.materials.append(gold_mat)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.055, depth=3.42, location=(0.0, 3.15, z_top), rotation=(0.0, math.radians(90.0), 0.0))
    cross = bpy.context.active_object
    cross.data.materials.append(gold_mat)

    # 18 Pendulum Wave Spheres
    num_spheres = 18
    rod_length = 2.55
    sphere_r = 0.145
    theta_max = 0.44  # ~25 deg swing keeps all 18 spheres inside 9:16 safe horizontal margins
    t_align = 7.36  # freezes at t=7.24s, just 0.12s shy of straight center alignment
    base_cycles = 4.0

    pivots = []
    for i in range(num_spheres):
        y_pos = y_min + (y_max - y_min) * (i / (num_spheres - 1))
        piv = bpy.data.objects.new(f"Pivot_{i:02d}", None)
        piv.location = (0.0, y_pos, z_top)
        scene.collection.objects.link(piv)

        # Rod
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.013, depth=rod_length, location=(0.0, 0.0, -rod_length / 2.0))
        rod = bpy.context.active_object
        rod.data.materials.append(rod_mat)
        rod.parent = piv

        # Glossy rainbow-pastel sphere
        hue = (0.02 + 0.78 * (i / (num_spheres - 1))) % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.72, 0.96)
        sph_mat = _make_principled_mat(
            f"SphereMat_{i:02d}",
            rgb,
            metallic=0.12,
            roughness=0.08,
            coat_weight=0.85,
            emission_color=rgb,
            emission_strength=0.12,
        )
        bpy.ops.mesh.primitive_uv_sphere_add(segments=36, ring_count=20, radius=sphere_r, location=(0.0, 0.0, -rod_length))
        sph = bpy.context.active_object
        bpy.ops.object.shade_smooth()
        sph.data.materials.append(sph_mat)
        sph.parent = piv

        freq = (base_cycles + i * 1.0) / t_align
        pivots.append((piv, freq))

    # Camera + Track-To Target
    target = bpy.data.objects.new("CamTarget", None)
    scene.collection.objects.link(target)
    target.location = (0.0, 0.0, 1.05)

    cam_data = bpy.data.cameras.new("MainCam")
    cam_data.lens = 35.0
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = 5.6
    cam = bpy.data.objects.new("MainCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    total_frames = max(2, int(round(args.duration * args.fps)))
    scene.frame_start = 1
    scene.frame_end = total_frames

    # Pre-bake keyframes per frame for smooth analytic wave & orbit
    for frame in range(1, total_frames + 1):
        t = (frame - 1) / float(args.fps)
        scene.frame_set(frame)
        for piv, freq in pivots:
            # Wave explodes from center line at t=0, weaves double-helix at t=T/2,
            # and sweeps fast toward dead-center alignment right before t=7.45s
            theta = theta_max * math.sin(2.0 * math.pi * freq * t)
            piv.rotation_euler = (0.0, theta, 0.0)
            piv.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Smooth ease camera from dynamic 3/4 view -> centered corridor framing all 18 spheres cleanly
        u = min(1.0, max(0.0, t / args.duration))
        ease = u * u * (3.0 - 2.0 * u)
        angle = math.radians(34.0 * (1.0 - ease))
        radius = 8.40 - 1.10 * ease
        cam.location = (
            radius * math.sin(angle),
            -radius * math.cos(angle) - 0.55,
            2.65 - 0.85 * ease,
        )
        cam.keyframe_insert(data_path="location", frame=frame)

        target.location = (0.0, -0.15 * (1.0 - ease), 1.15 - 0.05 * ease)
        target.keyframe_insert(data_path="location", frame=frame)

    os.makedirs(args.frames_dir, exist_ok=True)
    if args.preview_only:
        for fnum in (max(1, total_frames // 2), total_frames):
            scene.frame_set(fnum)
            scene.render.filepath = os.path.join(args.frames_dir, f"preview_{fnum:04d}.png")
            bpy.ops.render.render(write_still=True)
    else:
        scene.render.filepath = os.path.join(args.frames_dir, "frame_")
        bpy.ops.render.render(animation=True)


def main() -> None:
    args = _parse_args()
    _build_scene(args)


if __name__ == "__main__":
    main()
