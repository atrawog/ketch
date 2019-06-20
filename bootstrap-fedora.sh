#!/bin/bash
dnf makecache
dnf install -y openssh-server ansible curl python3-pip
systemctl enable --now sshd
cat /dev/zero | ssh-keygen -q -N ""
curl -L https://github.com/atrawog.keys >> /root/.ssh/authorized_keys
alternatives --install /usr/bin/python python /usr/bin/python3.7 2
pip3 install invoke certifi hetzner
dnf upgrade -y
dnf clean all
