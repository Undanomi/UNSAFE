#!/bin/sh

set -eu

install -d -m 0755 /usr/local/lib/slsg

cat >/usr/local/lib/slsg/update-login-banner <<'SCRIPT'
#!/bin/sh

set -eu

addresses=""
attempt=0
while [ "$attempt" -lt 60 ]; do
  addresses="$(ip -o -4 address show up scope global 2>/dev/null \
    | awk '{sub(/\/.*/, "", $4); print $4}' \
    | sort -u \
    | paste -sd ' ' -)"
  [ -n "$addresses" ] && break
  attempt=$((attempt + 1))
  sleep 1
done

temporary_issue="$(mktemp /etc/issue.slsg.XXXXXX)"
trap 'rm -f "$temporary_issue"' EXIT HUP INT TERM
{
  printf '\nSLSG Security Lab Target\n'
  if [ -n "$addresses" ]; then
    printf 'Target IPv4 address(es): %s\n' "$addresses"
  else
    printf 'Target IPv4 address: waiting for DHCP (no address assigned)\n'
  fi
  printf 'Login user: ubuntu\n\n'
} >"$temporary_issue"
chmod 0644 "$temporary_issue"
mv -f "$temporary_issue" /etc/issue
trap - EXIT HUP INT TERM
SCRIPT
chmod 0755 /usr/local/lib/slsg/update-login-banner

cat >/etc/systemd/system/slsg-login-banner.service <<'UNIT'
[Unit]
Description=Show the SLSG target IP address before console login
Wants=network-online.target getty-pre.target
After=network-online.target
Before=getty-pre.target

[Service]
Type=oneshot
ExecStart=/usr/local/lib/slsg/update-login-banner
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable slsg-login-banner.service
