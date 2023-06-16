import pyvisa
import time
import numpy as np
import logging

rm = pyvisa.ResourceManager()

class Instrument():
    def __init__(self,GPIB_address):
        self.GPIB_address = GPIB_address
        self.instr = rm.open_resource(GPIB_address)
        self.instr.write_termination = '\n'
        self.instr.read_termination = '\n'
    def query(self,command):
        logging.info(f"Query: {command}")
        response = self.instr.query(command)
        logging.info(f"Response: {response}")
        return response
    def write(self,command):
        logging.info(f"Write: {command}")
        self.instr.write(command)
    def identify(self):
        return self.query('*IDN?')

class Voltmeter(Instrument):
    # this currently works for both keithley 2182A and keysight 34461A
    def write(self,command):
        logging.info(f"Write: {command}")
        self.instr.write(command)
        logging.info(f"Response: {self.instr.query('SYST:ERR?')}")
    def __init__(self,GPIB_address):
        super().__init__(GPIB_address)
        self.write('*RST')
        self.write('*CLS')
        self.write(':SENS:VOLT:RANG:AUTO ON')
        self.write(':SENS:FUNC "VOLT"')
    def get_voltage(self):
        return float(self.query(':READ?'))
    def start_voltage_measurement(self):
        self.write(':INIT')
    def get_voltage_measurement(self):
        return float(self.query(':FETC?'))

class Sourcemeter(Instrument):
    def __init__(self,GPIB_address):
        super().__init__(GPIB_address)
        self.write('*RST')
        self.write('*CLS')
        self.write(':SOUR:CURR:RANG:AUTO ON')
    def write(self,command):
        logging.info(f"Write: {command}")
        self.instr.write(command)
        logging.info(f"Response: {self.instr.query('SYST:ERR?')}")
    def set_current(self,current):
        self.write(f'SOUR:CURR {current:.9f}')
    def get_current(self):
        status=int(self.query('STAT:MEAS:COND?'))
        if status & 8 == 8: # bit 3 on status register = compliance
            logging.warning('Current hit compliance')
            I = np.nan
        else:
            I = float(self.query('SOUR:CURR?'))
        return I
    def reverse_current(self):
        self.set_current(-float(self.query('SOUR:CURR?')))
    def turn_on(self):
        self.write('OUTP ON')
    def turn_off(self):
        self.write('OUTP OFF')
    def set_compliance(self,compliance):
        self.write(f'SOUR:CURR:COMP {compliance:.3f}')

class MercuryiPS(Instrument):
    def __init__(self,GPIB_address):
        super().__init__(GPIB_address)
    def get_config(self):
        return self.instr.query('READ:SYS:CAT')

class MercuryiTC(Instrument):
    # Daughter board unique identifiers for reference
    # DB3.H1 Heater
    # DB4.G1 Aux
    # DB5.P1 Pressure
    # DB8.T1 Probe
    # MB0.H1 Heater
    # MB1.T1 VTI
    def __init__(self,GPIB_address):
        super().__init__(GPIB_address)
    def query(self,command):
        logging.info(f'Query: {command}')
        response = self.instr.query(command)
        logging.info(f'Response: {response}')
        if response.endswith('INVALID'):
            logging.error(f'Invalid command: {command}')
        return response
    def write(self,command):
        # workaround: for Mercury controllers write commands leave an output in the buffer
        # this would lead to an erroneous response to the next query command
        # so we only use query commands
        logging.info(f"Write: {command}")
        response = self.instr.query(command)
        logging.info(f'Response: {response}')
        if response.endswith('INVALID'):
            logging.error(f'Invalid command: {command}')
    def get_config(self):
        return self.query('READ:SYS:CAT')
    
    ### Probe control ###
    def get_probe_temp(self):
        response=self.query('READ:DEV:MB0.H1:TEMP:SIG:TEMP?')
        T_K = float(response.split(':')[-1][:-1])
        return T_K
    def set_probe_temp(self,temp):
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:RENA:OFF')#turn off ramp
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:TSET:{temp}')#set temp
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:ENAB:ON')#turn on PID loop
        
    def get_probe_setpoint(self):
        response = self.query('READ:DEV:DB8.T1:TEMP:LOOP:TSET?')
        T_K = float(response.split(':')[-1][:-1])
        return T_K
    def get_probe_ramp_rate(self):
        response = self.query('READ:DEV:DB8.T1:TEMP:LOOP:RSET?')
        dTdt_Kpermin = float(response.split(':')[-1][:-3])
        return dTdt_Kpermin
    def ramp_probe_temp(self,temp,rate):
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:RSET:{rate}')
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:TSET:{temp}')
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:ENAB:ON')#turn on loop
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:RENA:ON')#turn on ramp
        return
    def get_probe_heater(self):
        response = self.query('READ:DEV:DB8.T1:TEMP:LOOP:HSET?')
        H_percentage = float(response.split(':')[-1])
        return H_percentage
    def set_probe_heater(self,heater_percentage):
        self.query(f'SET:DEV:DB8.T1:TEMP:LOOP:HSET:{heater_percentage}')#automatically turns off loop
        return
    def ramp_probe_heater(self,start_percentage,end_percentage,rate):
        # This would need to run asynchroneously. Might be more sensible to just synchronise this with measurements.
        set_points = np.linspace(start_percentage,end_percentage,int(60*rate))
        for set_point in set_points:
            self.set_probe_heater(set_point)
            print(f"Set point: {set_point}  Current T: {self.get_probe_temp()}")
            time.sleep(1)
        return
    
    ### VTI control ###
    def get_VTI_temp(self):
        response = self.query('READ:DEV:MB1.T1:TEMP:SIG:TEMP?')
        T_K = float(response.split(':')[-1][:-1])
        return T_K
    def set_VTI_temp(self,temp):
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:RENA:OFF')#turn off ramp
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:TSET:{temp}')
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:ENAB:ON')#turn on PID loop
        return
    def get_VTI_setpoint(self):
        response = self.query('READ:DEV:MB1.T1:TEMP:LOOP:TSET?')
        T_K = float(response.split(':')[-1][:-1])
        return T_K
    def get_VTI_ramp_rate(self):
        response = self.query('READ:DEV:MB1.T1:TEMP:LOOP:RSET?')
        dTdt_Kpermin = float(response.split(':')[-1][:-3])
        return dTdt_Kpermin
    def ramp_VTI_temp(self,temp,rate):
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:RSET:{rate}')
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:TSET:{temp}')
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:ENAB:ON')#turn on loop
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:RENA:ON')#turn on ramp
        return
    def get_VTI_heater(self):
        response = self.query('READ:DEV:MB1.T1:TEMP:LOOP:HSET?')
        H_percentage = float(response.split(':')[-1])
        return H_percentage
    def set_VTI_heater(self,heater_percentage):
        self.query(f'SET:DEV:MB1.T1:TEMP:LOOP:HSET:{heater_percentage}')#automatically turns off loop
        return
    def ramp_VTI_heater(self,start_percentage,end_percentage,rate):
        # This would need to run asynchroneously. Might be more sensible to just synchronise this with measurements.
        set_points = np.linspace(start_percentage,end_percentage,int(60*rate))
        for set_point in set_points:
            self.set_VTI_heater(set_point)
            print(f"Set point: {set_point}  Current T: {self.get_VTI_temp()}")
            time.sleep(1)
        return
    
    ### Pressure control ###
    def get_pressure(self):
        response = self.query('READ:DEV:DB5.P1:PRES:SIG:PRES?')
        P = float(response.split(':')[-1][:-2])
        return P
    def get_pressure_setpoint(self): # This doesn't work and I don't know why. It uses the code given in the manual.
        response = self.query('READ:DEV:DB5.P1:PRES:LOOP:TSET?')
        P = float(response.split(':')[-1][:-2])
        return P
    def set_pressure(self,pressure): # This doesn't work and I don't know why. It uses the code given in the manual.
        self.query(f'SET:DEV:DB5.P1:PRES:LOOP:ENAB:ON')#turn on loop
        self.query(f'SET:DEV:DB5.P1:PRES:LOOP:TSET:{pressure}')
        return
    def get_needlevalve(self):
        response = self.query('READ:DEV:DB5.P1:PRES:LOOP:FSET?')
        nv_percentage = float(response.split(':')[-1])
        return nv_percentage
    def set_needlevalve(self,percentage):
        self.query(f'SET:DEV:DB5.P1:PRES:LOOP:FSET:{percentage}')
        return