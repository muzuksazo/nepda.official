"""문제 장면 템플릿 `phone_distract` 의 블록아웃 — Blender 안에서 실행된다.

책상에 앉은 사람의 POV. 펼친 노트 위에 펜을 내려놓은 손이 옆의 스마트폰을 집어 얼굴 쪽으로 든다. 96프레임(4초, 24fps), 9:16.
사실적인 그림을 내려는 장면이 아니다. 구도·카메라·동작 타이밍을 정하는 블록아웃이고, 이것을 생성 모델(MiniMax H3 등)에
첫 프레임 또는 참조 영상(플레이블라스트)으로 넘겨 실사 영상을 받는다.

겉모습은 둘이다 (환경변수 C_DESK_STYLE):
  - blockout (기본)  회색 상자 + 상자로 만든 손. 플레이블라스트를 참조 영상으로 받는 모델(MiniMax)용.
  - real             나무 책상·실내 조명을 입히고 손은 뺀다. 이 첫 프레임에서 이어 만드는 모델(Google Veo)용이고, 손은 생성 모델이 그린다.
                     blender_scene_desk_real.py 가 이 값으로 같은 스크립트를 실행한다.

사용: blender -b -P blender_scene_desk.py -- <프레임 출력 폴더> <assets 폴더> [해상도 %] [시작 프레임] [끝 프레임]
Blender 창 안(Blender MCP)에서 그대로 실행하면 렌더하지 않고 새 장면 "C_desk_blockout" 만 만들어 보여 준다.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

END = 96
HEADLESS = "--" in sys.argv
REAL = os.environ.get("C_DESK_STYLE", "").strip().lower() == "real"
ASSETS = os.environ.get("C_ASSETS_DIR", "")
if HEADLESS:
    argv = sys.argv[sys.argv.index("--") + 1:]
    OUT, ASSETS = argv[0], argv[1]
    RES = int(argv[2]) if len(argv) > 2 else 100
    F_START = int(argv[3]) if len(argv) > 3 else 1
    F_END = int(argv[4]) if len(argv) > 4 else END
    globals()["ASSETS"] = argv[1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
else:
    old = bpy.data.scenes.get("C_desk_blockout")
    if old:
        for o in list(old.collection.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.scenes.remove(old)
    scene = bpy.data.scenes.new("C_desk_blockout")
    bpy.context.window.scene = scene


def mat(name, color, rough=0.6, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    if emit:
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = (*color, 1)
                break
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def obj(name, bm, material, parent=None):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    o = bpy.data.objects.new(name, mesh)
    o.data.materials.append(material)
    scene.collection.objects.link(o)
    if parent:
        o.parent = parent
    return o


def box(name, size, loc, material, rot=(0, 0, 0), parent=None, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=3, affect="EDGES")
    o = obj(name, bm, material, parent)
    o.location, o.rotation_euler = loc, rot
    for p in o.data.polygons:
        p.use_smooth = bool(bevel)
    return o


def cyl(name, radius, depth, loc, material, rot=(0, 0, 0), parent=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=radius, radius2=radius, depth=depth)
    o = obj(name, bm, material, parent)
    o.location, o.rotation_euler = loc, rot
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def empty(name, loc, parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.03
    e.location = loc
    scene.collection.objects.link(e)
    if parent:
        e.parent = parent
    return e


def key(o, frame, loc=None, rot=None):
    if loc is not None:
        o.location = loc
        o.keyframe_insert("location", frame=frame)
    if rot is not None:
        o.rotation_euler = rot
        o.keyframe_insert("rotation_euler", frame=frame)


def asset(*parts):
    p = os.path.join(ASSETS, *parts) if ASSETS else ""
    return p if p and os.path.exists(p) else None


def wood_mat(folder, scale):
    """Poly Haven 나무 텍스처(diff/rough/nor_gl.jpg). 책상 윗면은 물체 좌표로 입힌다."""
    m = bpy.data.materials.new("DeskWood")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc, mp = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Object"], mp.inputs[0])

    def img(file, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(os.path.join(folder, file))
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs[0], n.inputs["Vector"])
        return n
    nt.links.new(img("diff.jpg", False).outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(img("rough.jpg", True).outputs["Color"], bsdf.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("nor_gl.jpg", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    return m


wood_dir = asset("polyhaven", "table_wood") if REAL else None
WOOD = wood_mat(wood_dir, 1.6) if wood_dir else mat("Desk", (0.42, 0.27, 0.15) if REAL else (0.55, 0.38, 0.22), 0.5)
PAPER = mat("Paper", (0.93, 0.92, 0.88), 0.8)
INK = mat("Ink", (0.25, 0.3, 0.45), 0.7)
PEN = mat("Pen", (0.08, 0.1, 0.35), 0.3)
PHONE = mat("PhoneBody", (0.03, 0.03, 0.035), 0.25)
SCREEN = mat("PhoneScreen", (0.01, 0.01, 0.012), 0.06) if REAL else mat("PhoneScreen", (0.35, 0.55, 0.95), 0.2, emit=0.5)      # 실사용은 꺼진 화면
MUG = mat("Mug", (0.9, 0.88, 0.84), 0.15 if REAL else 0.4)
SKIN = mat("Skin", (0.86, 0.66, 0.54), 0.6)
SLEEVE = mat("Sleeve", (0.82, 0.8, 0.74), 0.9)
WALL = mat("Wall", (0.9, 0.89, 0.86), 0.9)
LAPTOP = mat("Laptop", (0.6, 0.62, 0.65), 0.4)

# ---------------- 책상과 소품 ----------------
box("Desk", (1.8, 1.1, 0.04), (0, 0.15, -0.02), WOOD)
box("Wall", (2.4, 0.02, 1.4), (0, 0.72, 0.6), WALL)
box("PageL", (0.15, 0.21, 0.006), (-0.105, 0.06, 0.003), PAPER)
box("PageR", (0.15, 0.21, 0.006), (0.05, 0.06, 0.003), PAPER)
for i in range(7):                                    # 왼쪽 장에 적다 만 줄
    w = 0.11 if i < 4 else 0.06
    box(f"Line{i}", (w, 0.004, 0.0006), (-0.105 - (0.11 - w) / 2, 0.14 - i * 0.022, 0.0066), INK)
box("LaptopBase", (0.32, 0.22, 0.012), (-0.22, 0.42, 0.006), LAPTOP, bevel=0.003)
box("LaptopLid", (0.32, 0.012, 0.21), (-0.22, 0.535, 0.11), LAPTOP, rot=(math.radians(-12), 0, 0), bevel=0.003)
cyl("Mug", 0.04, 0.09, (0.3, 0.4, 0.045), MUG)
pen = cyl("PenBody", 0.0045, 0.14, (0.07, 0.0, 0.012), PEN, rot=(math.radians(90), 0, math.radians(-35)))

phone = empty("PhoneRig", (0.27, 0.03, 0.006))
box("PhoneBody", (0.074, 0.152, 0.009), (0, 0, 0), PHONE, parent=phone, bevel=0.003)
box("PhoneScreen", (0.066, 0.142, 0.0006), (0, 0, 0.0049), SCREEN, parent=phone)

# ---------------- 손: 오른쪽 아래에서 들어온다 (실사용 장면에서는 화면 밖에 둔다. 손은 생성 모델이 그린다) ----------------
hand = empty("HandRig", (0.1, -0.03, 0.03))
hand_offset = Vector((0.0, -3.0, 0.0)) if REAL else Vector((0.0, 0.0, 0.0))
box("Palm", (0.085, 0.095, 0.028), (0, 0, 0), SKIN, parent=hand, bevel=0.01)
for i, x in enumerate((-0.03, -0.01, 0.01, 0.03)):
    box(f"Finger{i}", (0.017, 0.075, 0.017), (x, 0.08, -0.004), SKIN, parent=hand, rot=(math.radians(-12), 0, 0), bevel=0.006)
thumb = box("Thumb", (0.02, 0.06, 0.02), (-0.05, 0.035, 0.03), SKIN, parent=hand, rot=(0, 0, math.radians(35)), bevel=0.007)
box("Wrist", (0.065, 0.07, 0.03), (0.005, -0.075, 0.002), SKIN, parent=hand, bevel=0.01)
box("Sleeve", (0.1, 0.34, 0.07), (0.02, -0.27, 0.01), SLEEVE, parent=hand, rot=(0, 0, math.radians(-6)), bevel=0.02)

# 동작: 펜을 내려놓는다(1~20) → 폰으로 간다(20~44) → 집어 든다(44~70) → 엄지로 넘긴다(70~96)
key(hand, 1, Vector((0.085, -0.02, 0.035)) + hand_offset, (0, 0, math.radians(18)))
key(hand, 20, Vector((0.1, -0.05, 0.05)) + hand_offset, (0, 0, math.radians(10)))
key(hand, 44, Vector((0.275, -0.035, 0.03)) + hand_offset, (0, 0, math.radians(-4)))
key(hand, 70, Vector((0.17, -0.2, 0.2)) + hand_offset, (math.radians(48), 0, math.radians(-10)))
key(hand, END, Vector((0.165, -0.205, 0.205)) + hand_offset, (math.radians(50), 0, math.radians(-10)))
key(phone, 1, (0.27, 0.03, 0.006), (0, 0, math.radians(8)))
key(phone, 44, (0.27, 0.03, 0.006), (0, 0, math.radians(8)))
key(phone, 70, (0.17, -0.218, 0.247), (math.radians(48), 0, math.radians(-10)))          # 손바닥 위, 화면이 보는 사람 쪽
key(phone, END, (0.165, -0.223, 0.252), (math.radians(50), 0, math.radians(-10)))
if not REAL:                                          # 실사용 장면은 펜이 처음부터 노트 위에 놓여 있다
    key(pen, 1, (0.075, 0.02, 0.03), (math.radians(70), 0, math.radians(-35)))
key(pen, 14, (0.07, 0.0, 0.012), (math.radians(90), 0, math.radians(-35)))
for f, z in ((70, 35), (76, 20), (82, 35), (88, 20), (END, 35)):          # 엄지로 화면을 넘기는 움직임
    thumb.rotation_euler = (0, 0, math.radians(z))
    thumb.keyframe_insert("rotation_euler", frame=f)

# ---------------- 조명과 카메라 ----------------
sun = bpy.data.objects.new("Window", bpy.data.lights.new("Window", "SUN"))
sun.data.energy = 2.4 if REAL else 1.8
sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
scene.collection.objects.link(sun)
fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA"))
fill.data.energy, fill.data.size = 25, 1.2
fill.location = (-0.4, -0.5, 1.0)
scene.collection.objects.link(fill)
world = bpy.data.worlds.new("Room")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.85, 0.86, 0.9, 1)
bg.inputs[1].default_value = 0.35
hdri = asset("polyhaven", "room_hdri", "env.hdr") if REAL else None
if hdri:                                              # 실내 HDRI 로 반사와 부드러운 빛을 준다
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri)
    world.node_tree.links.new(env.outputs["Color"], bg.inputs[0])
    bg.inputs[1].default_value = 0.9
scene.world = world

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.data.lens = 24
if REAL:                                              # 폰으로 찍은 듯한 얕은 심도
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 0.7
    cam.data.dof.aperture_fstop = 2.8
scene.collection.objects.link(cam)
target = empty("CamTarget", (0.06, 0.08, 0.0))
track = cam.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
key(cam, 1, (0.02, -0.5, 0.52))                       # 앉은 사람 눈높이에서 책상을 내려다본다
key(cam, 44, (0.03, -0.5, 0.52))
key(cam, END, (0.07, -0.52, 0.5))                     # 폰을 들면 시선이 폰으로 조금 따라간다
key(target, 1, (0.06, 0.08, 0.0))
key(target, 44, (0.08, 0.08, 0.0))
key(target, END, (0.14, -0.02, 0.1))
scene.camera = cam

scene.frame_start, scene.frame_end = 1, END
scene.render.fps = 24
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.frame_set(1)

if HEADLESS:
    scene.render.resolution_percentage = RES
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 92
    scene.frame_start, scene.frame_end = F_START, F_END
    scene.render.filepath = os.path.join(OUT, "p_")
    bpy.ops.render.render(animation=True)
else:
    print("C_desk_blockout ready:", len(scene.collection.all_objects), "objects, frames 1 -", END)
