from __future__ import (division,print_function)

from invoke import task
import os  
import random
import yaml
import configparser
import CloudFlare
from hetzner.robot import Robot
from hetznercloud import HetznerCloudClientConfiguration, HetznerCloudClient

MASTER_NAME="c7lvmmaster"
MASTERGCP_NAME="c7gcpmaster"
MASTERMICRO_NAME="c7micro"
CLONE_NAME="c7vm1"
MASTER_MEMORY="2048"
CLONE_MEMORY="2048"
DISKSTORE="/var/lib/libvirt/images"
MASTER_SIZE="2G"
MASTERMICRO_SIZE="1G"
CLONE_SIZE="20G"
CENTOS7_MINIMAL="CentOS-7-x86_64-Minimal-1810"
CENTOS7_NETWORK="CentOS-7-x86_64-NetInstall-1810"
MAC="52:54:00:%02x:%02x:%02x" % (random.randint(0, 255),random.randint(0, 255),random.randint(0, 255))
IP="192.168.200.10"
CFG="ketch.cfg"
HOSTS="hosts.ini"
HETZNER_SERVER='hetznerserver'
HETZNER_CLOUD='hetznercloud'


def create_disk(c,disk,size,fmt='qcow2' ):
    if not os.path.exists(disk): 
        cmd="qemu-img create -f {fmt} -o size={size} {disk}".format(size=size,disk=disk,fmt=fmt)
        c.sudo(cmd, pty=True)


@task(help={'name': "Name of VM"})
def mastercloud(c,name=MASTER_NAME,memory=MASTER_MEMORY,diskstore=DISKSTORE,size=MASTER_SIZE,iso=CENTOS7_MINIMAL):
    disk="{diskstore}/{name}.qcow2".format(diskstore=diskstore,name=name)
    install_iso="{diskstore}/{name}.iso".format(diskstore=diskstore,name=iso)
    create_disk(c,disk=disk,size=size)
    install="virt-install --name {name} --memory {memory} --disk {disk},device=disk,bus=virtio --location {location} --os-type linux --os-variant centos7.0  --virt-type kvm --network network=default --initrd-inject templates/ks.cfg --extra-args='ks=file:/ks.cfg console=tty0 console=ttyS0,115200n8' --console pty,target_type=serial --accelerate --nographics --noreboot".format(name=name,memory=memory,disk=disk,location=install_iso)
    c.sudo(install, pty=True,warn=True)


@task(help={'name': "Name of VM"})
def mastergcp (c,name=MASTERGCP_NAME,memory=MASTER_MEMORY,diskstore=DISKSTORE,size=MASTER_SIZE,iso=CENTOS7_MINIMAL,fmt='qcow2'):
    disk="{diskstore}/{name}.{fmt}".format(diskstore=diskstore,name=name,fmt=fmt)
    install_iso="{diskstore}/{name}.iso".format(diskstore=diskstore,name=iso)
    create_disk(c,disk=disk,size=size,fmt=fmt)
    install="virt-install --name {name} --memory {memory} --disk {disk},device=disk,bus=virtio --location {location} --os-type linux --os-variant centos7.0  --virt-type kvm --network network=default --initrd-inject templates/ksgc7.cfg --extra-args='ks=file:/ksgc7.cfg console=tty0 console=ttyS0,38400n8d ' --console pty,target_type=serial --accelerate --nographics --noreboot".format(name=name,memory=memory,disk=disk,location=install_iso)
    c.sudo(install, pty=True,warn=True)

@task()
def mastermicro (c,name=MASTERMICRO_NAME,memory=MASTER_MEMORY,diskstore=DISKSTORE,size=MASTER_SIZE,iso=CENTOS7_MINIMAL,fmt='qcow2'):
    disk="{diskstore}/{name}.{fmt}".format(diskstore=diskstore,name=name,fmt=fmt)
    install_iso="{diskstore}/{name}.iso".format(diskstore=diskstore,name=iso)
    create_disk(c,disk=disk,size=size,fmt=fmt)
    install="virt-install --name {name} --memory {memory} --disk {disk},device=disk,bus=virtio --location {location} --os-type linux --os-variant centos7.0  --virt-type kvm --network network=default --initrd-inject templates/ks7micro.cfg --extra-args='ks=file:/ks7micro.cfg console=tty0 console=ttyS0,38400n8d ' --console pty,target_type=serial --accelerate --nographics --noreboot".format(name=name,memory=memory,disk=disk,location=install_iso)
    c.sudo(install, pty=True,warn=True)

    
@task()
def gcpupload (c,name=MASTERGCP_NAME,memory=MASTER_MEMORY,diskstore=DISKSTORE,size=MASTER_SIZE,iso=CENTOS7_MINIMAL,fmt='qcow2'):
    with c.cd(diskstore):
        disk="{name}.{fmt}".format(name=name,fmt=fmt)
        tar="{name}.{fmt}".format(name=name,fmt='tar.gz')
        if not os.path.exists(tar):
            c.run("qemu-img convert -f raw -O {fmt} {disk} disk.raw".format(tar=tar,disk=disk,fmt=fmt),pty=True,warn=True)
            c.run("tar --format=oldgnu -Sczf {tar} disk.raw".format(tar=tar),pty=True,warn=True)
            c.run("gsutil cp {tar} gs://{name}".format(tar=tar,name=name),pty=True,warn=True)
            c.run("gcloud compute images create {name} --source-uri gs://{name}/{name}.tar.gz".format(name=name),pty=True,warn=True)
        c.run("gcloud compute images list --no-standard-images",pty=True,warn=True)

@task()
def bucketcreate(c,name=MASTERGCP_NAME):
    c.run("gsutil mb gs://%s"%name)
    


def create_iso(c,name=CLONE_NAME,diskstore=DISKSTORE,ip=IP):
    
    md="""instance-id: id-00001
local-hostname: {name}
""".format(name=name)

    ud="""#cloud-config
ssh_pwauth: False
disable_root: False
bootcmd:
 - lvresize -L 4G /dev/kvg/root
 - resize2fs /dev/kvg/root 
"""
    nc="""version: 1
config:
  - type: physical
    name: eth0
    subnets:
      - type: static
        ipv4: true
        address: {ip}
        netmask: 255.255.255.0
        gateway: 192.168.200.1
        control: auto
  - type: nameserver
    address: 192.168.200.1
    search:
      - trawi.org
""".format(ip=ip)

    vnet="""<network>
  <name>vnet</name>
  <uuid>a6c5ce15-b40d-4f11-bcdf-e7e78d2e3b32</uuid>
  <forward mode='nat'>
    <nat>
      <port start='1024' end='65535'/>
    </nat>
  </forward>
  <bridge name='vnet' stp='on' delay='0'/>
  <mac address='52:54:00:be:8f:78'/>
  <ip address='192.168.200.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.200.200' end='192.168.200.254'/>
    </dhcp>
  </ip>
</network>
"""

    meta_data=open("meta-data","w")
    user_data=open("user-data","w")
    network_config=open("network-config","w")
    
    meta_data.write(md)
    user_data.write(ud)
    network_config.write(nc)
    meta_data.close()
    user_data.close()
    network_config.close()
    
    clone_iso="{diskstore}/{name}.iso".format(diskstore=diskstore,name=name)
    rm="rm -f {clone_iso}".format(clone_iso=clone_iso)
    geniso="genisoimage -output {clone_iso} -input-charset utf-8 -volid cidata -joliet -r meta-data user-data network-config".format(clone_iso=clone_iso)
    if not os.path.exists(clone_iso):
        c.run(rm,pty=True,warn=True)
        c.run(geniso,pty=True,warn=True)

    return clone_iso


def clone_master(c,master=MASTER_NAME,clone=CLONE_NAME,diskstore=DISKSTORE,memory=CLONE_MEMORY,size=CLONE_SIZE,ip=IP):
    disk_master="{diskstore}/{name}.qcow2".format(diskstore=diskstore,name=master)
    if not os.path.exists(disk_master):
        print("Run create-master first")
        exit(1) 
    disk_clone="{diskstore}/{name}.qcow2".format(diskstore=diskstore,name=clone)
    clone_iso=create_iso(c,diskstore=diskstore,name=clone,ip=ip)
    create="qemu-img create -f qcow2 -o preallocation=metadata {disk_clone} {size}".format(disk_clone=disk_clone,size=size)
    resize="virt-resize --expand /dev/sda2 {disk_master} {disk_clone}".format(disk_master=disk_master,disk_clone=disk_clone)
    install="virt-install --name {name} --memory {memory} --disk {disk},device=disk,bus=virtio --disk {clone_iso},device=cdrom --os-type linux --os-variant centos7.0  --virt-type kvm --network network=vnet --console pty,target_type=serial --accelerate --nographics --noreboot --import".format(name=clone,memory=memory,disk=disk_clone,clone_iso=clone_iso)
    start="virsh --connect qemu:///system start {clone}".format(clone=clone)
    if not os.path.exists(disk_clone): 
        c.sudo(create, pty=True,warn=True)
        c.sudo(resize, pty=True,warn=True)
        c.sudo(install, pty=True)
        c.sudo(start, pty=True,warn=True)


def update_cloudflare(username,token,domain,host,ip):
    print("Updating",host,domain,ip)
    cf = CloudFlare.CloudFlare(email=username, token=token)
    zones = {
        zone['name']: zone 
        for zone in cf.zones.get()
    }
    
    zone_id = zones[domain]['id']
   
    dns_records = cf.zones.dns_records.get(zone_id, params={'name':host+ '.' + domain})
    for dns_record in dns_records:
        dns_record_id = dns_record['id']
        cf.zones.dns_records.delete(zone_id, dns_record_id)
  
    cf.zones.dns_records.post(zone_id, data={'name':host, 'type':'A',    'content':ip})


def update_dns(name,ip,config=CFG):
    cfg = configparser.ConfigParser()
    cfg.read(config)
    update_cloudflare(cfg['cloudflare']['username'],cfg['cloudflare']['token'],cfg['cloudflare']['domain'],name,ip)
 

    
def update_inventory(group,name,ip,hosts=HOSTS):
    inventory = configparser.ConfigParser(allow_no_value=True,delimiters=(' '))
    inventory.read(hosts)
    if group not in inventory:
        inventory[group]={}
    inventory[group][name]="ansible_host=%s ansible_user=%s"%(ip,'root')
    with open(hosts, 'w') as configfile:
        inventory.write(configfile,space_around_delimiters=False)

  

@task()
def clones(c,master=MASTER_NAME,diskstore=DISKSTORE,memory=CLONE_MEMORY,size=CLONE_SIZE):
    clones=(('vm1','192.168.200.11'),('vm2','192.168.200.12'),('vm3','192.168.200.13'))
    for clone in clones:
        name,ip = clone
        clone_master(c,master,clone=name,diskstore=diskstore,memory=memory,size=CLONE_SIZE,ip=ip)
        update_dns(name,ip)
        update_inventory('local',name,ip)


@task()
def update(c):
    c.run("ansible-playbook site.yml")
    

@task()    
def hetzner(c,config=CFG,hosts=HOSTS):
    print("Fetching Hetzner Server")
    cfg = configparser.ConfigParser()
    cfg.read(config)
    
    inventory = configparser.ConfigParser(allow_no_value=True,delimiters=(' '))
    inventory.read(hosts)
    
    robot = Robot(cfg['hetzner']['username'], cfg['hetzner']['password'])
    configuration = HetznerCloudClientConfiguration().with_api_key(cfg['hetzner']['token']).with_api_version(1)
    client = HetznerCloudClient(configuration)
    
    #all_servers = client.servers().get_all() # gets all the servers as a generator
    all_servers_list = list(client.servers().get_all()) # gets all the servers as a list
    
    for server in all_servers_list:
        inventory[HETZNER_CLOUD][server.name]="ansible_host=%s ansible_user=%s"%(server.public_net_ipv4,cfg['ansible']['username'])
        update_dns(server.name,server.public_net_ipv4)
        #update_cloudflare(DOMAIN,server.name,server.public_net_ipv4)
    
    print("Fetching Hetzner Cloud")
    for server in robot.servers:
        inventory[HETZNER_SERVER][server.name]="ansible_host=%s ansible_user=%s"%(server.ip,cfg['ansible']['username'])
        update_dns(server.name,server.ip)
       # update_cloudflare(DOMAIN,server.name,server.ip)
    
    with open(hosts, 'w') as configfile:
        inventory.write(configfile,space_around_delimiters=False)    


@task()
def hosts(c,hosts=HOSTS):
    inventory = configparser.ConfigParser(allow_no_value=True,delimiters=(' '))
    inventory.read(hosts)

    if 'local' not in inventory:
        inventory['local']={}
    inventory['local']['localhost']="ansible_host=127.0.0.1 ansible_user=root ansible_python_interpreter=/usr/bin/python3"


    yaml.warnings({'YAMLLoadWarning': False})
    site = open("site.yml", "r")
    items = yaml.load_all(site)
    for i in items:
        for j in i:
            hs=(j['hosts'].split(','))
            for h in hs:
                host= (h.strip())
                if host not in inventory and host !='all':
                    inventory[host]={}
  
    with open(hosts, 'w') as configfile:
        inventory.write(configfile,space_around_delimiters=False)    

