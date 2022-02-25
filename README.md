# isatc-atcg

download raspberry pi imager 
https://downloads.raspberrypi.org/imager/imager_latest.exe

download 32bit raspbian lite
https://www.raspberrypi.com/software/operating-systems/#raspberry-pi-os-32-bit

**install OS**
```
connect SDcard to card reader 
select the image
select destination usb
click write
```

**connect raspberry pi to monitor and keyboard**
```
username:pi 
password:raspberry
```
**expand filesystem**
```
sudo raspi-config
go to advance options -> Expand Filesystem
click finish and reboot 
```
**configure wifi**
```
got to system-options -> wireless LAN
set SSID
set password
reboot
```

**configure hostname**
```
got to system-options -> Hostname
```

**install the application**
```
sudo apt install git -y 
git clone https://github.com/arickbro/isatc-atcg.git
cd isatc-atcg/
./install.sh
```

**change ethernet to static IP**
```
sudo nano /etc/dhcpcd.conf
```
```
interface eth0
static ip_address=10.196.172.28/28
static routers=10.196.172.29
static domain_name_servers=202.155.0.10 10.140.32.20 10.140.32.21
```
