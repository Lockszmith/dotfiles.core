{ config, pkgs, lib, ... }:

let
  cfg = config.sz.desktop.hyprland;
in
{
  options.sz.desktop.hyprland.enable = lib.mkEnableOption "Hyprland window manager";

  config = lib.mkIf cfg.enable {
    xdg.dataFile."wayland-sessions/hyprland.desktop".source =
      "${pkgs.hyprland}/share/wayland-sessions/hyprland.desktop";

    wayland.windowManager.hyprland = {
      enable = true;
      configType = "hyprlang";
      systemd.enable = true;
      settings = {
        monitor = ",preferred,auto,1";

        "$mod" = "SUPER";

        exec-once = [ ];

        env = [
          "XCURSOR_SIZE,24"
          "XDG_CURRENT_DESKTOP,Hyprland"
          "LIBVA_DRIVER_NAME,nvidia"
          "__GLX_VENDOR_LIBRARY_NAME,nvidia"
          "GBM_BACKEND,nvidia-drm"
        ];

        general = {
          gaps_in = 5;
          gaps_out = 10;
          border_size = 2;
          "col.active_border" = "rgba(33ccffee) rgba(00ff99ee) 45deg";
          "col.inactive_border" = "rgba(595959aa)";
          layout = "dwindle";
        };

        decoration = {
          rounding = 10;
          blur = {
            enabled = true;
            size = 3;
            passes = 1;
          };
        };

        animations = {
          enabled = true;
          bezier = "myBezier, 0.05, 0.9, 0.1, 1.05";
          animation = [
            "windows, 1, 7, myBezier"
            "windowsOut, 1, 7, default, popin 80%"
            "border, 1, 10, default"
            "fade, 1, 7, default"
            "workspaces, 1, 6, default"
          ];
        };

        input = {
          kb_layout = "us,il";
          kb_options = "caps:escape,shift:both_capslock";
          follow_mouse = 1;
          sensitivity = 0;
          touchpad = {
            natural_scroll = true;
          };
        };

        dwindle = {
          preserve_split = true;
        };

        bind = [
          "$mod, Return, exec, ghostty"
          "$mod, Q, killactive,"
          "$mod, F, fullscreen, 0"
          "$mod, Space, togglefloating,"
          "$mod, P, pseudo,"
          "$mod, E, exec, doublecmd"
          "$mod, B, exec, zen-browser"
          "$mod ALT, Space, exec, vicinae toggle"
          "$mod ALT, V, exec, vicinae 'vicinae://launch/clipboard/history?toggle=true'"
          ", Print, exec, flameshot gui"
          "$mod, left, movefocus, l"
          "$mod, right, movefocus, r"
          "$mod, up, movefocus, u"
          "$mod, down, movefocus, d"
        ]
        ++ lib.concatLists (map (i:
          let ws = toString (i + 1);
          in [
            "$mod, code:1${toString i}, workspace, ${ws}"
            "$mod SHIFT, code:1${toString i}, movetoworkspace, ${ws}"
          ]
        ) (lib.genList (x: x) 9));

        bindm = [
          "$mod, mouse:272, movewindow"
          "$mod, mouse:273, resizewindow"
        ];
      };
    };
  };
}
