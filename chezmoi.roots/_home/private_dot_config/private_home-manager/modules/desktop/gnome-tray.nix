{ config, pkgs, lib, ... }:

let
  cfg = config.sz.desktop.gnomeTray;
  extensionPkg = pkgs.gnomeExtensions.appindicator;
  extensionId = extensionPkg.extensionUuid;

  gnomeTrayEnableScript = pkgs.writeShellScript "gnome-tray-enable" ''
    set -euo pipefail
    case "''${XDG_CURRENT_DESKTOP:-}" in
      *GNOME*|*gnome*) ;;
      *) exit 0 ;;
    esac
    command -v dconf >/dev/null || exit 0
    export DBUS_SESSION_BUS_ADDRESS="''${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"

    ext_dir="$HOME/.local/share/gnome-shell/extensions/${extensionId}"
    [ -d "$ext_dir" ] || exit 0

    if command -v gnome-extensions >/dev/null; then
      gnome-extensions enable "${extensionId}" 2>/dev/null || true
    fi

    current=$(dconf read /org/gnome/shell/enabled-extensions 2>/dev/null || echo "[]")
    if ! echo "$current" | grep -Fq "${extensionId}"; then
      new=$(echo "$current" | ${pkgs.jq}/bin/jq -c --arg ext "${extensionId}" '. + [$ext]')
      dconf write /org/gnome/shell/enabled-extensions "$new"
    fi
  '';
in
{
  options.sz.desktop.gnomeTray.enable = lib.mkEnableOption ''
    GNOME AppIndicator/KStatusNotifier tray support (Beeper, Slack, Zoom background icons)
  '';

  config = lib.mkIf cfg.enable {
    # GNOME scans ~/.local/share/gnome-shell/extensions before nix profile paths.
    xdg.dataFile."gnome-shell/extensions/${extensionId}".source =
      "${extensionPkg}/share/gnome-shell/extensions/${extensionId}";

    home.packages = [
      pkgs.libappindicator
      pkgs.libayatana-appindicator
    ];

    home.activation.gnomeTrayExtension = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD ${gnomeTrayEnableScript}
    '';

    systemd.user.services.gnome-tray-enable = {
      Unit = {
        Description = "Enable GNOME AppIndicator/KStatusNotifier tray extension at login";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "oneshot";
        ExecStart = gnomeTrayEnableScript;
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };
  };
}
