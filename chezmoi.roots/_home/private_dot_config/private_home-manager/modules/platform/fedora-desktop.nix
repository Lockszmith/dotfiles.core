{ config, pkgs, lib, ... }:

let
  cfg = config.sz.platform.fedoraDesktop;

  dedupHelper = pkgs.writeShellScript "dedup-desktop-helper" ''
    exec ${pkgs.python3}/bin/python3 ${../activations/dedup-desktop-entries.py} "$@"
  '';
in
{
  options.sz.platform.fedoraDesktop = {
    enable = lib.mkEnableOption "Fedora/KDE desktop entry sync workarounds";

    packageDesktopStrips = lib.mkOption {
      type = lib.types.attrsOf (lib.types.listOf lib.types.str);
      default = { };
      description = ''
        Desktop basenames to remove from selected nix packages at build time when
        equivalent system entries exist. Keys match home.packages attribute names.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    sz.platform.fedoraDesktop.packageDesktopStrips = lib.mkDefault {
      libreoffice = [
        "calc.desktop"
        "writer.desktop"
        "impress.desktop"
        "startcenter.desktop"
      ];
    };

    # GNOME/KDE on Fedora do not reliably index ~/.nix-profile/share/applications;
    # copy entries and icons into ~/.local/share for the app launcher.
    home.activation.syncNixDesktopEntries = lib.hm.dag.entryAfter [ "installPackages" ] ''
      appdir="$HOME/.local/share/applications"
      icondir="$HOME/.local/share/icons"
      pixmapdir="$HOME/.local/share/pixmaps"
      mkdir -p "$appdir" "$icondir" "$pixmapdir"
      for desktop in "$HOME/.nix-profile/share/applications/"*.desktop; do
        [ -f "$desktop" ] || continue
        if ! ${dedupHelper} should-sync "$desktop"; then
          continue
        fi
        base=$(basename "$desktop")
        cp -Lf "$desktop" "$appdir/$base"
        chmod a+r "$appdir/$base"
      done
      if [ -d "$HOME/.nix-profile/share/icons" ]; then
        cp -rL "$HOME/.nix-profile/share/icons/." "$icondir/" 2>/dev/null || true
      fi
      if [ -d "$HOME/.nix-profile/share/pixmaps" ]; then
        cp -rL "$HOME/.nix-profile/share/pixmaps/." "$pixmapdir/" 2>/dev/null || true
      fi
      if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$appdir" 2>/dev/null || true
      fi
      if [ -d "$icondir/hicolor" ] && command -v gtk-update-icon-cache >/dev/null; then
        chmod -R u+w "$icondir" 2>/dev/null || true
        gtk-update-icon-cache -f -t "$icondir/hicolor" 2>/dev/null || true
      fi
      case "''${XDG_CURRENT_DESKTOP:-}''${DESKTOP_SESSION:+:}''$DESKTOP_SESSION" in
        *KDE*|*kde*)
          rm -f "$HOME"/.cache/ksycoca6_*
          if command -v kbuildsycoca6 >/dev/null; then
            kbuildsycoca6 --noincremental || true
          fi
          ;;
      esac
    '';
  };
}
