# Prompt for Claude Code on the VPS

Copy the text below the line into Claude Code on this machine.

---

Integrate a Markdown-to-PDF render pipeline into my personal web app.

## What already exists (do not rebuild it)

A tested, self-contained pipeline is at `~/projects/md-render-pipeline/`:

- `render.sh <input.md> <output.pdf>` — the only entry point. It
  cleans AI-generated Markdown artifacts, auto-fixes math, and runs
  `pandoc --pdf-engine=typst` with the style assets in the same
  directory. Read its `README.md` first for details and limits.
- Dependencies are already satisfied on this machine: pandoc 3.1.3,
  typst 0.15.1, node 22, and `npm install` has been run in the
  pipeline directory. A test render passed
  (`/tmp/test-render.pdf`).
- Do NOT change the files in `~/projects/md-render-pipeline/` except
  `typst-header.typ` font names, and only if a font problem appears.
  Treat the directory as a vendored tool.

## Your task

1. Find my web app in `~/projects/` and add a "Markdown to PDF"
   feature to it:
   - An endpoint or page where I submit Markdown (file upload or
     text paste).
   - The server calls
     `~/projects/md-render-pipeline/render.sh <in.md> <out.pdf>`
     as a subprocess with a timeout of 120 seconds, then returns the
     PDF as the response (`Content-Type: application/pdf`).
   - Use a per-request temp directory for input and output files, and
     delete it after the response.
2. Safety rules for the endpoint:
   - Limit the upload size (2 MB is enough; the largest test file was
     190 KB).
   - Never pass user text through a shell string. Use an argument
     list (`subprocess.run([...])` or `execFile`), not
     `shell=True` / `exec`.
   - On a non-zero exit from `render.sh`, return HTTP 422 with the
     stderr text so I can see what is wrong with the Markdown.
3. Verify the feature end to end: start the app, POST a small
   Markdown sample with a table and `$...$` math, and confirm the
   response is a valid PDF (check the `%PDF` magic bytes and a
   nonzero page count with `pdfinfo` if available).
4. Show me the endpoint URL and one `curl` example that I can run.

Ask me first if it is unclear which project in `~/projects/` is the
web app, or where new routes belong in it.
