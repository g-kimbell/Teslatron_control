import time
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThreadPool
from instruments import Voltmeter, Sourcemeter, VSourcemeter, MercuryiTC, MercuryiPS
import pyqtgraph as pg
import logging

class InitialiseWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Initialise Instruments')
        self.init_UI()
        self.show()

    # super the QTableWidget class to add a method to load data from an array
    class TableWidget(QtWidgets.QTableWidget):
        def load_data(self, data):
            for i, row in enumerate(data):
                for j, col in enumerate(row):
                    item = QtWidgets.QTableWidgetItem(col)
                    self.setItem(i, j, item)
        def get_data(self):
            data=[]
            for i in range(self.rowCount()):
                # ignore empty rows
                if self.item(i,0) is None:
                    continue
                row=[]
                for j in range(self.columnCount()):
                    row.append(self.item(i,j).text().strip())
                data.append(row)
            return data

    def init_UI(self):
        # load data from instruments.txt
        try:
            with open("instruments.txt") as f:
                lines = f.readlines()
                lines = [line for line in lines if line.strip()] # delete empty lines
                lines = [line for line in lines if not line.startswith('#')] # delete lines with comments
                lines = [line.rstrip('\n') for line in lines] # delete newlines
                label_idx = [i for i, line in enumerate(lines) if line.startswith('[')] # split into a separate list for each instrument type
                label = [lines[i].strip('[').strip(']') for i in label_idx] # labels are the strings in between the square brackets of the label_idx
                lines = [line.split(',') for line in lines] # split data lines by comma
                data = [lines[i+1:j] for i, j in zip(label_idx, label_idx[1:]+[None])] # split data into a separate list for each instrument type
                data_dict = dict(zip(label, data)) # make a dictionary with the labels as keys and the data as values
                logging.info("instruments.txt loaded successfully")
        except:
            logging.error('Error: instruments.txt not found or incorrectly formatted. Loading defaults.')
            data_dict = {'Voltmeter': [['V_A', 'GPIB::6::INSTR'],
                                        ['V_B', 'GPIB::12::INSTR'],
                                        ['V_C', 'GPIB::22::INSTR'],
                                        ['V_D', 'GPIB::25::INSTR']],
                        'Current source': [['I_A', 'GPIB::5::INSTR'],
                                            ['I_B', 'GPIB::11::INSTR']],
                        'Voltage source': [['Vg_A', 'GPIB::1::INSTR'],
                                            ['Vg_B', 'GPIB::2::INSTR']],
                        'Temperature controller': [['iTC', 'ASRL7::INSTR']],
                        'Magnet Power supply': [['iPS', 'ASRL8::INSTR']]}

        voltmeter_data = data_dict['Voltmeter']
        Isource_data = data_dict['Current source']
        Vsource_data = data_dict['Voltage source']
        iTC_data = data_dict['Temperature controller']
        iPS_data = data_dict['Magnet Power supply']

        self.button = QtWidgets.QPushButton('Initialise all', self)
        self.button.clicked.connect(self.start_button_clicked)

        self.voltmeter_table = self.TableWidget()
        self.voltmeter_table.setColumnCount(2)
        self.voltmeter_table.setRowCount(10)
        self.voltmeter_table.load_data(voltmeter_data)
        self.voltmeter_table.setHorizontalHeaderLabels(['Name', 'GPIB Address'])

        self.sourcemeter_table = self.TableWidget()
        self.sourcemeter_table.setColumnCount(2)
        self.sourcemeter_table.setRowCount(10)
        self.sourcemeter_table.load_data(Isource_data)
        self.sourcemeter_table.setHorizontalHeaderLabels(['Name', 'GPIB Address'])

        self.Vsourcemeter_table = self.TableWidget()
        self.Vsourcemeter_table.setColumnCount(2)
        self.Vsourcemeter_table.setRowCount(10)
        self.Vsourcemeter_table.load_data(Vsource_data)
        self.Vsourcemeter_table.setHorizontalHeaderLabels(['Name', 'GPIB Address'])

        self.iTC_label = QtWidgets.QLabel("COM address:")
        self.iTC_COM = QtWidgets.QLineEdit(iTC_data[0][0])

        self.iPS_label = QtWidgets.QLabel("COM address:")
        self.iPS_COM = QtWidgets.QLineEdit(iPS_data[0][0])
        self.iPS_COM.setAlignment(QtCore.Qt.AlignTop)

        self.instr_layout = QtWidgets.QGridLayout(self)
        self.instr_layout.addWidget(QtWidgets.QLabel('Voltmeter'), 0, 0, 1, 1)
        self.instr_layout.addWidget(self.voltmeter_table, 1, 0, 3, 1)
        self.instr_layout.addWidget(QtWidgets.QLabel('Current Source'), 0, 2 )
        self.instr_layout.addWidget(self.sourcemeter_table, 1, 2, 3, 1)
        self.instr_layout.addWidget(QtWidgets.QLabel('Voltage Source'), 0, 4 ,1, 1)
        self.instr_layout.addWidget(self.Vsourcemeter_table, 1, 4, 3, 1)
        self.instr_layout.addWidget(QtWidgets.QLabel('Temperature Controller'), 0, 6, 1, 1)
        self.instr_layout.addWidget(self.iTC_label, 1, 6, 1, 1)
        self.instr_layout.addWidget(self.iTC_COM, 2, 6, 1, 1)
        self.instr_layout.addWidget(QtWidgets.QLabel('Magnet Power Supply'), 0, 8, 1, 1)
        self.instr_layout.addWidget(self.iPS_label, 1, 8, 1, 1)
        self.instr_layout.addWidget(self.iPS_COM, 2, 8, 1, 1)
        self.instr_layout.addWidget(self.button,4,0,1,2)

    def start_button_clicked(self):
        self.init_instruments()
        self.start_GUI()

    def init_instruments(self):
        global voltmeters, sourcemeters, Vsourcemeters, iTC, iPS
        voltmeters = {}
        for row in self.voltmeter_table.get_data():
            voltmeters[row[0]] = Voltmeter(row[1])
        sourcemeters = {}
        for row in self.sourcemeter_table.get_data():
            sourcemeters[row[0]] = Sourcemeter(row[1])
        Vsourcemeters = {}
        for row in self.Vsourcemeter_table.get_data():
            Vsourcemeters[row[0]] = VSourcemeter(row[1])
        if self.iTC_COM.text():
            iTC = MercuryiTC(self.iTC_COM.text())
        if self.iPS_COM.text():
            iPS = MercuryiPS(self.iPS_COM.text())

    def start_GUI(self):
        window.show()
        self.close()

class WorkerSignals(QtCore.QObject): # class used to send signals to main GUI thread
    result = QtCore.pyqtSignal(list)
    finished = QtCore.pyqtSignal()

class Data_Collector(QtCore.QRunnable): # thread that collects the data
    def __init__(self):
        super(Data_Collector, self).__init__()
        self.signals = WorkerSignals()
        self.filename = window.filename
        self.loop_counter = 0


    @QtCore.pyqtSlot() # this is the function that is called when the thread is started
    def run(self):
        while window.measuring == True:
            self.loop_counter += 1
            # Get all the data
            data = {}
            t = time.time()
            data["Time"] = t
            for name,voltmeter in voltmeters.items():
                voltmeter.start_voltage_measurement()
            for name,voltmeter in voltmeters.items():
                data[name] = voltmeter.get_voltage_measurement()
            for name,sourcemeter in sourcemeters.items():
                data[name] = sourcemeter.get_current()
            for name,Vsourcemeter in Vsourcemeters.items():
                data[name] = Vsourcemeter.get_voltage()
            data["T_probe"] = iTC.get_probe_temp()
            data["T_probe_setpoint"] = iTC.get_probe_setpoint()
            data["T_probe_ramp_rate"] = iTC.get_probe_ramp_rate()
            data["T_probe_heater"] = iTC.get_probe_heater()
            data["T_VTI"] = iTC.get_VTI_temp()
            data["T_VTI_setpoint"] = iTC.get_VTI_setpoint()
            data["T_VTI_ramp_rate"] = iTC.get_VTI_ramp_rate()
            data["T_VTI_heater"] = iTC.get_VTI_heater()

            time.sleep(0.5)
            self.signals.result.emit(data)
        self.signals.finished.emit()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Test GUI')
        self.setGeometry(50,50,800,600)
        self.measuring = False
        self.filename = 'test_data.txt'
        self.plot_data = []
        self.initUI()

    def initUI(self):
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QtWidgets.QGridLayout()
        self.central_widget.setLayout(self.layout)

        self.start_button = QtWidgets.QPushButton('Start')
        self.start_button.clicked.connect(self.start)
        self.layout.addWidget(self.start_button,0,0)

        self.stop_button = QtWidgets.QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop)
        self.layout.addWidget(self.stop_button,0,1)

        self.run_script_button = QtWidgets.QPushButton('Run script')
        self.run_script_button.clicked.connect(self.run_script)
        self.layout.addWidget(self.run_script_button,0,2)

        self.plot = pg.PlotWidget()
        self.layout.addWidget(self.plot,1,0,1,3)

    def start(self):
        self.start_time = time.time()
        self.measuring = True
        self.worker = Data_Collector()
        self.worker.signals.result.connect(self.update_plot)
        self.worker.signals.finished.connect(self.finished)
        QtCore.QThreadPool.globalInstance().start(self.worker)

    def stop(self):
        self.measuring = False

    def update_plot(self,data):
        #TODO let the user choose which data to plot as x and y
        #TODO allow the user to scroll, pan, zoom etc
        self.plot_data.append(data)
        for i in range(len(data)-1):
            self.plot.plot([x[0]-self.start_time for x in self.plot_data],[x[i+1] for x in self.plot_data],pen=(i,len(data)-1),symbol='o')

    def finished(self):
        logging.info('Finished measurement')

    def run_script(self):
        #TODO allow the user to run a script with various commands e.g. sweep field and measure etc.
        pass


global threadpool
threadpool= QThreadPool()
app = QtWidgets.QApplication([])
window = MainWindow()
init_window = InitialiseWindow()
app.exec_()