"""문제 장면 템플릿 `drain_smell` — Blender 안에서 실행된다 (blender -b -P blender_scene_drain.py -- …).

욕실 불을 켜고 들어선 POV. 바닥 배수구에서 냄새가 연기처럼 올라오고 카메라가 움찔 물러난다.
방향제를 뿌리면 잠깐 잦아들지만 곧 더 크게 다시 올라온다. 240프레임(10초, 24fps), 9:16. 앞 3.5초만 써도 된다.
타일(요철·물기), 연기(가장자리가 풀리고 흐르는 무늬), 분무(작은 방울 여러 개), 얕은 심도와 모션 블러까지 절차적으로 만든다.
assets/ 에 실내 HDRI 가 있으면 반사에 쓴다.

사용: blender -b -P blender_scene_drain.py -- <프레임 출력 폴더> <assets 폴더> [해상도 %] [시작 프레임] [끝 프레임]
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


def flat_mat(name, color, rough=0.5, metallic=0.0, **extra):
    m, b = new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    for k, v in extra.items():
        try:
            b.inputs[k].default_value = v
        except Exception as e:
            print("mat input", k, e)
    return m


def blended(mat):
    for attr, value in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        try:
            setattr(mat, attr, value)
        except Exception as e:
            print(mat.name, attr, e)


def math_node(nt, op, a, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def map_range(nt, sock, a, b, lo, hi):
    n = nt.nodes.new("ShaderNodeMapRange")
    n.clamp = True
    for i, v in zip((1, 2, 3, 4), (a, b, lo, hi)):
        n.inputs[i].default_value = v
    nt.links.new(sock, n.inputs[0])
    return n.outputs[0]


def tile_mat(name, tile, grout, scale, rough, wet=0.0):
    """줄눈이 패인 타일. 타일마다 색이 조금 다르고, wet 만큼 물 얼룩이 번들거린다."""
    m, b = new_mat(name)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset, br.squash = 0.0, 1.0
    br.inputs["Color1"].default_value = (*tile, 1)
    br.inputs["Color2"].default_value = (*[c * 0.93 for c in tile], 1)
    br.inputs["Mortar"].default_value = (*grout, 1)
    br.inputs["Scale"].default_value = scale
    br.inputs["Mortar Size"].default_value = 0.014
    br.inputs["Mortar Smooth"].default_value = 0.25
    br.inputs["Brick Width"].default_value = 0.5
    br.inputs["Row Height"].default_value = 0.5
    nt.links.new(tc.outputs["UV"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value, noise.inputs["Detail"].default_value = 5.0, 4.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    puddle = map_range(nt, noise.outputs[0], 0.50, 0.62, 0.0, wet)                      # 물기 있는 자리
    r = math_node(nt, "SUBTRACT", math_node(nt, "ADD", rough, math_node(nt, "MULTIPLY", br.outputs["Fac"], 0.5)), puddle)
    nt.links.new(r, b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value, bump.inputs["Distance"].default_value = 0.9, 0.004
    nt.links.new(math_node(nt, "SUBTRACT", 1.0, br.outputs["Fac"]), bump.inputs["Height"])
    nt.links.new(bump.outputs[0], b.inputs["Normal"])
    return m


# ---------------- 욕실: 바닥 타일, 벽 타일, 배수구 ----------------
bpy.ops.mesh.primitive_plane_add(size=3)
bpy.context.active_object.data.materials.append(tile_mat("FloorTile", (0.20, 0.23, 0.25), (0.05, 0.055, 0.055), 12, 0.20, wet=0.16))
bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0.55, 1.5), rotation=(math.radians(90), 0, 0))
bpy.context.active_object.data.materials.append(tile_mat("WallTile", (0.62, 0.65, 0.64), (0.30, 0.32, 0.31), 8, 0.12))
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.545, 0.03))                      # 벽 아래 실리콘 마감
bpy.context.active_object.scale = (3, 0.012, 0.06)
bpy.context.active_object.data.materials.append(flat_mat("Sealant", (0.80, 0.80, 0.76), 0.5))

chrome = flat_mat("Chrome", (0.80, 0.81, 0.83), 0.16, 1.0)
dark = flat_mat("Hole", (0.005, 0.005, 0.005), 0.9)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.064, depth=0.006, location=(0, 0, 0.003))
grate = bpy.context.active_object
grate.data.materials.append(chrome)
bev = grate.modifiers.new("Bevel", "BEVEL")
bev.width, bev.segments = 0.0018, 3
for p in grate.data.polygons:
    p.use_smooth = True
bpy.ops.mesh.primitive_torus_add(major_radius=0.066, minor_radius=0.0035, major_segments=64, minor_segments=12, location=(0, 0, 0.004))
bpy.context.active_object.data.materials.append(chrome)
for ring, count in ((0.0, 1), (0.019, 6), (0.038, 12)):
    for i in range(count):
        a = i * 2 * math.pi / count + (0.26 if ring > 0.03 else 0)
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.0052, depth=0.002, location=(ring * math.cos(a), ring * math.sin(a), 0.0066))
        bpy.context.active_object.data.materials.append(dark)
# 배수구 둘레의 물때: 가장자리가 풀리는 얼룩
stain, stb = new_mat("Stain")
snt = stain.node_tree
stc = snt.nodes.new("ShaderNodeTexCoord")
sgr = snt.nodes.new("ShaderNodeTexGradient")
sgr.gradient_type = "SPHERICAL"
snt.links.new(stc.outputs["Object"], sgr.inputs["Vector"])
sno = snt.nodes.new("ShaderNodeTexNoise")
sno.inputs["Scale"].default_value = 9.0
snt.links.new(stc.outputs["Object"], sno.inputs["Vector"])
snt.links.new(math_node(snt, "MULTIPLY", map_range(snt, sgr.outputs[0], 0.0, 0.55, 0.0, 0.75), map_range(snt, sno.outputs[0], 0.35, 0.7, 0.4, 1.0)),
              stb.inputs["Alpha"])
stb.inputs["Base Color"].default_value = (0.20, 0.17, 0.09, 1)
stb.inputs["Roughness"].default_value = 0.35
blended(stain)
bpy.ops.mesh.primitive_circle_add(vertices=64, radius=1.0, fill_type="NGON", location=(0.006, -0.004, 0.0008))
ring = bpy.context.active_object
ring.scale = (0.13, 0.12, 1)
ring.data.materials.append(stain)

# ---------------- 냄새: 배수구에서 올라오는 연기 ----------------
stink, sb = new_mat("Stink")
nt = stink.node_tree
uv = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(uv.outputs["UV"], sep.inputs[0])
across = math_node(nt, "ABSOLUTE", math_node(nt, "SUBTRACT", math_node(nt, "MULTIPLY", sep.outputs[0], 2.0), 1.0))     # 0 가운데 → 1 가장자리
edge = math_node(nt, "POWER", math_node(nt, "SUBTRACT", 1.0, across), 1.6)                                           # 가장자리로 갈수록 풀린다
rise = math_node(nt, "MULTIPLY", map_range(nt, sep.outputs[1], 0.0, 0.07, 0.0, 1.0), map_range(nt, sep.outputs[1], 0.25, 1.0, 1.0, 0.0))
flow = nt.nodes.new("ShaderNodeTexNoise")
flow.noise_dimensions = "4D"
flow.inputs["Scale"].default_value, flow.inputs["Detail"].default_value = 3.2, 5.0
stretch = nt.nodes.new("ShaderNodeMapping")
stretch.inputs["Scale"].default_value = (1.0, 5.0, 1.0)
nt.links.new(uv.outputs["UV"], stretch.inputs[0])
nt.links.new(stretch.outputs[0], flow.inputs["Vector"])
for f in (1, END):                                               # 무늬가 계속 흐른다
    flow.inputs["W"].default_value = f * 0.035
    flow.inputs["W"].keyframe_insert("default_value", frame=f)
wisp = map_range(nt, flow.outputs[0], 0.22, 0.62, 0.30, 1.0)
nt.links.new(math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", edge, rise), math_node(nt, "MULTIPLY", wisp, 0.95)), sb.inputs["Alpha"])
sb.inputs["Base Color"].default_value = (0.10, 0.15, 0.005, 1)
sb.inputs["Emission Color"].default_value = (0.16, 0.24, 0.01, 1)
sb.inputs["Emission Strength"].default_value = 0.2
sb.inputs["Roughness"].default_value = 1.0
blended(stink)

SEG, HEIGHT = 48, 0.70
random.seed(5)
ribbons = []
for i in range(11):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rows = [(bm.verts.new((-0.02, 0, k * HEIGHT / SEG)), bm.verts.new((0.02, 0, k * HEIGHT / SEG))) for k in range(SEG + 1)]
    for k in range(SEG):
        face = bm.faces.new((rows[k][0], rows[k][1], rows[k + 1][1], rows[k + 1][0]))
        for loop, (u, v) in zip(face.loops, ((0, k / SEG), (1, k / SEG), (1, (k + 1) / SEG), (0, (k + 1) / SEG))):
            loop[uvl].uv = (u, v)
    me = bpy.data.meshes.new(f"Stink{i}")
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new(f"Stink{i}", me))
    o.data.materials.append(stink)
    a, rad = random.uniform(0, 6.28), random.uniform(0.0, 0.045)
    o.location = (rad * math.cos(a), rad * math.sin(a) * 0.7, 0.008)
    o.rotation_euler = (0, 0, random.uniform(-0.22, 0.22))
    ribbons.append({"obj": o, "width": random.uniform(0.032, 0.058), "phase": random.uniform(0, 6.28), "amp": random.uniform(0.016, 0.034),
                    "freq": random.uniform(11, 17), "speed": random.uniform(0.20, 0.32), "start": 4 + i * 2, "tall": random.uniform(0.75, 1.0)})


def wave(scn, *_):
    """프레임마다 연기 띠를 다시 만든다. 불이 켜진 뒤 자라고, 방향제에 잠깐 눌렸다가, 더 크게 다시 올라온다."""
    f = scn.frame_current
    for r in ribbons:
        grow = max(0.0, min(1.0, (f - r["start"]) / 24))
        grow = grow * grow * (3 - 2 * grow)
        if f > 112:
            grow = 1.0 - 0.72 * min(1.0, (f - 112) / 30)
        if f > 178:
            k = min(1.0, (f - 178) / 32)
            grow = 0.28 + 0.98 * k * k * (3 - 2 * k)
        vs = r["obj"].data.vertices
        for k in range(SEG + 1):
            a, b = vs[2 * k], vs[2 * k + 1]
            t = k / SEG
            z = t * HEIGHT * grow * r["tall"]
            x = r["amp"] * (0.15 + 1.6 * t) * math.sin(r["freq"] * z - r["speed"] * f + r["phase"]) + 0.02 * t * math.sin(0.11 * f + r["phase"])
            w = r["width"] * (0.55 + 1.5 * t)
            a.co, b.co = (x - w, 0, z), (x + w, 0, z)
        r["obj"].data.update()


bpy.app.handlers.frame_change_pre.append(wave)

# ---------------- 방향제 스프레이: 화면 오른쪽 아래에서 들어와 뿌리고 나간다 (3.5초~7초) ----------------
bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
can = link(bpy.data.objects.new("Spray", None))


def can_part(radius, depth, z, mat, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=(0, 0, z))
    o = bpy.context.active_object
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    o.modifiers.new("Bevel", "BEVEL").width = 0.0015
    try:
        o.modifiers.new("Normals", "WEIGHTED_NORMAL")
    except Exception:
        pass
    o.parent = can
    return o


can_part(0.030, 0.19, 0.0, flat_mat("CanBody", (0.93, 0.36, 0.55), 0.22, 0.75, **{"Coat Weight": 0.6}))
can_part(0.0305, 0.070, -0.015, flat_mat("CanLabel", (0.97, 0.96, 0.92), 0.45))
can_part(0.027, 0.012, 0.100, flat_mat("CanRim", (0.82, 0.83, 0.85), 0.2, 1.0))
can_part(0.017, 0.030, 0.118, flat_mat("CanCap", (0.97, 0.97, 0.97), 0.3))
can_part(0.004, 0.012, 0.118, flat_mat("Nozzle", (0.1, 0.1, 0.1), 0.5), verts=16).location = (-0.017, 0, 0.122)
TILT = -58
can.rotation_euler = (math.radians(8), math.radians(TILT), 0)                       # 꼭지가 배수구 쪽(왼쪽 아래)을 향한다
REST = (0.215, -0.20, 0.265)
for f, loc in ((1, (0.80, -0.30, 0.20)), (90, (0.80, -0.30, 0.20)), (104, REST), (152, (REST[0], REST[1], REST[2] + 0.008)), (168, (0.85, -0.32, 0.22))):
    can.location = loc
    can.keyframe_insert("location", frame=f)
for n, f in enumerate(range(108, 152, 5)):                                           # 누를 때마다 살짝 까딱인다
    can.rotation_euler = (math.radians(8), math.radians(TILT + (3.5 if n % 2 else 0)), 0)
    can.keyframe_insert("rotation_euler", frame=f)

mist, mb = new_mat("Mist")
mnt = mist.node_tree
mtc = mnt.nodes.new("ShaderNodeTexCoord")
mgr = mnt.nodes.new("ShaderNodeTexGradient")
mgr.gradient_type = "SPHERICAL"
mnt.links.new(mtc.outputs["Object"], mgr.inputs["Vector"])
mamt = mnt.nodes.new("ShaderNodeValue")                                              # 전체 농도 (키프레임)
mnt.links.new(math_node(mnt, "MULTIPLY", map_range(mnt, mgr.outputs[0], 0.0, 0.8, 0.0, 1.0), mamt.outputs[0]), mb.inputs["Alpha"])
mb.inputs["Base Color"].default_value = (1.0, 0.78, 0.87, 1)
mb.inputs["Emission Color"].default_value = (1.0, 0.72, 0.84, 1)
mb.inputs["Emission Strength"].default_value = 0.55
mb.inputs["Roughness"].default_value = 1.0
blended(mist)
for f, a in ((1, 0.0), (107, 0.0), (111, 0.62), (158, 0.5), (198, 0.0)):
    mamt.outputs[0].default_value = a
    mamt.outputs[0].keyframe_insert("default_value", frame=f)
random.seed(8)
nozzle = Vector((0.145, -0.185, 0.335))
aim_dir = (Vector((0.0, 0.0, 0.12)) - nozzle).normalized()
for i in range(46):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0, location=nozzle)
    puff = bpy.context.active_object
    for p in puff.data.polygons:
        p.use_smooth = True
    puff.data.materials.append(mist)
    born = 108 + random.randint(0, 40)
    reach = random.uniform(0.10, 0.34)
    spread = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.6, 1))) * (0.10 * reach / 0.3)
    end = nozzle + aim_dir * reach + spread
    s0, s1 = random.uniform(0.022, 0.038), random.uniform(0.060, 0.110)
    for f, loc, s in ((1, nozzle, 0.0), (born, nozzle, 0.0), (born + 7, nozzle + (end - nozzle) * 0.55, s0), (born + 30, end, s1),
                      (205, end + Vector((0, 0, 0.09)), s1 * 1.4)):
        puff.location, puff.scale = loc, (s, s, s)
        puff.keyframe_insert("location", frame=f)
        puff.keyframe_insert("scale", frame=f)

# ---------------- 조명: 어두웠다가 형광등이 깜빡 켜진다 ----------------
world = bpy.data.worlds.new("Bath")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
hdri = os.path.join(ASSETS, "polyhaven", "room_hdri", "env.hdr")
if os.path.exists(hdri):
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri)
    world.node_tree.links.new(env.outputs["Color"], bg.inputs[0])
else:
    bg.inputs[0].default_value = (0.85, 0.88, 0.92, 1)
lamp_d = bpy.data.lights.new("Ceiling", "AREA")
lamp_d.size = 0.5
lamp_d.color = (0.92, 0.97, 1.0)
lamp = link(bpy.data.objects.new("Ceiling", lamp_d))
lamp.location = (-0.25, -0.15, 1.5)
lamp.rotation_euler = (math.radians(8), math.radians(-12), 0)
fill_d = bpy.data.lights.new("Fill", "AREA")
fill_d.size = 1.2
fill = link(bpy.data.objects.new("Fill", fill_d))
fill.location = (0.5, -1.0, 0.8)
fill.rotation_euler = (math.radians(62), 0, math.radians(25))
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
for f, k in ((1, 0.02), (2, 0.02), (3, 0.8), (4, 0.2), (6, 1.0), (END, 1.0)):
    lamp_d.energy, fill_d.energy = 62 * k, 10 * k
    bg.inputs[1].default_value = 0.22 * k
    lamp_d.keyframe_insert("energy", frame=f)
    fill_d.keyframe_insert("energy", frame=f)
    bg.inputs[1].keyframe_insert("default_value", frame=f)

# ---------------- 카메라: 문 열고 들어선 폰. 냄새가 올라오면 움찔 물러난다 ----------------
cd = bpy.data.cameras.new("Cam")
cd.lens = 32
cam = link(bpy.data.objects.new("Cam", cd))
aim = link(bpy.data.objects.new("CamTarget", None))
track = cam.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
focus = link(bpy.data.objects.new("Focus", None))
focus.location = (0, 0, 0.05)
cd.dof.use_dof = True
cd.dof.focus_object = focus
cd.dof.aperture_fstop = 1.6
bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
random.seed(11)
for f in range(1, END + 1, 3):
    j = 0.005
    if f < 30:
        base, look = (0.03, -0.60 + 0.10 * f / 30, 0.60), (0, 0.0, 0.10)          # 다가간다
    elif f < 40:
        k = (f - 30) / 10
        base, look = (0.03 + 0.03 * k, -0.50 - 0.22 * k, 0.60 + 0.10 * k), (0, 0.0, 0.10 + 0.14 * k)   # 움찔
        j = 0.016
    elif f < 186:
        base, look = (0.06, -0.72, 0.70), (0, 0.0, 0.24)
    elif f < 198:                                                     # 다시 올라오자 한 번 더 물러난다
        k = (f - 186) / 12
        base, look = (0.06 + 0.02 * k, -0.72 - 0.14 * k, 0.70 + 0.06 * k), (0, 0.0, 0.24 + 0.10 * k)
        j = 0.014
    else:
        base, look = (0.08, -0.86, 0.76), (0, 0.0, 0.34)
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
scene.render.motion_blur_shutter = 0.35
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception as e:
    print("look", e)
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 95
os.makedirs(OUT, exist_ok=True)
scene.render.filepath = os.path.join(OUT, "p_")
scene.render.use_overwrite = False
bpy.ops.render.render(animation=True)
print("DRAIN_SCENE_DONE")
