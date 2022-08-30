import numpy as np
from keplerrpc import KeplerRPC

class Kepler():

  def __init__(self, port="/dev/ttyUSB1"):
    self._port = port
    self.cli = KeplerRPC(port)

  def call(self, method, *args):
    ret = self.cli.call(method, *args)
    print("Kepler: call {} args {} ret {}".format(method, args, ret))
    #if isinstance(ret, list):
    #    for i in range(len(ret)):
    #        if isinstance(ret[i], int) and ret[i] > 2**31:
    #            ret[i] = ret[i] - 2**32
    #elif isinstance(ret, int) and ret > 2**31:
    #    ret = ret - 2**32

    return ret

  def load_pilot(self, waveform):
    ret = self.cli.call('pilot_enable',0)
    dd = (waveform.real.astype(dtype='int16') + (waveform.imag.astype(dtype='int16')*2**16))
    dd_b = dd.tobytes()
    ret = self.cli.call('load_pilot',dd_b)
    print("load_pilot : loaded {} samples : ret {}".format(len(dd_b), ret))

    self.cli.call('pilot_enable',1)
    return ret

  def tuner_test_load(self, tdd, tunerdata):
    dd_b = tunerdata.tobytes()
    print('tuner_test_load : tdd {} tunerdata len {} dd_b {} bytes'.format(tdd, len(tunerdata), len(dd_b)))
    ret = self.cli.call('tuner_test_load',tdd,dd_b)
    return ret
    
  def tuner_test_get(self, tdd):
    data = self.cli.call('tuner_test_get',tdd)
    arr = np.frombuffer(data, dtype='float32')
    return arr

  def canxfir_get(self, tdd):
    data = self.cli.call('canxfir_get',tdd)
    arr = np.frombuffer(data, dtype='float32')
    return arr

  def canxfir_load(self, tdd, data):
    dd_b = data.tobytes()
    print('canxfir_load : tdd {} data len {} dd_b {} bytes'.format(tdd, len(data), len(dd_b)))
    ret = self.cli.call('canxfir_load',tdd,dd_b)
    return ret
    
  def program_mcu(self, binfile):
    self.cli.call_noreply('bootloader')
    time.sleep(0.5)
    os.system('stm32loader -b 57600 -p {} -e -w -v {}'.format(self._port, binfile))
    time.sleep(0.5)
    os.system('stm32loader -p {} -g 0x08000000'.format(self._port))
    return '1'

  def reset_mcu(self):
    self.cli.call_noreply('bootloader')
    time.sleep(0.5)
    os.system('stm32loader -p {} -g 0x08000000'.format(self._port))
    return '1'

  def get_capture(self, group, length, triggered):
    data = self.cli.call('read_capture', group, length, triggered)
    arr = np.frombuffer(data, dtype='int16')
    ret = arr[0::2] + 1j*arr[1::2]
    return ret

