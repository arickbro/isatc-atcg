import serial
import sqlite3
from isatc_helper import *
from random import randint
from email.utils import parseaddr

import time
import logging
import threading
import glob
import RPi.GPIO as GPIO

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

class ISATC:
    def __init__(self):
        self.isConnected = False
        self.conn = False
        self.status = {}
        self.deviceInfo = {}
        self.egcs = {}
        self.dir = {}
        self.txlog = {}
        self.lock = threading.Lock() 
        self.signal ={'ts':0,'signal':None}
        self.initRead = True
        self.startTime = time.time()
        self.ch1 = 18
        self.ch2 = 16
        
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.ch1, GPIO.OUT)
        GPIO.setup(self.ch2, GPIO.OUT)

        self.config = {}
        self.db = sqlite3.connect('/home/pi/prod/isatc.db',check_same_thread=False)
        self.get_config_from_db()

        self.connect()
        self.daemon = threading.Thread(target=self.keep_alive, args=())
        self.daemon.start()

    def get_config_from_db(self):
        result = {"error":"","data":{}}
        try:
            cursor = self.db.execute("SELECT * from isatc_config")
            for row in cursor:
                if row[2] == "int":
                    self.config[row[0]] = int(row[1])
                elif row[2] == "bytes":
                    self.config[row[0]] = bytes(row[1], 'utf-8')
                else:
                    self.config[row[0]] = row[1].strip()
                
                result['data'][row[0]] = row[1]
                
        except Exception as e:
            result["error"] = str(e)
        logging.debug(self.config)
        return result

    def set_config(self,config):
        result = {"error":"","data":"configuration successfully saved"}
        try:
            for key in config:
                self.db.execute("update isatc_config set config_value=? where config_name=?",(config[key],key))
                self.db.commit()
            self.get_config_from_db()
        except Exception as e:
            result["error"] = str(e)

        return result

    def get_historical_snr(self,param):
        result = {"error":"","data":[]}
        try:
            sql = "select (timestamp/?)*? as ts, avg(signal_level) as snr from isatc_signal where timestamp >= ? and timestamp < ? group by ts "
            cursor = self.db.execute(sql, (param['bucket'],param['bucket'],param['start'],param['end']))
            for row in cursor:
                result["data"].append(row)
        except Exception as e:
            result["error"] = str(e)
        return result

    def get_egc(self,param):

        result = {"error":"","columns":["les","service","priority","lang","timestamp","bytes","sequence","error","repetition","filename"], "data":[],"count":None}
        sql = "select count(timestamp) from isatc_egc where timestamp >= ? and timestamp < ? "
        try:
            cursor = self.db.execute(sql, (param['start'],param['end']))
            result["count"] = cursor.fetchone()[0]
            
            sql = "select "+",".join(result["columns"])+" from isatc_egc where timestamp >= ? and timestamp < ?  LIMIT ? OFFSET ?"
            cursor = self.db.execute(sql, (param['start'],param['end'],param['limit'],param['offset']))
            for row in cursor:
                result["data"].append(row)
        except Exception as e:
            result["error"] = str(e)
        return result

    def get_dir(self,param):

        result = {"error":"","columns":["filename","timestamp","bytes","content"], "data":[],"count":None}
        sql = "select count(timestamp) from isatc_dir where timestamp >= ? and timestamp < ? "
        try:
            cursor = self.db.execute(sql, (param['start'],param['end']))
            result["count"] = cursor.fetchone()[0]
            
            sql = "select "+",".join(result["columns"])+" from isatc_dir where timestamp >= ? and timestamp < ?  LIMIT ? OFFSET ?"
            cursor = self.db.execute(sql, (param['start'],param['end'],param['limit'],param['offset']))
            for row in cursor:
                result["data"].append(row)
        except Exception as e:
            result["error"] = str(e)
        return result
        
    def get_txlog(self,param):

        result = {"error":"","columns":["timestamp","parameters","content","service_number","priority","bytes","destination","network_type","is_alarm_tx","tx_status","reference"], "data":[],"count":None}
        sql = "select count(timestamp) from isatc_txlog where timestamp >= ? and timestamp < ? "
        try:
            cursor = self.db.execute(sql, (param['start'],param['end']))
            result["count"] = cursor.fetchone()[0]
            
            sql = "select "+",".join(result["columns"])+" from isatc_txlog where timestamp >= ? and timestamp < ?  order by timestamp desc LIMIT ? OFFSET ? "
            
            cursor = self.db.execute(sql, (param['start'],param['end'],param['limit'],param['offset']))
            for row in cursor:
                result["data"].append(row)
        except Exception as e:
            result["error"] = str(e)
        return result
        
    def get_dir_by_id(self,timestamp,filename):
        result = {"error":"","data":None}

        try:
            sql = "select * from isatc_dir where timestamp=? and filename=?"
            cursor = self.db.execute(sql,(timestamp,filename))
            result["data"] = cursor.fetchone()
        except Exception as e:
            result["error"] = str(e)
        return result

    def connect(self):
        self.isConnected = False
        try:
        
            if self.conn:
                self.conn.close()
            
            if self.config["serial"] == 'auto':  
                listPort = glob.glob('/dev/ttyUSB*')
                logging.info(listPort)
                if listPort:
                    port = listPort[0]
                else:
                    logging.error('port not found ')
                    time.sleep(5)
                    return False
            else:
                port = self.config["serial"]
            
            logging.info('connecting to '+str(port))
            
            self.lock.acquire()
            self.conn = serial.Serial(
                port=port, baudrate=self.config["baudrate"], 
                timeout=self.config["read_timeout"], 
                write_timeout=self.config["write_timeout"]
            )

            if self.conn.is_open:
            
                string = self.conn.read_until().decode('ascii')
                logging.debug(string)
                
                if string.find(str(self.config["tcu_prompt"])) != -1 :
                    self.conn.write(b"minic\n")
                    string = self.conn.read_until(self.config["minic_prompt"]).decode('ascii')
                    
                logging.debug(string)
                logging.info('connected')
                self.lock.release()
                self.isConnected = True
                self.initRead = True
                self.fetch_device_info()
                if self.deviceInfo['serialNumber'] == None:
                   self.fetch_device_info()
                   
                self.fetch_info()
                self.fetch_gps()
                
                
                return True
        except Exception as e:
            if self.lock.locked():
                self.lock.release()
            logging.error(str(e))
        
        return False 

    def close(self):
        if self.isConnected:
            self.conn.close()
            
    def reboot_tcu(self):
        logging.debug("rebooting tcu ..")
        if self.isConnected == False:
            return "not connected"
            
        try:
            self.conn.write(b"exit")
            string = self.conn.read_until(self.config["tcu_prompt"]).decode('ascii')
            logging.debug(string)
            self.write(b"restart")
            
        except Exception as e:
            logging.error(str(e))
            
        return True
        
    def reboot_minic(self):
        logging.debug("rebooting minic_shell ..")
        
        if self.isConnected == False:
            return "not connected"
            
        try:    
            self.conn.write(b"exit")
            string = self.conn.read_until(self.config["tcu_prompt"]).decode('ascii')
            logging.debug(string)
            self.write(b"minic_reboot")

        except Exception as e:
            logging.error(str(e))   

        return True 
        
    def write(self,data,forceInMinic=True):
        string =""
        self.lock.acquire() 
        logging.debug("lock:"+str(time.time()))
        
        try:
            logging.debug(data.decode('utf-8'))
            self.conn.reset_input_buffer()
            self.conn.write(data)
            string = self.conn.read_until(self.config["minic_prompt"]).decode('ascii')
            logging.debug(string)
        
            if forceInMinic and string.find(self.config["tcu_prompt"].decode('ascii'))  != -1 :
                logging.warning("looks like on TCU, entering minic console")
                self.conn.write(b"minic\n")
                self.conn.read_until(self.config["minic_prompt"]).decode('ascii')
                    
            self.status['lastResponse'] = int(time.time())
            
        except Exception as e:
            if self.lock.locked():
                self.lock.release()
            logging.error(str(e))
            time.sleep(5)
            self.connect()

        if self.lock.locked():  
            self.lock.release()
        logging.debug("release:"+str(time.time()))
        return string
        
    def fetch_device_info(self):
        string = self.write(b"status -i\n")
        self.deviceInfo['serialNumber'] = singleLine(r"Serial number\s*:\s*(.+)",string)
        self.deviceInfo['terminalType'] = singleLine(r"Terminal type\s*:\s*(.+)",string)
        self.deviceInfo['mobileNumber'] = singleLine(r"Mobile number\s*:\s*(.+)",string)
        self.deviceInfo['mobileType'] = singleLine(r"Mobile type\s*:\s*(.+)",string)
        self.deviceInfo['ISNnumber'] = singleLine(r"ISN number\s*:\s*(.+)",string)
        self.deviceInfo['HWid'] = singleLine(r"Hardware id\s*:\s*(.+)",string)


    def fetch_snr(self):
        string = filterNonPrint(self.write(b"status -s\n"))
        snr = singleLine(r"Signal strength\s*:\s*(\d+)",string)
        if snr != None :
            snr = int(snr)

        self.db.execute("insert into isatc_signal values(?,?)",(int(time.time()),snr))
        self.db.commit()
        self.signal ={'ts':int(time.time()), 'signal':snr, 'raw':string }

    def fetch_info(self):
        string = filterNonPrint(self.write(b"status -c\n"))
        self.status['sync'] = singleLine(r"Synchronization\s*:\s*(\S+)",string)
        self.status['tdmType'] = singleLine(r"TDM type\s*:\s*(\S+)",string)
        self.status['tdmChannel'] = singleLine(r"TDM channel number\s*:\s*(\S+)",string)
        self.status['currentChannel'] = singleLine(r"Current channel\s*:\s*(\S+)",string)
        self.status['currentProtocol'] = singleLine(r"Current protocol\s*:\s*(\S+)",string)
        self.status['tdmOrigin'] = singleLine(r"TDM origin\s*:\s*(.+)",string)
        self.status['tdmFrameNumber'] = singleLine(r"TDM frame number\s*:\s*(\S+)",string)
        self.status['bbErrorRate'] = singleLine(r"BB error rate\s*:\s*(\S+)",string)
        self.status['preferredOcean'] = singleLine(r"Preferred ocean\s*:\s*(.+)",string)


        #distress log
    def fetch_distress_log(self):
        result = {"error":"","data":{}}
        try:
            string = filterNonPrint(self.write(b"status -a\n"))
            result['data'] ['latestDistress'] = singleLine(r"Latest Distress\s*:\s*(.+)",string)
            result['data'] ['latestDistressTest'] = singleLine(r"Latest Distress test\s*:\s*(.+)",string)
        except Exception as e:
            result["error"] = str(e)
        return result

 
    def fetch_program_version(self):
        self.status['version'] = filterNonPrint(self.write(b"status -v\n")).strip()

    def fecth_ncs_config(self):
        self.status['ncsConfig'] = filterNonPrint(self.write(b"ncs -n\n")).strip()

    def fetch_ncs_list(self):
        self.status['ncsList'] = filterNonPrint(self.write(b"ncs -l\n")).strip()
    
    def send_distress(self,ch):
        logging.warning("distress triggered on channel "+str(ch))
        result = {"error":"","data":"success, distress triggered on channel "+str(ch)}
        try:
            if ch=="1":
                gpio_port = self.ch1
            else:
                gpio_port = self.ch2
                
            self.lock.acquire()    
            GPIO.output(gpio_port, GPIO.LOW)
            time.sleep(7)
            GPIO.output(gpio_port, GPIO.HIGH)
            self.lock.release()
            
        except Exception as e:
            result["error"] = str(e)
        return result
        
    def fetch_gps(self):
        #gps 
        string = filterNonPrint(self.write(b"gps -g\n"))
        self.deviceInfo['latitude'] = singleLine(r"Position\s+:\s+(.+N|S).+",string)
        self.deviceInfo['longitude'] = singleLine(r"Position\s+:\s+.+[N|S](.+E|W)",string)
        self.deviceInfo['altitude'] = singleLine(r"Altitude\s*:\s+(.+)\s*ft",string)
        self.deviceInfo['GPStime'] = singleLine(r"Position.*at(.*)",string)

    def fetch_tx_status(self):
        result = {"error":"","data":{}, "columns":["LES","Sv","P","L","Date","Time","Bytes","Destination","MTCA","Status","File/Ref"]}
        try:
            string = filterNonPrint(self.write(b"status -t\n"))
            regex = r"^(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)$"
            result['data'] = multiLine(regex,string)
        except Exception as e:
            result["error"] = str(e)
        return result

    def fetch_link_test(self):

        result = {"error":"","data":{}}

        try:
            string = self.write(b"status -m\n")
            result['data']['LES'] = singleLine(r"Test LES\s*:\s*(.+)",string)
            result['data']['attempts'] = singleLine(r"Attempts\s*:\s*(.+)",string)
            result['data']['bber'] = singleLine(r"Bber\s*:\s*(.+)",string)
            result['data']['fwdAttemps'] = singleLine(r"Forward attempts\s*:\s*(.+)",string)
            result['data']['rtnAttemps'] = singleLine(r"Return attempts\s*:\s*(.+)",string)
            result['data']['distresTest'] = singleLine(r"Distress test\s*:\s*(.+)",string)
            result['data']['signalStrength'] = singleLine(r"Signal strength\s*:\s*(.+)",string)
            result['data']['status'] = singleLine(r"Test status\s*:\s*(.+)",string)
            result['data']['time'] = singleLine(r"Test at UTC\s*:\s*(.+)",string)
        except Exception as e:
            result["error"] = str(e)

        return result

    def allow_transmit(self):
        result = {"error":"","data":{}}
        if ( self.signal['signal'] == None or self.signal['signal'] <= 0):
            result["error"] = "no signal"
        return result

    def transmit(self,param):
        result = {"error":"","data":{}}
        
        if param['content'].strip() == "":
            result["error"] = "content cannot be empty"
            return result
            
        if is_int(param['les_id']) == None or is_int(param['delivery_service']) == None or is_int(param['destination_network']) == None or is_int(param['language']) == None:
            result["error"] = " les_id , delivery_service , destination_network and language must be an integer"
            return result
                
        state =  self.allow_transmit()
        if state["error"] != "":
            return  state

        try:
            filename = str(randint(10000, 99999))+".api"
            
            tx = "tx "+filename+" -c "+param['les_id']+" -s "+param['delivery_service']+" -t "+param['destination_network']+" -l "+param['language']
            
            if "destination_ext" in param and param['destination_ext'].strip() != "":
                tx = tx+" -e "+str(param['destination_ext'])

            if "distress_priority" in param and bool(param["distress_priority"]):
                tx = tx+" -a "
            
            if "required_confirmation" in param and bool(param["required_confirmation"]):
                tx = tx+" -v "

            if "date" in param:
                tx = tx+" -y "+str(param['date'])
            
            if "hour_minute" in param:
                tx = tx+" -h "+str(param['hour_minute'])

            self.lock.acquire()
            self.conn.write(bytes("transfer "+filename+"\n", 'utf-8'))
            self.lock.release()
            
            self.write(bytes(param['content']+"\x03", 'utf-8'))
            
            byteSize = self.find_bytes(filename)
            
            self.write(bytes(tx+"\n", 'utf-8'))
            result["data"] = "data are being transmitted, please check the Tx Log for the latest status"
            
            #PK minute(timestamp)-lesid-bytes-network_type
            epoch = int(time.time())
            PK = str(int(epoch/60))+"-"+str(param['les_id'])+"-"+byteSize+"-"+str(param['destination_network'])
            self.db.execute("insert into isatc_txlog (id,timestamp,parameters,content) values(?,?,?,?)",(PK,epoch,tx,param['content']))
            self.db.commit()

        except Exception as e:
            result["error"] = str(e)

        return result

    def send_email(self,to,body,lesId="",sac="",subject="",cc=""):
        result = {"error":"","data":{}}

        state =  self.allow_transmit()
        if state["error"] != "":
            return state

        if is_valid_email(to) == False:
            result["error"] ="invalid email "+to
            return result

        try:
            filename = str(randint(10000, 99999))+".eml"
            
            emailBody = "TO:"+to+"\n"
            if subject.strip() !="" :
                emailBody += "SUBJECT:"+subject.strip()+"\n"

            if cc.strip() != "":
                emailBody += "CC:"+cc.strip()+"\n"
            emailBody += "\n"+body+"\x03"  

            self.lock.acquire()
            self.conn.write(bytes("transfer "+filename+"\n", 'utf-8'))
            self.lock.release()
            
            self.write(bytes(emailBody, 'utf-8'))
            byteSize = self.find_bytes(filename)
            
            if lesId == "":
                lesId = self.config['email_les_id']
            
            if sac == "":
                sac = self.config['email_sac']
                
            command = "tx "+filename+" -c "+lesId+" -s 0 -t 6 -l 0 -e "+sac+"\n"
            
            self.write(bytes(command, 'utf-8'))
            result["data"] = "email are being transmitted, please check the Tx Log for the latest status"
            
            #PK minute(timestamp)-lesid-bytes-destination_ext-network_type
            epoch = int(time.time())
            PK = str(int(epoch/60))+"-"+str(lesId)+"-"+byteSize+"-6"
            self.db.execute("insert into isatc_txlog (id,timestamp,parameters,content) values(?,?,?,?)",(PK,epoch,command,emailBody))
            self.db.commit()
            
        except Exception as e:
            result["error"] = str(e)

        return result
    
    def find_bytes(self,filename):
        regex = r"^(\S+)\s+(\S+)\s+(\d+)\s+(\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})$"
        string = filterNonPrint(self.write(b"ls\n"))
        
        for data in multiLine(regex,string):
            if data[0]+"."+data[1] ==  filename:
                return data[2]
        
        return "na"
            
    def read_egc(self):

        if self.initRead == False and ( self.signal['signal'] == None or self.signal['signal'] <= 0):
            logging.warning("no signal")
            return
            
        logging.info("reading egc")
        
        '''read egc content'''
        regex = r"^(\d+)\s+(\d+)\s+(\w+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)$"
        string = filterNonPrint(self.write(b"status -e\n"))
        
        for data in multiLine(regex,string):
            epoch = tsToEpoch(data[4]+" "+data[5])
            key = data[11]+"-"+str(epoch)
            if key in self.egcs:
                continue

            self.db.execute("insert OR IGNORE into isatc_egc values(?,?,?,?,?,?,?,?,?,?)",(
                int(data[0]),#les
                int(data[1]),#service
                int(data[2]),#priority
                int(data[3]),#lang
                int(epoch),
                int(data[6]),#bytes
                int(data[7]),#sequence
                int(data[8]),#error
                int(data[9]),#repetition
                data[11],#filename
                )
            )
            self.egcs[key] = data[0]
            self.db.commit()
       

        #read dir content   
        regex = r"^(\S+)\s+(\S+)\s+(\d+)\s+(\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})$"
        string = filterNonPrint(self.write(b"ls\n"))
        
        for data in multiLine(regex,string):
            epoch = tsToEpoch(data[3]+" "+data[4])
            filename = data[0]+"."+data[1]
            key = filename+"-"+str(epoch)
            if key in self.dir:
                continue
            
            content = removeSufficPrefix(self.write(str.encode("cat "+filename+"\n")))
            self.db.execute("insert OR IGNORE into isatc_dir values(?,?,?,?)",(
                filename,
                epoch,
                int(data[2]),
                content
                )
            )
            self.db.commit()
            self.dir[key] = data[2]

    def fetch_tx_log(self):
        logging.info("fetch txStatus")
        string = filterNonPrint(self.write(b"status -t\n"))
        regex = r"^(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$"
        for data in multiLine(regex,string):
        
            epoch = tsToEpoch(data[4]+" "+data[5])
            #PK minute(timestamp)-lesid-bytes-network_type
            PK = str(int(epoch/60))+"-"+data[0]+"-"+data[6]+"-"+data[8][1]
            
            #only update if the value are changed
            value = data[9]+"-"+data[10]
            if PK in self.txlog:
                if self.txlog[PK] == value:
                    continue
                    
            self.txlog[PK] = value
            
            tupple = (
                data[1],#Service number.
                int(data[2]),#Priority number.
                data[3],#Language (presentation).
                int(data[6]),#bytes
                data[7],#Number of the called party.
                int(data[8][0]),#multi_addressed
                int(data[8][1]),#network_type
                int(data[8][2]),#confirmation_request
                int(data[8][3]),#is_alarm_tx
                data[9],#tx_status
                data[10],#reference
                PK
            )
            self.db.execute("update isatc_txlog set service_number=?,priority=?,lang=?,bytes=?,destination=?,multi_addressed=?,network_type=?,confirmation_request=?,is_alarm_tx=?,tx_status=?,reference=? where id=?",tupple)
            self.db.commit()
            
    def shutdown(self):
        self.daemon.stop()
        
    def get_status(self):
        self.fetch_info()
        return {"error":"","data":self.status}

    def get_snr(self):
        return {"error":"","data":self.signal}

    def get_device_info(self):
        self.deviceInfo['isSerialConnected'] = self.isConnected
        self.deviceInfo['hostUptime'] = int(time.monotonic())
        self.deviceInfo['applicationUptime'] = int(time.time() - self.startTime)
        return {"error":"","data":self.deviceInfo}

    def keep_alive(self):
        currentEpoch = 0
        lastEpoch = 0
        lastEpochEgc = 0
        lastEpochEmail = 0

        while True:
      
            if self.isConnected == False:
                logging.debug("not connected ")
                time.sleep(5)
                self.connect()
                continue
                
            try:  
                
                currentEpoch = int(time.time())
                ''' send recurring email'''

                if self.config["enable_recurring_email"] == 1 and  (currentEpoch - lastEpochEmail) >= self.config["email_send_interval"] :
                    logging.info("send recurring email ...")
                    lastEpochEmail = currentEpoch
                    out = self.send_email(
                        self.config["email_destination"],
                        self.config["email_content"],
                        self.config["email_les_id"],
                        self.config["email_sac"],
                        self.config["email_subject"],
                        self.config["email_cc"],
                    )
                    logging.info(out)
                '''read signal strength every 10 secs'''
                if currentEpoch - lastEpoch >= self.config["signal_read_interval"] :
                    lastEpoch = currentEpoch
                    logging.debug("check signal level")
                    self.fetch_snr()
                    
                ''' read EGC every 30 second and if there is a signal '''
                if self.initRead or (currentEpoch - lastEpochEgc >= self.config["egc_read_interval"]) :
                    lastEpochEgc = currentEpoch
                    self.read_egc()
                    self.fetch_tx_log()
                    self.initRead = False

            except Exception as e:
                logging.error(str(e))

            time.sleep(1)
