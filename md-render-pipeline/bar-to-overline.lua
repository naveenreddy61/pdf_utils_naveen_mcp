-- Pandoc 3.1's typst writer emits TeX \bar{x} as x^(‾) — a superscript
-- dash, not a bar over the letter. Rewrite to \overline so typst-header.typ
-- can map compact overlines to a macron accent.

local function rewrite_braced_bars(s)
  local out = {}
  local i = 1
  local n = #s
  while true do
    local a, brace = s:find("\\bar%s*%{", i)
    if not a then
      out[#out + 1] = s:sub(i)
      break
    end
    out[#out + 1] = s:sub(i, a - 1)
    local depth, j = 1, brace + 1
    while j <= n and depth > 0 do
      local c = s:sub(j, j)
      if c == "{" then
        depth = depth + 1
      elseif c == "}" then
        depth = depth - 1
      end
      j = j + 1
    end
    out[#out + 1] = "\\overline{" .. s:sub(brace + 1, j - 2) .. "}"
    i = j
  end
  return table.concat(out)
end

function Math(el)
  el.text = rewrite_braced_bars(el.text)
  el.text = el.text:gsub("\\bar%s+(\\[%a]+)", "\\overline{%1}")
  el.text = el.text:gsub("\\bar%s+(%a)", "\\overline{%1}")
  return el
end
