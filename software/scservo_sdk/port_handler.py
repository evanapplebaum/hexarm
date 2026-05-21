#!/usr/bin/env python

import time
import serial
import sys
import platform

DEFAULT_BAUDRATE = 1000000
LATENCY_TIMER = 50 

class PortHandler(object):
    def __init__(self, port_name):
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
            # self.setupPort(38400)
            # self.baudrate = baudrate
            return False  # TODO: setCustomBaudrate(baudrate)
        else:
            self.baudrate = baudrate
            return self.setupPort(baud)

    def getBaudRate(self):
        return self.baudrate

    def getBytesAvailable(self):
        return self.ser.in_waiting

    def readPort(self, length):
        """Read `length` bytes from the serial port with resync on framing errors.

        At the TX→RX bus turnaround, the servo's line-driver turn-on transient
        can corrupt the start bit of the first response byte. The PL011 flags a
        framing error and the Linux tty layer silently discards that byte.

        Fix: read one extra byte (length+1), then locate the FF FF packet header.
        If found at offset > 0, skip the leading garbage. If only a lone FF is
        found (first 0xFF dropped), prepend the missing 0xFF to reconstruct the
        original packet before returning it to the protocol handler.
        """
        buf = bytearray()
        deadline = time.time() + (self.packet_timeout / 1000.0) + 0.5
        target = length + 1  # one extra byte to absorb a possible leading dropped byte

        while len(buf) < target and time.time() < deadline:
            b = self.ser.read(1)
            if b:
                if sys.version_info > (3, 0):
                    buf.extend(b)
                else:
                    buf.extend([ord(ch) for ch in b])

        # --- resync: find FF FF header ---
        for i in range(len(buf) - 1):
            if buf[i] == 0xFF and buf[i + 1] == 0xFF:
                result = bytes(buf[i:i + length])
                return result if sys.version_info > (3, 0) else list(result)

        # --- lone FF: first 0xFF was dropped by framing error, reconstruct ---
        for i in range(len(buf)):
            if buf[i] == 0xFF:
                reconstructed = bytearray([0xFF]) + buf[i:i + length - 1]
                return bytes(reconstructed) if sys.version_info > (3, 0) else list(reconstructed)

        # --- nothing useful: return whatever we have ---
        result = bytes(buf[:length])
        return result if sys.version_info > (3, 0) else list(result)

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
            timeout=0
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