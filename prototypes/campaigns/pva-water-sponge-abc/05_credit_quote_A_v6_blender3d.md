# Google Flow Hook Credit Quote — `pva-water-sponge-abc-A-v6-b3d`

> Scope: `0-5s` hooks ONLY (`5-25s` body reuses real source footage at `0 cr`). Mode: `Omni 1.2 Flash` (`x1` enforced) + `Nano Banana 2 Lite` (`0 cr`).

## 1. Real-Source Anchor Frames (`0 cr`, via `extract-first-frame`)

| Asset ID | Source Timestamp | Output | Purpose |
|---|---|---|---|
| (none) | - | - | No source anchors declared |

## 2. Hook Keyframe Plates (`Nano Banana 2 Lite`, `0 cr`, `x1`)

| Ref ID | Attach Anchors | Output | Credits |
|---|---|---|---|
| `R_A1_v6_b3d` | `(none)` | `refs/R_A1_v6_b3d.png` | `0 cr` |
| `R_A2_v6_b3d` | `R_A1_v6_b3d` | `refs/R_A2_v6_b3d.png` | `0 cr` |

## 3. Opening Motion Clips (`Omni 1.2 Flash`, Parallel 1-Wave `--concurrency 3`)

| Unit | Variant | Mode | Duration | `360p` Cost | `720p` Cost | Output |
|---|---|---|---|---|---|---|
| `A1_v6_b3d` | `ad_A_domino_docu_b3d` | `ingredients` | `5s` | `5 cr` | `15 cr` | `clips/A1_v6_b3d.mp4` |
| `A2_v6_b3d` | `ad_A_domino_docu_b3d` | `ingredients` | `5s` | `5 cr` | `15 cr` | `clips/A2_v6_b3d.mp4` |
| **TOTAL** | **2 hooks** | **1-wave parallel** | - | **`10 cr`** | **`30 cr`** | - |

## 4. Exact Run Commands (After Explicit User Approval)

```bash
SCRIPTS=${CLAUDE_PLUGIN_ROOT}/libraries/media-tools
python3 "$SCRIPTS/flow_automator.py" refs --tab <TAB_ID> --project <PROJECT_DIR> --ids "R_A1_v6_b3d,R_A2_v6_b3d" --log
python3 "$SCRIPTS/flow_automator.py" contact-sheet --project <PROJECT_DIR> --out refs/sheet.png
python3 "$SCRIPTS/flow_automator.py" video-batch --tab <TAB_ID> --project <PROJECT_DIR> --ids "A1_v6_b3d,A2_v6_b3d" --concurrency 3 --max-credits 30 --log
```
