sudo rm -r /usr/src/linux-headers-5.4.0-109
sudo rm -r /usr/src/linux-headers-5.4.0-109-generic
sudo rm -r /usr/lib/modules/5.4.0-109-generic
sudo rm -r /usr/src/linux-headers-5.4.0-110
sudo rm -r /usr/src/linux-headers-5.4.0-110-generic
sudo rm -r /usr/lib/modules/5.4.0-110-generic
sudo rm -r /usr/src/linux-headers-5.4.0-113
sudo rm -r /usr/src/linux-headers-5.4.0-113-generic
sudo rm -r /usr/lib/modules/5.4.0-113-generic
sudo journalctl --vacuum-size=100M
sudo df -h