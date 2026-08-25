-- table-widths.lua
-- Assign proportional column widths to every table so the LaTeX writer
-- emits wrapping p{width} columns instead of non-wrapping l/c/r columns.
function table_widths(tbl)
  local ncols = #tbl.colspecs
  if ncols == 0 then return nil end

  local function plain_len(inlines)
    return #pandoc.utils.stringify(inlines)
  end

  local widths = {}
  for i = 1, ncols do widths[i] = 0 end

  if tbl.head and tbl.head.rows then
    for _, row in ipairs(tbl.head.rows) do
      for i, cell in ipairs(row.cells) do
        for _, b in ipairs(cell.contents) do
          widths[i] = math.max(widths[i], plain_len(b))
        end
      end
    end
  end
  if tbl.bodies then
    for _, body in ipairs(tbl.bodies) do
      local rows = body.body
      if rows then
        for _, row in ipairs(rows) do
          for i, cell in ipairs(row.cells) do
            for _, b in ipairs(cell.contents) do
              widths[i] = math.max(widths[i], plain_len(b))
            end
          end
        end
      end
    end
  end

  -- Square-root scaling softens extreme ratios so no column gets crushed
  -- (a 200-char column vs a 10-char column becomes ~4.5:1, not 20:1).
  local total = 0
  for i = 1, ncols do
    widths[i] = math.max(widths[i], 5)
    widths[i] = math.sqrt(widths[i])
    total = total + widths[i]
  end

  for i = 1, ncols do
    tbl.colspecs[i][2] = widths[i] / total
  end

  return tbl
end

return {
  { Table = table_widths },
}
