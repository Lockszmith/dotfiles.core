-- Pull in the wezterm API
local wezterm = require("wezterm")
local act = wezterm.action

-- This table will hold the configuration.
local config = {}

-- In newer versions of wezterm, use the config_builder which will
-- help provide clearer error messages
if wezterm.config_builder then
	config = wezterm.config_builder()
end

config.hide_tab_bar_if_only_one_tab = true
config.window_background_opacity = 0.9
config.text_background_opacity = 0.9

-- This is where you actually apply your config choices
config.audible_bell = "Disabled"

config.visual_bell = {
	fade_in_function = "EaseIn",
	fade_in_duration_ms = 50,
	fade_out_function = "Constant",
	fade_out_duration_ms = 0,
}
-- config.colors = {
--   visual_bell = '#202020',
-- }

-- For example, changing the color scheme:
-- config.color_scheme = 'AdventureTime'
-- config.color_scheme = 'Batman'
-- config.color_scheme = 'Apple System Colors'
-- config.color_scheme = 'Azu (Gogh)'
-- config.color_scheme = 'Bim (Gogh)'
-- config.colorCMD_scheme = 'Cai (Gogh)'
-- config.color_scheme = 'CGA'
-- config.color_scheme = 'Chalkboard'
-- config.color_scheme = 'Dark Pastel'
-- config.color_scheme = 'Dark Violet (base16)'
-- config.color_scheme = 'Default Dark (base16)'
-- config.color_scheme = 'Dotshare (terminal.sexy)'
-- config.color_scheme = 'Dracula'
-- config.color_scheme = 'Dracula (Official)'
-- config.color_scheme = 'Dracula+'
-- config.color_scheme = 'duckbones'
-- config.color_scheme = 'Floraverse' -- *****
-- config.color_scheme = 'Galizur'
-- config.color_scheme = 'Github Dark (Gogh)'
-- config.color_scheme = 'Glacier'
-- config.color_scheme = 'Gnometerm (terminal.sexy)'
-- config.color_scheme = 'Gotham (Gogh)'
-- config.color_scheme = 'Grayscale Dark (base16)'
-- config.color_scheme = 'Hardcore (Gogh)'
-- config.color_scheme = 'Highway'
-- config.color_scheme = 'Hybrid (terminal.sexy)'
-- config.color_scheme = 'Ibm3270 (Gogh)'
-- config.color_scheme = 'Iiamblack (terminal.sexy)'
-- config.color_scheme = 'iTerm2 Default'
-- config.color_scheme = 'iTerm2 Smoooooth'
-- config.color_scheme = 'iTerm2 Tango Dark'
-- config.color_scheme = 'Jason Wryan (terminal.sexy)'
-- config.color_scheme = 'Kibble'
-- config.color_scheme = 'Kibble (Gogh)'
-- config.color_scheme = 'Konsolas'
-- config.color_scheme = 'LiquidCarbonTransparent'
-- config.color_scheme = 'MaterialDark'
-- config.color_scheme = 'MaterialDesignColors'
-- config.color_scheme = 'Muse (terminal.sexy)'
-- config.color_scheme = 'niji'
-- config.color_scheme = 'Oceanic Next (Gogh)'
-- config.color_scheme = 'Pasque (base16)' -- Purple/Lavendar hues
config.color_scheme = "Pencil Dark (Gogh)" -- ****1/2
-- config.color_scheme = 'PencilDark'
-- config.color_scheme = 'Popping and Locking'
-- config.color_scheme = 'Rasi (terminal.sexy)'
-- config.color_scheme = 'Rezza (terminal.sexy)'
-- config.color_scheme = 'Rosé Pine (Gogh)'
-- config.color_scheme = 'Rouge 2'
-- config.color_scheme = 'Royal' -- ****1/2
-- config.color_scheme = 'Sea Shells (Gogh)'
-- config.color_scheme = 'Seti'
-- config.color_scheme = 'shades-of-purple'
-- config.color_scheme = 'SpaceGray Eighties'
-- config.color_scheme = 'Tango (terminal.sexy)'
-- config.color_scheme = 'Twilight (dark) (terminal.sexy)'
-- config.color_scheme = 'VibrantInk'
-- config.color_scheme = 'Vice Alt (base16)'
-- config.color_scheme = 'Vice Dark (base16)'

-- config.font = wezterm.font 'CaskaydiaCove Nerd Font Mono Regular'
config.font = wezterm.font_with_fallback({
	"FiraCode Nerd Font Mono",
	"FiraCode Nerd Font Mono SemBd",
	"FiraCode Nerd Font Mono Ret",
	"FiraMono Nerd Font Mono",
	"DroidSansM Nerd Font",
	"DroidSansMono NF",
	"DroidSansMono",
	"Consolas",
	"Courier New",
	"monospace",
})

config.disable_default_key_bindings = true

--config.default_prog = { 'pwsh' }

config.keys = {
	{
		key = "T",
		mods = "CTRL|SHIFT",
		action = wezterm.action.ShowLauncher,
	},
	{
		key = "T",
		mods = "SUPER",
		action = wezterm.action.ShowLauncher,
	},
}
--   {
--     key = ',',
--     mods = 'CMD',
--     action = act.SpawnCommandInNewTab {
--       cwd = os.getenv('WEZTERM_CONFIG_DIR'),
--       set_environment_variables = {
--         TERM = 'screen-256color',
--       },
--       args = {
--         'code',
--         os.getenv('WEZTERM_CONFIG_FILE'),
--       },
--     },
--   },
--   {
--     key = 'R',
--     mods = 'CMD|SHIFT',
--     action = act.PromptInputLine {
--       description = 'Enter new name for tab',
--       action = wezterm.action_callback(function(window, _, line)
--         -- line will be `nil` if they hit escape without entering anything
--         -- An empty string if they just hit enter
--         -- Or the actual line of text they wrote
--         if line then
--           window:active_tab():set_title(line)
--         end
--       end),
--     },
--   },
--   -- other keys
--   -- {
--   --   key = "n",
--   --   mods = "CTRL",
--   --   action = wezterm.action.SpawnCommandInNewTab({
--   --     args = {"code ."}
--   --   })
--   -- },
-- }

config.window_background_gradient = {
	-- Can be "Vertical" or "Horizontal".  Specifies the direction
	-- in which the color gradient varies.  The default is "Horizontal",
	-- with the gradient going from left-to-right.
	-- Linear and Radial gradients are also supported; see the other
	-- examples below
	orientation = "Vertical",

	-- Specifies the set of colors that are interpolated in the gradient.
	-- Accepts CSS style color specs, from named colors, through rgb
	-- strings and more
	colors = {
		"#0f0c29",
		"#302b63",
		"#24243e",
	},

	-- Instead of specifying `colors`, you can use one of a number of
	-- predefined, preset gradients.
	-- A list of presets is shown in a section below.
	-- preset = "Warm",

	-- Specifies the interpolation style to be used.
	-- "Linear", "Basis" and "CatmullRom" as supported.
	-- The default is "Linear".
	interpolation = "Linear",

	-- How the colors are blended in the gradient.
	-- "Rgb", "LinearRgb", "Hsv" and "Oklab" are supported.
	-- The default is "Rgb".
	blend = "Rgb",

	-- To avoid vertical color banding for horizontal gradients, the
	-- gradient position is randomly shifted by up to the `noise` value
	-- for each pixel.
	-- Smaller values, or 0, will make bands more prominent.
	-- The default value is 64 which gives decent looking results
	-- on a retina macbook pro display.
	-- noise = 64,

	-- By default, the gradient smoothly transitions between the colors.
	-- You can adjust the sharpness by specifying the segment_size and
	-- segment_smoothness parameters.
	-- segment_size configures how many segments are present.
	-- segment_smoothness is how hard the edge is; 0.0 is a hard edge,
	-- 1.0 is a soft edge.

	-- segment_size = 11,
	-- segment_smoothness = 0.0,
}
config.window_background_gradient = null
config.prefer_to_spawn_tabs = true

wezterm.on("format-tab-title", function(tab, tabs, panes, config, hover, max_width)
	local pane_title = tab.active_pane.title
	local user_title = tab.active_pane.user_vars.panetitle

	if user_title ~= nil and #user_title > 0 then
		pane_title = user_title
	end

	return {
		-- {Background={Color="blue"}},
		-- {Foreground={Color="white"}},
		{ Text = " " .. pane_title .. " " },
	}
end)

-- # First and only argument is the desired term title
-- function rename_wezterm_title { printf "\x1b]1337;SetUserVar=panetitle=%s\x07" "$(echo -n "$*" | base64)"; }; rename_wezterm_title Serial:$(hostname)

-- wezterm.on("merge_all_windows", function(window, pane)
--   local workspace = wezterm.mux.get_active_workspace()
--   local all_windows = wezterm.mux.all_windows()

--   -- Find the first window in the workspace to move all tabs into
--   local target_window = nil
--   for _, win in ipairs(all_windows) do
--     if win:get_workspace() == workspace then
--       target_window = win
--       break
--     end
--   end

--   if not target_window then return end

--   -- Move all tabs from other windows into target_window
--   for _, win in ipairs(all_windows) do
--     if win ~= target_window and win:get_workspace() == workspace then
--       for _, tab in ipairs(win:tabs()) do
--         tab:move_to_window(target_window)
--       end
--       -- Close the now empty window
--       win:perform_action(wezterm.action.CloseCurrentPane { confirm = false }, win:active_pane())
--     end
--   end
-- end)

-- and finally, return the configuration to wezterm
return config
