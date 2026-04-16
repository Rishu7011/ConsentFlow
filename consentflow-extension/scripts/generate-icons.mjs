import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';

const root = process.cwd();
const svgPath = path.join(root, 'public', 'icons', 'icon.svg');
const outDir = path.join(root, 'public', 'icons');

const sizes = [16, 32, 48, 128];

await mkdir(outDir, { recursive: true });

const svg = await readFile(svgPath);

await Promise.all(
  sizes.map(async (size) => {
    const outPath = path.join(outDir, `icon${size}.png`);
    const png = await sharp(svg, { density: 256 })
      .resize(size, size)
      .png()
      .toBuffer();
    await writeFile(outPath, png);
  }),
);

console.log(`[ConsentFlow] Generated icons: ${sizes.join(', ')}`);

