"""Static Hyprland loader and strict, non-executable keyboard data."""
import os
from pathlib import Path
import re


MARKER = "-- Managed by madmatt.keyboard-settings. Remove through its recovery command.\n"
DATA_HEADER_V1 = b"madmatt.keyboard-settings-v1\n"
DATA_HEADER = b"madmatt.keyboard-settings-v2\n"
FIELDS = ("name", "layout", "variant", "options")
SESSION_PATTERN = re.compile(r"[A-Za-z0-9_.:-]{1,256}")


LOADER = (MARKER + r'''local state_home = os.getenv("XDG_STATE_HOME")
if not state_home or state_home == "" then
  state_home = (os.getenv("HOME") or "") .. "/.local/state"
end

local root = state_home .. "/omarchy/keyboard-settings"
local active_path = root .. "/active-v1.conf"
local pending_path = root .. "/pending-v1.conf"
local header_v1 = "madmatt.keyboard-settings-v1\n"
local header_v2 = "madmatt.keyboard-settings-v2\n"

local function decode_hex(value)
  if #value % 2 ~= 0 or value:find("[^0-9a-f]") then return nil end
  return (value:gsub("..", function(pair) return string.char(tonumber(pair, 16)) end))
end

local function read_data(path)
  local file = io.open(path, "rb")
  if not file then return nil end
  local data = file:read("*a")
  file:close()
  if data:sub(-1) ~= "\n" then return nil end

  local body, saved_session
  if data:sub(1, #header_v2) == header_v2 then
    local encoded, remaining = data:sub(#header_v2 + 1):match("^session\t([0-9a-f]*)\n(.*)$")
    if not encoded then return nil end
    saved_session = decode_hex(encoded)
    if not saved_session or #saved_session > 256 or saved_session:find("[^%w_.:%-]") then return nil end
    body = remaining
  elseif data:sub(1, #header_v1) == header_v1 then
    saved_session = ""
    body = data:sub(#header_v1 + 1)
  else
    return nil
  end

  local rows, names = {}, {}
  for line in body:gmatch("([^\n]*)\n") do
    if line ~= "" then
      local name, layout, variant, options = line:match(
        "^([0-9a-f]*)\t([0-9a-f]*)\t([0-9a-f]*)\t([0-9a-f]*)$")
      if not name then return nil end
      name, layout, variant, options = decode_hex(name), decode_hex(layout),
        decode_hex(variant), decode_hex(options)
      if not name or not layout or not variant or not options or name == "" or names[name] then return nil end
      names[name] = true
      table.insert(rows, {name = name, layout = layout, variant = variant, options = options})
    end
  end
  return rows, data, saved_session
end

local function same_rows(first, second)
  if not first or not second or #first ~= #second then return false end
  for index, row in ipairs(first) do
    local other = second[index]
    if row.name ~= other.name or row.layout ~= other.layout or row.variant ~= other.variant
        or row.options ~= other.options then return false end
  end
  return true
end

local function shell_quote(value)
  return "'" .. value:gsub("'", "'\\''") .. "'"
end

local function command_succeeds(command)
  -- Hyprland owns SIGCHLD and can reap this process before Lua's pclose(), so
  -- os.execute()/handle:close() may report failure after a successful command.
  -- Read a token printed only when every shell step completed instead.
  local opened, handle = pcall(io.popen, command .. " && printf keyboard-settings-ok")
  if not opened or not handle then return false end
  local proof = handle:read("*a")
  handle:close()
  return proof == "keyboard-settings-ok"
end

local function write_active(data)
  local temporary = active_path .. ".session"
  local output = io.open(temporary, "wb")
  if not output then return false end
  local written = output:write(data)
  output:flush()
  output:close()
  if not written then os.remove(temporary); return false end

  local secured = command_succeeds("chmod 600 -- " .. shell_quote(temporary)
    .. " && sync -f " .. shell_quote(temporary) .. " >/dev/null 2>&1")
  if not secured then os.remove(temporary); return false end

  local check = io.open(temporary, "rb")
  local checked = check and check:read("*a") or nil
  if check then check:close() end
  if checked ~= data then os.remove(temporary); return false end

  if not os.rename(temporary, active_path) then os.remove(temporary); return false end
  return command_succeeds("sync -f " .. shell_quote(root) .. " >/dev/null 2>&1")
end

local active = read_data(active_path)
local pending, pending_data, saved_session = read_data(pending_path)
local current_session = os.getenv("HYPRLAND_INSTANCE_SIGNATURE") or ""

-- A save records the current compositor instance. Reloads in that same instance
-- continue to use active data. The first parse in a new instance promotes the
-- pending data before device declarations are registered.
if pending and saved_session ~= "" and current_session ~= ""
    and saved_session ~= current_session and not same_rows(active, pending)
    and write_active(pending_data) then
  active = pending
end

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
''').encode()


def _session(value=None):
    value = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "") if value is None else value
    if not isinstance(value, str) or (value and not SESSION_PATTERN.fullmatch(value)):
        raise ValueError("invalid Hyprland session identifier")
    return value


def render_rows(targets, session=None):
    """Encode validated device targets with the compositor session that saved them."""
    names = set()
    checked = []
    for target in targets:
        if not isinstance(target, dict) or any(not isinstance(target.get(key), str) for key in FIELDS):
            raise ValueError("saved keyboard target is invalid")
        if not target["name"] or target["name"] in names:
            raise ValueError("saved keyboard names overlap")
        names.add(target["name"])
        checked.append(target)
    session = _session(session)
    lines = [DATA_HEADER.rstrip(b"\n"), b"session\t" + session.encode("utf-8").hex().encode("ascii")]
    lines += [b"\t".join(target[key].encode("utf-8").hex().encode("ascii") for key in FIELDS)
              for target in checked]
    return b"\n".join(lines) + b"\n"


def render(saved, session=None):
    """Encode saved profiles as inert, strict device records."""
    targets = []
    profiles = saved.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("saved profiles must be an object")
    for identity in sorted(profiles):
        group = profiles[identity]
        if not isinstance(group, list):
            raise ValueError("saved profile targets must be a list")
        targets.extend(group)
    return render_rows(targets, session)


def decode(data):
    """Validate keyboard data and return its saving session and device rows."""
    if not isinstance(data, bytes) or not data.endswith(b"\n"):
        raise ValueError("invalid deferred keyboard data")
    if data.startswith(DATA_HEADER):
        lines = data[len(DATA_HEADER):].splitlines()
        if not lines or not lines[0].startswith(b"session\t"):
            raise ValueError("invalid deferred keyboard session")
        fields = lines.pop(0).split(b"\t")
        if len(fields) != 2:
            raise ValueError("invalid deferred keyboard session")
        try:
            saved = bytes.fromhex(fields[1].decode("ascii")).decode("utf-8")
        except (UnicodeError, ValueError) as exc:
            raise ValueError("invalid deferred keyboard session") from exc
        _session(saved)
    elif data.startswith(DATA_HEADER_V1):
        lines = data[len(DATA_HEADER_V1):].splitlines()
        saved = ""
    else:
        raise ValueError("invalid deferred keyboard data")

    rows = []
    for line in lines:
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
    return saved, rows


def parse(data):
    """Validate and decode inert data for tests, migration, and diagnostics."""
    return decode(data)[1]


def saved_session(data):
    """Return the compositor session recorded in validated keyboard data."""
    return decode(data)[0]


def valid_file(path):
    try:
        parse(Path(path).read_bytes())
        return True
    except (OSError, ValueError):
        return False
