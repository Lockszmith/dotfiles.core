# Remove duplicate .desktop entries after syncNixDesktopEntries / gearleverApps.

{ config, pkgs, lib, ... }:

let
  cfg = config.sz.platform.fedoraDesktop;
in
{
  config = lib.mkIf cfg.enable {
    home.activation.dedupDesktopEntries = lib.hm.dag.entryAfter [
      "gearleverApps"
      "patchLibreOfficeStartcenterDesktop"
    ] ''
      appdir="$HOME/.local/share/applications"
      # zoom-us ships Zoom.desktop; HM zoom.nix provides zoom.desktop with full Exec path.
      rm -f "$appdir/Zoom.desktop"
      # LibreOffice nix entries are synced as libreoffice-*.desktop; drop legacy names.
      rm -f "$appdir/calc.desktop" "$appdir/writer.desktop" "$appdir/impress.desktop"
      # gearlever --integrate creates Beeper.desktop; drop HM beeper.desktop if both exist.
      if [ -f "$appdir/Beeper.desktop" ]; then
        rm -f "$appdir/beeper.desktop"
      fi
      if [ -d "$appdir" ] && command -v update-desktop-database >/dev/null; then
        update-desktop-database "$appdir" 2>/dev/null || true
      fi
    '';
  };
}
