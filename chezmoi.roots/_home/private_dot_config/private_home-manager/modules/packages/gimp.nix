{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.gimp;
in
{
  options.sz.packages.gimp.enable = lib.mkEnableOption "GIMP image editor";

  config = lib.mkIf cfg.enable {
    home.packages = with pkgs; [
      gimp
      gimpPlugins.gmic
    ];
  };
}
