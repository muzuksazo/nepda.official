"""문제 장면 템플릿 `phone_distract_desk` — 책상 장면의 실사용 버전 (blender -b -P blender_scene_desk_real.py -- …).

blender_scene_desk.py 와 같은 장면·카메라를 쓰되 나무 책상과 실내 조명을 입히고 손은 뺀다.
이 첫 프레임을 Google Veo 에 넘기면 Veo 가 손이 들어와 폰을 집는 영상으로 이어 만든다.
"""
import os
import runpy

os.environ["C_DESK_STYLE"] = "real"
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_scene_desk.py"), run_name="__main__")
