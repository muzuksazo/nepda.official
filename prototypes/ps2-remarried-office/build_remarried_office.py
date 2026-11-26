"""Step 2: 4-Act 15.00s (450f @ 30fps) Corporate-Palace Parody Scene:
"재혼황후 K-직장 버전 — 권고사직 수락 & 경쟁사 연봉 2배 이직 승인 요구"
Zero voxel humans, verified zero-clip rpm_player A-pose arms, Inworld + 3-cast audio.
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
    from mathutils import Euler, Vector
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
ROOT = "/Users/yun-yeowon/workspace/ad-studio/ps2-remarried-office"
TEX_DIR = os.path.join(ROOT, "textures")
FRAMES_DIR = os.path.join(ROOT, "frames")
QA_PREVIEW = os.path.join(ROOT, "qa_preview_6frames.png")

TOTAL_FRAMES = 450
FPS = 30
RENDER_W = 540
RENDER_H = 960


def skin_char(
    hum: Dict[str, object],
    *,
    suit_tint: Tuple[float, float, float],
    suit_blend: str = "MULTIPLY",
    suit_val: float = 0.85,
    hair_tint: Tuple[float, float, float] | None = None,
    hair_val: float = 0.22,
    skin_val: float = 0.78,
    scale: float = 1.0,
) -> bpy.types.Object:
    arm: bpy.types.Object = hum["arm"]
    if abs(scale - 1.0) > 1e-3:
        arm.scale = (scale, scale, scale)
        bpy.context.view_layer.update()
        foots = [o for o in bpy.data.objects if o.parent == arm and o.type == "MESH" and "Footwear" in o.name]
        if foots:
            min_z = min((fo.matrix_world @ Vector(c)).z for fo in foots for c in fo.bound_box)
            arm.location.z -= min_z
            bpy.context.view_layer.update()

    for o in [ob for ob in bpy.data.objects if ob.parent == arm and ob.type == "MESH"]:
        for slot in o.material_slots:
            if slot.material is not None:
                m = slot.material.copy()
                slot.material = m
                if "Top" in o.name or "Bottom" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=76, tint=suit_tint, blend_type=suit_blend, tint_fac=0.72, val_mul=suit_val, roughness=0.84)
                elif "Hair" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=64, tint=hair_tint, blend_type="MIX" if hair_tint else "MULTIPLY", tint_fac=0.75, val_mul=hair_val, roughness=0.86)
                elif "Head" in o.name or "Body" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=84, val_mul=skin_val, sat_mul=1.12, roughness=0.68)
                elif "Footwear" in o.name:
                    apply_ps2_pixel_shader(m, pixel_res=64, val_mul=0.5, roughness=0.82)
    return arm


def attach_crown(scene: bpy.types.Scene, arm: bpy.types.Object, gold_m: bpy.types.Material, ruby_m: bpy.types.Material) -> bpy.types.Object:
    """Attach comic PS2 Golden Crown cleanly to Head bone (tilts crooked in Act 4 meltdown!)."""
    cpiv = bpy.data.objects.new("BossCrownPiv", None)
    scene.collection.objects.link(cpiv)
    cpiv.parent = arm
    cpiv.parent_type = "BONE"
    cpiv.parent_bone = "Head"
    cpiv.location = (0.0, 0.115, 0.01)

    add_cyl("CrownBand", (0.0, 0.0, 0.0), 0.115, 0.045, (90.0, 0.0, 0.0), gold_m, cpiv, verts=16)
    for idx in range(5):
        ang = math.radians(idx * 72.0)
        px, pz = 0.095 * math.cos(ang), 0.095 * math.sin(ang)
        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.025, depth=0.075, location=(px, 0.045, pz))
        sp = bpy.context.active_object
        sp.rotation_euler = (math.radians(-90.0), 0.0, 0.0)
        sp.data.materials.append(gold_m)
        sp.parent = cpiv
    add_box("CrownRuby", (0.0, 0.01, -0.115), (0.032, 0.032, 0.022), ruby_m, cpiv, bevel=0.005)
    return cpiv


def boss_pose_face(f: int) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, float]]:
    if f <= 125:
        # Smug arrogant Team Leader sliding 권고사직서 across table
        shv = smoothstep(35.0, 62.0, float(f)) * (1.0 - smoothstep(82.0, 108.0, float(f)))
        pose = {
            "Spine": (4.0 * shv, 0.0, 0.0),
            "Head": (-5.0 + 3.0 * math.sin(f * 0.2), -6.0, 0.0),
            "LeftArm": (16.0, 0.0, 5.0),
            "RightArm": (lerp(16.0, 8.0, shv), 0.0, lerp(-5.0, -68.0, shv)),
            "LeftForeArm": (0.0, 0.0, 14.0),
            "RightForeArm": (0.0, 0.0, lerp(-14.0, -18.0, shv)),
        }
        face = {
            "mouthSmileLeft": 0.62, "mouthSmileRight": 0.45,
            "browDownLeft": 0.35, "browDownRight": 0.20,
            "jawOpen": 0.28 * abs(math.sin(f * 0.45)) if f <= 125 else 0.05,
        }
        return pose, face
    if f <= 355:
        # Stunned realization
        st = smoothstep(210.0, 240.0, float(f))
        pose = {
            "Spine": (-3.0 * st, 0.0, 0.0),
            "Head": (-6.0 * st, 0.0, 0.0),
            "LeftArm": (16.0, 0.0, 6.0),
            "RightArm": (16.0, 0.0, -6.0),
            "LeftForeArm": (0.0, 0.0, 16.0),
            "RightForeArm": (0.0, 0.0, -16.0),
        }
        face = {
            "eyeWideLeft": 0.85 * st, "eyeWideRight": 0.85 * st,
            "browInnerUp": 0.80 * st,
            "jawOpen": 0.48 * st,
        }
        return pose, face
    # Act 4: TOTAL MELTDOWN! Screaming at top of lungs, arms flailing!
    melt = smoothstep(356.0, 374.0, float(f))
    trem = math.sin((f - 356) * 0.85) * 4.0 * melt
    pose = {
        "Spine": (-12.0 * melt, trem * 0.5, 0.0),
        "Head": (-14.0 * melt, trem, 0.0),
        "LeftArm": (-14.0 * melt + 16.0 * (1.0 - melt), 0.0, 42.0 * melt + trem),
        "RightArm": (-14.0 * melt + 16.0 * (1.0 - melt), 0.0, -42.0 * melt - trem),
        "LeftForeArm": (0.0, 0.0, 46.0 * melt),
        "RightForeArm": (0.0, 0.0, -46.0 * melt),
    }
    face = {
        "eyeWideLeft": 1.0 * melt, "eyeWideRight": 1.0 * melt,
        "browInnerUp": 1.0 * melt, "browOuterUpLeft": 0.9 * melt, "browOuterUpRight": 0.9 * melt,
        "jawOpen": (0.88 + 0.10 * math.sin(f * 0.6)) * melt,
        "mouthStretchLeft": 0.85 * melt, "mouthStretchRight": 0.85 * melt,
        "mouthFrownLeft": 0.90 * melt, "mouthFrownRight": 0.90 * melt,
    }
    return pose, face


def ace_pose_face(f: int) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, float]]:
    if f <= 175:
        pose = {
            "Spine": (1.0, 0.0, 0.0),
            "Head": (-3.0, 0.0, 0.0),
            "LeftArm": (16.0, 0.0, 5.0),
            "RightArm": (16.0, 0.0, -5.0),
            "LeftForeArm": (0.0, 0.0, 14.0),
            "RightForeArm": (0.0, 0.0, -14.0),
        }
        face = {"browDownLeft": 0.25, "browDownRight": 0.25, "jawOpen": 0.14 if f >= 145 else 0.02}
        return pose, face
    if f <= 255:
        # Confidently drops mic / slides resignation approval & demands job transfer!
        pt = smoothstep(182.0, 210.0, float(f)) * (1.0 - smoothstep(235.0, 255.0, float(f)))
        pose = {
            "Spine": (4.0 * pt, 0.0, 0.0),
            "Head": (-5.0, 0.0, 0.0),
            "LeftArm": (16.0, 0.0, 5.0),
            "RightArm": (lerp(16.0, 6.0, pt), 0.0, lerp(-5.0, -68.0, pt)),
            "LeftForeArm": (0.0, 0.0, 14.0),
            "RightForeArm": (0.0, 0.0, lerp(-14.0, -12.0, pt)),
        }
        face = {
            "browOuterUpLeft": 0.35, "browOuterUpRight": 0.35,
            "mouthSmileLeft": 0.35, "mouthSmileRight": 0.35,
            "jawOpen": 0.26 * abs(math.sin(f * 0.4)),
        }
        return pose, face
    # Walks toward Rival CEO with cool victorious smile
    pose = {
        "Spine": (2.0, 0.0, 0.0),
        "Head": (-2.0, 0.0, 0.0),
        "LeftArm": (16.0, 0.0, 5.0),
        "RightArm": (16.0, 0.0, -5.0),
        "LeftForeArm": (0.0, 0.0, 14.0),
        "RightForeArm": (0.0, 0.0, -14.0),
    }
    face = {"mouthSmileLeft": 0.72, "mouthSmileRight": 0.72, "browOuterUpLeft": 0.30, "browOuterUpRight": 0.30}
    return pose, face


def build_scene(samples: int = 10) -> Tuple[bpy.types.Scene, List[Tuple[str, int]]]:
    clear_scene_safe()
    scene = bpy.context.scene

    setup_eevee(
        scene, width=RENDER_W, height=RENDER_H, fps=FPS,
        samples=samples, total_frames=TOTAL_FRAMES,
        exposure=0.05, glare_strength=0.38,
    )
    scene.render.use_motion_blur = False
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    w = bpy.data.worlds.new("OfficePalaceWorld")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.04, 0.045, 0.06, 1.0)
        bg.inputs["Strength"].default_value = 0.45

    marble_m = make_mat("PalaceMarble", (0.76, 0.75, 0.72), roughness=0.22, coat=0.45)
    carpet_m = make_mat("RoyalCrimsonCarpet", (0.48, 0.04, 0.06), roughness=0.88)
    gold_m = make_mat("PalaceGold", (0.94, 0.72, 0.16), metallic=0.92, roughness=0.20)
    ruby_m = make_mat("CrownRuby", (0.85, 0.05, 0.08), roughness=0.12, emission_color=(0.7, 0.05, 0.08), emission_strength=1.2)
    mahogany_m = make_mat("BoardroomMahogany", (0.22, 0.10, 0.06), roughness=0.32, coat=0.4)
    wall_m = make_mat("CorporateWoodWall", (0.16, 0.13, 0.11), roughness=0.62)
    pillar_m = make_mat("FlutedMarble", (0.82, 0.80, 0.76), roughness=0.38)
    glass_m = make_mat("DoorGlass", (0.55, 0.75, 0.90), roughness=0.08, transmission=0.72, alpha=0.55)
    throne_red = make_mat("ThroneVelvet", (0.52, 0.04, 0.07), roughness=0.78)

    screen_mat = make_tex_mat("BoardroomKPI", os.path.join(TEX_DIR, "boardroom_screen.png"), emission=1.15, roughness=0.3)
    doc_mat = make_tex_mat("ResignDoc", os.path.join(TEX_DIR, "resignation_doc.png"), emission=0.15, roughness=0.8)
    card_mat = make_tex_mat("ScoutCard", os.path.join(TEX_DIR, "scout_card.png"), emission=1.35, roughness=0.25)

    # Grand Boardroom Lighting + Dramatic Golden CEO Entrance Backlight
    for name, loc, rot, en, sz, col in (
        ("PalaceTopKey", (0.0, 0.2, 3.6), (12.0, 0.0, 0.0), 180.0, 4.5, (1.0, 0.96, 0.90)),
        ("BossKey", (-0.6, 0.2, 2.3), (62.0, 0.0, -18.0), 42.0, 1.8, (1.0, 0.95, 0.88)),
        ("AceKey", (0.5, 0.6, 2.3), (62.0, 0.0, 160.0), 48.0, 1.8, (0.94, 0.98, 1.0)),
    ):
        ld = bpy.data.lights.new(name, type="AREA")
        ld.energy = en
        ld.size = sz
        ld.color = col
        lo = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = tuple(math.radians(a) for a in rot)

    ld_gold = bpy.data.lights.new("GoldenBacklight", type="AREA")
    ld_gold.energy = 10.0
    ld_gold.size = 3.0
    ld_gold.color = (1.0, 0.84, 0.35)
    lo_gold = bpy.data.objects.new("GoldenBacklight", ld_gold)
    scene.collection.objects.link(lo_gold)
    lo_gold.location = (0.0, -4.6, 2.2)
    lo_gold.rotation_euler = (math.radians(-78.0), 0.0, 0.0)
    for f in (1, 245, 265, 340, TOTAL_FRAMES):
        ld_gold.energy = 360.0 if 255 <= f <= 355 else 15.0
        ld_gold.keyframe_insert(data_path="energy", frame=f)

    # Marble Floor + Crimson Red Carpet with Gold Borders
    add_box("MarbleFloor", (0.0, 0.0, -0.10), (12.0, 14.0, 0.20), marble_m)
    add_box("RedCarpet", (0.0, -0.4, 0.004), (1.75, 8.8, 0.008), carpet_m)
    for gx in (-0.90, 0.90):
        add_box(f"CarpetGoldTrim_{gx}", (gx, -0.4, 0.005), (0.06, 8.8, 0.010), gold_m)

    # Walls & 6 Palace Columns
    add_box("BackWall", (0.0, 3.4, 2.2), (10.0, 0.25, 4.4), wall_m)
    add_box("LeftWall", (-3.2, 0.0, 2.2), (0.25, 11.0, 4.4), wall_m)
    add_box("RightWall", (3.2, 0.0, 2.2), (0.25, 11.0, 4.4), wall_m)
    add_box("Ceiling", (0.0, 0.0, 4.2), (10.0, 11.0, 0.25), wall_m)
    for cy in (-2.2, 0.4, 2.8):
        for cx in (-2.65, 2.65):
            add_cyl(f"Col_{cx}_{cy}", (cx, cy, 2.0), 0.24, 4.0, (0.0, 0.0, 0.0), pillar_m, verts=16)
            add_box(f"ColCap_{cx}_{cy}", (cx, cy, 3.92), (0.62, 0.62, 0.22), gold_m)
            add_box(f"ColBase_{cx}_{cy}", (cx, cy, 0.12), (0.62, 0.62, 0.24), gold_m)

    # Giant KPI Presentation Screen behind Team Leader (facing -Y upright!)
    add_box("ScreenFrame", (0.0, 3.22, 2.15), (2.75, 0.10, 1.45), gold_m, bevel=0.02)
    add_sign_plane("BoardroomScreen", (0.0, 3.16, 2.15), (2.56, 1.28), (90.0, 0.0, 0.0), screen_mat)

    # Front Doorway Wall & Tall Glass-Gold Double Doors at y=-3.6
    add_box("FrontWallL", (-3.15, -3.6, 2.2), (4.4, 0.22, 4.4), wall_m)
    add_box("FrontWallR", (3.15, -3.6, 2.2), (4.4, 0.22, 4.4), wall_m)
    add_box("FrontDoorHdr", (0.0, -3.6, 3.55), (2.0, 0.24, 1.5), wall_m)

    door_piv_l = bpy.data.objects.new("DoorPivL", None)
    door_piv_r = bpy.data.objects.new("DoorPivR", None)
    for dp, px in ((door_piv_l, -0.95), (door_piv_r, 0.95)):
        scene.collection.objects.link(dp)
        dp.location = (px, -3.6, 0.0)
    add_box("DoorFrameL", (0.47, 0.0, 1.40), (0.94, 0.08, 2.80), gold_m, door_piv_l)
    add_box("DoorPaneL", (0.47, 0.0, 1.40), (0.76, 0.03, 2.55), glass_m, door_piv_l)
    add_box("DoorFrameR", (-0.47, 0.0, 1.40), (0.94, 0.08, 2.80), gold_m, door_piv_r)
    add_box("DoorPaneR", (-0.47, 0.0, 1.40), (0.76, 0.03, 2.55), glass_m, door_piv_r)

    for f in (1, 245, 260, 268, TOTAL_FRAMES):
        op = smoothstep(245.0, 262.0, float(f))
        door_piv_l.rotation_euler = (0.0, 0.0, math.radians(-85.0 * op))
        door_piv_r.rotation_euler = (0.0, 0.0, math.radians(85.0 * op))
        door_piv_l.keyframe_insert(data_path="rotation_euler", frame=f)
        door_piv_r.keyframe_insert(data_path="rotation_euler", frame=f)

    # Mahogany Conference Table + Golden Throne Chair behind Boss + Sliding Paper Prop
    add_box("MahoganyTableTop", (0.0, 0.60, 0.74), (2.35, 1.05, 0.07), mahogany_m, bevel=0.015)
    for lx in (-0.95, 0.95):
        add_box(f"TableLeg_{lx}", (lx, 0.60, 0.36), (0.14, 0.72, 0.72), mahogany_m)
    add_box("ThroneBack", (0.0, 2.02, 1.32), (0.72, 0.14, 1.45), throne_red, bevel=0.03)
    add_box("ThroneTrim", (0.0, 2.03, 1.36), (0.78, 0.10, 1.52), gold_m, bevel=0.02)

    paper = add_sign_plane("ResignationPaper", (0.0, 0.92, 0.782), (0.34, 0.42), (0.0, 0.0, 0.0), doc_mat)
    for f in (1, 42, 68, 195, 225, TOTAL_FRAMES):
        py = 0.92 if f <= 42 else (0.32 if f <= 195 else 0.85)
        paper.location = (0.0, py, 0.782)
        paper.keyframe_insert(data_path="location", frame=f)

    # Character 1: 꼰대 팀장 (Emperor, crowned, charcoal-purple suit)
    boss_h = import_human_grounded(scene, location=(0.0, 1.55, 0.0), yaw_deg=0.0)
    boss_arm = skin_char(boss_h, suit_tint=(0.18, 0.12, 0.28), suit_val=0.85, hair_val=0.18)
    crown = attach_crown(scene, boss_arm, gold_m, ruby_m)

    # Character 2: 아부꾼 대리 (Lackey, burgundy-pink suit beside boss)
    lackey_h = import_human_grounded(scene, location=(0.56, 1.42, 0.0), yaw_deg=-18.0)
    lackey_arm = skin_char(lackey_h, suit_tint=(0.65, 0.22, 0.36), suit_blend="MIX", suit_val=0.95, hair_val=0.22, scale=0.97)
    apply_pose_euler_dict(lackey_arm, 1, {
        "Spine": (2.0, 0.0, 0.0), "Head": (-2.0, 6.0, 0.0),
        "LeftArm": (16.0, 0.0, 5.0), "RightArm": (16.0, 0.0, -5.0),
        "LeftForeArm": (0.0, 0.0, 14.0), "RightForeArm": (0.0, 0.0, -14.0),
    })

    # Character 3: 에이스 과장 ("Empress", emerald-teal suit + platinum blond hair)
    ace_h = import_human_grounded(scene, location=(0.0, -0.45, 0.0), yaw_deg=180.0)
    ace_arm = skin_char(
        ace_h, suit_tint=(0.08, 0.44, 0.36), suit_blend="MIX", suit_val=1.25,
        hair_tint=(0.88, 0.85, 0.76), hair_val=1.85, scale=0.95,
    )
    ace_base_z = ace_arm.location.z

    # Character 4: 경쟁사 대표 ("Prince", ivory-gold luxury suit + golden blond hair + VIP Scout Card!)
    ceo_h = import_human_grounded(scene, location=(-0.18, -4.35, 0.0), yaw_deg=180.0)
    ceo_arm = skin_char(
        ceo_h, suit_tint=(0.94, 0.92, 0.84), suit_blend="MIX", suit_val=1.65,
        hair_tint=(0.92, 0.74, 0.28), hair_val=1.75, scale=1.03,
    )
    ceo_base_z = ceo_arm.location.z
    apply_pose_euler_dict(ceo_arm, 1, {
        "Spine": (2.0, 0.0, 0.0), "Head": (-3.0, 0.0, 0.0),
        "LeftArm": (16.0, 0.0, 5.0), "RightArm": (8.0, 0.0, -64.0),
        "LeftForeArm": (0.0, 0.0, 14.0), "RightForeArm": (0.0, 0.0, -14.0),
    })
    apply_all_face_weights(ceo_h["shaped_meshes"], 1, {"mouthSmileLeft": 0.82, "mouthSmileRight": 0.82, "browOuterUpLeft": 0.3, "browOuterUpRight": 0.3})

    # Attach glowing Gold VIP Scout Offer Card facing camera clearly in Rival CEO's RightHand!
    card = add_sign_plane("VIPScoutCard", (0.0, 0.0, 0.0), (0.38, 0.19), (0.0, 0.0, 0.0), card_mat)
    card.parent = ceo_arm
    card.parent_type = "BONE"
    card.parent_bone = "RightHand"
    card.location = (0.0, 0.12, 0.03)
    card.rotation_euler = (math.radians(-95.0), math.radians(170.0), math.radians(105.0))

    # Animate all 4 characters
    for f in range(1, TOTAL_FRAMES + 1):
        bp, bf = boss_pose_face(f)
        apply_pose_euler_dict(boss_arm, f, bp)
        apply_all_face_weights(boss_h["shaped_meshes"], f, bf)

        # Crown tilts comically 20° on Boss meltdown!
        tilt = smoothstep(356.0, 380.0, float(f))
        crown.rotation_euler = (math.radians(-6.0 * tilt), 0.0, math.radians(22.0 * tilt))
        crown.keyframe_insert(data_path="rotation_euler", frame=f)

        # Lackey smug -> jaw-drop shock
        if f in (1, 120, 210, 240, 355, 375, TOTAL_FRAMES):
            lsh = smoothstep(355.0, 375.0, float(f))
            apply_all_face_weights(lackey_h["shaped_meshes"], f, {
                "mouthSmileLeft": 0.82 * (1.0 - lsh), "mouthSmileRight": 0.82 * (1.0 - lsh),
                "eyeWideLeft": 1.0 * lsh, "eyeWideRight": 1.0 * lsh,
                "jawOpen": 0.90 * lsh, "browInnerUp": 1.0 * lsh,
            })

        # Ace employee: turns toward Rival CEO & steps beside him (F255..340)
        ap, af = ace_pose_face(f)
        apply_pose_euler_dict(ace_arm, f, ap)
        apply_all_face_weights(ace_h["shaped_meshes"], f, af)
        turn_ceo = smoothstep(258.0, 295.0, float(f))
        walk_ceo = smoothstep(290.0, 342.0, float(f))
        ace_arm.location = (lerp(0.0, 0.34, walk_ceo), lerp(-0.45, -1.52, walk_ceo), ace_base_z)
        ace_arm.rotation_euler = (0.0, 0.0, math.radians(lerp(180.0, 15.0, turn_ceo)))
        ace_arm.keyframe_insert(data_path="location", frame=f)
        ace_arm.keyframe_insert(data_path="rotation_euler", frame=f)

        # Rival CEO: strides heroically down crimson carpet (F250..325)
        ent = smoothstep(250.0, 322.0, float(f))
        ceo_arm.location = (-0.22, lerp(-4.35, -1.58, ent), ceo_base_z)
        ceo_arm.keyframe_insert(data_path="location", frame=f)

    # 4-Act Dynamic Camera
    cam = create_camera(scene, "ParodyCam")
    for f in range(1, TOTAL_FRAMES + 1):
        if f <= 122:
            # Act 1: Boss & Lackey behind mahogany table + "에이스 과장 98%" screen behind them!
            u = (f - 1) / 121.0
            loc = lerp_vec((0.28, -0.32, 1.56), (0.18, -0.18, 1.56), u)
            tgt = Vector((0.22, 1.58, 1.58))
            lens = lerp(33.0, 36.0, u)
        elif f <= 245:
            # Act 2: Ace Employee composed close-up -> push counter-offer
            u = (f - 123) / 122.0
            loc = lerp_vec((-0.34, 1.02, 1.52), (-0.24, 0.90, 1.50), u)
            tgt = Vector((0.0, -0.45, 1.48))
            lens = lerp(35.0, 40.0, u)
        elif f <= 355:
            # Act 3: Doors burst open! CEO strides down red carpet + Ace joins him!
            u = (f - 246) / 109.0
            loc = lerp_vec((0.55, -0.10, 1.38), (0.48, -0.25, 1.42), u)
            tgt = lerp_vec((-0.10, -2.85, 1.35), (0.06, -1.55, 1.42), smoothstep(246.0, 330.0, float(f)))
            lens = lerp(26.0, 31.0, u)
        else:
            # Act 4: Crash zoom onto Boss & Lackey total meltdown + crooked crown!
            u = smoothstep(356.0, 415.0, float(f))
            shk = 0.045 * math.sin(f * 3.1) * math.exp(-(f - 356) / 12.0)
            loc = lerp_vec((0.22, 0.02, 1.56), (0.20, 0.35, 1.58), u) + Vector((shk, 0.0, shk * 0.7))
            tgt = Vector((0.22, 1.58, 1.62))
            lens = lerp(30.0, 45.0, u)
        keyframe_camera(cam, f, loc, tgt, lens=lens)

    return scene, [
        ("F045_boss_fire", 45),
        ("F155_ace_choice", 155),
        ("F215_ace_counter", 215),
        ("F295_ceo_entrance", 295),
        ("F340_ace_joins_ceo", 340),
        ("F415_boss_wasted", 415),
    ]


def _blender_main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=10)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--render-all", action="store_true")
    args = p.parse_args(argv)

    os.makedirs(FRAMES_DIR, exist_ok=True)
    scene, previews = build_scene(samples=args.samples)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "ps2_remarried_office.blend"))

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
                print(f"[office] Rendered {fnum}/{TOTAL_FRAMES}", flush=True)


def _host_main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=10)
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
        print(f"[office] Saved 6-frame Visual Gate sheet: {QA_PREVIEW}", flush=True)


if __name__ == "__main__":
    if IN_BLENDER:
        _blender_main()
    else:
        _host_main()
