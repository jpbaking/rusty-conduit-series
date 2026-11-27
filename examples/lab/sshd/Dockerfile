# Lab SSH server for the rusty-conduit-series examples. Dev and testing only.
# It stands in for a real bastion or homelab host, so the SSH examples run on their own.
FROM alpine:3.22

RUN apk add --no-cache openssh-server openssh-keygen curl \
    && adduser -D -s /bin/sh lab \
    && sed -i 's/^lab:!/lab:*/' /etc/shadow

COPY sshd_config /etc/ssh/sshd_config
COPY --chmod=0755 lab-keygen.sh /usr/local/bin/lab-keygen

EXPOSE 22
# sshd needs root to switch to the login user; this image exists only for the lab.
CMD ["/usr/sbin/sshd", "-D", "-e"]
