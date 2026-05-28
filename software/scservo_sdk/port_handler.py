#!/usr/bin/env python

import time
import serial
import sys
import platform

DEFAULT_BAUDRATE = 1000000
LATENCY_TIMER = 50 

class PortHandler(object):
    def __init__(self, port_name): # self is keyword that refers to the instance of the method, ex when u do port_handler = PortHandler(/dev/ttyACM0), self refers to port_handler
        self.is_open = False
        self.baudrate = DEFAULT_BAUDRATE
        self.packet_start_time = 0.0
        self.packet_timeout = 0.0
        self.tx_time_per_byte = 0.0

        self.is_using = False
        self.port_name = port_name
        self.ser = None

    def openPort(self):
        return self.setBaudRate(self.baudrate)

    def closePort(self):
        self.ser.close()
        self.is_open = False

    def clearPort(self):
        self.ser.flush()

    def setPortName(self, port_name):
        self.port_name = port_name

    def getPortName(self):
        return self.port_name

    def setBaudRate(self, baudrate):
        baud = self.getCFlagBaud(baudrate)

        if baud <= 0:
            return False 
        else:
            self.baudrate = baudrate
            return self.setupPort(baud)

    def getBaudRate(self):
        return self.baudrate

    def getBytesAvailable(self):
        return self.ser.in_waiting

    def readPort(self, length):
        """Read up to `length` bytes from the serial port.

        Previously this had a custom resync/reconstruction loop intended to
        recover from framing errors at the half-duplex bus turnaround. That
        turned out to be working around getty/console interference on
        /dev/ttyAMA0, not a real framing error — once the serial console was
        removed (cmdline.txt + serial-getty disabled, see docs/debugging/),
        clean 6/6 responses came back consistently.

        The old "read length+1 to absorb a dropped leading byte" pattern also
        actively broke multi-transaction SDK calls like ping() (which reads
        the PING reply and then the model-number register). Reading length+1
        bytes from the kernel and slicing to `length` discarded the extra
        byte the SECOND transaction needed, producing COMM_RX_CORRUPT.

        We now defer to pyserial's blocking read. If a real framing error
        ever returns (it shouldn't with the console off), handle it at the
        SDK-call level via the retry wrappers in software/control/_serial_utils.py
        rather than re-introducing the byte-stealing behavior here.
        """
        if sys.version_info > (3, 0):
            return self.ser.read(length)
        else:
            return [ord(ch) for ch in self.ser.read(length)]

    def writePort(self, packet):
        return self.ser.write(packet)

    def setPacketTimeout(self, packet_length):
        self.packet_start_time = self.getCurrentTime()
        self.packet_timeout = (self.tx_time_per_byte * packet_length) + (self.tx_time_per_byte * 3.0) + LATENCY_TIMER

    def setPacketTimeoutMillis(self, msec):
        self.packet_start_time = self.getCurrentTime()
        self.packet_timeout = msec

    def isPacketTimeout(self):
        if self.getTimeSinceStart() > self.packet_timeout:
            self.packet_timeout = 0
            return True

        return False

    def getCurrentTime(self):
        return round(time.time() * 1000000000) / 1000000.0

    def getTimeSinceStart(self):
        time_since = self.getCurrentTime() - self.packet_start_time
        if time_since < 0.0:
            self.packet_start_time = self.getCurrentTime()

        return time_since

    def setupPort(self, cflag_baud):
        if self.is_open:
            self.closePort()

        self.ser = serial.Serial(
            port=self.port_name,
            baudrate=self.baudrate,
            # parity = serial.PARITY_ODD,
            # stopbits = serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS,
            timeout=0.1   # was 0 (O_NONBLOCK); 0.1 uses select-based timeout so VMIN works
        )
        
        self.ser.setRTS(False)
        self.ser.setDTR(False)

        self.is_open = True

        self.ser.reset_input_buffer()

        self.tx_time_per_byte = (1000.0 / self.baudrate) * 10.0

        return True

    def getCFlagBaud(self, baudrate):
        if baudrate in [4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 250000, 500000, 1000000]:
            return baudrate
        else:
            return -1          