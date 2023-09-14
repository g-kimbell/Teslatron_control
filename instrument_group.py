from time import ctime, time, sleep
import numpy as np
import os
import csv

class InstrumentGroup():
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
        for name,sourcemeter in self.sourcemeters:
            headers.append(name+"_I (A)")
        for name,Vsourcemeter in self.Vsourcemeters:
            headers.append(name+"_Vg (V)")
            headers.append(name+"_Ileak (A)")
        for name,voltmeter in self.voltmeters:
            headers.append(name+"_V+ (V)")
        for name,voltmeter in self.voltmeters:
            headers.append(name+"_V- (V)")
        return headers

    def read_everything(self):
        data=[]
        data += [ctime()]
        data += [time()]
        for name,voltmeter in self.voltmeters:
            voltmeter.start_voltage_measurement()
        if self.iTC:
            data += [self.iTC.get_probe_temp(),
                          self.iTC.get_probe_setpoint(),
                          self.iTC.get_probe_ramp_rate(),
                          self.iTC.get_probe_heater(),
                          self.iTC.get_VTI_temp(),
                          self.iTC.get_VTI_setpoint(),
                          self.iTC.get_VTI_ramp_rate(),
                          self.iTC.get_VTI_heater(),
                          self.iTC.get_pressure(),
                          self.iTC.get_needlevalve()]
        if self.iPS:
            data += [self.iPS.get_field(),
                           self.iPS.get_field_setpoint(),
                           self.iPS.get_field_sweep_rate()]
        for name,sourcemeter in self.sourcemeters:
            data += [sourcemeter.get_current()]
        for name,Vsourcemeter in self.Vsourcemeters:
            data += [Vsourcemeter.get_voltage()]
        for name,voltmeter in self.voltmeters:
            data += [voltmeter.get_voltage_measurement()]
        for name,sourcemeter in self.sourcemeters:
            sourcemeter.reverse_current()
        for name,voltmeter in self.voltmeters:
            voltmeter.start_voltage_measurement()
        for name,voltmeter in self.voltmeters:
            data += [voltmeter.get_voltage_measurement()]
        return data

    @staticmethod
    def check_filename_duplicate(path):
        filename,extension = os.path.splitext(path)
        i=1
        while os.path.isfile(path):
            path = filename + "_" + str(i) + extension
            i+=1
        return path
        
    def measure_until_interrupted(self,filename,timeout_hours=12):
        try:
            time0 = time()
            timeout=timeout_hours*3600
            filename = self.check_filename_duplicate(filename)
            with open(filename, 'w', newline='') as f:
                print(f"Writing data to {filename}")
                writer = csv.writer(f)
                headers = self.get_headers()
                writer.writerows([headers])
                measuring=True
                while measuring:
                    data = self.read_everything()
                    writer.writerows([data])
                    f.flush()
                    sleep(0.01)

                    if time()-time0 > timeout:
                        measuring=False
                        print("Timeout reached")
                        break

        except KeyboardInterrupt:
            print("User interrupted measurement")
            pass
    
    def ramp_T(self,filename,controller,Ts,rates,threshold=0.05,timeout_hours=12):
        filename = self.check_filename_duplicate(filename)

        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            headers = self.get_headers()
            writer.writerows([headers])

            if type(Ts) is not list:
                Ts=[Ts]
            if type(rates) is not list:
                rates=[rates for T in Ts]
            if len(Ts) != len(rates):
                print("Warning: length of T and rate lists are not equal")

            for T,rate in zip(Ts,rates):
                match controller:
                    case "probe":
                        self.iTC.ramp_probe_temp(T,rate)
                    case "VTI":
                        self.iTC.ramp_VTI_temp(T,rate)
                    case "both":
                        self.iTC.ramp_probe_temp(T,rate)
                        self.iTC.ramp_VTI_temp(T,rate)
                    case _:
                        raise ValueError("Invalid controller. Use 'probe', 'VTI', or 'both'")
                print(f"Ramping {controller} to {T} K at {rate} K/min")

                time0 = time()
                timeout=timeout_hours*3600

                condition_met = 0
                measuring = True
                while measuring:
                    data = self.read_everything()
                    writer.writerows([data])
                    f.flush()
                    sleep(0.01)

                    match controller:
                        case "probe":
                            if abs(self.iTC.get_probe_temp()-T) < threshold:
                                condition_met += 1
                            else:
                                condition_met = 0
                        case "VTI":
                            if abs(self.iTC.get_VTI_temp()-T) < threshold:
                                condition_met += 1
                            else:
                                condition_met = 0
                        case "both":
                            if (abs(self.iTC.get_probe_temp()-T) < threshold) and (abs(self.iTC.get_VTI_temp()-T) < threshold):
                                condition_met += 1
                            else:
                                condition_met = 0
                    if condition_met >= 20:
                        measuring=False
                        print(f"Finished ramping {controller} to {T} K")
                        break
                    if time()-time0 > timeout:
                        measuring=False
                        print("Timeout reached")
                        break
        return
    
    def set_T(self,filename,controller,temp,threshold=0.05,timeout_hours=12):
        match controller:
            case "probe":
                self.iTC.set_probe_temp(temp)
            case "VTI":
                self.iTC.set_VTI_temp(temp)
            case "both":
                self.iTC.set_probe_temp(temp)
                self.iTC.set_VTI_temp(temp)
            case _:
                raise ValueError("Invalid controller, use 'probe', 'VTI', or 'both'")
        print(f"Setting {controller} to {temp} K")

        time0 = time()
        timeout=timeout_hours*3600

        filename = self.check_filename_duplicate(filename)
        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            headers = self.get_headers()
            writer.writerows([headers])
            
            condition_met = 0
            measuring = True
            while measuring:
                data = self.read_everything()
                writer.writerows([data])
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
                        
                if condition_met >= 20:
                    measuring=False
                    print(f"Finished ramping {controller} to {temp} K")
                    break

                if time()-time0 > timeout:
                    measuring=False
                    print("Timeout reached")
                    break
        return
    
    def ramp_B(self,filename,Bs,rates,threshold=0.005,timeout_hours=12):
        filename = self.check_filename_duplicate(filename)

        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            headers = self.get_headers()
            writer.writerows([headers])

            if type(Bs) is not list:
                Ts=[Bs]
            if type(rates) is not list:
                rates=[rates for T in Ts]
            if len(Bs) != len(rates):
                print("Warning: length of B and rate lists are not equal")

            for B,rate in zip(Bs,rates):
                self.iPS.set_field(B,rate)
                print(f"Ramping magnet to {B} T at {rate} T/min")

                time0 = time()
                timeout=timeout_hours*3600

                condition_met = 0
                measuring = True
                while measuring:
                    data = self.read_everything()
                    writer.writerows([data])
                    f.flush()
                    sleep(0.01)

                    if abs(self.iPS.get_field()-B) < threshold:
                        condition_met += 1
                    else:
                        condition_met = 0

                    if condition_met >= 20:
                        measuring=False
                        print(f"Finished ramping magnet to {B} T")
                        break
                    if time()-time0 > timeout:
                        measuring=False
                        print("Timeout reached")
                        break
        return
    
    def ramp_B(self,filename,Bs,rates,threshold=0.005,timeout_hours=12):
        filename = self.check_filename_duplicate(filename)

        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            headers = self.get_headers()
            writer = csv.writer(f)
            headers = self.get_headers()
            writer.writerows([headers])

            if type(Bs) is not list:
                Ts=[Bs]
            if type(rates) is not list:
                rates=[rates for T in Ts]
            if len(Bs) != len(rates):
                print("Warning: length of B and rate lists are not equal")

            for B,rate in zip(Bs,rates):
                self.iPS.set_field(B,rate)
                print(f"Ramping magnet to {B} T at {rate} T/min")

                time0 = time()
                timeout=timeout_hours*3600

                condition_met = 0
                measuring = True
                while measuring:
                    data = self.read_everything()
                    writer.writerows([data])
                    f.flush()
                    sleep(0.01)

                    if abs(self.iPS.get_field()-B) < threshold:
                        condition_met += 1
                    else:
                        condition_met = 0

                    if condition_met >= 5:
                        measuring=False
                        print(f"Finished ramping magnet to {B} T")
                        break
                    if time()-time0 > timeout:
                        measuring=False
                        print("Timeout reached")
                        break
        return

    def set_Vg(self,filename,Vgs,compliance=5e-7,wait=0.1):
        filename = self.check_filename_duplicate(filename)
        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            headers = self.get_headers()
            writer = csv.writer(f)
            headers = self.get_headers()
            writer.writerows([headers])
            
            if type(Vgs) is not list:
                Vgs=[Vgs]

            for _,Vsourcemeter in self.Vsourcemeters:
                Vsourcemeter.set_compliance(compliance)
            
            for Vg in Vgs:
                for _,Vsourcemeter in self.Vsourcemeters:
                    Vsourcemeter.set_voltage(Vg)
                    sleep(wait)
                    data = self.read_everything()
                    writer.writerows([data])
                    f.flush()


                