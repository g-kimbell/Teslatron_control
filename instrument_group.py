from time import ctime, time, sleep
import numpy as np

class Instrument_Group():
    def __init__(self, voltmeters, sourcemeters, Vsourcemeters, iTC, iPS):
        self.voltmeters = voltmeters
        self.sourcemeters = sourcemeters
        self.Vsourcemeters = Vsourcemeters
        self.iTC = iTC
        self.iPS = iPS

    def get_headers(self):
        headers = ["Date", "Time"]
        if self.iTC:
            headers += ["T_probe (K)", "T_probe_setpoint (K)", "T_probe_ramp_rate (K/min)", "heater_probe (%)", "T_VTI (K)", "T_VTI_setpoint (K)", "T_VTI_ramp_rate (K/min)", "heater_VTI (%)","Pressure (mB)","Needlevalve"]
        if self.iPS:
            headers += ["B (T)", "B_setpoint (T)", "B_ramp_rate (T/min)"]
        for name,sourcemeter in self.sourcemeters.items():
            headers.append(name+"_I (A)")
        for name,Vsourcemeter in self.Vsourcemeters.items():
            headers.append(name+"_V (V)")
            headers.append(name+"_Ileak (A)")
        for name,voltmeter in self.voltmeters.items():
            headers.append(name+"_V+ (V)")
            headers.append(name+"_V- (V)")
        return headers

    def read_everything(self):
        data=np.array(len(self.get_headers()))
        data[0] = ctime()
        data[1] = time()
        for name,voltmeter in self.voltmeters.items():
            voltmeter.start_voltage_measurement()
        i=2
        if self.iTC:
            data[2:11] = [self.iTC.get_probe_temp(),
                          self.iTC.get_probe_setpoint(),
                          self.iTC.get_probe_ramp_rate(),
                          self.iTC.get_probe_heater(),
                          self.iTC.get_VTI_temp(),
                          self.iTC.get_VTI_setpoint(),
                          self.iTC.get_VTI_ramp_rate(),
                          self.iTC.get_VTI_heater(),
                          self.iTC.get_pressure(),
                          self.iTC.get_needlevalve()]
            i+=10
        if self.iPS:
            data[i:i+3] = [self.iPS.get_field(),
                           self.iPS.get_field_setpoint(),
                           self.iPS.get_field_ramp_rate()]
            i+=3
        for name,sourcemeter in self.sourcemeters.items():
            data[i] = sourcemeter.get_current()
            i+=1
        for name,Vsourcemeter in self.Vsourcemeters.items():
            data[i] = Vsourcemeter.get_voltage()
            i+=1
        for name,voltmeter in self.voltmeters.items():
            data[i] = voltmeter.get_voltage_measurement()
            i+=1
        for name,sourcemeter in self.sourcemeters.items():
            sourcemeter.reverse_current()
        for name,voltmeter in self.voltmeters.items():
            voltmeter.start_voltage_measurement()
        for name,voltmeter in self.voltmeters.items():
            data[i] = voltmeter.get_voltage_measurement()
            i+=1
        sleep(0.01)
        return data

    def ramp_VTI(self,filename,temp,rate,threshold=0.05,timeout_hours=12):
        self.iTC.ramp_VTI_temp(self,temp,rate)
        print("Ramping VTI to {} K at {} K/min".format(temp,rate))

        time0 = time.time()
        timeout=timeout_hours*3600

        with open(filename,'w') as f:
            print("Writing data to {}".format(filename))
            while measuring==True:
                data = self.read_everything()
                f.write(data)
                f.flush()
                sleep(0.1)
                if abs(self.iTC.get_VTI_temp()-temp) < threshold:
                    measuring=False
                    print("Finished ramping VTI to {} K".format(temp))
                    break
                if time.time()-time0 > timeout:
                    measuring=False
                    print("Timeout reached")
                    break
        return
    
    def ramp_probe(self,filename,temp,rate,threshold=0.05,timeout_hours=12):
        self.iTC.ramp_probe_temp(self,temp,rate)
        print("Ramping probe to {} K at {} K/min".format(temp,rate))

        time0 = time.time()
        timeout=timeout_hours*3600

        with open(filename,'w') as f:
            print("Writing data to {}".format(filename))
            while measuring==True:
                data = self.read_everything()
                f.write(data)
                f.flush()
                sleep(0.1)
                if abs(self.iTC.get_probe_temp()-temp) < threshold:
                    measuring=False
                    print("Finished ramping VTI to {} K".format(temp))
                    break
                if time.time()-time0 > timeout:
                    measuring=False
                    print("Timeout reached")
                    break
        return