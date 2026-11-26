"""Step 2: 4-Act 15.00s (450f @ 30fps) Comedy Story Episode:
"PS2 캐릭터의 첫 2호선 출근길 (반전 엔딩)"
Reuses zero-voxel 3D humans, UV-Snap PS2 shaders, & curved Seoul Line 2 interior from build_ps2_subway.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import subprocess
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, "/Users/yun-yeowon/workspace/ad-studio/viral-3d-templates")
sys.path.insert(0, "/Users/yun-yeowon/workspace/ad-studio/ps2-kr-subway")

try:
    import bpy
    from mathutils import Vector
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

if IN_BLENDER:
    from build_ps2_subway import (
        add_box,
        add_cyl,
        add_sign_plane,
        apply_all_face_weights,
        apply_ps2_pixel_shader,
        build_curved_ceiling,
        build_green_line2_handle,
        import_commuter_michelle,
        import_commuter_rpm,
        make_tex_mat,
    )
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
    from PIL import Image, ImageDraw, ImageFont
    FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

    def stitch_6grid(frame_paths: List[str], out_png: str) -> None:
        imgs = [Image.open(p).resize((480, 854), Image.Resampling.LANCZOS) for p in frame_paths[:6]]
        canvas = Image.new("RGB", (480 * 3, 854 * 2), (16, 18, 24))
        font = ImageFont.truetype(FONT_PATH, size=20, index=4)
        for idx, (p, im) in enumerate(zip(frame_paths[:6], imgs)):
            x, y = (idx % 3) * 480, (idx // 3) * 854
            canvas.paste(im, (x, y))
            d = ImageDraw.Draw(canvas)
            d.rectangle([x + 10, y + 10, x + 360, y + 46], fill=(0, 0, 0))
            d.text((x + 18, y + 14), os.path.basename(p), font=font, fill=(120, 255, 180))
        canvas.save(out_png)

BLENDER_BIN = "/Applications/Blender.app/Contents/MacOS/Blender"
ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-kr-subway"
TEX_DIR = os.path.join(ROOT, "textures")
FRAMES_DIR = os.path.join(ROOT, "frames_story")
QA_PREVIEW = os.path.join(ROOT, "qa_story_preview_6frames.png")

TOTAL_FRAMES = 450
FPS = 30
RENDER_W = 540
RENDER_H = 960


def story_hero_pose_and_face(f: int) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, float]]:
    # Act 1a (F001..F050): Smug cocky platform stance facing camera with natural arms
    if f <= 50:
        nod = math.sin(f * 0.25) * 4.5
        pose = {
            "Spine": (2.0, 0.0, 0.0),
            "Head": (nod - 2.0, 5.0, 0.0),
            "LeftShoulder": (0.0, 0.0, -5.0),
            "RightShoulder": (0.0, 0.0, 5.0),
            "LeftArm": (16.0, 0.0, 6.0),
            "RightArm": (16.0, 0.0, -6.0),
            "LeftForeArm": (0.0, 0.0, 16.0),
            "RightForeArm": (0.0, 0.0, -16.0),
            "LeftUpLeg": (3.0, 0.0, 4.0),
            "RightUpLeg": (3.0, 0.0, -4.0),
            "LeftLeg": (-6.0, 0.0, 0.0),
            "RightLeg": (-6.0, 0.0, 0.0),
        }
        face = {
            "mouthSmileLeft": 0.55,
            "mouthSmileRight": 0.45,
            "browOuterUpLeft": 0.40,
            "browOuterUpRight": 0.40,
            "jawOpen": 0.14 if 10 <= f <= 46 else 0.04,
        }
        return pose, face

    # Act 1b (F051..F095): Doors open -> JAW-DROP shock at solid wall of commuters!
    if f <= 95:
        sh = smoothstep(55.0, 74.0, float(f))
        pose = {
            "Spine": (-7.0 * sh, 0.0, 0.0),
            "Head": (-10.0 * sh, 0.0, 0.0),
            "LeftShoulder": (0.0, 0.0, 6.0 * sh),
            "RightShoulder": (0.0, 0.0, -6.0 * sh),
            "LeftArm": (lerp(16.0, 10.0, sh), 0.0, lerp(6.0, 22.0, sh)),
            "RightArm": (lerp(16.0, 10.0, sh), 0.0, lerp(-6.0, -22.0, sh)),
            "LeftForeArm": (0.0, 0.0, lerp(16.0, 44.0, sh)),
            "RightForeArm": (0.0, 0.0, lerp(-16.0, -44.0, sh)),
            "LeftUpLeg": (5.0, 0.0, 4.0),
            "RightUpLeg": (5.0, 0.0, -4.0),
            "LeftLeg": (-10.0, 0.0, 0.0),
            "RightLeg": (-10.0, 0.0, 0.0),
        }
        face = {
            "eyeWideLeft": 0.96 * sh,
            "eyeWideRight": 0.96 * sh,
            "browInnerUp": 0.92 * sh,
            "browOuterUpLeft": 0.70 * sh,
            "browOuterUpRight": 0.70 * sh,
            "jawOpen": 0.68 * sh,
            "mouthFunnel": 0.25 * sh,
        }
        return pose, face

    # Act 2a (F096..F138): Lunge forward and push hard into crowd's backs!
    if f <= 138:
        u = smoothstep(96.0, 114.0, float(f))
        pw = max(0.0, math.sin((f - 104) * 0.30))
        stride = math.sin((f - 96) * 0.42) * 16.0
        pose = {
            "Spine": (22.0 * u + 6.0 * pw, 0.0, 0.0),
            "Spine1": (10.0 * u, 0.0, 0.0),
            "Head": (-18.0 * u, 0.0, 0.0),
            "LeftShoulder": (0.0, 0.0, 16.0 * u),
            "RightShoulder": (0.0, 0.0, -16.0 * u),
            "LeftArm": (lerp(10.0, 8.0, u), 0.0, lerp(22.0, 70.0 + 8.0 * pw, u)),
            "RightArm": (lerp(10.0, 8.0, u), 0.0, lerp(-22.0, -70.0 - 8.0 * pw, u)),
            "LeftForeArm": (0.0, 0.0, lerp(44.0, 14.0, u)),
            "RightForeArm": (0.0, 0.0, lerp(-44.0, -14.0, u)),
            "LeftUpLeg": (14.0 + stride, 0.0, 5.0),
            "RightUpLeg": (14.0 - stride, 0.0, -5.0),
            "LeftLeg": (-24.0 - 0.3 * abs(stride), 0.0, 0.0),
            "RightLeg": (-24.0 - 0.3 * abs(stride), 0.0, 0.0),
        }
        face = {
            "browDownLeft": 0.72, "browDownRight": 0.72,
            "eyeSquintLeft": 0.70, "eyeSquintRight": 0.70,
            "jawOpen": 0.35 + 0.25 * pw,
            "mouthStretchLeft": 0.55, "mouthStretchRight": 0.55,
        }
        return pose, face

    # Act 2b (F139..F200): BOUNCED BACK! Stumbling backward onto platform, arms windmilling!
    if f <= 200:
        bnc = math.sin(min(1.0, (f - 139) / 28.0) * math.pi)
        rec = smoothstep(172.0, 196.0, float(f))
        flail = math.sin((f - 139) * 0.55) * 28.0 * (1.0 - rec)
        pose = {
            "Spine": (-24.0 * bnc + 4.0 * rec, 0.0, 0.0),
            "Head": (-18.0 * bnc + 6.0 * rec, 8.0 * bnc, 0.0),
            "LeftShoulder": (0.0, 0.0, 12.0 * (1.0 - rec)),
            "RightShoulder": (0.0, 0.0, -12.0 * (1.0 - rec)),
            "LeftArm": (lerp(-18.0, 16.0, rec), 0.0, lerp(48.0, 6.0, rec) + flail * 0.6),
            "RightArm": (lerp(-18.0, 16.0, rec), 0.0, lerp(-48.0, -6.0, rec) - flail * 0.6),
            "LeftForeArm": (0.0, 0.0, 28.0),
            "RightForeArm": (0.0, 0.0, -28.0),
            "LeftUpLeg": (28.0 * bnc + 5.0 * rec, 0.0, 8.0),
            "RightUpLeg": (-14.0 * bnc + 5.0 * rec, 0.0, -8.0),
            "LeftLeg": (-32.0 * bnc - 8.0, 0.0, 0.0),
            "RightLeg": (-18.0 * bnc - 8.0, 0.0, 0.0),
        }
        face = {
            "eyeWideLeft": 0.95, "eyeWideRight": 0.95,
            "browInnerUp": 0.95,
            "jawOpen": 0.85 * (1.0 - 0.6 * rec),
            "mouthStretchLeft": 0.72, "mouthStretchRight": 0.72,
        }
        return pose, face

    # Act 3 (F201..F320): Rush back & spin 180 to force way in BACK-FIRST before doors slam!
    if f <= 320:
        run_s = math.sin((f - 201) * 0.50) * 20.0 * (1.0 - smoothstep(260.0, 305.0, float(f)))
        jam = smoothstep(245.0, 275.0, float(f))
        wiggle = math.sin((f - 255) * 0.45) * 6.0 * jam * (1.0 - smoothstep(305.0, 320.0, float(f)))
        pose = {
            "Spine": (lerp(14.0, -10.0, jam), wiggle, 0.0),
            "Head": (-6.0, wiggle * 0.6, 0.0),
            "LeftShoulder": (0.0, 0.0, -8.0),
            "RightShoulder": (0.0, 0.0, 8.0),
            "LeftArm": (20.0, 0.0, 12.0),
            "RightArm": (20.0, 0.0, -12.0),
            "LeftForeArm": (0.0, 0.0, 32.0),
            "RightForeArm": (0.0, 0.0, -32.0),
            "LeftUpLeg": (8.0 + run_s, 0.0, 4.0),
            "RightUpLeg": (8.0 - run_s, 0.0, -4.0),
            "LeftLeg": (-14.0 - 0.3 * abs(run_s), 0.0, 0.0),
            "RightLeg": (-14.0 - 0.3 * abs(run_s), 0.0, 0.0),
        }
        face = {
            "browDownLeft": 0.80, "browDownRight": 0.80,
            "eyeSquintLeft": 0.75, "eyeSquintRight": 0.75,
            "jawOpen": 0.45, "mouthStretchLeft": 0.55, "mouthStretchRight": 0.55,
        }
        return pose, face

    # Act 4a (F321..F386): Exhausted relief sigh wedged inside ("휴... 살았다...")
    sway = math.sin((f - 321) * 0.48) * 2.8
    if f <= 386:
        rel = smoothstep(325.0, 345.0, float(f))
        pose = {
            "Spine": (2.0, sway * 0.4, 0.0),
            "Head": (4.0 * rel, sway, 0.0),
            "Neck": (2.0 * rel, sway * 0.3, 0.0),
            "LeftShoulder": (0.0, 0.0, -6.0),
            "RightShoulder": (0.0, 0.0, 6.0),
            "LeftArm": (22.0, 0.0, 8.0),
            "RightArm": (22.0, 0.0, -8.0),
            "LeftForeArm": (0.0, 0.0, 18.0),
            "RightForeArm": (0.0, 0.0, -18.0),
            "LeftUpLeg": (4.0, 0.0, 3.0),
            "RightUpLeg": (4.0, 0.0, -3.0),
            "LeftLeg": (-6.0, 0.0, 0.0),
            "RightLeg": (-6.0, 0.0, 0.0),
        }
        face = {
            "eyeSquintLeft": 0.88 * rel, "eyeSquintRight": 0.88 * rel,
            "browInnerUp": 0.75 * rel,
            "mouthFrownLeft": 0.55 * rel, "mouthFrownRight": 0.55 * rel,
            "jawOpen": 0.24 * rel,
            "mouthFunnel": 0.28 * rel,
        }
        return pose, face

    # Act 4b (F387..F450): WRONG-WAY TWIST HORROR! Eyes snap WIDE OPEN + total despair scream!
    hr = smoothstep(387.0, 396.0, float(f))
    tremble = math.sin((f - 387) * 0.9) * 1.8 * hr
    pose = {
        "Spine": (-3.0 * hr, sway * 0.4, 0.0),
        "Head": (-10.0 * hr, tremble, 0.0),
        "Neck": (-4.0 * hr, tremble * 0.5, 0.0),
        "LeftShoulder": (0.0, 0.0, -4.0),
        "RightShoulder": (0.0, 0.0, 4.0),
        "LeftArm": (22.0, 0.0, 8.0),
        "RightArm": (22.0, 0.0, -8.0),
        "LeftForeArm": (0.0, 0.0, 18.0),
        "RightForeArm": (0.0, 0.0, -18.0),
        "LeftUpLeg": (4.0, 0.0, 3.0),
        "RightUpLeg": (4.0, 0.0, -3.0),
        "LeftLeg": (-6.0, 0.0, 0.0),
        "RightLeg": (-6.0, 0.0, 0.0),
    }
    face = {
        "eyeWideLeft": 1.0 * hr, "eyeWideRight": 1.0 * hr,
        "browInnerUp": 1.0 * hr,
        "browOuterUpLeft": 0.85 * hr, "browOuterUpRight": 0.85 * hr,
        "jawOpen": 0.94 * hr,
        "mouthStretchLeft": 0.82 * hr, "mouthStretchRight": 0.82 * hr,
        "mouthFrownLeft": 0.92 * hr, "mouthFrownRight": 0.92 * hr,
        "mouthLowerDownLeft": 0.72 * hr, "mouthLowerDownRight": 0.72 * hr,
    }
    return pose, face


def build_story_scene(samples: int = 14) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    clear_scene_safe()
    scene = bpy.context.scene

    setup_eevee(
        scene, width=RENDER_W, height=RENDER_H, fps=FPS,
        samples=samples, total_frames=TOTAL_FRAMES,
        exposure=0.08, glare_strength=0.35,
    )
    scene.render.use_motion_blur = False
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    w = bpy.data.worlds.new("PS2StoryMood")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.035, 0.042, 0.048, 1.0)
        bg.inputs["Strength"].default_value = 0.35

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
    wrong_led_mat = make_tex_mat("SeongsuWrongLED", os.path.join(TEX_DIR, "seongsu_wrong_led.png"), emission=1.65, roughness=0.28)
    routemap_mat = make_tex_mat("Line2RouteMap", os.path.join(TEX_DIR, "line2_routemap.png"), emission=0.40, roughness=0.4)
    psd_mat = make_tex_mat("PSDDecal", os.path.join(TEX_DIR, "psd_decal.png"), emission=0.22, roughness=0.5)

    for name, loc, rot, en, sz, col in (
        ("CarFluorFront", (0.0, 0.75, 2.38), (0.0, 0.0, 0.0), 48.0, 2.4, (0.92, 1.0, 0.93)),
        ("CarFluorBack", (0.0, 2.05, 2.38), (0.0, 0.0, 0.0), 48.0, 2.4, (0.92, 1.0, 0.93)),
        ("PlatformOverhead", (0.0, -2.1, 3.3), (12.0, 0.0, 0.0), 95.0, 4.0, (0.90, 0.95, 1.0)),
        ("PlatformHeroKey", (0.9, -2.4, 2.3), (58.0, 0.0, 22.0), 28.0, 1.6, (0.96, 0.98, 1.0)),
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

    add_box("PlatformSlab", (0.0, -2.85, -0.25), (14.0, 5.4, 0.50), plat_m)
    add_box("TactileStrip", (0.0, -0.56, 0.004), (14.0, 0.28, 0.012), tactile_m)

    train_root = bpy.data.objects.new("SubwayTrain", None)
    scene.collection.objects.link(train_root)

    add_box("CarFloor", (0.0, 1.45, -0.05), (12.0, 3.1, 0.10), car_floor_m, train_root)
    build_curved_ceiling(scene, car_wall_m, train_root)
    for lx in (-2.4, -1.2, 0.0, 1.2, 2.4):
        add_box(f"ACVent_{lx}", (lx, 1.45, 2.43), (0.95, 0.58, 0.025), car_trim_m, train_root)

    add_box("BackWallLow", (0.0, 2.95, 0.50), (12.0, 0.14, 1.0), car_wall_m, train_root)
    add_box("BackWallTop", (0.0, 2.95, 2.18), (12.0, 0.14, 0.52), car_wall_m, train_root)
    add_box("BackWindowDark", (0.0, 2.98, 1.45), (11.6, 0.06, 0.92), win_tunnel_m, train_root)
    for px in (-4.2, -2.1, 0.0, 2.1, 4.2):
        add_box(f"BackPillar_{px}", (px, 2.91, 1.45), (0.34, 0.16, 0.96), car_wall_m, train_root)

    add_box("FrontWallLeft", (-3.4, 0.0, 1.24), (5.24, 0.12, 2.48), car_wall_m, train_root)
    add_box("FrontWallRight", (3.4, 0.0, 1.24), (5.24, 0.12, 2.48), car_wall_m, train_root)
    add_box("FrontDoorHeader", (0.0, 0.0, 2.28), (1.60, 0.14, 0.42), car_wall_m, train_root)
    add_box("FrontDoorGreenTrim", (0.0, -0.075, 2.09), (1.64, 0.04, 0.05), green_m, train_root)
    for gx in (-0.79, 0.79):
        add_box(f"DoorGasket_{gx}", (gx, -0.05, 1.04), (0.04, 0.10, 2.08), car_trim_m, train_root)

    for ry, sgn in ((0.22, 1.0), (2.70, -1.0)):
        for wy in range(4):
            add_cyl(f"RackWire_{ry}_{wy}", (0.0, ry + sgn * (0.05 * wy), 1.98), 0.008, 10.5, (0.0, 90.0, 0.0), steel_m, train_root, verts=8)
        for bx in (-3.0, -1.5, 0.0, 1.5, 3.0):
            add_cyl(f"RackBracket_{ry}_{bx}", (bx, ry + sgn * 0.08, 1.98), 0.012, 0.22, (90.0, 0.0, 0.0), steel_m, train_root, verts=8)

    for sx in (-1.45, 1.45):
        add_box(f"PSDPillar_{sx}", (sx, -0.22, 1.22), (0.58, 0.10, 2.44), steel_m)
    add_box("PSDTopBeam", (0.0, -0.22, 2.34), (8.0, 0.12, 0.28), steel_m)
    add_sign_plane("PSD_Sign", (0.0, -0.29, 2.32), (1.45, 0.24), (90.0, 0.0, 0.0), psd_mat)

    train_door_l = add_box("TrainDoorL", (-0.40, -0.05, 1.04), (0.80, 0.06, 2.08), steel_m, train_root)
    train_door_r = add_box("TrainDoorR", (0.40, -0.05, 1.04), (0.80, 0.06, 2.08), steel_m, train_root)
    add_box("DoorWinL", (-0.40, -0.06, 1.38), (0.46, 0.08, 0.85), door_glass_m, train_door_l)
    add_box("DoorWinR", (0.40, -0.06, 1.38), (0.46, 0.08, 0.85), door_glass_m, train_door_r)

    psd_door_l = add_box("PSDDoorL", (-0.40, -0.18, 1.06), (0.78, 0.05, 2.12), door_glass_m)
    psd_door_r = add_box("PSDDoorR", (0.40, -0.18, 1.06), (0.78, 0.05, 2.12), door_glass_m)

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

    # Dual-state ceiling monitor: Wangsimni F1..374 -> flips to 성수행 (반대방향) F375..450!
    add_box("LCDBox", (0.0, 1.98, 2.08), (0.94, 0.14, 0.42), car_trim_m, train_root, bevel=0.015)
    for sx in (-0.30, 0.30):
        add_cyl(f"LCDPipe_{sx}", (sx, 1.98, 2.36), 0.014, 0.24, (0.0, 0.0, 0.0), steel_m, train_root, verts=10)
    add_sign_plane("WangsimniScreenFront", (0.0, 1.905, 2.08), (0.88, 0.38), (90.0, 0.0, 0.0), wangsimni_mat, train_root)
    wrong_screen = add_sign_plane("WrongWayScreenFront", (0.0, 1.901, 2.08), (0.88, 0.38), (90.0, 0.0, 0.0), wrong_led_mat, train_root)
    add_sign_plane("RouteMapSign", (0.0, 0.075, 2.24), (1.35, 0.24), (90.0, 0.0, 180.0), routemap_mat, train_root)

    for f in (1, 374, 375, 377, 379, TOTAL_FRAMES):
        wrong_screen.hide_render = (f < 375) or (f in (377, 378))
        wrong_screen.keyframe_insert(data_path="hide_render", frame=f)

    # Animate doors (closed F1..42, open F43..245, close F246..308 with bump at F296)
    for f in range(1, TOTAL_FRAMES + 1):
        if f < 42:
            open_w = 0.0
        elif f <= 62:
            open_w = smoothstep(42.0, 62.0, float(f))
        elif f < 248:
            open_w = 1.0
        elif f <= 308:
            open_w = 1.0 - smoothstep(248.0, 308.0, float(f))
            if 294 <= f <= 302:
                open_w = max(open_w, 0.16 * math.sin((f - 294) * 0.55))
        else:
            open_w = 0.0
        shift = 0.76 * open_w
        train_door_l.location.x = -0.40 - shift
        train_door_r.location.x = 0.40 + shift
        psd_door_l.location.x = -0.40 - shift
        psd_door_r.location.x = 0.40 + shift
        for o in (train_door_l, train_door_r, psd_door_l, psd_door_r):
            o.keyframe_insert(data_path="location", frame=f)

        dep = smoothstep(316.0, 355.0, float(f))
        vib_z = 0.010 * math.sin(f * 1.1) * dep
        train_root.location = (0.0, 0.0, vib_z)
        train_root.keyframe_insert(data_path="location", frame=f)
        for j, hp in enumerate(handle_pivots):
            sw = (8.0 * dep + 3.0 * math.sin(f * 0.35 + j * 0.7)) * dep
            hp.rotation_euler = (0.0, math.radians(sw), 0.0)
            hp.keyframe_insert(data_path="rotation_euler", frame=f)

    # Tunnel pillar lights moving cleanly F316..450
    pass_post_m = make_mat("TunnelPost", (0.95, 0.65, 0.25), emission_color=(0.95, 0.65, 0.25), emission_strength=3.5)
    for k in range(4):
        tp = add_box(f"TunnelLight_{k}", (-6.0 + k * 4.5, 4.2, 1.5), (0.18, 0.18, 1.4), pass_post_m)
        for f in range(1, TOTAL_FRAMES + 1):
            if f % 4 != 0 and f not in (1, TOTAL_FRAMES):
                continue
            dep = max(0.0, (f - 316) / 30.0)
            tp.location.x = ((k * 4.5 - 6.0 - 20.0 * dep) % 18.0) - 9.0
            tp.keyframe_insert(data_path="location", frame=f)

    # 12 Real 3D Low-Poly Commuters
    rpm_specs = [
        (-0.34, 0.78, 175.0, 0.99, (0.14, 0.15, 0.18), 0.18, 0.75, True),
        (0.36, 0.80, -172.0, 1.01, (0.12, 0.15, 0.24), 0.16, 0.78, False),
        (-0.34, 0.62, 162.0, 1.05, (0.14, 0.16, 0.20), 0.16, 0.78, True),
        (0.34, 0.64, -162.0, 1.04, (0.18, 0.20, 0.26), 0.18, 0.76, False),
        (-0.82, 1.28, 165.0, 0.97, (0.24, 0.25, 0.27), 0.20, 0.76, False),
        (0.84, 1.24, -162.0, 1.02, (0.18, 0.19, 0.21), 0.15, 0.78, True),
        (-0.42, 1.56, 178.0, 0.98, (0.13, 0.16, 0.24), 0.16, 0.72, False),
        (0.44, 1.54, -176.0, 1.03, (0.26, 0.21, 0.18), 0.18, 0.75, True),
        (-1.18, 0.88, 145.0, 0.96, (0.22, 0.23, 0.25), 0.19, 0.74, False),
    ]
    npcs: List[Dict[str, object]] = []
    for idx, (nx, ny, nyaw, sc, tint, hv, sv, gl) in enumerate(rpm_specs):
        npc = import_commuter_rpm(
            scene, idx, loc=(nx, ny, 0.0), yaw_deg=nyaw, scale_mul=sc,
            suit_tint=tint, hair_val=hv, skin_val=sv, has_glasses=gl, glass_mat=glass_frame_m,
        )
        apply_pose_euler_dict(npc["arm"], 1, {
            "Spine": (2.0, 0.0, 0.0),
            "Head": (4.0, (idx % 3 - 1) * 6.0, 0.0),
            "LeftArm": (16.0, 0.0, 4.0),
            "RightArm": (16.0, 0.0, -4.0),
            "LeftForeArm": (0.0, 0.0, 12.0),
            "RightForeArm": (0.0, 0.0, -12.0),
        })
        npcs.append(npc)

    for m_idx, (mx, my, myaw, mtint) in enumerate((
        (-0.02, 1.88, 175.0, (0.62, 0.56, 0.48)),
        (1.16, 0.92, -148.0, (0.28, 0.30, 0.34)),
        (-0.86, 1.82, 168.0, (0.36, 0.32, 0.30)),
    )):
        fm = import_commuter_michelle(scene, m_idx, loc=(mx, my, 0.0), yaw_deg=myaw, tint=mtint)
        if fm is not None:
            npcs.append(fm)

    # Commuter push compression (F115..140), spring-back launch (F140..158), & Act 4 pack-in!
    for f in range(1, TOTAL_FRAMES + 1):
        if f % 4 != 0 and f not in (1, 138, 145, 315, 321, TOTAL_FRAMES):
            continue
        push_in = smoothstep(110.0, 138.0, float(f)) * (1.0 - smoothstep(138.0, 160.0, float(f)))
        spring_out = math.sin(clamp01((f - 138.0) / 18.0) * math.pi) if 138 <= f <= 160 else 0.0
        pack_in = smoothstep(290.0, 320.0, float(f))
        dep = smoothstep(316.0, 355.0, float(f))
        for idx, npc in enumerate(npcs):
            arm_n = npc["arm"]
            bx, by, _ = npc["base_loc"]
            byaw = npc["base_yaw"]
            bz = npc["base_z"]
            if idx in (2, 3):
                sx = lerp(bx * 2.15, bx, pack_in)
                sy = lerp(0.95, by, pack_in)
            elif idx in (0, 1):
                sx = bx * (1.0 + 0.55 * pack_in)
                sy = by + 0.22 * push_in - 0.14 * spring_out + 0.44 * pack_in
            else:
                sx = bx
                sy = by + (0.16 * push_in - 0.08 * spring_out) * (1.0 / (1.0 + idx * 0.12))
            sway_x = 0.012 * math.sin(f * 0.45 + idx) * dep
            sway_z = (0.010 * math.sin(f * 1.1) * dep) if f >= 316 else 0.0
            arm_n.location = (sx + sway_x, sy, bz + sway_z)
            arm_n.rotation_euler = (math.radians(-5.0 * push_in + 4.0 * spring_out), math.radians(2.0 * math.sin(f * 0.4 + idx) * dep), math.radians(byaw))
            arm_n.keyframe_insert(data_path="location", frame=f)
            arm_n.keyframe_insert(data_path="rotation_euler", frame=f)

    # Original PS2 Hero ("민수") starting facing camera (-Y / +X, yaw_deg=25) in Act 1a!
    hero = import_human_grounded(scene, location=(0.0, -1.35, 0.0), yaw_deg=25.0, ground_flush=True)
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
        if f <= 48:
            hy = -1.35
            hyaw = 25.0
            hz = base_z
        elif f <= 95:
            turn = smoothstep(48.0, 68.0, float(f))
            hy = lerp(-1.35, -1.20, turn)
            hyaw = lerp(25.0, 180.0, turn)
            hz = base_z
        elif f <= 138:
            u = smoothstep(96.0, 134.0, float(f))
            hy = lerp(-1.20, -0.10, u)
            hyaw = 180.0
            hz = base_z
        elif f <= 200:
            # Bounced backward off crowd back onto platform!
            u = smoothstep(139.0, 174.0, float(f))
            hy = lerp(-0.10, -1.42, u)
            hop = 0.14 * math.sin(u * math.pi)
            hyaw = 180.0
            hz = base_z + hop
        elif f <= 320:
            # Sprint back + spin 180° to squeeze in BACK-FIRST!
            run_u = smoothstep(202.0, 248.0, float(f))
            spin_u = smoothstep(235.0, 265.0, float(f))
            jam_u = smoothstep(255.0, 310.0, float(f))
            hy = lerp(-1.42, -0.35, run_u) + (0.35 + 0.70) * jam_u
            hyaw = lerp(180.0, 0.0, spin_u)
            hz = base_z
        else:
            hy = 1.05
            hyaw = 0.0
            dep = smoothstep(316.0, 355.0, float(f))
            hz = base_z + 0.010 * math.sin(f * 1.1) * dep

        dep = smoothstep(316.0, 355.0, float(f)) if f > 316 else 0.0
        hx = 0.012 * math.sin(f * 0.55) * dep
        arm.location = (hx, hy, hz)
        arm.rotation_euler = (0.0, 0.0, math.radians(hyaw))
        arm.keyframe_insert(data_path="location", frame=f)
        arm.keyframe_insert(data_path="rotation_euler", frame=f)

        pose, face = story_hero_pose_and_face(f)
        apply_pose_euler_dict(arm, f, pose)
        apply_all_face_weights(hero["shaped_meshes"], f, face)

    # 4-Act Dynamic Story Camera
    cam = create_camera(scene, "PS2StoryCam")
    for f in range(1, TOTAL_FRAMES + 1):
        if f <= 48:
            # Act 1a: Front-3/4 smug platform view with Wangsimni PSD behind Hero!
            u = (f - 1) / 47.0
            loc = lerp_vec((0.72, -2.55, 1.56), (0.62, -2.38, 1.56), u)
            tgt = lerp_vec((0.0, -1.25, 1.52), (0.0, -1.25, 1.54), u)
            lens = 34.0
        elif f <= 95:
            # Act 1b: Swing behind right shoulder to reveal packed crowd as doors slide open!
            u = smoothstep(49.0, 74.0, float(f))
            loc = lerp_vec((0.62, -2.38, 1.56), (0.50, -2.18, 1.56), u)
            tgt = lerp_vec((0.0, -1.25, 1.54), (0.0, 0.72, 1.42), u)
            lens = lerp(34.0, 28.0, u)
        elif f <= 200:
            # Act 2: Wide-side doorway shot tracking push lunge + backward bounce!
            u = (f - 96) / 104.0
            shk = 0.05 * math.sin(f * 3.1) * math.exp(-(f - 139) / 6.0) if f >= 139 else 0.0
            loc = lerp_vec((0.88, -2.10, 1.54), (1.08, -2.55, 1.50), u) + Vector((shk, 0.0, shk * 0.7))
            tgt = lerp_vec((0.0, -0.15, 1.32), (0.0, -1.10, 1.36), smoothstep(138.0, 175.0, float(f)))
            lens = 26.0
        elif f <= 320:
            # Act 3: Urgent doorway angle watching back-first squeeze & closing door slam!
            u = (f - 201) / 119.0
            shk = 0.05 * math.sin(f * 3.1) if 294 <= f <= 308 else 0.0
            loc = lerp_vec((0.58, -2.10, 1.54), (0.44, -1.55, 1.52), u) + Vector((shk, 0.0, shk * 0.6))
            tgt = lerp_vec((0.0, -0.60, 1.35), (0.0, 0.45, 1.38), u)
            lens = 28.0
        else:
            # Act 4: Slide-0 interior close-up with sharp shock zoom-in on twist scream!
            u = smoothstep(321.0, 386.0, float(f))
            twist_z = smoothstep(387.0, 412.0, float(f))
            rattle = 0.008 * math.sin(f * 1.15) * smoothstep(321.0, 350.0, float(f))
            loc = Vector((0.01 + rattle * 0.4, lerp(0.06, 0.14, u) + 0.06 * twist_z, 1.60 + rattle))
            tgt = Vector((0.0, 1.12, 1.72 - 0.03 * twist_z))
            lens = lerp(26.0, 30.0, u) + 6.5 * twist_z
        keyframe_camera(cam, f, loc, tgt, lens=lens)

    return scene, [
        ("F025_swagger", 25),
        ("F080_crowd_shock", 80),
        ("F155_bounce_back", 155),
        ("F265_back_squeeze", 265),
        ("F355_relief_squish", 355),
        ("F425_wrong_way_horror", 425),
    ]


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _blender_main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=14)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--render-all", action="store_true")
    args = p.parse_args(argv)

    os.makedirs(FRAMES_DIR, exist_ok=True)
    scene, previews = build_story_scene(samples=args.samples)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "ps2_kr_subway_story.blend"))

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
                print(f"[ps2-story] Rendered {fnum}/{TOTAL_FRAMES}", flush=True)


def _host_main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=14)
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
        stitch_6grid(prev_imgs, QA_PREVIEW)
        print(f"[ps2-story] Saved 6-frame Visual Gate sheet: {QA_PREVIEW}", flush=True)


if __name__ == "__main__":
    if IN_BLENDER:
        _blender_main()
    else:
        _host_main()
