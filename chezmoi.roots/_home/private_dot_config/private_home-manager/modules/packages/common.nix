{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.common;
in
{
  options.sz.packages.common.enable = lib.mkEnableOption "common CLI and desktop packages";

  config = lib.mkIf cfg.enable {
    home.packages = with pkgs; [
      cachix
      flameshot
      fsearch
      gping
      htop
      imagemagick
      nerdfetch
      rambox
      slack
      code-cursor
      wl-clipboard
      libreoffice
      xournalpp
      kdePackages.okular
      scantailor-advanced
      sane-backends
      nerd-fonts."m+"
      nerd-fonts.noto
    ];
  };
}
