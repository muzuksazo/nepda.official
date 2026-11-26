"""문제 장면 템플릿 `evaporate_diffuser` — Blender 안에서 실행된다 (blender -b -P blender_scene_evaporate.py -- …).

테이블 위 액체 리드 디퓨저를 며칠 동안 찍은 타임랩스. 처음 채운 높이에 붙인 테이프는 그대로인데
액체만 바닥까지 줄어든다. 해가 여러 번 뜨고 지며 그림자가 돈다. 96프레임(4초, 24fps), 9:16.
assets/ 에 에셋이 있으면 쓰고 없으면 기본 도형으로 만든다.

사용: blender -b -P blender_scene_evaporate.py -- <프레임 출력 폴더> <assets 폴더> [해상도 %] [시작 프레임] [끝 프레임]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, ASSETS = argv[0], argv[1]
RES = int(argv[2]) if len(argv) > 2 else 100
F_START = int(argv[3]) if len(argv) > 3 else 1
F_END = int(argv[4]) if len(argv) > 4 else 96
END = 96
DAYS = 3                        # 타임랩스 동안 해가 뜨고 지는 횟수
BR, BH = 0.034, 0.105           # 병 반지름, 높이
FULL, EMPTY = 0.070, 0.007      # 액체 높이: 처음, 끝

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def asset(*parts):
    p = os.path.join(ASSETS, *parts)
    return p if os.path.exists(p) else None


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


def flat_mat(name, color, rough=0.5, **extra):
    m, b = new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    for k, v in extra.items():
        try:
            b.inputs[k].default_value = v
        except Exception as e:
            print("mat input", k, e)
    return m


def texture_mat(name, folder, scale):
    m, b = new_mat(name)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["UV"], mp.inputs[0])

    def img(file, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(os.path.join(folder, file))
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs[0], n.inputs["Vector"])
        return n
    nt.links.new(img("diff.jpg", False).outputs["Color"], b.inputs["Base Color"])
    nt.links.new(img("rough.jpg", True).outputs["Color"], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("nor_gl.jpg", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    return m


def revolve(name, prof, n=64, caps=True):
    bm = bmesh.new()
    rings = [[bm.verts.new((r * math.cos(i * 2 * math.pi / n), r * math.sin(i * 2 * math.pi / n), z)) for i in range(n)] for r, z in prof]
    for k in range(len(prof) - 1):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i])).smooth = True
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def append_objects(blend_path):
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    out = []
    for o in dst.objects:
        if o is not None and o.type == "MESH":
            out.append(link(o))
        elif o is not None:
            bpy.data.objects.remove(o, do_unlink=True)
    return out


# ---------------- 방: 테이블, 벽, 소품 ----------------
bpy.ops.mesh.primitive_plane_add(size=4)
table = bpy.context.active_object
wood_dir = asset("polyhaven", "table_wood")
table.data.materials.append(texture_mat("TableWood", wood_dir, 3.33) if wood_dir else flat_mat("TableWood", (0.35, 0.20, 0.10), 0.45))
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0.9, 0), rotation=(math.radians(90), 0, 0))
bpy.context.active_object.data.materials.append(flat_mat("Wall", (0.70, 0.67, 0.60), 0.9))
for name, loc, scale in (("prop_plant", (0.24, 0.36, 0.0), 1.0), ("prop_vase", (-0.27, 0.48, 0.0), 0.8)):
    blend = asset("polyhaven", name, "model.blend")
    if blend:
        for o in append_objects(blend):
            o.location, o.scale = loc, (scale, scale, scale)

world = bpy.data.worlds.new("Room")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
hdri = asset("polyhaven", "room_hdri", "env.hdr")
if hdri:
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri)
    world.node_tree.links.new(env.outputs["Color"], bg.inputs[0])
else:
    bg.inputs[0].default_value = (0.25, 0.25, 0.25, 1)

# ---------------- 리드 디퓨저: 투명한 병 + 줄어드는 액체 + 처음 높이에 붙인 테이프 ----------------
glass = flat_mat("Glass", (0.80, 0.86, 0.88), 0.03, **{"Alpha": 0.07, "Coat Weight": 0.15, "Specular IOR Level": 0.35})
for attr, value in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
    try:
        setattr(glass, attr, value)
    except Exception as e:
        print("glass", attr, e)
bottle = revolve("Bottle", [(BR - 0.003, 0.0), (BR, 0.004), (BR, BH * 0.72), (BR * 0.5, BH * 0.9), (BR * 0.42, BH), (BR * 0.34, BH)])
bottle.data.materials.append(glass)

liquid = revolve("Liquid", [(BR - 0.0035, 0.0), (BR - 0.0035, 1.0)], caps=True)       # 높이 1 짜리 원기둥, 바닥이 원점
liquid.location = (0, 0, 0.0035)
liquid.data.materials.append(flat_mat("Oil", (0.42, 0.13, 0.005), 0.03, **{"Coat Weight": 1.0}))

tape = revolve("Tape", [(BR + 0.0005, FULL + 0.0005), (BR + 0.0005, FULL + 0.0065)], caps=False)
tape.data.materials.append(flat_mat("Tape", (0.93, 0.90, 0.78), 0.75))

reed_wet = (0.42, 0.26, 0.10)
reed_dry = (0.72, 0.58, 0.36)
reed_mat, reed_bsdf = new_mat("Reed")
reed_bsdf.inputs["Roughness"].default_value = 0.8
random.seed(3)
for i in range(7):
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.0016, depth=0.22)
    r = bpy.context.active_object
    r.name = f"Reed{i}"
    r.data.materials.append(reed_mat)
    a = i * 2 * math.pi / 7
    tilt = math.radians(random.uniform(5, 8))                 # 병 안쪽 벽을 뚫지 않을 만큼만 기울인다
    r.rotation_euler = (tilt * math.sin(a), tilt * math.cos(a), 0)
    r.location = (0.006 * math.cos(a), -0.006 * math.sin(a), 0.118)

# ---------------- 타임랩스: 액체 높이, 막대 색, 해 ----------------
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
for f in range(1, END + 1, 5):
    t = (f - 1) / (END - 1)
    drop = min(1.0, t / 0.86)                                   # 마지막 0.5초쯤은 바닥난 채로 보여 준다
    liquid.scale = (1, 1, FULL + (EMPTY - FULL) * drop - 0.0035)
    liquid.keyframe_insert("scale", frame=f)
    reed_bsdf.inputs["Base Color"].default_value = (*[w + (d - w) * drop for w, d in zip(reed_wet, reed_dry)], 1)
    reed_bsdf.inputs["Base Color"].keyframe_insert("default_value", frame=f)

sun_d = bpy.data.lights.new("Sun", "AREA")
sun_d.size = 0.7
sun = link(bpy.data.objects.new("Sun", sun_d))
target = Vector((0, 0, 0.05))
for f in range(1, END + 1, 2):
    day = (f - 1) / (END - 1) * DAYS
    phase = day % 1.0                                           # 0 해 뜸 → 0.5 한낮 → 1 해 짐
    up = math.sin(math.pi * phase)
    ang = math.radians(-70 + 140 * phase)
    sun.location = (1.1 * math.sin(ang), -0.75, 0.25 + 0.85 * up)
    sun.rotation_euler = (target - sun.location).to_track_quat("-Z", "Y").to_euler()
    sun_d.energy = (10 + 55 * up) if hdri else (30 + 150 * up)
    sun_d.color = (1.0, 0.72 + 0.28 * up, 0.5 + 0.5 * up)       # 아침저녁은 노랗게
    bg.inputs[1].default_value = (0.35 + 0.8 * up) if hdri else (0.4 + 0.6 * up)
    sun.keyframe_insert("location", frame=f)
    sun.keyframe_insert("rotation_euler", frame=f)
    sun_d.keyframe_insert("energy", frame=f)
    sun_d.keyframe_insert("color", frame=f)
    bg.inputs[1].keyframe_insert("default_value", frame=f)

# ---------------- 카메라: 선반에 세워 둔 폰. 조금씩 다가간다 ----------------
cd = bpy.data.cameras.new("Cam")
cd.lens = 58
cam = link(bpy.data.objects.new("Cam", cd))
aim = link(bpy.data.objects.new("CamTarget", None))
aim.location = (0, 0, 0.062)
track = cam.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
random.seed(11)
for f in range(1, END + 1, 6):
    t = (f - 1) / (END - 1)
    j = 0.0015
    cam.location = (-0.05 + 0.02 * t + random.uniform(-j, j), -0.60 + 0.16 * t + random.uniform(-j, j), 0.27 - 0.06 * t + random.uniform(-j, j))
    cam.keyframe_insert("location", frame=f)
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
print("EVAPORATE_SCENE_DONE")
