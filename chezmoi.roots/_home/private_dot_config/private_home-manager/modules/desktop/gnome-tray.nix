{ config, pkgs, lib, ... }:

let
  cfg = config.sz.desktop.gnomeTray;
  extensionId = pkgs.gnomeExtensions.appindicator.extensionUuid;
in
{
  options.sz.desktop.gnomeTray.enable = lib.mkEnableOption ''
    GNOME AppIndicator/KStatusNotifier tray support (Beeper, Slack, Zoom background icons)
  '';

  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.gnomeExtensions.appindicator ];

    home.activation.gnomeTrayExtension = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      if command -v dconf >/dev/null; then
        export DBUS_SESSION_BUS_ADDRESS="''${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
        current=$(dconf read /org/gnome/shell/enabled-extensions 2>/dev/null || echo "[]")
        if ! echo "$current" | grep -Fq "${extensionId}"; then
          new=$(echo "$current" | ${pkgs.jq}/bin/jq -c --arg ext "${extensionId}" '. + [$ext]')
          dconf write /org/gnome/shell/enabled-extensions "$new"
        fi
      fi
    '';
  };
}
