{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.doublecmd;
  doublecmd = pkgs.writeShellScriptBin "doublecmd" ''
    export QT_QPA_PLATFORM=xcb
    exec ${pkgs.doublecmd}/bin/doublecmd "$@"
  '';
  doublecmd-desktop = pkgs.makeDesktopItem {
    name = "doublecmd";
    desktopName = "Double Commander";
    genericName = "File Manager";
    comment = "Dual-panel file manager";
    exec = "${doublecmd}/bin/doublecmd %F";
    tryExec = "${doublecmd}/bin/doublecmd";
    icon = "doublecmd";
    categories = [ "System" "FileManager" ];
    terminal = false;
    startupNotify = true;
  };
in
{
  options.sz.packages.doublecmd.enable = lib.mkEnableOption "Double Commander file manager";

  config = lib.mkIf cfg.enable {
    home.packages = [
      doublecmd
      doublecmd-desktop
      (lib.lowPrio pkgs.doublecmd)
    ];
  };
}
