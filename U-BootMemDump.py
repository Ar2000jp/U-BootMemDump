#!/usr/bin/python3
# -*- coding:utf-8 -*-

#
# Copyright (C) 2014 Ahmad Draidi
# E-Mail: ar2000jp@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import time
import serial
import array
import argparse

def atExit():
    try:
        G_TTYDev.close()
        G_OutFile.close()
    except Exception:
        pass

G_MemOpStartAddr = 0xDEADBEEF
G_MemOpByteCount = 1024 * 128
G_MemOpBurstSize = 1024
G_BytesPerLine = 16

G_TTYDevName = "/dev/ttyACM0"

# Used to check if U-Boot has finished executing a command.
G_UBootPrompt = "U-Boot#"
# This code can only handle the byte variant.
G_UBootMemDumpCmd = "md.b"
# Used to check if U-Boot is responding. No need to change this.
G_UBootNopCmd = " "

G_OutFileName = "dump-0x{0:08X}.bin".format(G_MemOpStartAddr)

print("U-BootMemDump.\nCopyright (C) 2014 Ahmad Draidi")

parser = argparse.ArgumentParser(description="Dump memory through"
				 " the U-Boot shell.")
parser.add_argument("address", help="Memory dump start address.",
		    metavar="StartAddress")
parser.add_argument("-s", "--size", help="Number of bytes to dump."
		    " Default is {0:d} bytes.".format(G_MemOpByteCount),
                    metavar="Bytes")
parser.add_argument("-b", "--burstsize", help="Number of bytes per"
		    " single operation. Must be a multiple of "
		    "{0:d}.".format(G_BytesPerLine), metavar="Bytes")
parser.add_argument("-d", "--ttydevice", help="TTY device to use."
		    " Default is \"{0:s}\".".format(G_TTYDevName),
		    metavar="Device")
parser.add_argument("-p", "--prompt", help="U-Boot shell prompt."
		    " Default is \"{0:s}\".".format(G_UBootPrompt),
		    metavar="PromptString")
parser.add_argument("-f", "--outfile", help="Output file name."
		    " Default is \"{0:s}\", where 0x{1:08X} is replaced"
		    " with the StartAddress.".format(G_OutFileName,
		    G_MemOpStartAddr), metavar="OutFileName")
args = parser.parse_args()

G_MemOpStartAddr = int(args.address, 0)

if(args.prompt != None):
    G_UBootPrompt = args.prompt

if(args.ttydevice != None):
    G_TTYDevName = args.ttydevice

if(args.burstsize != None):
    G_MemOpBurstSize = int(args.burstsize, 0)

if(args.size != None):
    G_MemOpByteCount = int(args.size, 0)

if(args.outfile != None):
    G_OutFileName = args.outfile
else:
    G_OutFileName = "dump-0x{0:08X}.bin".format(G_MemOpStartAddr)

if((G_MemOpBurstSize % G_BytesPerLine) != 0):
    print("Burst size ({0:d}) isn't ".format(G_MemOpBurstSize) +
          "a multiple of {0:d}.".format(G_BytesPerLine))
    exit(1)

if((G_MemOpByteCount % G_MemOpBurstSize) != 0):
    print("Dump size ({0:d}) isn't a multiple of".format(G_MemOpByteCount) +
	  " Burst size({0:d}).".format(G_MemOpBurstSize))
    exit(1)

sys.exitfunc = atExit

try:
    G_TTYDev = serial.Serial(G_TTYDevName, 115200, timeout=1)
except serial.SerialException as e:
    print(str(e))
    exit(1)

ttySettingsDict = G_TTYDev.getSettingsDict()

if(os.path.exists(G_OutFileName)):
    print("Output file already exists. Won\'t overwrite.")
    exit(1)

time.sleep(1)

G_TTYDev.flushInput()
G_TTYDev.flushOutput()

# Check if we're connected to U-Boot.
for i in range(2):
    curCmd = bytes(G_UBootNopCmd + "\n", "ascii")
    G_TTYDev.write(curCmd)
    print("Executing: " + str(curCmd))

    buf = " "
    while buf:
        buf = G_TTYDev.read(G_TTYDev.inWaiting() + 16)
        if(bytes(G_UBootPrompt, "ascii") in buf):
            break

    if(bytes(G_UBootPrompt, "ascii") in buf):
        print("U-Boot responding.")
    else:
        print("U-Boot not responding.")
        exit(1)

# Use shorter timeout between reads
ttySettingsDict["timeout"] = 0.01
G_TTYDev.applySettingsDict(ttySettingsDict)

G_OutFile = open(G_OutFileName, "wb")

print("Output file name: {0:s}".format(G_OutFileName))
print("Start address: 0x{0:08X}".format(int(G_MemOpStartAddr)))
print("Count: {0:d} bytes.".format(G_MemOpByteCount))

curAddr = G_MemOpStartAddr
finishedByteCount = 0
startTime = time.time()

while(finishedByteCount < G_MemOpByteCount):
    curCmd = bytes(G_UBootMemDumpCmd +
                   " 0x{0:08X} 0x{1:08X}".format(curAddr,
                                                 G_MemOpBurstSize) + "\n",
                   "ascii")
    G_TTYDev.write(curCmd)
    print("Executing: " + str(curCmd))

    buf = bytes()
    tmpBuf = G_TTYDev.read(G_TTYDev.inWaiting() + 16)
    while tmpBuf != bytes():
        buf += tmpBuf
        tmpBuf = G_TTYDev.read(G_TTYDev.inWaiting() + 16)

    bufLines = buf.splitlines()

# Check if the last line is a U-Boot prompt.
    if(bytes(G_UBootPrompt, "ascii") not in bufLines[-1]):
        print("U-Boot not responding correctly.")
        exit(1)

#Skip lines that don't have an address in them. Addresses end with ":".
    for line in bufLines:
        if((line == bytes()) or (bytes(":", "ascii") not in line)):
            continue
        linePieces = line.split()

# Sanity check. First part must contain address.
        if(linePieces[0].endswith(bytes(":", "ascii")) == False):
            print("Invalid line structure. Probably an IO error.")
            exit(1)

# Sanity check. Calculated address must be equal to read address.
        if(int(linePieces[0][:-1], 16) != curAddr):
            print("Error: Current Address != Line Address."
                  " Probably an IO error.")
            exit(1)

        print("Line Address: " + str(linePieces[0][:-1]))

        byteArray = array.array("B")
        print("Line pieces: ", end=" ")
        for i in range(1, 17):
            print(linePieces[i], end=" ")
            byteArray.append(int(linePieces[i], 16))
            finishedByteCount += 1

        print()
        byteArray.tofile(G_OutFile)
        curAddr = G_MemOpStartAddr + finishedByteCount

    print("Finished: {0:d} bytes.".format(finishedByteCount))

print("Done.")
rate = (finishedByteCount / (time.time() - startTime)) / 1024
print("Rate: {0:.2g} kB/s".format(rate))
