{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.common;
  inherit (import ../lib/desktop-package.nix { inherit lib; }) stripPackageDesktopEntries;
  packageDesktopStrips = config.sz.platform.fedoraDesktop.packageDesktopStrips or { };
  stripOrKeep = name: pkg: stripPackageDesktopEntries pkg (packageDesktopStrips.${name} or [ ]);
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
      (stripOrKeep "libreoffice" libreoffice)
      xournalpp
      kdePackages.okular
      scantailor-advanced
      sane-backends
      nerd-fonts."m+"
      nerd-fonts.noto
    ];
  };
}
