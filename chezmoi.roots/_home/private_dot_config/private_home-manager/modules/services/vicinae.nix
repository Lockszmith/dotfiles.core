{ config, pkgs, lib, ... }:

let
  cfg = config.services.vicinae;

  vicinaeGnomeShortcutsScript = pkgs.writeShellScript "vicinae-gnome-shortcuts" ''
    set -euo pipefail
    case "''${XDG_CURRENT_DESKTOP:-}" in
      *GNOME*|*gnome*) ;;
      *) exit 0 ;;
    esac
    command -v dconf >/dev/null || exit 0
    export DBUS_SESSION_BUS_ADDRESS="''${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
    vicinae_bin="${config.home.homeDirectory}/.nix-profile/bin/vicinae"
    [ -x "$vicinae_bin" ] || exit 0
    dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings \
      "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/', '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/']"
    dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/name "'Vicinae'"
    dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/command "'$vicinae_bin toggle'"
    dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/binding "'<Super><Alt>space'"
    dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/name "'Vicinae Clipboard History'"
    dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/command "'$vicinae_bin vicinae://launch/clipboard/history?toggle=true'"
    dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/binding "'<Super><Alt>v'"
  '';
in
{
  config = lib.mkIf cfg.enable {
    # Vicinae binary cache (user nix.conf; Determinate also reads extra-* keys here)
    xdg.configFile."nix/nix.conf".text = ''
      extra-substituters = https://vicinae.cachix.org
      extra-trusted-public-keys = vicinae.cachix.org-1:1kDrfienkGHPYbkpNj1mWTr7Fm1+zcenzgTizIcI3oc=
    '';

    systemd.user.services.vicinae.service.ExecStart = lib.mkForce
      "${config.services.vicinae.package}/bin/vicinae server --replace";

    services.vicinae = {
      systemd = {
        environment = {
          # Native Qt Wayland/EGL crashes on NVIDIA; XWayland works on Plasma and Hyprland.
          USE_LAYER_SHELL = 0;
          QT_QPA_PLATFORM = "xcb";
          DISPLAY = ":0";
          __NV_DISABLE_EXPLICIT_SYNC = 1;
        };
      };
    };

    home.activation.vicinaeGnomeShortcuts = lib.hm.dag.entryAfter [ "patchVicinaeDesktop" ] ''
      $DRY_RUN_CMD ${vicinaeGnomeShortcutsScript}
    '';

    systemd.user.services.vicinae-gnome-shortcuts = {
      Unit = {
        Description = "Configure Vicinae GNOME keyboard shortcuts (toggle on Meta+Alt+Space)";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "oneshot";
        ExecStart = vicinaeGnomeShortcutsScript;
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

    home.activation.vicinaePlasmaShortcut = lib.hm.dag.entryAfter [ "vicinaeGnomeShortcuts" ] ''
      if command -v kwriteconfig6 >/dev/null; then
        kwriteconfig6 --file kglobalshortcutsrc --group services --group vicinae.desktop \
          --key toggle "Meta+Alt+Space,none,Toggle Vicinae Window"
        kwriteconfig6 --file kglobalshortcutsrc --group services --group vicinae.desktop \
          --key clipboard "Meta+Alt+V,none,Vicinae Clipboard History"
      fi
      if command -v gdbus >/dev/null && qdbus org.kde.kglobalaccel >/dev/null 2>&1; then
        gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
          --method org.kde.KGlobalAccel.doRegister \
          "['vicinae.desktop', 'toggle', 'Vicinae', 'Toggle Vicinae Window']" \
          >/dev/null 2>&1 || true
        gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
          --method org.kde.KGlobalAccel.setShortcutKeys \
          "['vicinae.desktop', 'toggle', 'Vicinae', 'Toggle Vicinae Window']" \
          "[([402653216, 0, 0, 0],)]" 4 >/dev/null 2>&1 || true
      fi
    '';
  };
}
