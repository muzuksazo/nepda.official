"""문제 장면 템플릿 `drain_smell` — Blender 안에서 실행된다 (blender -b -P blender_scene_drain.py -- …).

욕실 불을 켜고 들어선 POV. 바닥 배수구에서 냄새가 올라오고(만화식 물결 연기) 카메라가 움찔 물러난다.
방향제를 뿌리면 잠깐 잦아들지만 곧 더 크게 다시 올라온다. 240프레임(10초, 24fps), 9:16. 앞 3.5초만 써도 된다. 에셋 없이 기본 도형과 절차적 타일만 쓴다.

사용: blender -b -P blender_scene_drain.py -- <프레임 출력 폴더> <assets 폴더> [해상도 %] [시작 프레임] [끝 프레임]
"""
import math
import os
import random
import sys

import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
RES = int(argv[2]) if len(argv) > 2 else 100
F_START = int(argv[3]) if len(argv) > 3 else 1
F_END = int(argv[4]) if len(argv) > 4 else 240
END = 240

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


def tile_mat(name, tile, grout, scale, rough):
    """줄눈이 있는 타일. 벽돌 텍스처를 어긋남 없이 써서 격자로 만든다."""
    m, b = new_mat(name)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset, br.squash = 0.0, 1.0
    br.inputs["Color1"].default_value = (*tile, 1)
    br.inputs["Color2"].default_value = (*[c * 0.96 for c in tile], 1)
    br.inputs["Mortar"].default_value = (*grout, 1)
    br.inputs["Scale"].default_value = scale
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Brick Width"].default_value = 0.5
    br.inputs["Row Height"].default_value = 0.5
    nt.links.new(tc.outputs["UV"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    return m


# ---------------- 욕실: 바닥 타일, 벽 타일, 배수구 ----------------
bpy.ops.mesh.primitive_plane_add(size=3)
bpy.context.active_object.data.materials.append(tile_mat("FloorTile", (0.40, 0.43, 0.45), (0.16, 0.17, 0.17), 12, 0.35))
bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0.55, 1.5), rotation=(math.radians(90), 0, 0))
bpy.context.active_object.data.materials.append(tile_mat("WallTile", (0.90, 0.91, 0.90), (0.62, 0.63, 0.62), 8, 0.2))

chrome = flat_mat("Chrome", (0.75, 0.76, 0.78), 0.22, 1.0)
dark = flat_mat("Hole", (0.01, 0.01, 0.01), 0.9)
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.062, depth=0.006, location=(0, 0, 0.003))
bpy.context.active_object.data.materials.append(chrome)
for ring, count in ((0.0, 1), (0.020, 6), (0.040, 12)):
    for i in range(count):
        a = i * 2 * math.pi / count
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.0055, depth=0.002, location=(ring * math.cos(a), ring * math.sin(a), 0.0066))
        bpy.context.active_object.data.materials.append(dark)
# 배수구 둘레의 물때
bpy.ops.mesh.primitive_circle_add(vertices=48, radius=0.085, fill_type="NGON", location=(0.004, -0.003, 0.0006))
bpy.context.active_object.data.materials.append(flat_mat("Stain", (0.36, 0.34, 0.26), 0.6))

# ---------------- 냄새: 배수구에서 올라오는 물결 연기 (B급 만화식) ----------------
stink, sb = new_mat("Stink")
nt = stink.node_tree
tcn = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tcn.outputs["Object"], sep.inputs[0])
fade = nt.nodes.new("ShaderNodeMapRange")           # 아래는 진하고 위로 갈수록 사라진다
fade.inputs[1].default_value, fade.inputs[2].default_value = 0.0, 0.62
fade.inputs[3].default_value, fade.inputs[4].default_value = 1.0, 0.0
nt.links.new(sep.outputs[2], fade.inputs[0])
nt.links.new(fade.outputs[0], sb.inputs["Alpha"])
sb.inputs["Base Color"].default_value = (0.16, 0.24, 0.01, 1)
sb.inputs["Emission Color"].default_value = (0.22, 0.34, 0.01, 1)
sb.inputs["Emission Strength"].default_value = 0.6
for attr, value in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
    try:
        setattr(stink, attr, value)
    except Exception as e:
        print("stink", attr, e)

SEG, HEIGHT = 40, 0.62
random.seed(5)
ribbons = []
for i in range(5):
    bm = bmesh.new()
    width = random.uniform(0.012, 0.020)
    rows = [(bm.verts.new((-width, 0, k * HEIGHT / SEG)), bm.verts.new((width, 0, k * HEIGHT / SEG))) for k in range(SEG + 1)]
    for k in range(SEG):
        bm.faces.new((rows[k][0], rows[k][1], rows[k + 1][1], rows[k + 1][0]))
    me = bpy.data.meshes.new(f"Stink{i}")
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new(f"Stink{i}", me))
    o.data.materials.append(stink)
    o.location = ((i - 2) * 0.030 + random.uniform(-0.006, 0.006), random.uniform(-0.02, 0.02), 0.008)
    ribbons.append({"obj": o, "width": width, "phase": random.uniform(0, 6.28), "amp": random.uniform(0.018, 0.030),
                    "freq": random.uniform(17, 24), "speed": random.uniform(0.30, 0.42), "start": 5 + i * 3})


def wave(scn, *_):
    """프레임마다 띠를 물결 모양으로 다시 만든다. 불이 켜진 뒤 아래에서부터 자라난다."""
    f = scn.frame_current
    for r in ribbons:
        grow = max(0.0, min(1.0, (f - r["start"]) / 22))
        if f > 112:                                   # 방향제를 뿌리면 잠깐 잦아들었다가, 더 크게 다시 올라온다
            grow = 1.0 - 0.7 * min(1.0, (f - 112) / 30)
        if f > 178:
            grow = 0.3 + 0.95 * min(1.0, (f - 178) / 30)
        vs = r["obj"].data.vertices
        for k in range(SEG + 1):
            a, b = vs[2 * k], vs[2 * k + 1]
            z = k * HEIGHT / SEG * grow
            x = r["amp"] * (0.25 + z / HEIGHT) * math.sin(r["freq"] * z - r["speed"] * f + r["phase"])
            w = r["width"] * (0.6 + 0.8 * z / HEIGHT)
            a.co, b.co = (x - w, 0, z), (x + w, 0, z)
        r["obj"].data.update()


bpy.app.handlers.frame_change_pre.append(wave)

# ---------------- 방향제 스프레이: 들어와서 뿌리고 나간다 (3.5초~7초) ----------------
bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
can = link(bpy.data.objects.new("Spray", None))
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.030, depth=0.17, location=(0, 0, 0))
body = bpy.context.active_object
body.data.materials.append(flat_mat("CanBody", (0.95, 0.42, 0.60), 0.3, 0.3))
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.031, depth=0.05, location=(0, 0, -0.02))
band = bpy.context.active_object
band.data.materials.append(flat_mat("CanBand", (0.97, 0.95, 0.90), 0.5))
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.016, depth=0.035, location=(0, 0, 0.10))
cap = bpy.context.active_object
cap.data.materials.append(flat_mat("CanCap", (0.96, 0.96, 0.96), 0.3))
for part in (body, band, cap):
    for p in part.data.polygons:
        p.use_smooth = True
    part.parent = can
can.rotation_euler = (0, math.radians(-55), 0)                      # 꼭지가 배수구 쪽(왼쪽 아래)을 향한다
for f, loc in ((1, (0.75, -0.10, 0.50)), (92, (0.75, -0.10, 0.50)), (106, (0.20, -0.08, 0.30)), (152, (0.20, -0.08, 0.31)), (168, (0.80, -0.10, 0.55))):
    can.location = loc
    can.keyframe_insert("location", frame=f)
for f in range(108, 150, 6):                                         # 누를 때마다 살짝 흔들린다
    can.rotation_euler = (0, math.radians(-55 + (4 if (f // 6) % 2 else 0)), 0)
    can.keyframe_insert("rotation_euler", frame=f)

mist, mb = new_mat("Mist")
mb.inputs["Base Color"].default_value = (1.0, 0.62, 0.78, 1)
mb.inputs["Emission Color"].default_value = (1.0, 0.62, 0.78, 1)
mb.inputs["Emission Strength"].default_value = 0.5
mb.inputs["Roughness"].default_value = 1.0
for attr, value in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
    try:
        setattr(mist, attr, value)
    except Exception as e:
        print("mist", attr, e)
for f, a in ((1, 0.0), (107, 0.0), (110, 0.5), (160, 0.42), (196, 0.0)):
    mb.inputs["Alpha"].default_value = a
    mb.inputs["Alpha"].keyframe_insert("default_value", frame=f)
random.seed(8)
nozzle = (0.12, -0.08, 0.24)
for i in range(9):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0, location=nozzle)
    puff = bpy.context.active_object
    for p in puff.data.polygons:
        p.use_smooth = True
    puff.data.materials.append(mist)
    born = 108 + i * 5
    end = (random.uniform(-0.09, 0.05), random.uniform(-0.05, 0.05), random.uniform(0.08, 0.26))
    for f, loc, s in ((1, nozzle, 0.0), (born, nozzle, 0.0), (born + 10, tuple(n + (e - n) * 0.6 for n, e in zip(nozzle, end)), 0.045),
                      (born + 40, end, 0.085), (200, (end[0], end[1], end[2] + 0.10), 0.10)):
        puff.location, puff.scale = loc, (s, s, s)
        puff.keyframe_insert("location", frame=f)
        puff.keyframe_insert("scale", frame=f)

# ---------------- 조명: 어두웠다가 불이 켜진다 ----------------
world = bpy.data.worlds.new("Bath")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.85, 0.88, 0.92, 1)
lamp_d = bpy.data.lights.new("Ceiling", "AREA")
lamp_d.size = 0.9
lamp = link(bpy.data.objects.new("Ceiling", lamp_d))
lamp.location = (0.1, -0.3, 1.6)
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
for f, energy, ambient in ((1, 1, 0.02), (2, 1, 0.02), (3, 50, 0.22), (4, 12, 0.08), (6, 60, 0.28), (END, 60, 0.28)):   # 형광등처럼 한 번 깜빡
    lamp_d.energy = energy
    bg.inputs[1].default_value = ambient
    lamp_d.keyframe_insert("energy", frame=f)
    bg.inputs[1].keyframe_insert("default_value", frame=f)

# ---------------- 카메라: 문 열고 들어선 폰. 냄새가 올라오면 움찔 물러난다 ----------------
cd = bpy.data.cameras.new("Cam")
cd.lens = 30
cam = link(bpy.data.objects.new("Cam", cd))
aim = link(bpy.data.objects.new("CamTarget", None))
track = cam.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
random.seed(11)
for f in range(1, END + 1, 3):
    j = 0.006
    if f < 30:
        base, look = (0.03, -0.62 + 0.10 * f / 30, 0.62), (0, 0.0, 0.10)          # 다가간다
    elif f < 40:
        k = (f - 30) / 10
        base, look = (0.03 + 0.03 * k, -0.52 - 0.22 * k, 0.62 + 0.10 * k), (0, 0.0, 0.10 + 0.14 * k)   # 움찔
        j = 0.018
    elif f < 186:
        base, look = (0.06, -0.74, 0.72), (0, 0.0, 0.24)
    elif f < 198:                                                     # 다시 올라오자 한 번 더 물러난다
        k = (f - 186) / 12
        base, look = (0.06 + 0.02 * k, -0.74 - 0.14 * k, 0.72 + 0.06 * k), (0, 0.0, 0.24 + 0.10 * k)
        j = 0.016
    else:
        base, look = (0.08, -0.88, 0.78), (0, 0.0, 0.34)
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
for k, v in (("taa_render_samples", 32), ("use_raytracing", True)):
    try:
        setattr(scene.eevee, k, v)
    except Exception as e:
        print("eevee", k, e)
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 95
os.makedirs(OUT, exist_ok=True)
scene.render.filepath = os.path.join(OUT, "p_")
scene.render.use_overwrite = False
bpy.ops.render.render(animation=True)
print("DRAIN_SCENE_DONE")
