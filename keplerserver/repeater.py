import numpy as np
import pickle
import time
import os
import datetime

class Repeater():

  def __init__(self, keplerobj):
    self._kepler = keplerobj
    self._curconfig = {}
    self._kepler_status = {}
    self._tdd_status = {}
    self._adcdac_pwr_history = [[] for i in range(12)]
    self._pwr_history_len = 30
    self._savefile = '.kepler_server_config.cfg'
    self.MIN_DIG_GAIN = -10.
    self._prev_mode = None
    self._counter = 0
    self._donorrx_dbm2dbfs = 0.
    self._tstat_h = {}
    self._tstat_v = {}
    self._kstat_h = {}
    self._kstat_v = {}
    self._bw_values = [5,10,15,20,25,30,40,50,60,70,80,90,100,200]
    self._prev_uptime = 0.
    self.init()

  def init(self):

    self._tstat_h['status'] = 'TDD Sync'
    self._tstat_h['cellid'] = 'Donor Cell ID'
    self._tstat_h['lindex'] = 'L-index'
    self._tstat_h['scs'] = 'SCS (kHz)'
    self._tstat_h['arfcn'] = 'ARFCN'
    self._tstat_h['ssrssi'] = 'SS-RSSI   (dBm)'
    self._tstat_h['lastdetected'] = 'Last Seen (ms)'
    self._kstat_h['gain'] = 'Gain (dB)'
    self._kstat_h['center_freq'] = 'Center Frequency (MHz)'
    self._kstat_h['tdd_mode'] = 'TDD Mode'
    self._kstat_h['lowgain_mode'] = 'LowGain Mode'
    self._kstat_h['agc_on'] = 'Gain Control Mode'
    self._kstat_h['canx_on'] = 'Canx Mode'
    self._kstat_h['dltxpwr'] = 'DL Tx Power (dBm)'
    self._kstat_h['dlrxpwr'] = 'DL Rx Power (dBm)'
    self._kstat_h['dlechopwr'] = 'DL Echo Power (dBm)'
    self._kstat_h['ultxpwr'] = 'UL Tx Power (dBm)'
    self._kstat_h['ulrxpwr'] = 'UL Rx Power (dBm)'
    self._kstat_h['ulechopwr'] = 'UL Echo Power (dBm)'
    self._kstat_h['preisol'] = 'Est. Pre-Canx Isolation (dB)'
    self._kstat_h['postisol'] = 'Est. Post-Canx Isolation (dB)'
    self._kstat_h['dacpwr'] = 'DAC Inst Power (dBFS)'
    self._kstat_h['dacpwr_max'] = 'DAC Max Power (dBFS)'
    self._kstat_h['adcpwr'] = 'ADC Inst Power (dBFS)'
    self._kstat_h['adcpwr_max'] = 'ADC Max Power (dBFS)'
    self._kstat_h['uptime'] = 'Up Time'

    self._kepler.call('vendor', 1)

    boxcal_data = self._kepler.call('get_boxcal_data')
    dl_atten = self._kepler.call('dl_atten')
    ul_atten = self._kepler.call('ul_atten')
    donorrx_dbm2dbfs = (boxcal_data[8] - np.array(dl_atten[2:4])/4) + boxcal_data[0:2]
    donortx_dbfs2dbm = boxcal_data[2:4]
    serverrx_dbm2dbfs = (boxcal_data[9] - np.array(ul_atten[2:4])/4) + boxcal_data[4:6]
    servertx_dbfs2dbm = boxcal_data[6:8]
    analog_gain = max(np.add(donorrx_dbm2dbfs, servertx_dbfs2dbm))
    self._analog_gain = analog_gain
    print("analog gain : {}".format(analog_gain))

     # do initial boot-up things
    self.fetch_curconfig()
    try:
        saved_config = self.load_config()
    except:
        saved_config = None
    if saved_config != None:
      print('Found saved config, applying..')
      try:
          self.change_config(saved_config)
      except:
          pass
      time.sleep(5)
    self.fetch_kepler_status()
    self.fetch_tdd_status()

  def get_config(self):
    return self._curconfig

  def fetch_curconfig(self):
    self._curconfig['center_freq'] = self._kepler.call('center_freq')/1e6

    rpt_mode = self._kepler.call('mode')
    if rpt_mode[1] == 0:
        # manual gain
        self._curconfig['target_gain'] = int(self._kepler.call('gain') + self._analog_gain)
    else:
        # auto gain
        rpt_params = self._kepler.call('repeater_params')
        self._curconfig['target_gain'] = int(rpt_params[0] + self._analog_gain)

#print('Fetching Curconfig : target gain {} analog gain {}'.format(self._curconfig['target_gain'], self._analog_gain))
    pa_en = self._kepler.call('pa_enabled')
    self._curconfig['rpt_on'] = 1 if pa_en[0] > 0 or pa_en[1] > 0 else 0 

    if self._curconfig['rpt_on'] == 0 and self._prev_mode != None:
      self._curconfig['canx_on'] = self._prev_mode[0]
      self._curconfig['agc_on'] = self._prev_mode[1]
    else:
      self._curconfig['canx_on'] = rpt_mode[0]
      self._curconfig['agc_on'] = rpt_mode[1]

    dl_atten = self._kepler.call('dl_atten')
    self._curconfig['dl_rx_1'] = dl_atten[2]
    self._curconfig['dl_rx_2'] = dl_atten[3]

    ul_atten = self._kepler.call('ul_atten')
    self._curconfig['ul_rx_1'] = ul_atten[2]
    self._curconfig['ul_rx_2'] = ul_atten[3]

    tdd_mode = self._kepler.call('tdd_mode')
    if tdd_mode[0] == 0:
        self._curconfig['tdd_mode'] = 1
    if tdd_mode[0] == 1:
        self._curconfig['tdd_mode'] = 2+tdd_mode[1]

    lowgain_mode = self._kepler.call('tuner_lowgain_mode')
#print("lowgain_mode : {}".format(lowgain_mode))
    if lowgain_mode == 0:
        self._curconfig['lowgain_mode'] = 1
    if lowgain_mode == 1:
        self._curconfig['lowgain_mode'] = 2

    chan_byp = self._kepler.call('bypass_chan_fir')
    bank_sel = self._kepler.call('chan_fir_bank_sel')
#bank_sel_names = ["5", "10", "15", "20", "25", "30", "40", "50", "60", "70", "80", "90", "100", "200"]
    if chan_byp == 1:
      self._curconfig['rfbw'] = 999
      self._curconfig['chan_fir_byp'] = "selected"
      for i in range(14):
        self._curconfig['chan_fir_{}'.format(i)] = ""
    else:
      self._curconfig['rfbw'] = self._bw_values[bank_sel]
      for i in range(14):
        self._curconfig['chan_fir_{}'.format(i)] = "selected" if self._curconfig['rfbw'] == self._bw_values[i] else ""
      self._curconfig['chan_fir_byp'] = ""

#    tdd_band, tdd_arfcn = self._tdd.get_band_arfcn()
#    self._curconfig['band'] = tdd_band
#    self._curconfig['arfcn'] = tdd_arfcn
    ssb_arfcn, freq_start, freq_stop, freq_step = self._kepler.call('tdd_sync_search_freq')
    self._curconfig['arfcn'] = 0 if freq_step > 0 else ssb_arfcn

#    tdd_status = self._tdd.read_status_simple()
    tdd_schedule = self._kepler.call('tdd_frame_schedule')

    self._curconfig['slot1_dl'] = tdd_schedule[0]
    self._curconfig['slot1_ul'] = tdd_schedule[1]
    self._curconfig['slot2_dl'] = tdd_schedule[2]
    self._curconfig['slot2_ul'] = tdd_schedule[3]
    self._curconfig['ssf_symbols_dl'] = tdd_schedule[4]
    self._curconfig['ssf_symbols_gp'] = tdd_schedule[5]
    self._curconfig['ssf_symbols_ul'] = tdd_schedule[6]
    self._curconfig['tdd_blanking'] = tdd_schedule[7]

  def change_config(self, newconfig):
    for k, v in newconfig.items():
      if k in ['center_freq', 'rpt_on', 'canx_on', 'agc_on','gain']:
        continue
      if self._curconfig[k] != v:
        if k == 'dl_rx_1' or k == 'dl_rx_2':
          print('DL Atten RX : {}/{} -> {}/{}'.format(self._curconfig['dl_rx_1'], self._curconfig['dl_rx_2'], newconfig['dl_rx_1'], newconfig['dl_rx_2']))
          self._curconfig['dl_rx_1'] = int(newconfig['dl_rx_1'])
          self._curconfig['dl_rx_2'] = int(newconfig['dl_rx_2'])
          self._kepler.call('dl_atten', 100, 100, int(self._curconfig['dl_rx_1']), int(self._curconfig['dl_rx_2']))
        if k == 'ul_rx_1' or k == 'ul_rx_2':
          print('UL Atten RX : {}/{} -> {}/{}'.format(self._curconfig['ul_rx_1'], self._curconfig['ul_rx_2'], newconfig['ul_rx_1'], newconfig['ul_rx_2']))
          self._curconfig['ul_rx_1'] = int(newconfig['ul_rx_1'])
          self._curconfig['ul_rx_2'] = int(newconfig['ul_rx_2'])
          self._kepler.call('ul_atten', 100, 100, int(self._curconfig['ul_rx_1']), int(self._curconfig['ul_rx_2']))
        if k == 'tdd_mode':
          print('TDD Mode : {} -> {}'.format(self._curconfig[k], v))
          self._curconfig[k] = int(v)
          if self._curconfig[k] == 1:
            # HW TDD
            self._kepler.call('tdd_mode', 0, 1)
          elif self._curconfig[k] == 2:
            # DL only
            self._kepler.call('tdd_mode', 1, 0)
          elif self._curconfig[k] == 3:
            # UL only
            self._kepler.call('tdd_mode', 1, 1)
          else:
            raise RuntimeError('????')

        if k == 'lowgain_mode':
          print('LowGain Mode : {} -> {}'.format(self._curconfig[k], v))
          self._curconfig[k] = int(v)
          if self._curconfig[k] == 1:
            # Lowgain Mode OFF
            self._kepler.call('tuner_lowgain_mode', 0)
          elif self._curconfig[k] == 2:
            # Lowgain Mode ON
            self._kepler.call('tuner_lowgain_mode', 1)
          else:
            raise RuntimeError('????')

        if k == 'rfbw':
#print("!!!!!!!!!!!!!!!!! rfbw {}".format(v))
          self._curconfig[k] = v
          if v == 999:
            self._kepler.call('bypass_chan_fir',1)
            self._curconfig['chan_fir_byp'] = "selected"
            for i in range(14):
              self._curconfig['chan_fir_{}'.format(i)] = ""
          else:
            self._kepler.call('bypass_chan_fir',0)
            self._kepler.call('chan_fir_bank_sel', self._bw_values.index(v))
            for i in range(14):
              self._curconfig['chan_fir_{}'.format(i)] = "selected" if self._curconfig['rfbw'] == self._bw_values[i] else ""
            self._curconfig['chan_fir_byp'] = ""
          self._kepler.call('tdd_sync_stop')
          try:
            if self._curconfig['arfcn'] == 0:
              if self._curconfig['rfbw'] == 999:
                self._kepler.call('tdd_sync_start_search',6,1)
              else:
                self._kepler.call('tdd_sync_start_search',6,1, self._curconfig['center_freq']*1e6 - self._curconfig['rfbw']*1e6/2, self._curconfig['center_freq']*1e6 + self._curconfig['rfbw']*1e6/2)
            else:
              self._kepler.call('tdd_sync_start_search_arfcn',6,1,self._curconfig['arfcn'])
          except:
            pass


        if k in ['arfcn','slot1_ul','slot1_dl','slot2_ul','slot2_dl','ssf_symbols_ul','ssf_symbols_gp','ssf_symbols_dl', 'tdd_blanking']:
          for item in ['arfcn','slot1_ul','slot1_dl','slot2_ul','slot2_dl','ssf_symbols_ul','ssf_symbols_gp','ssf_symbols_dl', 'tdd_blanking']:
            print('{} : {} -> {}'.format(item, self._curconfig[item], newconfig[item]))
            if item == 'tdd_blanking':
              self._curconfig[item] = newconfig[item]
            else:
              self._curconfig[item] = int(newconfig[item])
#          sync_config = '0{:X}0{:X}0{:X}0{:X}0{:X}0{:X}0{:X}'.format(  \
#              self._curconfig['slot1_ul'],self._curconfig['slot1_dl'], \
#              self._curconfig['slot2_ul'],self._curconfig['slot2_dl'], \
#              self._curconfig['ssf_symbols_ul'],self._curconfig['ssf_symbols_gp'], \
#              self._curconfig['ssf_symbols_dl'])
#          self._tdd.config(self._curconfig['band'], self._curconfig['arfcn'], sync_config)
          print("tdd_blanking : {}, len {}".format(self._curconfig['tdd_blanking'], len(self._curconfig['tdd_blanking'])))
          if len(self._curconfig['tdd_blanking']) == 0:
            self._kepler.call('tdd_frame_schedule',  
              self._curconfig['slot1_dl'],self._curconfig['slot1_ul'], \
              self._curconfig['slot2_dl'],self._curconfig['slot2_ul'], \
              self._curconfig['ssf_symbols_dl'],self._curconfig['ssf_symbols_gp'], \
              self._curconfig['ssf_symbols_ul'])
          else:
            self._kepler.call('tdd_frame_schedule',  
              self._curconfig['slot1_dl'],self._curconfig['slot1_ul'], \
              self._curconfig['slot2_dl'],self._curconfig['slot2_ul'], \
              self._curconfig['ssf_symbols_dl'],self._curconfig['ssf_symbols_gp'], \
              self._curconfig['ssf_symbols_ul'],self._curconfig['tdd_blanking'])
          self._kepler.call('tdd_sync_stop')
          if self._kepler.call('center_freq') > 3e9:
            try:
              if self._curconfig['arfcn'] == 0:
                if self._curconfig['rfbw'] == 999:
                  self._kepler.call('tdd_sync_start_search',6,1)
                else:
                  self._kepler.call('tdd_sync_start_search',6,1, self._curconfig['center_freq']*1e6 - self._curconfig['rfbw']*1e6/2, self._curconfig['center_freq']*1e6 + self._curconfig['rfbw']*1e6/2)
              else:
                self._kepler.call('tdd_sync_start_search_arfcn',6,1,self._curconfig['arfcn'])
            except:
              pass

    if 'center_freq' in newconfig.keys() and newconfig['center_freq'] != self._curconfig['center_freq']:
      self._curconfig['center_freq'] = newconfig['center_freq']
      prev_pa = self._kepler.call('pa_enable')
      prev_mode = self._kepler.call('mode')
      self._kepler.call('gain', -30)
      self._kepler.call('pa_enable', 0, 0)
      self._kepler.call('mode', 0, 0)
      self._kepler.call('tuner_reset')
      self._kepler.call('center_freq', self._curconfig['center_freq']*1e6)
      self._kepler.call('mode', *prev_mode)
      self._kepler.call('pa_enable', *prev_pa)
      self._kepler.call('tdd_sync_stop')
      try:
        if self._curconfig['arfcn'] == 0:
          if self._curconfig['rfbw'] == 999:
            self._kepler.call('tdd_sync_start_search',6,1)
          else:
            self._kepler.call('tdd_sync_start_search',6,1, self._curconfig['center_freq']*1e6 - self._curconfig['rfbw']*1e6/2, self._curconfig['center_freq']*1e6 + self._curconfig['rfbw']*1e6/2)
        else:
          self._kepler.call('tdd_sync_start_search_arfcn',6,1,self._curconfig['arfcn'])
      except:
        pass

    if 'canx_on' in newconfig.keys() or 'agc_on' in newconfig.keys():
      if newconfig['canx_on'] != self._curconfig['canx_on'] or newconfig['agc_on'] != self._curconfig['agc_on']:
        self._curconfig['canx_on'] = newconfig['canx_on']
        self._curconfig['agc_on'] = newconfig['agc_on']
        self._kepler.call('mode', self._curconfig['canx_on'], self._curconfig['agc_on'])
        self._kepler.call('tuner_reset')

    if 'rpt_on' in newconfig.keys() and newconfig['rpt_on'] != self._curconfig['rpt_on']:
      self._curconfig['rpt_on'] = newconfig['rpt_on']
      if self._curconfig['rpt_on'] == 0:
        self._prev_mode = self._kepler.call('mode')
        self._kepler.call('mode', 0, 0)
        self._kepler.call('gain', self.MIN_DIG_GAIN)
        self._kepler.call('pa_enable', 0, 0)
      if self._curconfig['rpt_on'] == 1:
        if self._prev_mode != None:
          self._curconfig['canx_on'] = self._prev_mode[0]
          self._curconfig['agc_on'] = self._prev_mode[1]
        self._kepler.call('pa_enable', 1, 1)
        self._kepler.call('mode', self._curconfig['canx_on'], self._curconfig['agc_on'])
        self._prev_mode = None

    boxcal_data = self._kepler.call('get_boxcal_data')
    dl_atten = self._kepler.call('dl_atten')
    ul_atten = self._kepler.call('ul_atten')
    donorrx_dbm2dbfs = (boxcal_data[8] - np.array(dl_atten[2:4])/4) + boxcal_data[0:2]
    donortx_dbfs2dbm = boxcal_data[2:4]
    serverrx_dbm2dbfs = (boxcal_data[9] - np.array(ul_atten[2:4])/4) + boxcal_data[4:6]
    servertx_dbfs2dbm = boxcal_data[6:8]
    analog_gain = max(np.add(donorrx_dbm2dbfs, servertx_dbfs2dbm))
    self._analog_gain = analog_gain
    print("analog gain = {}".format(analog_gain))

    self._curconfig['dl_rx_1'] = dl_atten[2]
    self._curconfig['dl_rx_2'] = dl_atten[3]
    self._curconfig['ul_rx_1'] = ul_atten[2]
    self._curconfig['ul_rx_2'] = ul_atten[3]

    if 'target_gain' in newconfig.keys() and newconfig['target_gain'] != self._curconfig['target_gain']:
      print('Target Gain : {} -> {}'.format(self._curconfig['target_gain'], newconfig['target_gain']))
      self._curconfig['target_gain'] = int(newconfig['target_gain'])
#print('Change config : target gain {}'.format(self._curconfig['target_gain']))
      rpt_mode = self._kepler.call('mode')
      if rpt_mode[1] == 0:
        # manual gain
        self._kepler.call('gain', self._curconfig['target_gain'] - self._analog_gain)
        self._kepler.call('dac_fr_accum_reset')
      else:
        # auto gain
        rpt_params = self._kepler.call('repeater_params')
        rpt_params[0] = self._curconfig['target_gain'] - self._analog_gain
        self._kepler.call('repeater_params', *rpt_params)
    self.save_config()  

  def save_config(self):
    with open(self._savefile, 'wb') as f:
      pickle.dump(self._curconfig, f, protocol=pickle.HIGHEST_PROTOCOL)
      os.sync()

  def load_config(self):
    if not os.path.exists(self._savefile):
      return None
    with open(self._savefile, 'rb') as f:
      saved_config = pickle.load(f)
    return saved_config
 
  def get_kepler_status(self):
    return self._kstat_h, self._kstat_v

  def get_tdd_status(self):
    return self._tstat_h, self._tstat_v

  def fetch_tdd_status(self):
#    rf_status = self._kepler.call('rf_status')
#    stat = self._tdd.read_status_simple()
#    self._tstat_v['status'] = 'OK' if rf_status[1] == 1 else 'SEARCHING'
#    self._tstat_v['cellid'] = str(stat['cell_id'])
#    self._tstat_v['rssi'] = str(stat['rssi'])
#    self._tstat_v['rsrp'] = str(stat['ss_rsrp'])
#    self._tstat_v['lindex'] = str(stat['l_id'])
#    self._tstat_v['scs'] = '15' if stat['sc_interval'] == 0 else '30'
#    self._tstat_v['band'] = 'n' + str(stat['band'])
#    self._tstat_v['arfcn'] = self._curconfig['arfcn']
    stat = self._kepler.call('tdd_sync_status')
    self._tstat_v['status'] = 'OK' if stat[0] == 2 else 'SEARCHING' if stat[0] == 1 else 'IDLE'
    self._tstat_v['cellid'] = str(stat[2])
    self._tstat_v['ssrssi'] = '{:.1f}'.format(stat[4] - self._donorrx_dbm2dbfs)
    self._tstat_v['lastdetected'] = '{:.1f}'.format(stat[5])
    self._tstat_v['lindex'] = str(stat[3])
    self._tstat_v['scs'] = '30'
    self._tstat_v['arfcn'] = str(stat[1])

  def check_alive(self):
    uptime = self._kepler.call('secs_alive')
    if uptime < self._prev_uptime:
      print("!!!!!!!!!!!!!! Module rebooted !?!? Re-initializing the module..")
      self.init()
    self._prev_uptime = uptime

  def fetch_kepler_status(self):
    self._kepler.call('dac_fr_accum_reset')
#    tdd_module_status = self._tdd.read_status_simple()
    delchan_pwrs = self._kepler.call('get_delchan_pwrs')
    fullchan_pwrs = self._kepler.call('get_fullchan_pwrs')
    current_gain = self._kepler.call('gain')
#    rf_status = self._kepler.call('rf_status')
    accum_status = self._kepler.call('accum_status')
    adcdac_pwrs = self._kepler.call('read_powers')
    boxcal_data = self._kepler.call('get_boxcal_data')
    center_freq = self._kepler.call('center_freq')/1e6
    tdd_mode = self._kepler.call('tdd_mode')
    lowgain_mode = self._kepler.call('tuner_lowgain_mode')
    canx_mode = self._kepler.call('mode')

    dl_atten = self._kepler.call('dl_atten')
    ul_atten = self._kepler.call('ul_atten')
    donorrx_dbm2dbfs = (boxcal_data[8] - np.array(dl_atten[2:4])/4) + boxcal_data[0:2]
    self._donorrx_dbm2dbfs = donorrx_dbm2dbfs[0]
    donortx_dbfs2dbm = boxcal_data[2:4]
    serverrx_dbm2dbfs = (boxcal_data[9] - np.array(ul_atten[2:4])/4) + boxcal_data[4:6]
    servertx_dbfs2dbm = boxcal_data[6:8]
    analog_gain = max(np.add(donorrx_dbm2dbfs, servertx_dbfs2dbm))
    self._analog_gain = analog_gain

    dl_tx_pwr = np.add(adcdac_pwrs[12:14], servertx_dbfs2dbm)
    dl_rx_pwr = np.subtract(adcdac_pwrs[20:22], donorrx_dbm2dbfs)
    dl_echo_pwr = np.subtract(adcdac_pwrs[16:18], donorrx_dbm2dbfs)
    ul_tx_pwr = np.add(adcdac_pwrs[14:16], donortx_dbfs2dbm)
    ul_rx_pwr = np.subtract(adcdac_pwrs[22:24], serverrx_dbm2dbfs)
    ul_echo_pwr = np.subtract(adcdac_pwrs[18:20], serverrx_dbm2dbfs)

    pa_en = self._kepler.call('pa_enable')
    rpt_on = 1 if pa_en[0] > 0 or pa_en[1] > 0 else 0 

    self._kstat_v['gain'] = 'OFF' if rpt_on == 0 else '{:.1f}'.format(analog_gain + current_gain) if accum_status[1] == 0 else '{:.1f} OSC!'.format(analog_gain + current_gain - 12.)
    self._kstat_v['center_freq'] = '{:.3f}'.format(center_freq)
    self._kstat_v['tdd_mode'] = 'Auto' if tdd_mode[0] == 0 else 'DL Only' if tdd_mode[1] == 0 else 'UL Only'
    self._kstat_v['lowgain_mode'] = 'OFF' if lowgain_mode == 0 else 'ON'
    self._kstat_v['agc_on'] = '-' if self._curconfig['rpt_on'] == 0 else ('Auto' if canx_mode[1] == 1 else 'Manual')
    self._kstat_v['canx_on'] = '-' if self._curconfig['rpt_on'] == 0 else ('ON' if canx_mode[0] == 1 else 'OFF')
    self._kstat_v['dltxpwr'] = ' / '.join('{:.1f}'.format(k) for k in dl_tx_pwr)
    self._kstat_v['dlrxpwr'] = ' / '.join('{:.1f}'.format(k) for k in dl_rx_pwr)
    self._kstat_v['dlechopwr'] = ' / '.join('{:.1f}'.format(k) for k in dl_echo_pwr)
    self._kstat_v['ultxpwr'] = ' / '.join('{:.1f}'.format(k) for k in ul_tx_pwr)
    self._kstat_v['ulrxpwr'] = ' / '.join('{:.1f}'.format(k) for k in ul_rx_pwr)
    self._kstat_v['ulechopwr'] = ' / '.join('{:.1f}'.format(k) for k in ul_echo_pwr)

    isol_offset_dl = [-servertx_dbfs2dbm[0]-donorrx_dbm2dbfs[0], -servertx_dbfs2dbm[0]-donorrx_dbm2dbfs[1], -servertx_dbfs2dbm[1]-donorrx_dbm2dbfs[0], -servertx_dbfs2dbm[1]-donorrx_dbm2dbfs[1]]
    isol_offset_dl = np.add(isol_offset_dl, 10.)
#    isol_offset_ul = [-donortx_dbfs2dbm[0]-serverrx_dbm2dbfs[0], -donortx_dbfs2dbm[0]-serverrx_dbm2dbfs[1], -donortx_dbfs2dbm[1]-serverrx_dbm2dbfs[0], -donortx_dbfs2dbm[1]-serverrx_dbm2dbfs[1]]
#    isol_offset_ul = np.add(isol_offset_ul, 10.)
    pre_isol_dl = np.add(fullchan_pwrs[0:4], isol_offset_dl)
#    pre_isol_ul = np.add(fullchan_pwrs[4:8], isol_offset_ul)
    post_isol_dl = np.add(delchan_pwrs[0:4], isol_offset_dl)
#    post_isol_ul = np.add(delchan_pwrs[4:8], isol_offset_ul)

    self._kstat_v['preisol'] = '{:.1f}  ({:.1f} / {:.1f} / {:.1f} / {:.1f})'.format(max(pre_isol_dl), *pre_isol_dl)
    self._kstat_v['postisol'] = '{:.1f}  ({:.1f} / {:.1f} / {:.1f} / {:.1f})'.format(max(post_isol_dl), *post_isol_dl)
    self._kstat_v['dacpwr'] = 'DL {:.1f} / {:.1f}   UL {:.1f} / {:.1f}'.format(*adcdac_pwrs[0:4])
    self._kstat_v['dacpwr_max'] = 'DL {:.1f} / {:.1f}   UL {:.1f} / {:.1f}'.format(*adcdac_pwrs[12:16])
    self._kstat_v['adcpwr'] = 'DL {:.1f} / {:.1f}   UL {:.1f} / {:.1f}'.format(*adcdac_pwrs[4:8])
    self._kstat_v['adcpwr_max'] = 'DL {:.1f} / {:.1f}   UL {:.1f} / {:.1f}'.format(*adcdac_pwrs[16:20])
    
    str_tm = str(datetime.timedelta(seconds=self._prev_uptime))
    if ',' in str_tm:
        day = str_tm.split(',')[0]
        hour, minute, second = str_tm.split(',')[1].split(':')
    else:
        day = ''
        hour, minute, second = str_tm.split(':')

    self._kstat_v['uptime'] = '{}{} hour {} min {} sec'.format(day, hour, minute, int(float(second)))
