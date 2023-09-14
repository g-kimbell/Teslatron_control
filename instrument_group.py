from time import ctime, time, sleep
import numpy as np
import os

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

    @staticmethod
    def check_filename_duplicate(filename):
        if os.path.isfile(filename):
            print(f"Filename '{filename}' already exists")
            i=1
            while os.path.isfile(filename+"_"+str(i)):
                i+=1
            filename = filename+"_"+str(i)
            print(f"Saving data to '{filename}'")
        return filename
    
    def ramp_T(self,filename,controller,temp,rate,threshold=0.05,timeout_hours=12):
        match controller:
            case "probe":
                self.iTC.ramp_probe_temp(self,temp,rate)
            case "VTI":
                self.iTC.ramp_VTI_temp(self,temp,rate)
            case "both":
                self.iTC.ramp_probe_temp(self,temp,rate)
                self.iTC.ramp_VTI_temp(self,temp,rate)
            case _:
                raise ValueError("Invalid controller. Use 'probe', 'VTI', or 'both'.")
        print("Ramping {} to {} K at {} K/min".format(controller,temp,rate))

        time0 = time.time()
        timeout=timeout_hours*3600

        filename = self.check_filename_duplicate(filename)
        with open(filename,'w') as f:
            print(f"Writing data to {filename}")
            condition_met = 0
            while measuring==True:
                data = self.read_everything()
                f.write(data)
                f.write("\n")
                f.flush()
                sleep(0.01)
                
                match controller:
                    case "probe":
                        if abs(self.iTC.get_probe_temp()-temp) < threshold:
                            condition_met += 1
                        else:
                            condition_met = 0
                    case "VTI":
                        if abs(self.iTC.get_VTI_temp()-temp) < threshold:
                            condition_met += 1
                        else:
                            condition_met = 0
                    case "both":
                        if (abs(self.iTC.get_probe_temp()-temp) < threshold) and (abs(self.iTC.get_VTI_temp()-temp) < threshold):
                            condition_met += 1
                        else:
                            condition_met = 0
                        
                if condition_met >= 5:
                    measuring=False
                    print(f"Finished ramping {controller} to {temp} K.")
                    break

                if time.time()-time0 > timeout:
                    measuring=False
                    print("Timeout reached.")
                    break
        return