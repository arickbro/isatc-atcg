import json
from isatc_serial import ISATC
from flask import Flask, request, render_template
from flask_cors import CORS, cross_origin
ic = ISATC()

app = Flask(__name__)  
CORS(app)

@app.route("/")
def index():
   return render_template("index.html")
   
@app.route('/status', methods=['GET'])
def get_status():
    return json.dumps(ic.get_status())

@app.route('/configuration', methods=['GET'])
def get_config_from_db():
    return json.dumps(ic.get_config_from_db())

@app.route('/configuration', methods=['POST'])
def set_config():
    return json.dumps(ic.set_config(request.json))

@app.route('/egc', methods=['GET'])
def get_egc():
    parameter = {}
    parameter['start'] = int(request.args.get('start'))
    parameter['end'] = int(request.args.get('end'))
    parameter['offset'] = int(request.args.get('offset'))
    parameter['limit'] = int(request.args.get('limit'))
    return json.dumps(ic.get_egc(parameter))

@app.route('/egc/<id>', methods=['GET'])
def signal(id):
    ts_filename = id.split("-")
    return json.dumps(ic.get_dir_by_id(ts_filename[0],ts_filename[1]))

@app.route('/snr', methods=['GET'])
def last():
    return json.dumps(ic.get_snr())

@app.route('/historical_snr', methods=['GET'])
def get_historical_snr():
    parameter = {}
    parameter['start'] = int(request.args.get('start'))
    parameter['end'] = int(request.args.get('end'))
    parameter['bucket'] = int(request.args.get('bucket'))
    return json.dumps(ic.get_historical_snr(parameter))

@app.route('/txstatus', methods=['GET'])
def fetch_tx_status():
    return json.dumps(ic.fetch_tx_status())

@app.route('/linktestresult', methods=['GET'])
def getLinkTest():
    return json.dumps(ic.fetch_link_test())

@app.route('/command', methods=['POST'])
def exec():
    result = {"error":"","data":{}}
    try:
        cmd = request.form.get('cmd')
        result['data'] = ic.write(bytes(cmd+"\n", 'utf-8'))
    except Exception as e:
        result["error"] = str(e)

    return result

@app.route('/info', methods=['GET'])
def get_device_info():
    return json.dumps(ic.get_device_info())

@app.route('/distress', methods=['POST'])
def send_distress():
    ch = request.form.get('ch')
    return json.dumps(ic.send_distress(ch))
    
@app.route('/email', methods=['POST'])
def send_email():
    dest = request.form.get('dest')
    subject = request.form.get('subject')
    body = request.form.get('body')
    return json.dumps(ic.send_email(to=dest,body=body,subject=subject))
    
@app.route('/distress_log', methods=['GET'])
def fetch_distress_log():
    return json.dumps(ic.fetch_distress_log())

@app.route('/directory', methods=['GET'])
def get_dir():
    parameter = {}
    parameter['start'] = int(request.args.get('start'))
    parameter['end'] = int(request.args.get('end'))
    parameter['offset'] = int(request.args.get('offset'))
    parameter['limit'] = int(request.args.get('limit'))
    return json.dumps(ic.get_dir(parameter))

@app.route('/txlog', methods=['GET'])
def get_txlog():
    parameter = {}
    parameter['start'] = int(request.args.get('start'))
    parameter['end'] = int(request.args.get('end'))
    parameter['offset'] = int(request.args.get('offset'))
    parameter['limit'] = int(request.args.get('limit'))
    return json.dumps(ic.get_txlog(parameter))

@app.route('/directory/<id>', methods=['GET'])
def get_dir_by_id(id):
    ts_filename = id.split("-")
    return json.dumps(ic.get_dir_by_id(ts_filename[0],ts_filename[1]))
    
@app.route('/tx', methods=['POST'])
def transmit():
    string = ic.transmit(request.json)
    return string

    
if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=80)
    except KeyboardInterrupt:
        ic.shutdown()
        print("Server closed with KeyboardInterrupt!")