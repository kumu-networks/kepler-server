from flask import Flask, render_template, request, Response, jsonify, url_for
import msgpack
import msgpack_numpy
import numpy as np
import RPi.GPIO as GPIO
import time
import datetime

msgpack_numpy.patch()

from .kepler import Kepler
from .tdd_module import TDDModule
from .repeater import Repeater

app = Flask(__name__, template_folder='templates', static_folder='static')

port_tdd = "/dev/ttyAMA2"
port_kepler = "/dev/ttyAMA1"
gpio_ue = 24
gpio_kepler = 10
gpio_tdd = 25

GPIO.setmode(GPIO.BCM)
GPIO.setup(gpio_kepler, GPIO.OUT)

@app.route("/", methods =["GET", "POST"])
@app.route("/home", methods =["GET", "POST"])
def index():
    if request.method == "POST":
        output = request.form.to_dict()
        for k, v in output.items():
          if k in ['center_freq', 'target_gain']:
            output[k] = float(v)
          else:
            output[k] = int(v)
        _rpt.change_config(output)

    _rpt.fetch_kepler_status()
    kstat_h, kstat_v = _rpt.get_kepler_status()

    _rpt.fetch_tdd_status()
    tstat_h, tstat_v = _rpt.get_tdd_status()

    _rpt.fetch_curconfig()
    config = _rpt.get_config()

    return render_template("main.html", kstat_h=kstat_h, kstat_v=kstat_v, tstat_h=tstat_h, tstat_v=tstat_v, config=config, current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/_fetch_status', methods = ['GET'])
def fetch_status():
  _rpt.fetch_kepler_status()
  kstat_h, kstat_v = _rpt.get_kepler_status()

  _rpt.fetch_tdd_status()
  tstat_h, tstat_v = _rpt.get_tdd_status()
  return jsonify({"kstat": kstat_v, "tstat":tstat_v})


@app.route('/api/reset_ue')
def reset_ue_gpio():
    GPIO.setup(gpio_ue, GPIO.OUT)
    GPIO.output(gpio_ue, False)
    time.sleep(1)
    GPIO.output(gpio_ue, True)
    time.sleep(1)
    return Response("RESET SUCCESS", mimetype='text/html')

@app.route('/api/reset_kepler')
def reset_kepler_gpio():
    GPIO.setup(gpio_kepler, GPIO.OUT)
    GPIO.output(gpio_kepler, False)
    time.sleep(1)
    GPIO.output(gpio_kepler, True)
    time.sleep(1)
    return Response("RESET SUCCESS", mimetype='text/html')

@app.route('/api/tdd/probe')
def api_tdd_probe():
    ret_str = "{}\n\n".format(_tdd.probe())
    return Response(str(ret_str), mimetype='text/html')


@app.route('/api/tdd/config')
def api_tdd_config():
    arfcn = (request.args['arfcn'])
    band = (request.args['band'])
    try:
        ret = _tdd.config(int(band), int(arfcn))
        if ret:
            ret_str = "Sync Module is configured Successfully!\n\nBAND=n{}\nARFCN={}\n\n".format(band, arfcn)
        else:
            ret_str = "Sync Module is not configured.\tCheck USB connection/ Enter correct values.\n\n"
    except:
        ret_str = "Sync Module is not configured.\tCheck USB connection/ Enter correct values.\n\n"

    return Response(str(ret_str), mimetype='text/html')


@app.route('/api/tdd/status')
def api_tdd_status():
    result = _tdd.read_status()
    if len(result) == 0:
        result = "Sync Module status Read is not successful. Please check USB connection\n\n"
    else:
        result = '\n\n'.join(str(x) for x in result)
        result = result + "\n"+"\n"
    return Response(result, mimetype='application/json')

@app.route('/api/tdd/status_simple')
def api_tdd_status_simple():
    result = _tdd.read_status_simple()
    return jsonify(result)


@app.route('/api/kepler/load_pilot', methods=['POST'])
def kepler_load_pilot():
    data = request.get_data()
    print('load_pilot: received {} bytes'.format(len(data)))
    obj = msgpack.unpackb(data, use_list=True, raw=False)
    tx_wfm = obj.astype('complex64')
    ret = _kepler.load_pilot(tx_wfm)
    return Response(str(ret), mimetype='text/html')

@app.route('/api/kepler/tuner_test_load,<tddstr>', methods=['POST'])
def kepler_tuner_test_load(tddstr):
    tdd = int(tddstr)
    print('tuner_test_load, tdd {}'.format(tdd))
    data = request.get_data()
    obj = msgpack.unpackb(data, use_list=True, raw=False)
    tunerdata = obj.astype('float32')
    ret = _kepler.tuner_test_load(tdd, tunerdata)
    return Response(str(ret), mimetype='text/html')

@app.route('/api/kepler/canxfir_load,<tddstr>', methods=['POST'])
def kepler_canxfir_load(tddstr):
    tdd = int(tddstr)
    print('canxfir_load, tdd {}'.format(tdd))
    data = request.get_data()
    obj = msgpack.unpackb(data, use_list=True, raw=False)
    tunerdata = obj.astype('float32')

    ret = _kepler.canxfir_load(tdd, tunerdata)
    return Response(str(ret), mimetype='text/html')

@app.route('/api/kepler/<command>')
def kepler_dispatch(command):
    command = command.lower().strip().lstrip(':')
    if command.startswith('get_capture,'):
        group = int(command.split(',')[-3])
        length = int(command.split(',')[-2])
        triggered = int(command.split(',')[-1])
        print('got capture group {} len {} triggered {}'.format(group, length, triggered))
        capture = _kepler.get_capture(group, length, triggered)
        return Response(msgpack.packb(capture, use_bin_type=True), mimetype='application/x-msgpack')
    elif command.startswith('program_mcu'):
        filename = command.split(',')[-1]
        ret = _kepler.program_mcu(filename)
        return Response(str(ret), mimetype='text/html')
    elif command == 'reset_mcu':
        ret = _kepler.reset_mcu()
        return Response(str(ret), mimetype='text/html')
    elif command.startswith('tuner_test_get'):
        tdd = int(command.split(',')[-1])
        data = _kepler.tuner_test_get(tdd)
        return Response(msgpack.packb(data, use_bin_type=True), mimetype='application/x-msgpack')
    elif command.startswith('canxfir_get'):
        tdd = int(command.split(',')[-1])
        data = _kepler.canxfir_get(tdd)
        return Response(msgpack.packb(data, use_bin_type=True), mimetype='application/x-msgpack')
    elif command.startswith('tuner_get_channel'):
        tdd = int(command.split(',')[-3])
        num_avg = int(command.split(',')[-2])
        data_sel = int(command.split(',')[-1])
        rawdata = _kepler.cli.call('tuner_get_channel',tdd,num_avg,data_sel)
        data = np.frombuffer(rawdata, dtype='float32')
        return Response(msgpack.packb(data, use_bin_type=True), mimetype='application/x-msgpack')
    elif command.startswith('dbg_tuner_read_channel'):
        tdd = int(command.split(',')[-1])
        rawdata = _kepler.cli.call('dbg_tuner_read_channel',tdd)
        data = np.frombuffer(rawdata, dtype='float32')
        return Response(msgpack.packb(data, use_bin_type=True), mimetype='application/x-msgpack')
    elif command.startswith('tuner_read_chanbuf'):
        rawdata = _kepler.cli.call('tuner_read_chanbuf')
        data = np.frombuffer(rawdata, dtype='float32')
        return Response(msgpack.packb(data, use_bin_type=True), mimetype='application/x-msgpack')
    else:
        method = command.split(',')[0]
        arglist = command.split(',')[1:]
        args = [float(k) if '.' in k else int(k) for k in arglist]
        ret = _kepler.call(method, *args)
        return Response(str(ret), mimetype='text/html')
try:
    _tdd = TDDModule(port=port_tdd)
except:
    print("\nCheck USB Connection for Sync Module\n")
    exit(0)

try:
    _kepler = Kepler(port=port_kepler)
except:
    print("\nCheck USB Connection for Kepler Module\n")
    exit(0)

_rpt = Repeater(_kepler, _tdd)

app.config['PROPAGATE_EXCEPTIONS'] = True
print("Listening on port 5000...")
app.run(threaded=False, processes=1, debug=True, host='0.0.0.0', port=5000)

