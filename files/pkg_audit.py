#! /usr/bin/env python3
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 smartindent
# pylint: disable=invalid-name,missing-module-docstring

import os
import sys
import subprocess
import argparse
import json
import yaml

__doc__ = """
checkmk local check performin a pak audit on
freebsd / opnsense
"""

# you can acknowledge each vulnerable package by using a cfg file
# placed in the same directory as the script and with the same name,
# but the *.yml extension using yaml syntax:
# package-name:
#   issues:
#       - issue description as found running `pkg audit`
# example:
# ---
# cyrus-sasl:
#   issues:
#     - cyrus-sasl -- Fix off by one error
# openssl:
#   issues:
#     - OpenSSL -- Infinite loop in BN_mod_sqrt parsing certificates

argparser = argparse.ArgumentParser(description=__doc__)
argparser.add_argument(
    '-c', '--config-file',
    type=str,
    dest='configfile', action='store',
    default='%s.%s' % (os.path.splitext(os.path.abspath(__file__))[0], 'yml',),
    help='path to yaml config file for acknowledging audit vulnerable package'
    )
argparser.add_argument(
    '-p', '--print-config-file',
    action="store_true",
    help='do not perform a real check, just print a current config'
    )

args = argparser.parse_args()

cfg_file = args.configfile
vulnack = None
try:
    with open(cfg_file, "r") as ymlfile:
        vulnack = yaml.load(ymlfile, Loader=yaml.BaseLoader)
except FileNotFoundError:
    pass

pr = subprocess.run(
        ['pkg', 'audit', '-F', '--raw=json-compact', '-q'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False
    )
vulnx = json.loads(pr.stdout)
vuln_pkg_count = vulnx['pkg_count']

vulns = {}
for package, data in vulnx['packages'].items():
    vulns[package] = {}
    vulns[package]['issues'] = []
    for issue in data['issues']:
        vulns[package]['issues'].append(issue['description'])

if args.print_config_file:
    print(yaml.safe_dump(vulns))
    sys.exit(0)

if vulnack:
    for package in list(vulns.keys()):
        if package in vulnack:
            for ackeddescr in vulnack[package]['issues']:
                if ackeddescr in vulns[package]['issues']:
                    vulns[package]['issues'].remove(ackeddescr)
        if len(vulns[package]['issues']) == 0:
            vulns.pop(package)

unacked = len(vulns)
unackedissues = []
for package, data in vulns.items():
    for issue in data['issues']:
        unackedissues.append(issue)
warntxt = '; '.join(unackedissues)

ecode = 0
status = 'OK'
txt = 'no vulnerable packages found'
if vuln_pkg_count > 0:
    txt = 'no unacknowledged vulnerable packages found'
if unacked > 0:
    ecode = 1
    status = 'WARNING'
    txt = f'unacknowledged vulnerable packages: {unacked} ({warntxt})'

print(
        '%s PKGAUDIT vulnpackages=%s;;;;|acked=%s;;;; %s - %s' %
        (ecode, vuln_pkg_count, vuln_pkg_count-unacked, status, txt)
    )