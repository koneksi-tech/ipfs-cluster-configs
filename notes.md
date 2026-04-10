# server 5 openresty command 
validate: sudo openresty -t -c /etc/nginx/nginx.conf
restart: sudo systemctl restart openresty-etcnginx --no-pager


# server  openresty command 
validate: sudo openresty -t -c /etc/nginx/nginx.conf
restart: sudo systemctl restart openresty

# nodes+instance ssh command
ssh -o PubkeyAuthentication=no ubuntu@160.202.162.18


node1: 
pass: J'OYZ4cYufQsZ,oEtx[7))$=#'=AEa 
user: koneksi01 - 160.202.162.17

node2: 
pass: zhsprtl13@$
user: ubuntu -  211.238.12.8
peer ID: 12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq

node3: 
pass: _3P)R10cv)vg(vm30CuR2.p1tirxJu 
user: koneksi- 
218.38.136.33
node4: 
pass: 0U9BA]~_K'XiQ#v@L0c1-!Vo-t7)mM 
user: koneksi - 218.38.136.34

node5: 
pass: zhsprtl13@$
user: ubuntu - 160.202.162.18



today:
- SU with Koneksi team
- setup server 5 as main load balancer for staging prod env
- try to fix the error-pin in the cluster
- still ongoing configuration for node 2 as replication node 

today:
- SU with Koneksi team
- sync with Aldrick for Vault issue
- re-run the Repinning script for CID's target is to repin all cid with allocation to repin in 4 allocation
- Done with node 2 configuration as replication node 

today:
- Migrate Staging env to Koneksi DO
- Migrate the data from old Db to new
- Setup terraform deployment for staging environment

today:
- Finalize the domain for staging UAT and Prod Environment
- Migrate the data from old Db to new
- Sync with Aldrick to resolve mongodb issue
- Plan and make diagram for kubernetes deploymnet in NHN cloud



======= NHN cluster ======


ipfs-1: ubuntu@125.6.39.137
access: ssh -i nhn-key-pair.pem ubuntu@125.6.39.137
ipfs-2: ubuntu@133.186.151.67
access: ssh -i nhn-key-pair.pem ubuntu@133.186.151.67
ipfs-3: ubuntu@133.186.151.108
access: ssh -i nhn-key-pair.pem ubuntu@133.186.151.108

metadata-manager-1: ubuntu@180.210.82.9
metadata-manager-2: ubuntu@133.186.159.168
metadata-manager-3: ubuntu@125.6.39.129

hdd-server-1: ubuntu@180.210.83.72
hdd-server-2: ubuntu@180.210.83.30
hdd-server-3: ubuntu@180.210.83.141

ssd-server-1: ubuntu@133.186.135.101
ssd-server-2: ubuntu@133.186.135.245
ssd-server-3: ubuntu@133.186.135.194



sudo ln -sfn /etc/nginx/sites-available/testbed-ipfs.koneksi.co.kr \
  /etc/nginx/sites-enabled/testbed-ipfs.koneksi.co.kr

sudo nginx -t && sudo systemctl reload nginx