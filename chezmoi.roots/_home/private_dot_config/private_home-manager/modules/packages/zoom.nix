{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.zoom;

  zoomUs = pkgs.zoom-us.override {
    gnomeXdgDesktopPortalSupport = true;
    targetPkgsFixed = with pkgs; [
      gsettings-desktop-schemas
      gnome-settings-daemon
    ];
  };

  zoom = pkgs.writeShellScriptBin "zoom" ''
    # GNOME/vicinae launchers may omit DISPLAY; zoom-us bwrap needs it for XWayland.
    export DISPLAY="''${DISPLAY:-:0}"
    export QT_QPA_PLATFORM=xcb
    export GDK_BACKEND=x11
    exec ${zoomUs}/bin/zoom "$@"
  '';

  zoom-share = pkgs.buildEnv {
    name = "zoom-share";
    paths = [ zoomUs ];
    pathsToLink = [
      "/share/pixmaps"
      "/share/mime"
    ];
  };

  zoom-desktop = pkgs.makeDesktopItem {
    name = "zoom";
    desktopName = "Zoom Workplace";
    genericName = "Video Conference";
    comment = "Zoom video conferencing";
    exec = "${zoom}/bin/zoom %U";
    tryExec = "${zoom}/bin/zoom";
    icon = "Zoom";
    categories = [ "Network" "VideoConference" ];
    mimeTypes = [
      "x-scheme-handler/zoommtg"
      "x-scheme-handler/zoomus"
      "x-scheme-handler/tel"
      "x-scheme-handler/callto"
      "x-scheme-handler/zoomphonecall"
      "x-scheme-handler/zoomphonesms"
      "x-scheme-handler/zoomcontactcentercall"
      "application/x-zoom"
    ];
    terminal = false;
    startupNotify = true;
    startupWMClass = "zoom";
  };
in
{
  options.sz.packages.zoom.enable = lib.mkEnableOption "Zoom video conferencing";

  config = lib.mkIf cfg.enable {
    home.packages = [
      zoom
      zoom-desktop
      zoom-share
    ];
  };
}
