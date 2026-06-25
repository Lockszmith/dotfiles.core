{ config, lib, ... }:

let
  cfg = config.sz.activations.setNixTrustedUser;
  username = config.home.username;
  nixCustomConf = "/etc/nix/nix.custom.conf";
  sudoHint = "Re-run with: SUDO=sudo home-manager switch --flake .#sz";
in
{
  options.sz.activations.setNixTrustedUser.enable =
    lib.mkEnableOption "add user to nix trusted-users in /etc/nix/nix.custom.conf";

  config = lib.mkIf cfg.enable {
    home.activation.setNixTrustedUser = lib.hm.dag.entryAfter [ "installPackages" ] ''
      set +e
      nix_custom="${nixCustomConf}"
      user="${username}"

      if [ -f "$nix_custom" ] && grep -E '^trusted-users[[:space:]]*=' "$nix_custom" | grep -qw "$user"; then
        set -e
        exit 0
      fi

      if [ -z "''${SUDO:-}" ]; then
        echo "nix trusted-user: $user not listed in $nix_custom."
        echo "${sudoHint}"
        set -e
        exit 0
      fi

      $DRY_RUN_CMD "$SUDO" mkdir -p "$(dirname "$nix_custom")"
      if [ ! -f "$nix_custom" ]; then
        $DRY_RUN_CMD "$SUDO" touch "$nix_custom"
      fi

      if grep -qE '^trusted-users[[:space:]]*=' "$nix_custom"; then
        $DRY_RUN_CMD "$SUDO" sed -i "/^trusted-users[[:space:]]*=/s/\$/ $user/" "$nix_custom"
      else
        printf '%s\n' "trusted-users = $user" | $DRY_RUN_CMD "$SUDO" tee -a "$nix_custom" >/dev/null
      fi

      $DRY_RUN_CMD "$SUDO" systemctl restart nix-daemon 2>/dev/null || true
      set -e
    '';
  };
}
