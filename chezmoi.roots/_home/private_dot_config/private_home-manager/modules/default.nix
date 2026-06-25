{ ... }:

{
  imports = [
    ./core/identity.nix
    ./core/nixpkgs.nix
    ./core/home-manager.nix
    ./core/session.nix
    ./core/zsh.nix

    ./platform/generic-linux.nix
    ./platform/nvidia.nix
    ./platform/fedora-desktop.nix

    ./activations/set-login-shells.nix
    ./activations/set-nix-trusted-user.nix
    ./activations/patch-desktops.nix

    ./desktop/hyprland.nix
    ./desktop/plasma-keyboard.nix

    ./services/gearlever.nix
    ./services/browsers.nix
    ./services/vicinae.nix

    ./packages/common.nix
    ./packages/zen-browser.nix
    ./packages/doublecmd.nix
    ./packages/rustdesk.nix
    ./packages/zoom.nix
    ./packages/gimp.nix
    ./packages/gmic-qt.nix
    ./packages/rembg.nix
    ./packages/pinta.nix
    ./packages/ghostty.nix
    ./packages/nix-software-center.nix
    ./packages/winboat.nix
    ./packages/digikam.nix
  ];
}
