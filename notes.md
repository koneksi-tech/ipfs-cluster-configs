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