{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.pinta;
  pinta = pkgs.writeShellScriptBin "pinta" ''
    export GDK_BACKEND=x11
    export GSK_RENDERER=cairo
    export __GLX_VENDOR_LIBRARY_NAME=mesa
    exec ${pkgs.pinta}/bin/pinta "$@"
  '';
in
{
  options.sz.packages.pinta.enable = lib.mkEnableOption "Pinta image editor";

  config = lib.mkIf cfg.enable {
    home.packages = [
      pinta
      (lib.lowPrio pkgs.pinta)
    ];
  };
}
