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
        headers = ["Time"]
        if self.iTC:
            headers += ["T_probe (K)", "T_probe_setpoint (K)", "T_probe_ramp_rate (K/min)", "heater_probe (%)", "T_VTI (K)", "T_VTI_setpoint (K)", "T_VTI_ramp_rate (K/min)", "heater_VTI (%)","Pressure (mB)","Needlevalve"]
        if self.iPS:
            headers += ["B (T)", "B_setpoint (T)", "B_ramp_rate (T/min)"]
        for name,sourcemeter in self.sourcemeters:
            headers.append(f"I_{name} (A)")
        for name,Vsourcemeter in self.Vsourcemeters:
            headers.append(f"_Vg_{name} (V)")
            headers.append(f"Ileak_{name} (A)")
        for name,voltmeter in self.voltmeters:
            headers.append(f"V+_{name} (V)")
        for name,voltmeter in self.voltmeters:
            headers.append(f"V-_{name} (V)")
        for Iname,sourcemeter in self.sourcemeters:
            for Vname,voltmeter in self.voltmeters:
                headers.append(f"R_{Iname}{Vname} (ohm)")
        return headers

    def read_everything(self):
        Is = []
        Vps = []
        Vns = []
        data = [time()]
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
            Is += [sourcemeter.get_current()]
        data += Is
        for name,Vsourcemeter in self.Vsourcemeters:
            Vg,Ileak = Vsourcemeter.get_voltage_and_Ileak()
            data += [Vg,Ileak]
        for name,voltmeter in self.voltmeters:
            Vps += [voltmeter.get_voltage_measurement()]
        data += Vps
        for name,sourcemeter in self.sourcemeters:
            sourcemeter.reverse_current()
        for name,voltmeter in self.voltmeters:
            voltmeter.start_voltage_measurement()
        for name,voltmeter in self.voltmeters:
            Vns += [voltmeter.get_voltage_measurement()]
        data += Vns
        for I in Is:
            for Vp,Vn in zip(Vps,Vns):
                try:
                    data += [0.5*(Vp-Vn)/I]
                except:
                    data += [np.nan]
        return data
    
    def print_current_vals(self):
        headers=self.get_headers()
        data=self.read_everything()
        for header,datum in zip(headers,data):
            print(f"{header}: {datum}")

    @staticmethod
    def check_filename_duplicate(path):
        filename,extension = os.path.splitext(path)
        i=1
        while os.path.isfile(path):
            path = filename + "_" + str(i) + extension
            i+=1
        return path
    
    @staticmethod
    def make_list(x):
        if hasattr(x,'__iter__'):
            return list(x)
        else:
            return [x]
        
    def measure_until_interrupted(self,filename,timeout_hours=18,comment=" "):
        try:
            time0 = time()
            timeout=timeout_hours*3600
            filename = self.check_filename_duplicate(filename)
            with open(filename, 'w', newline='') as f:
                print(f"Writing data to {filename}")
                writer = csv.writer(f)
                writer.writerows([[str(ctime())],["Continuous measurement"],[comment],["[DATA]"]])
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
    
    def ramp_T(self,filename,controller,Ts,rates,threshold=0.05,base_T_threshold=0.001,timeout_hours=18,comment=" "):
        filename = self.check_filename_duplicate(filename)

        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            writer.writerows([[str(ctime())],[f"Ramp {controller} T"],[comment],["[DATA]"]])
            headers = self.get_headers()
            writer.writerows([headers])

            if type(Ts) is not list:
                Ts=[Ts]
            if type(rates) is not list:
                rates=[rates for T in Ts]
            if len(Ts) != len(rates):
                print("Warning: length of T and rate lists are not equal")

            for T,rate in zip(Ts,rates):
                if (rate==0) or (rate==np.nan) or (rate==np.inf):
                    match controller:
                        case "probe":
                            self.iTC.set_probe_temp(T)
                        case "VTI":
                            self.iTC.set_VTI_temp(T)
                        case "both":
                            self.iTC.set_probe_temp(T)
                            self.iTC.set_VTI_temp(T)
                        case _:
                            raise ValueError("Invalid controller, use 'probe', 'VTI', or 'both'")
                    print(f"Setting {controller} to {T} K")
                    min_time=120
                else:
                    match controller:
                        case "probe":
                            min_time = 60*abs(T-self.iTC.get_probe_temp())/rate
                            self.iTC.ramp_probe_temp(T,rate)
                        case "VTI":
                            min_time = 60*abs(T-self.iTC.get_VTI_temp())/rate
                            self.iTC.ramp_VTI_temp(T,rate)
                        case "both":
                            min_time = max(60*abs(T-self.iTC.get_VTI_temp())/rate,60*abs(T-self.iTC.get_probe_temp())/rate)
                            self.iTC.ramp_probe_temp(T,rate)
                            self.iTC.ramp_VTI_temp(T,rate)
                        case _:
                            raise ValueError("Invalid controller. Use 'probe', 'VTI', or 'both'")
                    print(f"Ramping {controller} to {T} K at {rate} K/min")
                    

                time0 = time()
                timeout=timeout_hours*3600

                T_reached = 0
                T_stopped = 0
                T_diff_sign_change = 0

                prev_VTI_T=0
                prev_VTI_diff=0
                prev_probe_T=0
                prev_probe_diff=0

                measuring = True
                while measuring:
                    data = self.read_everything()
                    writer.writerows([data])
                    f.flush()
                    sleep(0.01)

                    probe_T = self.iTC.get_probe_temp()
                    VTI_T = self.iTC.get_VTI_temp()
                    probe_diff = probe_T - prev_probe_T
                    VTI_diff = VTI_T - prev_VTI_T
                    match controller:
                        case "probe":
                            if abs(probe_T-T) < threshold:
                                T_reached += 1
                            else:
                                T_reached = 0
                            if abs(probe_diff) < base_T_threshold:
                                T_stopped += 1
                            else:
                                T_stopped = 0
                            if probe_diff*prev_probe_diff<0:
                                T_diff_sign_change = 1
                            else:
                                T_diff_sign_change = 0
                        case "VTI":
                            if abs(VTI_T-T) < threshold:
                                T_reached += 1
                            else:
                                T_reached = 0
                            if abs(VTI_diff) < base_T_threshold:
                                T_stopped += 1
                            else:
                                T_stopped = 0
                            if VTI_diff*prev_VTI_diff<0:
                                T_diff_sign_change = 1
                            else:
                                T_diff_sign_change = 0
                        case "both":
                            if (abs(probe_T-T) < threshold) and (abs(VTI_T-T) < threshold):
                                T_reached += 1
                            else:
                                T_reached = 0
                            if (abs(probe_diff) < base_T_threshold) and (abs(VTI_diff) < base_T_threshold):
                                T_stopped += 1
                            else:
                                T_stopped = 0
                            if (probe_diff*prev_probe_diff<0) and (VTI_diff*prev_VTI_diff<0):
                                T_diff_sign_change = 1
                            else:
                                T_diff_sign_change = 0
                    prev_probe_T = probe_T
                    prev_VTI_T = VTI_T
                    prev_probe_diff = probe_diff
                    prev_VTI_diff = VTI_diff

                    if (T_reached >= 30) and (T_diff_sign_change==1) and (time()-time0 > min_time):
                        measuring=False
                        print(f"Finished ramping {controller} to {T} K")
                        break
                    if (T_stopped >= 50) and (T_diff_sign_change==1) and (time()-time0 > min_time):
                        measuring=False
                        print(f"Reached base T in {controller} at {probe_T} K probe, {VTI_T} K VTI")
                        break
                    if time()-time0 > timeout:
                        measuring=False
                        print("Timeout reached")
                        break
        return
    
    def set_T(self,filename,controller,T,**kwargs):
        self.ramp_T(filename,controller,T,0,**kwargs)
        return
    
    def ramp_heater(self,filename,probe_heater,VTI_heater,wait=0.1,comment=" "):
        filename = self.check_filename_duplicate(filename)
        probe_heater=self.make_list(probe_heater)
        VTI_heater=self.make_list(VTI_heater)
        if len(probe_heater)==1:
            probe_heater = probe_heater*len(VTI_heater)
        if len(VTI_heater)==1:
            VTI_heater = VTI_heater*len(probe_heater)
        if len(probe_heater)!=len(VTI_heater):
                print("WARNING: Probe and VTI heater lists area a different length")

        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            writer.writerows([[str(ctime())],[f"Set Vg"],[comment],["[DATA]"]])
            headers = self.get_headers()
            writer.writerows([headers])
            
            for probe_heat,VTI_heat in zip(probe_heater,VTI_heater):
                self.iTC.set_probe_heater(probe_heat)
                self.iTC.set_VTI_heater(VTI_heat)
                sleep(wait)
                data = self.read_everything()
                writer.writerows([data])
                f.flush()
            print(f"Finished ramping heater")

    
    def ramp_B(self,filename,Bs,rates,threshold=0.005,timeout_hours=18,comment=" "):
        filename = self.check_filename_duplicate(filename)

        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            writer.writerows([[str(ctime())],[f"Ramp magnetic field"],[comment],["[DATA]"]])
            headers = self.get_headers()
            writer.writerows([headers])

            if type(Bs) is not list:
                Ts=[Bs]
            if type(rates) is not list:
                rates=[rates for T in Ts]
            if len(Bs) != len(rates):
                print("Warning: length of B and rate lists are not equal")

            for B,rate in zip(Bs,rates):
                min_time = 60*abs(B-self.iPS.get_field())/rate
                self.iPS.set_field(B,rate)
                print(f"Ramping magnet to {B} T at {rate} T/min")

                time0 = time()
                timeout=timeout_hours*3600

                B_reached = 0
                measuring = True
                while measuring:
                    data = self.read_everything()
                    writer.writerows([data])
                    f.flush()
                    sleep(0.01)

                    if abs(self.iPS.get_field()-B) < threshold:
                        B_reached += 1
                    else:
                        B_reached = 0

                    if (B_reached >= 10) and (time()-time0 > min_time):
                        measuring=False
                        print(f"Finished ramping magnet to {B} T")
                        break
                    if time()-time0 > timeout:
                        measuring=False
                        print("Timeout reached")
                        break
        return

    def set_Vg(self,filename,Vgs,compliance=5e-7,wait=0.1,comment=" "):
        filename = self.check_filename_duplicate(filename)
        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            writer.writerows([[str(ctime())],[f"Set Vg"],[comment],["[DATA]"]])
            headers = self.get_headers()
            writer.writerows([headers])
            
            if type(Vgs) is not list:
                Vgs=[Vgs]

            for _,Vsourcemeter in self.Vsourcemeters:
                Vsourcemeter.set_compliance(compliance)
            
            for Vg in Vgs:
                for _,Vsourcemeter in self.Vsourcemeters:
                    if abs(Vg)<250:
                        Vsourcemeter.set_voltage(Vg)
                        sleep(wait)
                        data = self.read_everything()
                        writer.writerows([data])
                        f.flush()
                    else:
                        print(f"Gate setpoint {Vg} V is larger than max 250 V")

    def set_current(self,I,compliance=5):
        print(f"Setting current to {I}, compliance {compliance}")
        if abs(I)<=1e-4:
            for _,sourcemeter in self.sourcemeters:
                sourcemeter.set_compliance(compliance)
                sourcemeter.set_current(I)
                sourcemeter.turn_on()
        else:
            print(f"Current setpoint {I} A is larger than max 1e-4 A")
    
    def perform_IV(self,filename,Is,compliance=5,wait=0.1,comment=" "):
        filename = self.check_filename_duplicate(filename)
        with open(filename, 'w', newline='') as f:
            print(f"Writing data to {filename}")
            writer = csv.writer(f)
            writer.writerows([[str(ctime())],[f"Measure IV"],[comment],["[DATA]"]])
            headers = self.get_headers()
            writer.writerows([headers])
            
            for _,sourcemeter in self.sourcemeters:
                sourcemeter.set_compliance(compliance)
                sourcemeter.set_current(Is[0])
                sourcemeter.turn_on()
            
            for I in Is:
                if abs(I)<=1e-4:
                    for _,sourcemeter in self.sourcemeters:
                        sourcemeter.set_current(I)
                        sleep(wait)
                        data = self.read_everything()
                        writer.writerows([data])
                        f.flush()
                else:
                    print(f"Current setpoint {I} A is larger than max 1e-4 A")

    




                