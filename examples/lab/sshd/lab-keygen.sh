#!/bin/sh
# Create the lab's SSH keys in /keys once, and the client files rusty-conduit-ssh mounts.
# Re-running keeps existing keys. Client files belong to UID 10001, the image user of
# ghcr.io/jpbaking/rusty-conduit-ssh, so this works on any Docker host without chown.
set -eu
d=/keys
host=${LAB_SSH_HOST:-sshd}

[ -f "$d/id_ed25519" ] || ssh-keygen -q -t ed25519 -N '' -C rcs-lab-client -f "$d/id_ed25519"
[ -f "$d/ssh_host_ed25519_key" ] || ssh-keygen -q -t ed25519 -N '' -C rcs-lab-host -f "$d/ssh_host_ed25519_key"

cp "$d/id_ed25519.pub" "$d/authorized_keys"
printf '%s %s\n' "$host" "$(cut -d' ' -f1,2 "$d/ssh_host_ed25519_key.pub")" > "$d/known_hosts"
cat > "$d/config" <<CONF
Host lab
    HostName $host
    User lab
    IdentityFile /keys/id_ed25519
    UserKnownHostsFile /keys/known_hosts
    BatchMode yes
    UpdateHostKeys no
CONF

chmod 755 "$d"
chmod 644 "$d/authorized_keys" "$d"/*.pub
chmod 600 "$d/ssh_host_ed25519_key"
chown 10001:10001 "$d/id_ed25519" "$d/known_hosts" "$d/config"
chmod 600 "$d/id_ed25519" "$d/known_hosts" "$d/config"
echo "lab keys ready in $d"
