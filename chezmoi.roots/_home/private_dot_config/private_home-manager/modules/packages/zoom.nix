{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.zoom;
  zoom = pkgs.writeShellScriptBin "zoom" ''
    export QT_QPA_PLATFORM=xcb
    exec ${pkgs.zoom-us}/bin/zoom "$@"
  '';
  zoom-desktop = pkgs.makeDesktopItem {
    name = "zoom";
    desktopName = "Zoom Workplace";
    genericName = "Video Conference";
    comment = "Zoom video conferencing";
    exec = "${zoom}/bin/zoom";
    tryExec = "${zoom}/bin/zoom";
    icon = "Zoom";
    categories = [ "Network" "VideoConference" ];
    terminal = false;
    startupNotify = true;
  };
in
{
  options.sz.packages.zoom.enable = lib.mkEnableOption "Zoom video conferencing";

  config = lib.mkIf cfg.enable {
    home.packages = [
      zoom
      zoom-desktop
      (lib.lowPrio pkgs.zoom-us)
    ];
  };
}
