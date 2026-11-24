# Google Flow Hook Credit Quote — `mooas-mugpot-abc`

> Scope: `0-5s` hooks ONLY (`5-25s` body reuses real source footage at `0 cr`). Mode: `Omni 1.2 Flash` (`x1` enforced) + `Nano Banana 2 Lite` (`0 cr`).

## 1. Real-Source Anchor Frames (`0 cr`, via `extract-first-frame`)

| Asset ID | Source Timestamp | Output | Purpose |
|---|---|---|---|
| `REF_PRODUCT` | `2.3s` | `refs/REF_PRODUCT.png` | Exact cream white mug pot with oak handle and stainless interior for Track B lifestyle grounding |
| `BRIDGE_B` | `4.0s` | `refs/BRIDGE_B.png` | Plugging detachable cord start-frame alignment reference |

## 2. Hook Keyframe Plates (`Nano Banana 2 Lite`, `0 cr`, `x1`)

| Ref ID | Attach Anchors | Output | Credits |
|---|---|---|---|
| `R_A` | `(none)` | `refs/R_A.png` | `0 cr` |
| `R_B` | `REF_PRODUCT` | `refs/R_B.png` | `0 cr` |
| `R_C` | `(none)` | `refs/R_C.png` | `0 cr` |

## 3. Opening Motion Clips (`Omni 1.2 Flash`, Parallel 1-Wave `--concurrency 3`)

| Unit | Variant | Mode | Duration | `360p` Cost | `720p` Cost | Output |
|---|---|---|---|---|---|---|
| `G_A` | `A` | `ingredients` | `4s` | `4 cr` | `12 cr` | `clips/G_A_t1.mp4` |
| `G_B` | `B` | `ingredients` | `4s` | `4 cr` | `12 cr` | `clips/G_B_t1.mp4` |
| `G_C` | `C` | `ingredients` | `3s` | `3 cr` | `9 cr` | `clips/G_C_t1.mp4` |
| **TOTAL** | **3 hooks** | **1-wave parallel** | - | **`11 cr`** | **`33 cr`** | - |

## 4. Exact Run Commands (After Explicit User Approval)

```bash
SCRIPTS=~/.claude/skills/shortform-ad-remix-director/scripts
python3 "$SCRIPTS/flow_automator.py" extract-first-frame --project <PROJECT_DIR> --video "source/mooas_36s_orig.mp4" --time 2.3 --id REF_PRODUCT --out "refs/REF_PRODUCT.png"
python3 "$SCRIPTS/flow_automator.py" extract-first-frame --project <PROJECT_DIR> --video "source/mooas_36s_orig.mp4" --time 4.0 --id BRIDGE_B --out "refs/BRIDGE_B.png"
python3 "$SCRIPTS/flow_automator.py" refs --tab <TAB_ID> --project <PROJECT_DIR> --ids "R_A,R_B,R_C" --log
python3 "$SCRIPTS/flow_automator.py" contact-sheet --project <PROJECT_DIR> --out refs/sheet.png
python3 "$SCRIPTS/flow_automator.py" video-batch --tab <TAB_ID> --project <PROJECT_DIR> --ids "G_A,G_B,G_C" --concurrency 3 --max-credits 33 --log
```
