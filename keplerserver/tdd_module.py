import serial
from datetime import datetime
import time

def s16(value):
    return -(value & 0x80) | (value & 0x7f)


class TDDModule():

    def __init__(self, port="/dev/ttyUSB4"):
        self._ser = serial.Serial()
        self._ser.port = port
        self._ser.baudrate = 115200
        self._ser.bytesize = serial.EIGHTBITS  # number of bits per bytes
        self._ser.parity = serial.PARITY_NONE  # set parity check: no parity
        self._ser.stopbits = serial.STOPBITS_ONE  # number of stop bits
        self._ser.timeout = .1  # timeout block read
        self._ser.xonxoff = False  # disable software flow control
        self._ser.rtscts = False  # disable hardware (RTS/CTS) flow control
        self._ser.dsrdtr = False  # disable hardware (DSR/DTR) flow control
        self._ser.open()

    def close_tdd_port(self):
        self._ser.close()

    def open_tdd_port(self):
        self._ser.open()

    def probe(self):
        self._ser.reset_output_buffer()
        self._ser.reset_input_buffer()
        cmd = "AT\r\n"
        # print(cmd)
        self._ser.write(cmd.encode())
        response1 = self._ser.readlines()
        return "TDD probe : response {}".format(response1)

    def get_band_arfcn(self):
        self._ser.reset_output_buffer()
        self._ser.reset_input_buffer()
        self._ser.write('AT*BAND?\r\n'.encode())
        resp_band = self._ser.readlines()
        if len(resp_band) != 3:
          band = None
        else:
          band = int(resp_band[1].decode('utf-8').split(',')[-1].split('\r')[0])

        self._ser.write('AT*CELLLOCK?\r\n'.encode())
        resp_arfcn = self._ser.readlines()
        if len(resp_arfcn) != 3:
          arfcn = None
        else:
          arfcn = int(resp_arfcn[1].decode('utf-8').split(',')[-1].split('\r')[0])

        return band, arfcn

        
    def config(self, band=77, arfcn=648672, sync_config="030002030004040406"):
        self._ser.reset_output_buffer()
        self._ser.reset_input_buffer()
        strcheck = repr(b'OK\r\n')
        # strerror=repr(b'+CME ERROR\r\n')
        response1 = ""
        response2 = ""
        response3 = ""

        cmd = "AT*BAND=16,10,15,0,0,{}\r\n".format(band)
        self._ser.write(cmd.encode())
        response1 = self._ser.readlines()
        # print(response1)

        cmd = "AT*CELLLOCK=1,3,{}\r\n".format(arfcn)
        self._ser.write(cmd.encode())
        response2 = self._ser.readlines()
        # print(response2)

        l1debug_string = "0300" + sync_config
        cmd = f"AT*L1DEBUG={l1debug_string}\r\n"
        self._ser.write(cmd.encode())
        response3 = self._ser.readlines()
        # print(response3)

        if len(response1) < 2 or len(response2) < 2 or len(response3) < 2:
            return False
        elif str(response1[1]).find(strcheck) != -1 and str(response2[1]).find(strcheck) != -1 and str(
                response3[1]).find(strcheck) != -1:
            return True
        else:
            return False

    def read_status(self):
        res_list = []
        self._ser.reset_output_buffer()
        self._ser.reset_input_buffer()
        for _ in range(5):
            self._ser.write("AT*L1DEBUG=0400\r\n".encode())
            response = self._ser.readlines()
            # print(response[1], type(response[1]), response[1][0], response[1][1], int(response[1][0:2], 16))
            # tmp = response[1]
            tmp = bytearray(response[1])  # because -> 'bytes' object does not support item assignment
            tmp[20:24] = tmp[22], tmp[23], tmp[20], tmp[21]
            # tmp = (bytes(tmp))
            # print(tmp, type(tmp), tmp[0], int(tmp[0:2], 16), int(tmp[20:24], 16))
            out = {}
            #out['<br>id'] = _
            out['time'] = datetime.now().strftime("%Y_%m_%d-%I:%M:%S_%p")
            out['ul_ts1'] = str(tmp[0:2], 'UTF-8')
            out['dl_ts1'] = str(tmp[2:4], 'UTF-8')
            out['ul_ts2'] = str(tmp[4:6], 'UTF-8')
            out['dl_ts2'] = str(tmp[6:8], 'UTF-8')
            out['ul_symbols'] = str(tmp[8:10], 'UTF-8')
            out['gp_symbols'] = str(tmp[10:12], 'UTF-8')
            out['dl_symbols'] = str(tmp[12:14], 'UTF-8')
            out['rssi'] = '-' + str(int(tmp[14:16], 16)) + 'dBm'
            out['ss_rsrp'] = str(int(tmp[16:18], 16) - 156) + 'dBm'
            out['snr'] = str(s16(int(tmp[18:20], 16))) + 'dB'
            out['cell_id'] = str(int(tmp[20:24], 16))
            out['sc_interval'] = tmp[24]
            out['l_id'] = str(int(tmp[25:27], 16))
            out['band'] = 'n' + str(int(tmp[27:29], 16))
            res_list.append(out)

        return res_list

    def read_status_simple(self):
        starttime = time.time()
        self._ser.reset_output_buffer()
        self._ser.reset_input_buffer()
        self._ser.write("AT*L1DEBUG=0400\r\n".encode())
        response = self._ser.readlines()
        tmp = bytearray(response[1])  # because -> 'bytes' object does not support item assignment
        tmp[20:24] = tmp[22], tmp[23], tmp[20], tmp[21]
        out = {}
        out['time'] = datetime.now().strftime("%Y_%m_%d-%I:%M:%S_%p")
        out['ul_ts1'] = int(tmp[0:2], 16)
        out['dl_ts1'] = int(tmp[2:4], 16)
        out['ul_ts2'] = int(tmp[4:6], 16)
        out['dl_ts2'] = int(tmp[6:8], 16)
        out['ul_symbols'] = int(tmp[8:10], 16)
        out['gp_symbols'] = int(tmp[10:12], 16)
        out['dl_symbols'] = int(tmp[12:14], 16)
        out['rssi'] = -int(tmp[14:16], 16)
        out['ss_rsrp'] = int(tmp[16:18], 16) - 156
        out['snr'] = s16(int(tmp[18:20], 16))
        out['cell_id'] = int(tmp[20:24], 16)
        out['sc_interval'] = tmp[24]
        out['l_id'] = int(tmp[25:27], 16)
        out['band'] = int(tmp[27:29], 16)

        return out

