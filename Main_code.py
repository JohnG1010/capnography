import numpy as np 
import serial
import sys
import os
import time
from time import sleep
from PyQt5.QtWidgets import *
from PyQt5 import QtCore
from PyQt5.QtGui import *
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
from scipy.signal import find_peaks
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import *
from tkinter.ttk import *

#Importing all libraries needed (import tkinter twice because of slightly different commands)

ser = serial.Serial("/dev/ttyUSB0", 38400)
#This sets our serial communications to the UART cable and the sensor. BAUD IS IMPORTANT

multi = 10 #Found in 'Check multiplier' function in menu
to_mmHg = 0.00076 #Conversion from ppm to mmHg

K_0 = str.encode("K 0\r\n") #Sets sensor to sleeping mode
K_1 = str.encode("K 1\r\n") #Sets sensor to streaming mode
K_2 = str.encode("K 2\r\n") #Sets sensor to polling mode
Z = str.encode("Z\r\n") #Returns most recent recorded value
z = str.encode("z\r\n")
setfilt = str.encode("A 0\r\n") #Initialises command for setting filter values.
setfilt_32 = str.encode("A 32\r\n") #The recommended filter for calibration is 32.
calibrate = str.encode("G\r\n") #Sets the zero point using fresh air
findMult = str.encode(".\r\n") #Finds the sensor multiplier
findFilter = str.encode("a\r\n")
findpressure_and_conc_comp = str.encode("s\r\n")
sensor_version = str.encode("Y\r\n")
#List of commands used to talk to sensor

ser.reset_input_buffer()
ser.reset_output_buffer()
ser.write(K_1)
ser.write(setfilt)

class capnoWindow(QMainWindow): # This uses PyQTGraph to design a window that displays our capnogram
    def __init__(self, *args, **kwargs): #Initialisation for the class
        super(capnoWindow, self).__init__(*args, **kwargs)
        self.count = 0
        self.capnoWidget = pg.PlotWidget()
        self.setCentralWidget(self.capnoWidget)
        self.capnoWidget.setXRange(0, 15)
        self.capnoWidget.setYRange(0, 60) #Sets the range from the minimum to maximum CO2 ppm that the sensor can detect.
        self.capnoWidget.setLabel('left', 'CO2 concentration (mmHg)')
        self.capnoWidget.setLabel('bottom', 'Time (s)')
        self.ET = pg.TextItem(text="ETCO2: ", anchor=(0,0))
        self.current_etco2 = "0"
        self.ET_val = pg.TextItem(text= self.current_etco2, anchor=(0.5,0))
        self.ET_val.setPos(1.5,58)
        self.ET_val.setFont(QFont('Arial', 35))
        self.capnoWidget.addItem(self.ET_val, ignoreBounds=True)
        self.breathTxt = pg.TextItem(text="Breaths per min:", anchor=(1,0))
        self.bpm = "0"
        self.breath_val = pg.TextItem(text= self.bpm, anchor=(0.5,0))
        self.breath_val.setFont(QFont('Arial', 35))
        self.ET.setPos(1,60)
        self.breathTxt.setPos(15,60)
        self.breath_val.setPos(13.9,58)
        self.warning = pg.TextItem(text="WARNING: LOW ETCO2", anchor=(0.5,0))
        self.warning.setPos(7.5,60)
        self.warning.setFont(QFont('Arial', 30))
        self.capnoWidget.addItem(self.ET, ignoreBounds=True)
        self.capnoWidget.addItem(self.breathTxt, ignoreBounds=True)
        self.x = np.arange(0, 15, 0.02) # 750 time points
        self.y = np.empty(750).tolist() #starting array.
        self.y_min = np.empty(3000).tolist()
        self.capnoWidget.setBackground('black')
        self.capnoWidget.showGrid(x=True,y=True)
        self.capnoWidget.setTitle("The Capnograph")
        pen = pg.mkPen(color=(0, 255, 0), width=3)
        self.data_line = self.capnoWidget.plot(self.x, self.y, pen=pen)
        self.timer = QtCore.QTimer()
        self.timer1 = QtCore.QTimer()
        self.timer2 = QtCore.QTimer()
        self.timer.setInterval(1)
        self.timer1.setInterval(1000)
        self.timer2.setInterval(500)
        self.timer.timeout.connect(self.updateCapno)
        self.timer1.timeout.connect(self.updateETC)
        self.timer2.timeout.connect(self.breathpm)
        
        self.timer.start()
        self.timer1.start()
        self.timer2.start()

    def updateCapno(self): #This definition is how we update the graph in real-time.
        try:
            resp_c = ser.read(10)
            test_c = bytes.decode(resp_c)
            test_c = round((float(test_c[4:8]) * multi)*to_mmHg, 1)
            self.y = self.y[1:]
            self.y.append(test_c)
            self.y_min = self.y_min[1:]
            self.y_min.append(test_c)
            self.data_line.setData(self.x, self.y) #Add in new data.
        except:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
    def updateETC(self):
        for idx,i in enumerate(self.y):
            if idx > 40:
                if max(self.y[idx-40:idx-21]) <= self.y[idx-20] >= max(self.y[idx-19:idx]):
                    if self.y[idx-20] > 5000*to_mmHg and self.y[idx-20] != float(self.current_etco2):
                        self.current_etco2 = str((self.y[idx-20]))
                        self.capnoWidget.removeItem(self.ET_val)
                        if self.y[idx-20] < 30000*to_mmHg:
                            self.capnoWidget.removeItem(self.warning)
                            self.ET_val = pg.TextItem(text= self.current_etco2, anchor=(0.5,0))
                            self.ET_val.setPos(1.5,58)
                            self.ET_val.setFont(QFont('Arial', 35))
                            self.capnoWidget.addItem(self.ET_val, ignoreBounds=True)
                            self.capnoWidget.addItem(self.warning, ignoreBounds=True)
                        else:
                            self.capnoWidget.removeItem(self.warning)
                            self.ET_val = pg.TextItem(text= self.current_etco2, anchor=(0.5,0))
                            self.ET_val.setPos(1.5,58)
                            self.ET_val.setFont(QFont('Arial', 35))
                            self.capnoWidget.addItem(self.ET_val, ignoreBounds=True)
                            
    def breathpm(self):
        try:
            peaks,_ = find_peaks(self.y_min, width=1, distance=40, height=8)
            local_max_num = len(peaks)
            self.bpm = local_max_num
            self.capnoWidget.removeItem(self.breath_val)
            self.breath_val = pg.TextItem(text= str(self.bpm), anchor=(0.5,0))
            self.breath_val.setPos(13.9,58)
            self.breath_val.setFont(QFont('Arial', 35))
            self.capnoWidget.addItem(self.breath_val, ignoreBounds=True)
        except:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        
def multiMode():
    ser.write(K_0)
    sleep(0.2)
    ser.write(setfilt)
    sleep(0.2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()  
    ser.write(findMult)
    mult = ser.read(10)
    multPrint = bytes.decode(mult)
    multPrint = float(multPrint[4:8])
    
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(findpressure_and_conc_comp)
    pres_conc = ser.read(10)
    pres_concPrint = bytes.decode(pres_conc)
    pres_concPrint = float(pres_concPrint[4:8])
    
    ser.reset_input_buffer()
    ser.reset_output_buffer()  
    ser.write(findFilter)
    filt = ser.read(10)
    filtPrint = bytes.decode(filt)
    filtPrint = float(filtPrint[4:8])
    
    ser.reset_input_buffer()
    ser.reset_output_buffer()  
    ser.write(sensor_version)
    version = ser.read(47)
    versionPrint = bytes.decode(version)
    
    popupmsg("Multiplier: " + str(multPrint) + "\n" + "Digital filter setting:" + str(filtPrint) + "\n" + "Pressure and concentration compensation value: " + str(pres_concPrint) + "\n\n" + "Firmware version and sensor serial number:" + "\n" + str(versionPrint))       
    
def capnoMode():
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(K_1)
    sleep(0.2)
    ser.write(setfilt)
    sleep(0.2)
    app = QApplication(sys.argv)
    w = capnoWindow()
    w.showMaximized()
    app.exec_()
    
def popupmsg(msg):
    popup = tk.Tk()
    popup.wm_title("!")
    label = ttk.Label(popup, text=msg, font=("Helvetica", 10))
    label.pack(side="top", fill="x", pady=10)
    B1 = ttk.Button(popup, text="Okay", command = popup.destroy)
    B1.pack()
    popup.mainloop()

def streamMode():
    ser.write(K_1)
    ser.reset_input_buffer()#Clears any input to the sensor, which stops data from becoming garbled
    ser.reset_output_buffer()
    while True:
        if key.is_pressed('q'): #Exit condition - check first.
            print('\nReturning to menu...\n')
            open('tkinterMenu.py')
            break
        #Here we read the CO2 values from the sensor, decode from a byte string and then trim the string so it only has the value we need.
        resp_m = ser.read(10)
        test_m = bytes.decode(resp_m)
        test_m = float(test_m[4:8]) * multi
        print("CO2 PPM = ", (test_m))

def exitMode():
    os.system("sudo shutdown now -h")

def zeroPoint():
    sleep(0.2)
    ser.write(setfilt_32)
    sleep(0.2)
    warningMsg = tk.Tk()
    warningMsg.wm_title("Calibration")
    label = ttk.Label(warningMsg, text="Please take the capnograph outside and let it acclimatise to fresh air for 5 minutes", font=("Helvetica", 10))
    label.pack(side="top", fill="x", pady=10)
    B1 = ttk.Button(warningMsg, text="Calibrate", command = ser.write(calibrate) and warningMsg.destroy)
    B1.pack()
    warningMsg.mainloop()
    popupmsg("Calibration complete")

def filterSetting():
    filterChange = tk.Tk()
    filterChange.wm_title("Filter Change")
    B1 = ttk.Button(filterChange, text="0 (recommended)", command = lambda: filterChanger("0"))
    B2 = ttk.Button(filterChange, text="4", command = lambda: filterChanger("4"))
    B3 = ttk.Button(filterChange, text="8", command = lambda: filterChanger("8"))
    B4 = ttk.Button(filterChange, text="12", command = lambda: filterChanger("12"))
    B5 = ttk.Button(filterChange, text="16", command = lambda: filterChanger("16"))
    B1.pack()
    B2.pack()
    B3.pack()
    B4.pack()
    B5.pack()
    filterChange.mainloop()

def filterChanger(no):
    global setfilt
    setfilt = str.encode("A " + no + "\r\n")


root = Tk()
photo = PhotoImage(file="/home/capno-jg/Documents/Capnography_mode.png.png")  
photo1 = PhotoImage(file="/home/capno-jg/Documents/Calibration_mode.png.png")
photo2 = PhotoImage(file="/home/capno-jg/Documents/Info_mode.png.png")  
photo3 = PhotoImage(file="/home/capno-jg/Documents/Shutdown.png.png")
photo4 = PhotoImage(file="/home/capno-jg/Documents/Filter_mode.png") #Import all the png files for use as buttons. Needs a bit of cleaning up  

photoimage = photo.subsample(6, 7)
photoimage1 = photo1.subsample(6, 7)
photoimage2 = photo2.subsample(6, 7)
photoimage3 = photo3.subsample(6, 7)
photoimage4 = photo4.subsample(6, 7) #This resizes the buttons so they look a tad nicer
 
Button(root, image = photoimage, compound = LEFT, command = capnoMode).pack(side = TOP)
Button(root, image = photoimage1, compound = LEFT, command = zeroPoint).pack(side = TOP)
Button(root, image = photoimage4, compound = LEFT, command = filterSetting).pack(side = TOP)
Button(root, image = photoimage2, compound = LEFT, command = multiMode).pack(side = LEFT)
Button(root, image = photoimage3, compound = LEFT, command = exitMode).pack(side = RIGHT) #Here we assign code to each button that runs when pressed.

root.wm_title("Capnograph Menu")  
root.attributes('-fullscreen', True)
mainloop()
