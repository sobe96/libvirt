#!/usr/bin/env python3

import argparse
import os
import sys
import json
import xml.etree.ElementTree


def checkFeature(cpuData, feature):
    if feature["type"] == "cpuid":
        # cpuData["cpuid"][eax_in][ecx_in] = {eax:, ebx:, ecx:, edx:}
        keyList = ["type", "eax_in", "ecx_in"]
        regList = ["eax", "ebx", "ecx", "edx"]
    elif feature["type"] == "msr":
        # cpuData["msr"][index] = {eax:, edx:}
        keyList = ["type", "index"]
        regList = ["eax", "edx"]
    else:
        return False

    for key in keyList:
        if feature[key] not in cpuData:
            return False
        cpuData = cpuData[feature[key]]

    for reg in regList:
        if feature[reg] > 0 and feature[reg] == feature[reg] & cpuData[reg]:
            return True
    return False


def addFeature(cpuData, feature):
    if feature["type"] == "cpuid":
        # cpuData["cpuid"][eax_in][ecx_in] = {eax:, ebx:, ecx:, edx:}
        keyList = ["type", "eax_in", "ecx_in"]
        regList = ["eax", "ebx", "ecx", "edx"]
    elif feature["type"] == "msr":
        # cpuData["msr"][index] = {eax:, edx:}
        keyList = ["type", "index"]
        regList = ["eax", "edx"]
    else:
        return

    for key in keyList:
        if feature[key] not in cpuData:
            cpuData[feature[key]] = dict()
        cpuData = cpuData[feature[key]]

    for reg in regList:
        cpuData[reg] = cpuData.get(reg, 0) | feature[reg]


def parseQemu(path, features):
    cpuData = {}
    with open(path, "r") as f:
        data, pos = json.JSONDecoder().raw_decode(f.read())

    for (prop, val) in data["return"]["model"]["props"].items():
        if val and prop in features:
            addFeature(cpuData, features[prop])

    return cpuData


def parseCPUData(path):
    cpuData = dict()
    for f in xml.etree.ElementTree.parse(path).getroot():
        if f.tag == "cpuid":
            reg_list = ["eax_in", "ecx_in", "eax", "ebx", "ecx", "edx"]
        elif f.tag == "msr":
            reg_list = ["index", "eax", "edx"]
        else:
            continue

        feature = {"type": f.tag}
        for reg in reg_list:
            feature[reg] = int(f.attrib.get(reg, "0"), 0)
        addFeature(cpuData, feature)
    return cpuData


def parseMap():
    path = os.path.dirname(sys.argv[0])
    path = os.path.join(path, "..", "..", "src", "cpu_map", "x86_features.xml")

    cpuMap = dict()
    for f in xml.etree.ElementTree.parse(path).getroot().iter("feature"):
        if f[0].tag == "cpuid":
            reg_list = ["eax_in", "ecx_in", "eax", "ebx", "ecx", "edx"]
        elif f[0].tag == "msr":
            reg_list = ["index", "eax", "edx"]
        else:
            continue

        feature = {"type": f[0].tag}
        for reg in reg_list:
            feature[reg] = int(f[0].attrib.get(reg, "0"), 0)
        cpuMap[f.attrib["name"]] = feature
    return cpuMap


def formatCPUData(cpuData, path, comment):
    print(path)
    with open(path, "w") as f:
        f.write("<!-- " + comment + " -->\n")
        f.write("<cpudata arch='x86'>\n")

        cpuid = cpuData["cpuid"]
        for eax_in in sorted(cpuid.keys()):
            for ecx_in in sorted(cpuid[eax_in].keys()):
                leaf = cpuid[eax_in][ecx_in]
                line = ("  <cpuid eax_in='0x%08x' ecx_in='0x%02x' "
                        "eax='0x%08x' ebx='0x%08x' "
                        "ecx='0x%08x' edx='0x%08x'/>\n")
                f.write(line % (
                        eax_in, ecx_in,
                        leaf["eax"], leaf["ebx"], leaf["ecx"], leaf["edx"]))

        if "msr" in cpuData:
            msr = cpuData["msr"]
            for index in sorted(msr.keys()):
                f.write("  <msr index='0x%x' edx='0x%08x' eax='0x%08x'/>\n" %
                        (index, msr[index]['edx'], msr[index]['eax']))

        f.write("</cpudata>\n")


def diff(args):
    cpuMap = parseMap()

    for jsonFile in args.json_files:
        cpuDataFile = jsonFile.replace(".json", ".xml")
        enabledFile = jsonFile.replace(".json", "-enabled.xml")
        disabledFile = jsonFile.replace(".json", "-disabled.xml")

        cpuData = parseCPUData(cpuDataFile)
        qemu = parseQemu(jsonFile, cpuMap)

        enabled = dict()
        disabled = dict()
        for feature in cpuMap.values():
            if checkFeature(qemu, feature):
                addFeature(enabled, feature)
            elif checkFeature(cpuData, feature):
                addFeature(disabled, feature)

        formatCPUData(enabled, enabledFile, "Features enabled by QEMU")
        formatCPUData(disabled, disabledFile, "Features disabled by QEMU")


def main():
    parser = argparse.ArgumentParser(description="Diff cpuid results")
    subparsers = parser.add_subparsers(dest="action", required=True)
    diffparser = subparsers.add_parser(
        "diff",
        help="Diff json description of CPU model against known features.")
    diffparser.add_argument(
        "json_files",
        nargs="+",
        metavar="FILE",
        type=os.path.realpath,
        help="Path to one or more json CPU model descriptions.")
    args = parser.parse_args()

    diff(args)


if __name__ == "__main__":
    main()
