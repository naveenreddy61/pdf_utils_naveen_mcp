import fs from "node:fs";
import katex from "katex";

// Robust $..$ / $$..$$ tokenizer that honors \$ escapes.

function* scanMath(s) {
  let i = 0;
  const n = s.length;
  const isEsc = (j) => j > 0 && s[j - 1] === "\\" && (j < 2 || s[j - 2] !== "\\");

  while (i < n) {
    if (s[i] === "\\") { i += 2; continue; }
    if (s.startsWith("$$", i) && !isEsc(i)) {
      let end = s.indexOf("$$", i + 2);
      while (end > 0 && isEsc(end)) end = s.indexOf("$$", end + 2);
      if (end < 0) { yield { type: "display", raw: s.slice(i + 2), unterminated: true, start: i }; return; }
      yield { type: "display", raw: s.slice(i + 2, end), start: i, end: end + 2 };
      i = end + 2;
    } else if (s[i] === "$" && !isEsc(i)) {
      let end = s.indexOf("$", i + 1);
      while (end > 0 && isEsc(end)) end = s.indexOf("$", end + 1);
      if (end < 0) { yield { type: "inline", raw: s.slice(i + 1), unterminated: true, start: i }; return; }
      const raw = s.slice(i + 1, end);
      if (raw.trim() && !raw.includes("\n")) {
        yield { type: "inline", raw, start: i, end: end + 1 };
      }
      i = end + 1;
    } else i++;
  }
}

function lineOf(s, idx) {
  let line = 1;
  for (let k = 0; k < idx && k < s.length; k++) if (s[k] === "\n") line++;
  return line;
}

export function lintMath(src) {
  const issues = [];
  for (const m of scanMath(src)) {
    if (m.unterminated) {
      issues.push({ line: lineOf(src, m.start), severity: "error", kind: "unterminated", tex: m.raw.slice(0, 40) });
      continue;
    }
    try {
      katex.renderToString(m.raw.trim(), {
        throwOnError: true,
        displayMode: m.type === "display",
        strict: "ignore",
      });
    } catch (e) {
      issues.push({
        line: lineOf(src, m.start),
        severity: "error",
        kind: "math",
        tex: m.raw.trim().slice(0, 60),
        msg: String(e.message).split("\n")[0],
      });
    }
  }
  return issues;
}

// --- Auto-fixes for common AI-generated artifacts ---

const FIXES = [
  {
    name: "empty-sqrt",
    desc: "Empty \\sqrt{} (breaks Typst, tolerated by LaTeX)",
    find: /\\sqrt\{\s*\}/g,
    replace: "\\sqrt{\\,}",
  },
  {
    name: "private-use",
    desc: "Private-use Unicode glyphs (U+E000–F8FF)",
    find: /[\uE000-\uF8FF]/g,
    replace: "",
  },
  {
    name: "stray-backslash-eol",
    desc: "Trailing backslash before a newline inside math",
    find: /\\\\[ \t]*\r?\n/g,
    replace: "\n",
  },
];

export function applyFixes(src, fixNames) {
  let out = src;
  const applied = [];
  for (const f of FIXES) {
    if (fixNames && fixNames.length > 0 && !fixNames.includes(f.name)) continue;
    const before = out;
    out = out.replace(f.find, f.replace);
    if (out !== before) applied.push({ name: f.name, desc: f.desc });
  }
  return { out, applied };
}
