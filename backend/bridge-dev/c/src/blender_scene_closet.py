"""문제 장면 템플릿 `closet_musty` — Blender 안에서 실행된다 (blender -b -P blender_scene_closet.py -- …).

장마철 방에서 옷장 문을 여는 POV. 문이 열리면 빽빽이 걸린 옷 사이에서 꿉꿉한 냄새가 옅은 연기처럼 새어 나오고
카메라가 살짝 물러난다. 96프레임(4초, 24fps), 9:16. assets/ 에 나무 바닥 텍스처와 HDRI 가 있으면 쓴다.

사용: blender -b -P blender_scene_closet.py -- <프레임 출력 폴더> <assets 폴더> [해상도 %] [시작 프레임] [끝 프레임]
"""
import math
import os
import random
import sys

import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, ASSETS = argv[0], argv[1]
RES = int(argv[2]) if len(argv) > 2 else 100
F_START = int(argv[3]) if len(argv) > 3 else 1
F_END = int(argv[4]) if len(argv) > 4 else 96
END = 96
W, D, H = 1.10, 0.58, 2.05          # 옷장 너비, 깊이, 높이
T = 0.02                             # 판 두께

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def link(o):
    scene.collection.objects.link(o)
    return o


def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m, next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def flat_mat(name, color, rough=0.5, metallic=0.0):
    m, b = new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m


def box(name, size, loc, mat, bevel=0.004):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.data.materials.append(mat)
    if bevel:
        b = o.modifiers.new("Bevel", "BEVEL")
        b.width, b.segments = bevel, 2
    return o


# ---------------- 방: 바닥, 벽 ----------------
bpy.ops.mesh.primitive_plane_add(size=6)
floor = bpy.context.active_object
wood = os.path.join(ASSETS, "polyhaven", "table_wood")
if os.path.exists(os.path.join(wood, "diff.jpg")):
    m, b = new_mat("Floor")
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (4, 4, 4)
    nt.links.new(tc.outputs["UV"], mp.inputs[0])
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(wood, "diff.jpg"))
    nt.links.new(mp.outputs[0], img.inputs["Vector"])
    nt.links.new(img.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    floor.data.materials.append(m)
else:
    floor.data.materials.append(flat_mat("Floor", (0.42, 0.30, 0.20), 0.5))
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, D / 2 + 0.01, 3), rotation=(math.radians(90), 0, 0))
bpy.context.active_object.data.materials.append(flat_mat("Wall", (0.80, 0.79, 0.74), 0.9))

# ---------------- 옷장: 몸통, 봉, 문 두 짝 ----------------
white = flat_mat("Closet", (0.90, 0.90, 0.88), 0.35)
inside = flat_mat("ClosetInside", (0.70, 0.68, 0.63), 0.6)
box("Back", (W, T, H), (0, D / 2 - T / 2, H / 2), inside, 0)
box("SideL", (T, D, H), (-W / 2 + T / 2, 0, H / 2), white)
box("SideR", (T, D, H), (W / 2 - T / 2, 0, H / 2), white)
box("Top", (W, D, T), (0, 0, H - T / 2), white)
box("Bottom", (W, D, 0.08), (0, 0, 0.04), white)
box("Shelf", (W - 2 * T, D - T, T), (0, 0, 0.34), inside, 0)
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.012, depth=W - 2 * T, location=(0, 0.02, H - 0.22), rotation=(0, math.radians(90), 0))
bpy.context.active_object.data.materials.append(flat_mat("Rail", (0.75, 0.76, 0.78), 0.25, 1.0))
handle = flat_mat("Handle", (0.70, 0.70, 0.72), 0.3, 1.0)
doors = []
for side in (-1, 1):                                    # 경첩은 바깥쪽 모서리, 문은 앞으로 열린다
    hinge = link(bpy.data.objects.new(f"Hinge{side}", None))
    hinge.location = (side * W / 2, -D / 2, 0)
    door = box(f"Door{side}", (W / 2 - 0.004, T, H - 0.10), (-side * (W / 4), -T / 2, H / 2 + 0.03), white, 0.003)
    door.parent = hinge
    knob = box(f"Knob{side}", (0.014, 0.03, 0.16), (-side * (W / 2 - 0.05), -T - 0.012, 1.0), handle, 0.004)
    knob.parent = hinge
    doors.append((side, hinge))
bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
for side, hinge in doors:
    for f, deg in ((1, 0), (3, 0), (22, 104 if side == 1 else 96), (30, 100 if side == 1 else 92), (END, 100 if side == 1 else 92)):
        hinge.rotation_euler = (0, 0, math.radians(side * deg))
        hinge.keyframe_insert("rotation_euler", frame=f)

# ---------------- 옷: 봉에 빽빽이 걸린 옷들 ----------------
random.seed(4)
colors = [(0.16, 0.18, 0.24), (0.55, 0.50, 0.42), (0.30, 0.32, 0.28), (0.62, 0.60, 0.58), (0.36, 0.24, 0.20), (0.20, 0.26, 0.34),
          (0.70, 0.66, 0.56), (0.24, 0.24, 0.26), (0.44, 0.36, 0.30), (0.52, 0.56, 0.58), (0.28, 0.20, 0.24)]
n = len(colors)
for i, col in enumerate(colors):
    x = -W / 2 + 0.08 + i * (W - 0.16) / (n - 1)
    length = random.uniform(0.75, 1.15)
    g = box(f"Garment{i}", (random.uniform(0.045, 0.07), 0.40, length), (x, 0.03, H - 0.30 - length / 2), flat_mat(f"Cloth{i}", col, 0.92), 0.02)
    g.rotation_euler = (0, random.uniform(-0.05, 0.05), random.uniform(-0.12, 0.12))
    sub = g.modifiers.new("Soft", "SUBSURF")
    sub.levels = sub.render_levels = 2
    for p in g.data.polygons:
        p.use_smooth = True
    bpy.ops.mesh.primitive_torus_add(major_radius=0.02, minor_radius=0.003, location=(x, 0.02, H - 0.24), rotation=(math.radians(90), 0, 0))
    bpy.context.active_object.data.materials.append(handle)

# ---------------- 꿉꿉한 냄새: 옷 사이에서 새어 나와 앞으로 흘러나오는 옅은 연기 ----------------
haze, hb = new_mat("Haze")
nt = haze.node_tree
uv = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(uv.outputs["UV"], sep.inputs[0])


def math_node(op, a, b=None):
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            node.inputs[i].default_value = v
        else:
            nt.links.new(v, node.inputs[i])
    return node.outputs[0]


def map_range(sock, a, b, lo, hi):
    node = nt.nodes.new("ShaderNodeMapRange")
    node.clamp = True
    for i, v in zip((1, 2, 3, 4), (a, b, lo, hi)):
        node.inputs[i].default_value = v
    nt.links.new(sock, node.inputs[0])
    return node.outputs[0]


edge = math_node("POWER", math_node("SUBTRACT", 1.0, math_node("ABSOLUTE", math_node("SUBTRACT", math_node("MULTIPLY", sep.outputs[0], 2.0), 1.0))), 1.4)
along = math_node("MULTIPLY", map_range(sep.outputs[1], 0.0, 0.12, 0.0, 1.0), map_range(sep.outputs[1], 0.35, 1.0, 1.0, 0.0))
flow = nt.nodes.new("ShaderNodeTexNoise")
flow.noise_dimensions = "4D"
flow.inputs["Scale"].default_value, flow.inputs["Detail"].default_value = 2.6, 5.0
stretch = nt.nodes.new("ShaderNodeMapping")
stretch.inputs["Scale"].default_value = (1.0, 4.0, 1.0)
nt.links.new(uv.outputs["UV"], stretch.inputs[0])
nt.links.new(stretch.outputs[0], flow.inputs["Vector"])
for f in (1, END):
    flow.inputs["W"].default_value = f * 0.03
    flow.inputs["W"].keyframe_insert("default_value", frame=f)
nt.links.new(math_node("MULTIPLY", math_node("MULTIPLY", edge, along), math_node("MULTIPLY", map_range(flow.outputs[0], 0.25, 0.65, 0.25, 1.0), 0.8)),
             hb.inputs["Alpha"])
hb.inputs["Base Color"].default_value = (0.20, 0.23, 0.12, 1)
hb.inputs["Emission Color"].default_value = (0.30, 0.34, 0.18, 1)
hb.inputs["Emission Strength"].default_value = 0.25
hb.inputs["Roughness"].default_value = 1.0
for attr, value in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
    try:
        setattr(haze, attr, value)
    except Exception as e:
        print("haze", attr, e)

SEG, LENGTH = 40, 1.1
ribbons = []
for i in range(9):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rows = [(bm.verts.new((-0.05, -k * LENGTH / SEG, 0)), bm.verts.new((0.05, -k * LENGTH / SEG, 0))) for k in range(SEG + 1)]
    for k in range(SEG):
        face = bm.faces.new((rows[k][0], rows[k][1], rows[k + 1][1], rows[k + 1][0]))
        for loop, (u, v) in zip(face.loops, ((0, k / SEG), (1, k / SEG), (1, (k + 1) / SEG), (0, (k + 1) / SEG))):
            loop[uvl].uv = (u, v)
    me = bpy.data.meshes.new(f"Haze{i}")
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new(f"Haze{i}", me))
    o.data.materials.append(haze)
    o.location = (random.uniform(-W / 2 + 0.12, W / 2 - 0.12), -0.05, random.uniform(0.75, 1.75))
    o.rotation_euler = (math.radians(random.uniform(60, 100)), 0, 0)             # 카메라를 향해 서 있는 띠
    ribbons.append({"obj": o, "width": random.uniform(0.07, 0.13), "phase": random.uniform(0, 6.28), "amp": random.uniform(0.03, 0.07),
                    "freq": random.uniform(5, 8), "speed": random.uniform(0.16, 0.26), "start": 18 + i * 2})


def drift(scn, *_):
    """문이 열린 뒤 연기 띠가 옷장 안에서 카메라 쪽으로 자라며 출렁인다."""
    f = scn.frame_current
    for r in ribbons:
        grow = max(0.0, min(1.0, (f - r["start"]) / 34))
        grow = grow * grow * (3 - 2 * grow)
        vs = r["obj"].data.vertices
        for k in range(SEG + 1):
            a, b = vs[2 * k], vs[2 * k + 1]
            t = k / SEG
            y = -t * LENGTH * grow
            x = r["amp"] * (0.2 + 1.5 * t) * math.sin(r["freq"] * t - r["speed"] * f + r["phase"])
            w = r["width"] * (0.6 + 1.3 * t)
            a.co, b.co = (x - w, y, 0), (x + w, y, 0)
        r["obj"].data.update()


bpy.app.handlers.frame_change_pre.append(drift)

# ---------------- 조명: 비 오는 날 창가 빛, 옷장 안은 어둡다 ----------------
world = bpy.data.worlds.new("Room")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = next(node for node in world.node_tree.nodes if node.type == "BACKGROUND")
hdri = os.path.join(ASSETS, "polyhaven", "room_hdri", "env.hdr")
if os.path.exists(hdri):
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri)
    world.node_tree.links.new(env.outputs["Color"], bg.inputs[0])
    bg.inputs[1].default_value = 0.35
else:
    bg.inputs[0].default_value = (0.75, 0.80, 0.88, 1)
    bg.inputs[1].default_value = 0.5
win_d = bpy.data.lights.new("Window", "AREA")
win_d.size, win_d.energy, win_d.color = 1.6, 260, (0.86, 0.92, 1.0)
win = link(bpy.data.objects.new("Window", win_d))
win.location = (-2.2, -1.6, 1.8)
win.rotation_euler = (math.radians(70), 0, math.radians(-55))

# ---------------- 카메라: 옷장 앞에 선 폰. 문이 열리고 냄새가 나오면 살짝 물러난다 ----------------
cd = bpy.data.cameras.new("Cam")
cd.lens = 26
cam = link(bpy.data.objects.new("Cam", cd))
aim = link(bpy.data.objects.new("CamTarget", None))
track = cam.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
random.seed(11)
for f in range(1, END + 1, 3):
    j = 0.006
    if f < 40:
        base, look = (0.04, -1.55 + 0.12 * f / 40, 1.42), (0, 0, 1.18)
    elif f < 52:
        k = (f - 40) / 12
        base, look = (0.04 + 0.03 * k, -1.43 - 0.26 * k, 1.42 + 0.03 * k), (0, 0, 1.18 + 0.05 * k)     # 움찔
        j = 0.016
    else:
        base, look = (0.07, -1.69, 1.45), (0, 0, 1.23)
    cam.location = tuple(b + random.uniform(-j, j) for b in base)
    aim.location = look
    cam.keyframe_insert("location", frame=f)
    aim.keyframe_insert("location", frame=f)
scene.camera = cam

# ---------------- 렌더 ----------------
scene.frame_start, scene.frame_end = F_START, F_END
scene.render.fps = 24
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1080, 1920, RES
scene.render.engine = "BLENDER_EEVEE"
for k, v in (("taa_render_samples", 48), ("use_raytracing", True)):
    try:
        setattr(scene.eevee, k, v)
    except Exception as e:
        print("eevee", k, e)
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.3
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 95
os.makedirs(OUT, exist_ok=True)
scene.render.filepath = os.path.join(OUT, "p_")
scene.render.use_overwrite = False
bpy.ops.render.render(animation=True)
print("CLOSET_SCENE_DONE")
