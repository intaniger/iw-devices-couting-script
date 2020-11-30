#!/usr/bin/python3

from subprocess import run, PIPE
from sys import argv, stderr
from os import geteuid
from re import match
from typing import List, Mapping
from functools import reduce
from time import sleep, time

bssRegex = r'^BSS\s([0-9a-f:]*)'
stationCountRegex = r'.*station count: (\d*)'
utilRegex = r'.*channel utilisation: (\d*)\/(\d*)'
signalRegex = r'.*signal: ([-]?\d*\.\d*) dBm'
ssidRegex = r'[ \t]SSID: (.*)'
primaryChannelRegex = r'.*primary channel: (\d*)'


def classifySignalQual(signal):
    if signal >= -50.00:
        return "excellent"
    elif signal >= -60.00:
        return "good"
    elif signal >= -67.00:
        return "reliable"
    elif signal >= -70.00:
        return "not good"
    else:
        return "unreliable"


class LRU(object):
    """
    LRU is the LRU
    """

    def __init__(self):
        self.data: List[APInfo] = []
        self.lastSeen: int = 0


class APInfo(object):
    """
    APInfo contain info about access point, signal strength
    """

    def __init__(self):
        self.bss = ""
        self.ssids = [""]
        self.signal = 0.0
        self.associated_count = 0
        self.utilization = 0.0
        self.channel = 0

    def __gt__(self, apinfo2):
        return (self.signal > apinfo2.signal)

    def __str__(self):
        return "%s channel %3d - (%10s), contain %2d ssids, devices=%3d, utils=%2.3f [%s]" % (self.bss, self.channel, classifySignalQual(self.signal), len(self.ssids), self.associated_count, self.utilization, ",".join(self.ssids))


aggregatedAPInfoes: List[APInfo] = []
grps: Mapping[str, LRU] = {}


def scan(deviceName):
    APInfoes: List[APInfo] = []
    result = run(['iw', 'dev', deviceName, 'scan', 'flush'],
                 stdout=PIPE).stdout.decode()

    for line in result.splitlines():
        bssMatch = match(bssRegex,  line)
        stationCountMatch = match(stationCountRegex, line)
        utilsMatch = match(utilRegex, line)
        signalMatch = match(signalRegex, line)
        ssidMatch = match(ssidRegex, line)
        channelMatch = match(primaryChannelRegex, line)

        if bssMatch != None:
            APInfoes.append(APInfo())
            APInfoes[-1].bss = bssMatch.group(1)
        elif stationCountMatch != None:
            APInfoes[-1].associated_count = int(stationCountMatch.group(1))
        elif utilsMatch != None:
            APInfoes[-1].utilization = 100.0 * (int(utilsMatch.group(1)) /
                                                int(utilsMatch.group(2)))
        elif signalMatch != None:
            APInfoes[-1].signal = float(signalMatch.group(1))
        elif ssidMatch != None:
            APInfoes[-1].ssids = [ssidMatch.group(1)]
        elif channelMatch != None:
            APInfoes[-1].channel = int(channelMatch.group(1))
    return APInfoes


def objectify(groups: Mapping[str, LRU], ts: int):
    obj = {
        "ts": ts,
    }


if geteuid() != 0:
    print("Root permission is required.")
    exit(1)

if len(argv) < 3:
    print("Usage: devices-est.py [wireless interface] [scan interval]")
    exit(1)

while True:
    rawInfoes = scan(argv[1])
    currenTime = int(time())
    localGrps = {}
    run('clear')
    for a in sorted(rawInfoes, key=lambda n: [n.bss], reverse=True):
        key = "%s*-%3d (%d, %d)" % (a.bss[0:-2],
                                    a.channel, a.associated_count, a.utilization)
        # a.bss[0:-2]+"* channel "+str(a.channel)
        if key in localGrps:
            localGrps[key].append(a)
        else:
            localGrps[key] = [a]

    for key in list(grps.keys()):
        if currenTime - int(grps[key].lastSeen) > 300:
            print("Haven't seen %s for more than 300 secs" % key)
            del grps[key]

    for key in localGrps.keys():
        grps[key] = LRU()
        grps[key].data = localGrps[key]
        grps[key].lastSeen = currenTime

    aggregatedAPInfoes = []
    for key in grps.keys():
        aggInfo = APInfo()
        aggInfo.bss = grps[key].data[0].bss[0:-2]+"*"
        aggInfo.associated_count = grps[key].data[0].associated_count
        aggInfo.utilization = grps[key].data[0].utilization
        aggInfo.channel = grps[key].data[0].channel
        aggInfo.ssids = list(map(lambda ai: ai.ssids[0], grps[key].data))
        aggInfo.signal = sum(
            list(map(lambda ai: ai.signal, grps[key].data))) / len(grps[key].data)

        aggregatedAPInfoes.append(aggInfo)

    for ai in sorted(aggregatedAPInfoes):
        print(ai)

    print("devices = %d" %
          sum(map(lambda i: i.associated_count, aggregatedAPInfoes)))
    sleep(int(argv[2]))
