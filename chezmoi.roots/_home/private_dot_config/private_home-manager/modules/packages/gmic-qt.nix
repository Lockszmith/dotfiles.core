{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.gmic-qt;
  gmic-qt = pkgs.writeShellScriptBin "gmic-qt" ''
    export QT_QPA_PLATFORM=xcb
    exec ${pkgs.gmic-qt}/bin/gmic_qt "$@"
  '';
  gmic-qt-desktop = pkgs.makeDesktopItem {
    name = "gmic-qt";
    desktopName = "G'MIC-Qt";
    genericName = "Image Processing";
    comment = "G'MIC plugin for GIMP and standalone filter UI";
    exec = "${gmic-qt}/bin/gmic-qt";
    tryExec = "${gmic-qt}/bin/gmic-qt";
    icon = "gimp";
    categories = [ "Graphics" "2DGraphics" ];
    terminal = false;
    startupNotify = true;
  };
in
{
  options.sz.packages.gmic-qt.enable = lib.mkEnableOption "G'MIC-Qt filter UI";

  config = lib.mkIf cfg.enable {
    home.packages = [
      gmic-qt
      gmic-qt-desktop
    ];
  };
}
