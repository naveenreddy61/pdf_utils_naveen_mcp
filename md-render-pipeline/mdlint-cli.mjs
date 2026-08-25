import fs from "node:fs";
import process from "node:process";
import { lintMath, applyFixes } from "./mdlint.mjs";

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith("-")) ?? "../source-long.md";
const write = args.includes("--fix");
const fixNames = args.filter((a) => a.startsWith("--fix=")).map((a) => a.slice(6));

const src = fs.readFileSync(file, "utf8");

console.log(`=== math lint: ${file} ===`);
const issues = lintMath(src);
if (issues.length === 0) {
  console.log("no math errors found");
} else {
  const byKind = {};
  for (const it of issues) {
    byKind[it.kind] = (byKind[it.kind] || 0) + 1;
    console.log(`[${it.severity}] line ${it.line} (${it.kind}) ${JSON.stringify(it.tex)}${it.msg ? " => " + it.msg : ""}`);
  }
  console.log("\nsummary:", byKind);
}

console.log(`\n=== auto-fixes available ===`);
const { out, applied } = applyFixes(src, fixNames);
for (const a of applied) console.log(`- ${a.name}: ${a.desc}`);

if (write) {
  fs.writeFileSync(file, out);
  console.log(`\nwrote fixes back to ${file} (${applied.map((a) => a.name).join(", ") || "none"})`);
} else {
  console.log("\n(dry run — pass --fix to write changes)");
}
