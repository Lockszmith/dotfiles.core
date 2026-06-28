{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.zoom;

  zoomUs = pkgs.zoom-us.override {
    gnomeXdgDesktopPortalSupport = true;
    targetPkgsFixed = with pkgs; [
      gsettings-desktop-schemas
      gnome-settings-daemon
      xdg-utils
    ];
  };

  browserBin = "$HOME/.nix-profile/bin/zen-browser";
  fallbackBrowserBin = "$HOME/.nix-profile/bin/ungoogled-chromium";

  zoom = pkgs.writeShellScriptBin "zoom" ''
    # GNOME/vicinae launchers may omit DISPLAY; zoom-us bwrap needs it for XWayland.
    export DISPLAY="''${DISPLAY:-:0}"
    export QT_QPA_PLATFORM=xcb
    export GDK_BACKEND=x11
    export PATH="$HOME/.nix-profile/bin:/usr/bin:/bin:$PATH"
    if [ -z "''${BROWSER:-}" ]; then
      if [ -x ${browserBin} ]; then
        export BROWSER=${browserBin}
      elif [ -x ${fallbackBrowserBin} ]; then
        export BROWSER=${fallbackBrowserBin}
      fi
    fi
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
      pkgs.xdg-utils
    ];

    home.activation.zoomMimeHandlers = lib.hm.dag.entryAfter [
      "syncNixDesktopEntries"
      "dedupDesktopEntries"
    ] ''
      desktop="$HOME/.local/share/applications/zoom.desktop"
      if [ -f "$desktop" ]; then
        if command -v xdg-mime >/dev/null; then
          for mime in \
            x-scheme-handler/zoommtg \
            x-scheme-handler/zoomus \
            x-scheme-handler/tel \
            x-scheme-handler/callto \
            x-scheme-handler/zoomphonecall \
            x-scheme-handler/zoomphonesms \
            x-scheme-handler/zoomcontactcentercall \
            application/x-zoom; do
            xdg-mime default zoom.desktop "$mime" 2>/dev/null || true
          done
        fi
      fi
    '';
  };
}
