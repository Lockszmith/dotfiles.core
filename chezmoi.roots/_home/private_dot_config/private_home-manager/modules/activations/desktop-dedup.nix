# Remove duplicate .desktop entries after syncNixDesktopEntries / gearleverApps / patchDuplicateDesktopActions.

{ config, pkgs, lib, ... }:

let
  cfg = config.sz.platform.fedoraDesktop;

  dedupScript = pkgs.writeShellScript "dedup-desktop-entries" ''
    exec ${pkgs.python3}/bin/python3 ${./dedup-desktop-entries.py} dedup
  '';
in
{
  config = lib.mkIf cfg.enable {
    home.activation.dedupDesktopEntries = lib.hm.dag.entryAfter [
      "gearleverApps"
      "patchDuplicateDesktopActions"
    ] ''
      $DRY_RUN_CMD ${dedupScript}
    '';
  };
}
