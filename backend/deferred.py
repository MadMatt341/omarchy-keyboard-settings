"""Static Hyprland loader and non-executable deferred keyboard data."""
from pathlib import Path


MARKER = "-- Managed by madmatt.keyboard-settings. Remove through its recovery command.\n"
DATA_HEADER = b"madmatt.keyboard-settings-v1\n"
FIELDS = ("name", "layout", "variant", "options")


LOADER = (MARKER + r'''local state_home = os.getenv("XDG_STATE_HOME")
if not state_home or state_home == "" then
  state_home = (os.getenv("HOME") or "") .. "/.local/state"
end

local root = state_home .. "/omarchy/keyboard-settings"
local active_path = root .. "/active-v1.conf"
local pending_path = root .. "/pending-v1.conf"
local header = "madmatt.keyboard-settings-v1\n"

local function decode_hex(value)
  if #value % 2 ~= 0 or value:find("[^0-9a-f]") then return nil end
  return (value:gsub("..", function(pair) return string.char(tonumber(pair, 16)) end))
end

local function read_data(path)
  local file = io.open(path, "rb")
  if not file then return nil end
  local data = file:read("*a")
  file:close()
  if data:sub(1, #header) ~= header or data:sub(-1) ~= "\n" then return nil end

  local rows = {}
  for line in data:sub(#header + 1):gmatch("([^\n]*)\n") do
    if line ~= "" then
      local name, layout, variant, options = line:match(
        "^([0-9a-f]*)\t([0-9a-f]*)\t([0-9a-f]*)\t([0-9a-f]*)$")
      if not name then return nil end
      name, layout, variant, options = decode_hex(name), decode_hex(layout),
        decode_hex(variant), decode_hex(options)
      if not name or not layout or not variant or not options or name == "" then return nil end
      table.insert(rows, {name = name, layout = layout, variant = variant, options = options})
    end
  end
  return rows, data
end

local active = read_data(active_path)
if active then
  for _, row in ipairs(active) do
    hl.device({
      name = row.name,
      kb_layout = row.layout,
      kb_variant = row.variant,
      kb_options = row.options,
    })
  end
end

local function shell_quote(value)
  return "'" .. value:gsub("'", "'\\''") .. "'"
end

hl.on("hyprland.shutdown", function()
  local pending, data = read_data(pending_path)
  if not pending then return end

  local current_file = io.open(active_path, "rb")
  local current = current_file and current_file:read("*a") or nil
  if current_file then current_file:close() end
  if current == data then return end

  local temporary = active_path .. ".shutdown"
  local output = io.open(temporary, "wb")
  if not output then return end
  local written = output:write(data)
  output:flush()
  output:close()
  if not written then os.remove(temporary); return end

  local secured = os.execute("chmod 600 -- " .. shell_quote(temporary)
    .. " && sync -f " .. shell_quote(temporary) .. " >/dev/null 2>&1")
  if secured ~= true and secured ~= 0 then os.remove(temporary); return end
  if not os.rename(temporary, active_path) then os.remove(temporary); return end
  os.execute("sync -f " .. shell_quote(root) .. " >/dev/null 2>&1")
end)
''').encode()


def render(saved):
    """Encode validated device targets as inert, strict hex records."""
    targets = []
    names = set()
    profiles = saved.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("saved profiles must be an object")
    for identity in sorted(profiles):
        group = profiles[identity]
        if not isinstance(group, list):
            raise ValueError("saved profile targets must be a list")
        for target in group:
            if not isinstance(target, dict) or any(not isinstance(target.get(key), str) for key in FIELDS):
                raise ValueError("saved keyboard target is invalid")
            if not target["name"] or target["name"] in names:
                raise ValueError("saved keyboard names overlap")
            names.add(target["name"])
            targets.append(target)
    lines = [DATA_HEADER.rstrip(b"\n")]
    lines += [b"\t".join(target[key].encode("utf-8").hex().encode("ascii") for key in FIELDS)
              for target in targets]
    return b"\n".join(lines) + b"\n"


def parse(data):
    """Validate and decode inert data for tests, migration, and diagnostics."""
    if not isinstance(data, bytes) or not data.startswith(DATA_HEADER) or not data.endswith(b"\n"):
        raise ValueError("invalid deferred keyboard data")
    rows = []
    for line in data[len(DATA_HEADER):].splitlines():
        if not line:
            continue
        fields = line.split(b"\t")
        if len(fields) != len(FIELDS):
            raise ValueError("invalid deferred keyboard row")
        try:
            row = {key: bytes.fromhex(value.decode("ascii")).decode("utf-8")
                   for key, value in zip(FIELDS, fields)}
        except (UnicodeError, ValueError) as exc:
            raise ValueError("invalid deferred keyboard field") from exc
        if not row["name"]:
            raise ValueError("invalid deferred keyboard name")
        rows.append(row)
    if len({row["name"] for row in rows}) != len(rows):
        raise ValueError("saved keyboard names overlap")
    return rows


def valid_file(path):
    try:
        parse(Path(path).read_bytes())
        return True
    except (OSError, ValueError):
        return False
