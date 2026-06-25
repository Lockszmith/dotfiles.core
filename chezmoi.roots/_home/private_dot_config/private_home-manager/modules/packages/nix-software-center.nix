{ config, pkgs, lib, nix-software-center, ... }:

let
  cfg = config.sz.packages.nix-software-center;
in
{
  options.sz.packages.nix-software-center.enable = lib.mkEnableOption "Nix Software Center";

  config = lib.mkIf cfg.enable {
    home.packages = [
      nix-software-center.packages.${pkgs.stdenv.hostPlatform.system}.default
    ];
  };
}
