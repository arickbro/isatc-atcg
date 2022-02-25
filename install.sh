sudo apt update -y 
sudo apt upgrade -y
sudo apt install python3 python3-pip
sudo pip3 install Flask
sudo pip3 install flask_cors
sudo pip3 install pyserial

mkdir -p /home/pi/prod/
sudo cp -R * /home/pi/prod/
sudo cp install/isatc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable isatc.service
sudo systemctl start isatc.service

