// 인물 장면 코드가 쓰는 에셋을 pipeline/public/bassets 로 복사한다.
// quaternius(캐릭터)는 통째로, 나머지(kenney·polypizza·polyhaven)는 장면 코드에 적힌 파일만 골라서.
import { copyFileSync, cpSync, existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ASSETS = join(HERE, "../../assets");
/** 장면 코드가 import 하는 공용 부품: 장면 폴더(src/generated)에 B<이름>.tsx 로 넣는다 */
const LIBS = { BCharacter: "Character.tsx", BSets: "Sets.tsx" } as const;

/** productModel: src/assets/products/<model>.tsx 를 BProduct.tsx 로 (반전 장면의 제품) */
export function installSceneLib(genDir: string, productModel?: string): void {
  for (const [name, file] of Object.entries(LIBS)) writeFileSync(join(genDir, `${name}.tsx`), readFileSync(join(HERE, file)));
  const model = productModel ?? process.env.B_PRODUCT_MODEL;
  if (model) {
    const src = join(HERE, "products", `${model}.tsx`);
    if (!existsSync(src)) throw new Error(`제품 모델이 없습니다: src/assets/products/${model}.tsx`);
    writeFileSync(join(genDir, "BProduct.tsx"), readFileSync(src));
  }
}

/** 만들어 둔 제품 모델 이름들 */
export function productModels(): string[] {
  const d = join(HERE, "products");
  return existsSync(d) ? readdirSync(d).filter((f) => f.endsWith(".tsx")).map((f) => f.slice(0, -4)) : [];
}

export function copySceneAssets(sceneFiles: string[], assetDir: string): string[] {
  cpSync(join(ASSETS, "quaternius"), assetDir, { recursive: true });
  const copied: string[] = [];
  // 공용 세트(BSets)를 쓰는 장면이면 세트 안의 가구 파일도 같이
  const files = [...sceneFiles];
  if (sceneFiles.some((f) => readFileSync(f, "utf8").includes("./BSets"))) files.push(join(HERE, LIBS.BSets));
  for (const f of files) {
    const code = readFileSync(f, "utf8");
    for (const m of code.matchAll(/bassets\/((?:kenney|polypizza|polyhaven)\/[^'"`\s]*)/g)) {
      const rel = m[1];
      const src = join(ASSETS, rel);
      if (!existsSync(src)) throw new Error(`${f}: 에셋 파일이 없습니다 (b/assets/${rel}). scripts/assets 로 다시 받으세요.`);
      // 'bassets/kenney/furniture-kit/' + 'desk.glb' 처럼 폴더만 적힌 경우: 코드에 이름이 나오는 파일만
      const picked = statSync(src).isDirectory()
        ? readdirSync(src).filter((n) => /\.(glb|gltf|hdr|png|jpg)$/i.test(n) && code.includes(n)).map((n) => join(rel, n).replace(/\\/g, "/"))
        : [rel];
      for (const r of picked) {
        const dst = join(assetDir, r);
        mkdirSync(dirname(dst), { recursive: true });
        copyFileSync(join(ASSETS, r), dst);
        copied.push(r);
      }
    }
  }
  return [...new Set(copied)];
}
