#!/bin/bash
yum install -y openssh-server ansible
systemctl enable --now sshd
yum update -y
cat /dev/zero | ssh-keygen -q -N ""
curl -L https://github.com/atrawog.keys >> /root/.ssh/authorized_keys
alternatives --install /usr/bin/python python /usr/bin/python3.7 2
