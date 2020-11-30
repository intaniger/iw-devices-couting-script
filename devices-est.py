#!/usr/bin/python3

from subprocess import run, PIPE
from sys import argv
from os import geteuid
from re import match
from typing import List, Mapping
from time import sleep, time
from json import dump

bssRegex = r'^BSS\s([0-9a-f:]*)'
stationCountRegex = r'.*station count: (\d*)'
utilRegex = r'.*channel utilisation: (\d*)\/(\d*)'
signalRegex = r'.*signal: ([-]?\d*\.\d*) dBm'
ssidRegex = r'[ \t]SSID: (.*)'
primaryChannelRegex = r'.*primary channel: (\d*)'

TTL = 300
outfile = None


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
        self.last_seen = 0

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


def objectify(ins: List[APInfo]):
    return list(
        map(
            lambda i: {
                "bss": i.bss,
                "ssids": i.ssids,
                "signal": i.signal,
                "associated_count": i.associated_count,
                "utilization": i.utilization,
                "channel": i.channel,
                "last_seen": i.last_seen
            },
            ins
        ),
    )


if geteuid() != 0:
    print("Root permission is required.")
    exit(1)

if len(argv) < 3:
    print(
        "Usage: devices-est.py [wireless interface] [scan interval] [TTL] [out filename]")
    exit(1)
if len(argv) >= 4:
    TTL = int(argv[3])
if len(argv) == 5:
    outfile = argv[4]

while True:
    rawInfoes = scan(argv[1])
    currenTime = int(time())
    run('clear')
    for a in sorted(rawInfoes, key=lambda n: [n.bss], reverse=True):
        key = "%s*-%d" % (a.bss[0:-2], a.channel)
        if key in grps:
            if grps[key].lastSeen != currenTime:
                grps[key].data = [a]
            else:
                grps[key].data.append(a)
            grps[key].lastSeen = currenTime
        else:
            grps[key] = LRU()
            grps[key].lastSeen = currenTime
            grps[key].data = [a]

    aggregatedAPInfoes = []
    for key in list(grps.keys()):
        if currenTime - int(grps[key].lastSeen) > TTL:
            print("Haven't seen %s for more than %d secs" % (key, TTL))
            del grps[key]
            continue
        aggInfo = APInfo()
        aggInfo.bss = grps[key].data[0].bss[0:-2]+"*"
        aggInfo.associated_count = grps[key].data[0].associated_count
        aggInfo.utilization = grps[key].data[0].utilization
        aggInfo.channel = grps[key].data[0].channel
        aggInfo.ssids = list(map(lambda ai: ai.ssids[0], grps[key].data))
        aggInfo.signal = sum(
            list(map(lambda ai: ai.signal, grps[key].data))) / len(grps[key].data)
        aggInfo.last_seen = grps[key].lastSeen

        aggregatedAPInfoes.append(aggInfo)

    aggregatedAPInfoes.sort()
    for ai in aggregatedAPInfoes:
        print(ai)

    totalDev = sum(map(lambda i: i.associated_count, aggregatedAPInfoes))

    print("devices = %d" % totalDev)
    if outfile != None:
        with open(outfile, mode="a") as target:
            if target.tell() == 0:
                target.write("[")
            dump(
                {
                    "ts": currenTime,
                    "totalDevs": totalDev,
                    "aps": objectify(aggregatedAPInfoes),
                },
                target
            )
            target.write(",")
            target.close()
    sleep(int(argv[2]))
