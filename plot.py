#!/usr/bin/python3

from json import loads
from subprocess import run
from sys import argv

data = []
start = 1
outfile = "data.dat"

if len(argv) > 2:
    start = int(argv[2])


with open(argv[1], "r") as target:
    raw = target.read()
    data = loads(raw[0:-1]+"]")

with open(outfile, "w") as out:
    for point in data[start:]:
        # y = point["totalDevs"]
        y = sum(
            map(
                lambda ap: ap["associated_count"],
                filter(
                    lambda a: point["ts"] - a["last_seen"] < 60,
                    point["aps"]
                )
            )
        )
        out.write("%d\t%d\n" % (point["ts"], y))


# run(["gnuplot", "-p", "-e", ("set terminal qt;set xdata time;set format x '%%H:%%M:%%S';plot '%s' using ($1 - 946684800 + (7 * 3600)):2" % outfile)])
