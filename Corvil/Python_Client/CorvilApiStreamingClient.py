#!/usr/bin/env python3

# Copyright (c) 2011, Corvil Limited. All rights reserved.
# THIS SOURCE CODE IS A TRADE SECRET OF CORVIL AND SHOULD NOT BE TRANSFERRED
# OR DISCLOSED TO ANY THIRD PARTY WITHOUT CORVIL'S PERMISSION. THIS SOURCE
# CODE IS LICENSED "AS IS", SOLELY FOR ILLUSTRATION PURPOSES, ONLY WITHIN
# THE LIMITED, SPECIFIC CONTEXT AND PARAMETERS INDICATED IN THE APPLICABLE
# CORVIL INSTRUCTIONS AND DOCUMENTATION, AND SUBJECT TO THE TERMS AND
# CONDITIONS OF THE CORVIL STANDARD SOFTWARE LICENSE AGREEMENT, INCLUDING
# WITHOUT LIMITATION THE LIABILITY LIMITATIONS SET FORTH THEREIN.

# NB: this was developed against Python v3.6 and Suds (suds-jurko) v0.6

# $Revision: 273102 $

"""
Corvil XML API example tool for streamed processing of MTOM attachments

Version: 3.2.0.202206301037-GA+273102

Usage: CorvilApiStreamingClient.py [<options>] <command> <args> ...

Commands + Arguments:
    version
Prints client version

    pcap            <host> <mp> <start_time> <end_time>
Get PCAP data

    gap-csv         <host> <mp> <start_time> <end_time>
Get message-gap CSV

    message-csv     <host> <mp> <start_time> <end_time>
Get message CSV

    packet-csv      <host> <mp> <start_time> <end_time>
Get packet CSV

    multihop-csv    <host> <mp> <packet_timestamp> <packet_id> <message_index>
Get multihop CSV

    lens-csv        <host> <period> [<view>]
Get Lens CSV

    mp-list         <host> [<period>]
Show measurement points

    flow-index      <host> <start_time> <end_time> <aggregations>
Get flow-index table CSV

    clock-tracking  <host> <start_time> <end_time>
Get clock tracking log

Arguments:
    host            CNE or CMC to use when requesting data, can specify port: host:port
    mp              Fully qualified measurement point name, e.g.
                    "channel//local-cne///PortA". Use mp-list command for
                    full list of available measurement points
    start_time      Period start time (see Time Formats below)
    end_time        Period end time (see Time Formats below)
    period          For lens-csv, Reporting Period name e.g. "Last 1 hour", "Business Day".
                    For mp-list one of 1-hour (default), 12-hours, 24-hours, 48-hours, 7-days, 30-days, 60-days
    view            Name of Corvil Lens view. Views can be configured using
                    Corvil Lens GUI. Default is 'Default'.
    aggregations    Optional aggregations for flow-index command; Available aggregations:
                    conversations, conversations-bidirectional, talkers, listeners, ports,
                    vports, vlans, applications, time-seconds, time-minutes, time-hours, clients,
                    servers, client-server-direction, eth-talkers, eth-listeners;
                    These can be specified as a list separated by comma as the last command line
                    argument for the flow-index command. for example: "talkers,listeners,applications"

  Options:
    -n <username>           Specify username, default: admin
    -p <password>           Specify password, default: admin
    -x <cne>                Specify CNE for requests sent to CMC
    -L <local-cne-name>     Specify the local CNE name, default: local-cne (clock-tracking)
    -b                      Request bidirectional export (pcap, gap-csv, message-csv, packet-csv)
    -c                      Request correlation analysis (message-csv)
    -C                      Request correlation IDs (message-csv)
    -a                      Request summaries (flow-index)
    -w                      Request watch list metadata (flow-index)
    -m                      Request additional measurement points (pcap)
    -s                      Request measurement points in the flow-index response (flow-index)
    -q <query>              Optional filter which utilizes Corvil Query Language (CQL) (flow-index)
    -l <columns>            Comma-separated list of columns to return (message-csv, packet-csv)
    -t <filter type>        CQL, Wireshark, BPF, Message
    -f <filter text>        Single line filter expression, one of CQL, Wireshark, BPF OR
                            Message filter with the following format:
                            protocol:msgType:msgField:msgFieldValue
                                    (all fields except protocol are optional)
                                    \ escapes delimeter if necessary.
                            Examples:   FIX:::
                                        FIX:NewOrderSingle::
                                        FIX::ClOrdID:
                                        FIX:NewOrderSingle:ClOrdID:7RIB3D-1
                                        
    -r                      Field value in Message filter is regex
    -d                      Optional Message filter delimiter (default is ':')
    -z                      Use https to access the CNE
    -g                      Specify snaplength for PCAP Export (pcap)
    -F                      Optional output format either uncompressed, zip or gzip.
                            uncompressed is the default if not specified.
    -T <timeout-seconds>    Request timeout in seconds, default value: 3600


  Time Formats:
    YYYY-MM-DD HH:MM:SS
    <epoch_sec>
    <epoch_nsec>
"""

import base64
import csv
import errno
import logging
import os
import traceback

import suds
from suds import plugin
from suds import client
from suds.transport.http import HttpTransport

try:
    import ssl
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass
import socket
import sys
import time
import getopt
import http.client
import inspect
from xml.dom import minidom

VERSION='3.2.0.202206301037-GA+273102'

logging.basicConfig(level=logging.INFO)
#logging.getLogger('suds.transport').setLevel(logging.DEBUG)

class SudsParameterPlugin(suds.plugin.MessagePlugin):
    """suds plugin to specify extra method parameters"""
    def __init__(self):
        self.attrs = {}
    def setAttrs(self, attrs):
        self.attrs = attrs
    def marshalled(self, context):
        body = context.envelope.getChild('Body')
        fnTag = body[0]
        for k,v in list(self.attrs.items()):
            fnTag.set(k, v)
        
class CorvilApiMtomClient():
    READ_BLOCK_SIZE = 1024 * 1024
    MAX_XML_SIZE = 64 * 1024
    SOCKET_TIMEOUT_SECONDS = 3600

    def __init__(self, host, port = 5101, username = 'admin', password = '', cne=None, useHttps=False, timeout=SOCKET_TIMEOUT_SECONDS):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.cne = cne
        self.url = "http://%s:%s/ws/statsMTOM-v2?wsdl" % (host, port)
        self.useHttps = useHttps
        if self.useHttps:
            self.url = "https://%s/api/ws/statsMTOM-v2?wsdl" % (host)
        self.timeout = timeout

        # suds plugin
        self.paramPlugin = SudsParameterPlugin()
        
        # we're going to do a 'nosend' for the MTOM client as SUDs doesn't
        # support MTOM, so we basically use SUDS to assemble the XML and then
        # send it manually.
        self.client = suds.client.Client(self.url, username = self.username,
                                         cache = None, password = self.password,
                                         plugins=[self.paramPlugin],
                                         timeout = timeout, nosend = True)
        

        # Check if this is an CMC or a CNE. The CMC has a 'getCnes' method.
        self.hostIsLmc = True
        try:
            self.hostIsLmc = (hasattr(self.client.service, "getCnes") and
                              callable(self.client.service.getCnes))
        except suds.MethodNotFound:
            self.hostIsLmc = False
        
        #after making the getCnes check, set the port to the MTOM port
        self.client.set_options(port = "StatsMtomPort")
        

    # Various helper methods
    def getSudsClient(self):
        """Return the suds client"""
        return self.client

    def createObject(self, type):
        """Create the specified suds object type"""
        return self.client.factory.create(type)

    def createMeasurementPointRequest(self, mpname):
        """Create a MeasurementPointRequest object"""
        mpReq = self.createObject("ns0:MeasurementPointRequest")
        mpReq._name = mpname
        return mpReq

    def createMeasurementPoints(self, mpname):
        """Create a MeasurementPointRequest object"""
        mp = self.createObject("ns0:MeasurementPointsRequest")
        mp.measurementPoint = self.createMeasurementPointRequest(mpname)
        return mp

    def createTimeRangeNs(self, fromNs, toNs):
        """Create a TimeRangeNs object"""
        timeRange = self.client.factory.create('ns0:TimeRangeNs')
        timeRange._fromNs = fromNs
        timeRange._toNs = toNs
        return timeRange

    def createDefinitionPoints(self, points = None):
        number_of_points = self.client.factory.create('ns0:NumberOfPoints')
        number_of_points._points = points
        return number_of_points

    def createDefinition(self, stat = [], statEventData = [], configurableStat = [],
                         configurableStatThreshold = [], configurableStatEventData = [], points=None):
        """ Create definition object to be used by getAnalytics call"""
        definition = self.client.factory.create('ns0:DefinitionWithPoints')
        definition._points = points
        definition.stat = stat
        definition.statEventData = statEventData
        definition.configurableStat = configurableStat
        definition.configurableStatThreshold = configurableStatThreshold
        definition.configurableStatEventData = configurableStatEventData
        return definition

    def createStat(self, statistic=None):
        """ Create stat object to be used by getAnalytics call"""
        s = self.client.factory.create('ns0:Stat')
        s._name = statistic["name"]
        s._requestedPercentiles = statistic["percentiles"]
        return s

    def createNamedReportingPeriod(self, rpName):
        """Create a NamedReportingPeriod object"""
        rp = self.client.factory.create('ns0:NamedReportingPeriod')
        rp._name = rpName
        return rp

    def createMessageId(self,packetId,timestamp,messageIndex):
        messageId = self.client.factory.create('ns0:MessageId')
        messageId._packetTs = timestamp
        messageId._packetId = packetId
        messageId._messageIndex = messageIndex
        return messageId

    def createLensView(self, viewName):
        """Create a LensView object"""
        view = self.client.factory.create('ns0:LensView')
        view._name = viewName
        return view

    def getXmlMtomResponseInBlocks(self, requestXml):
        """
           Sent the specified request in a POST request, and return
           a python generator that streams back the response
        """

        def patch_http_response_read(func):
            def inner(*args):
                try:
                    return func(*args)
                except http.client.IncompleteRead as e:
                    return e.partial

            return inner

        def readSock(sock, nbytes):
            """Handle EINTR in read"""
            while True:
                try:
                    data = sock.read(nbytes)
                except socket.error as e:
                    if e.args[0] == errno.EINTR:
                        continue
                    raise
                return data

        def getLine(resp, maxlen = self.MAX_XML_SIZE, allowPartial = False):
            """Read a line character by character from a response"""
            line = b''
            while len(line) < maxlen and (len(line) < 2 or line[-2:] != b'\r\n'):
                c = readSock(resp, 1)
                if not c:
                    if allowPartial:
                        return (False, line)
                    raise Exception("getLine failed line=`%s'" % line.decode("utf-8").strip())
                line += c
            if len(line) >= maxlen:
                raise Exception("line `%s' too long" % line.decode("utf-8").strip())
            line = line[:-2]
            if allowPartial:
                return (True, line)
            return line

        headers = {
            'Accept' : 'application/xop+xml',
            'Content-Type' : 'text/xml; charset=utf-8',
            'Authorization' : "Basic %s" % base64.encodebytes(('%s:%s' %
                (self.username, self.password)).encode('utf-8')).decode('utf-8')[:-1],
        }

        if self.useHttps:
            conn = http.client.HTTPSConnection(self.host, timeout=self.timeout)
        else:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
                    
        conn.request("POST", self.url, body = requestXml, headers = headers)
        start_time = time.time()
        resp = conn.getresponse()

        original_read = http.client.HTTPResponse.read
        http.client.HTTPResponse.read = patch_http_response_read(http.client.HTTPResponse.read)

        try:
            # Read the UUID, XML + headers
            uuid = getLine(resp)
            xml = b''
            while True:
                (ok, l) = getLine(resp, allowPartial = True)
                if not ok:
                    # Handle error responses
                    if l == (b'%s--' % uuid):
                        errHdrEndPos = xml.find("\n\n".encode("utf-8"))
                        if errHdrEndPos >= 0:
                            xml = xml[errHdrEndPos + 2:]
                        try:
                            xml = minidom.parseString(xml.decode("utf-8")).toprettyxml(indent="  ").encode("utf-8")
                        except Exception as e:
                            pass
                        raise Exception(xml.decode("utf-8"))
                    raise Exception("getLine failed - line is: (%s)" % l.decode("utf-8"))
                if l == uuid:
                    break
                xml += l + "\n".encode("utf-8")
                if len(xml) > self.MAX_XML_SIZE:
                    raise Exception("xml `%s' too large" % xml.decode("utf-8"))
            while True:
                l = getLine(resp)
                if l == b'':
                    break

            # Now stream back the data, checking for the UUID end marker
            endMarker = b'\r\n%s--' % uuid
            dat = b''
            while True:
                newDat = readSock(resp, self.READ_BLOCK_SIZE)
                if not newDat or len(dat) + len(newDat) < len(endMarker):
                    raise Exception("Missing end marker")
                dat += newDat
                if len(dat) > len(endMarker):
                     yield dat[:-len(endMarker)]
                dat = dat[-len(endMarker):]
                if dat == endMarker:
                    break
        finally:
            http.client.HTTPResponse.read = original_read

    def getPcapInBlocks(self, mpReq, timeRange, filters, extraMps = [], params = {}):
        self.paramPlugin.setAttrs(params)
        requestSOAP = self.client.service.getPcap(mpReq, timeRange, filters, extraMps)
        return self.getXmlMtomResponseInBlocks(requestSOAP.envelope)
    
    def getMessageGapCsvInBlocks(self, mpReq, timeRange, filters, params = {}):
        self.paramPlugin.setAttrs(params)
        requestSOAP = self.client.service.getMessageGapCsv(mpReq, timeRange, filters)
        return self.getXmlMtomResponseInBlocks(requestSOAP.envelope)
    
    def getMultihopCsvInBlocks(self, mpReq, messageId,params={}):
        self.paramPlugin.setAttrs(params)
        requestSOAP = self.client.service.getMessageMultiHopCsv(mpReq, messageId)
        return self.getXmlMtomResponseInBlocks(requestSOAP.envelope)

    def getMessageCsvInBlocks(self, mpReq, timeRange, filters, params = {}):
        self.paramPlugin.setAttrs(params)
        requestSOAP  = self.client.service.getMessageCsv(mpReq, timeRange, filters)
        return self.getXmlMtomResponseInBlocks(requestSOAP.envelope)

    def getPacketCsvInBlocks(self, mpReq, timeRange, filters, params = {}):
        self.paramPlugin.setAttrs(params)
        requestSOAP = self.client.service.getPacketCsv(mpReq, timeRange, filters)
        return self.getXmlMtomResponseInBlocks(requestSOAP.envelope)

    def getLensCsvInBlocks(self, rp, view, params = {}):
        self.paramPlugin.setAttrs(params)
        requestSOAP = self.client.service.getLensCsv(rp, view)
        return self.getXmlMtomResponseInBlocks(requestSOAP.envelope)

    def getFlowTableCsvInBlocks(self, timeRange, query, aggregation,
                                summariesOnly, params={}):
        self.paramPlugin.setAttrs(params)
        requestSOAP = self.client.service.getFlowTableCsv(timeRange, query, aggregation,summariesOnly)
        return self.getXmlMtomResponseInBlocks(requestSOAP.envelope)

    def getFlowTableCsvInLineArray(self, csv_generator):
        """Creates a generator object to stream back a CSV row by row.

        Args:
            csv_generator (generator): A generator object that creates a CSV.

        Returns:
            generator: The generator that will stream the CSV row by row.
        """

        keep = ""
        try:
            for block in csv_generator:
                # Add any partial row from prior pass to this data chunk.
                kept = keep + block.decode("utf-8")

                # Make sure the data chunk contains at least one whole row.
                if "\n" not in kept:
                    keep = kept
                    continue

                # Separate the last row from the main chunk.
                # Will remove and partial row and use it next pass.
                # If it's a complete row, no harm done.
                block_and_last_row = kept.rsplit("\n", 1)

                full_block = block_and_last_row[0]
                potential_partial = ""

                if len(block_and_last_row) > 1:
                    potential_partial = block_and_last_row[1]

                # Parse the full block into CSV rows,
                # store any partial information for next pass.
                lines = full_block.splitlines()
                keep = potential_partial
                yield lines
        except Exception as exception:
            raise exception
        finally:
            csv_generator.close()


class MtomTool(CorvilApiMtomClient):
    def __init__(self, host="localhost", port=5101, username='admin', password='LOCAL:', cne=None, useHttps=False, commandLine=False):
        self.msgBlock = ""
        self.msgSize = 0
        if commandLine == False:
            self.client = CorvilApiMtomClient(host, port=port,
                password = password, username=username,cne=cne, useHttps=useHttps)
            if self.client.hostIsLmc and cne is not None:
                self.baseParams = {'cne': cne}
            else:
                self.baseParams = {}

    def help(self, message=None, exitcode=2):
        if message:
            sys.stdout.write(message)
        sys.stdout.write(__doc__) # doc string from top of file
        sys.exit(exitcode)

    def version(self):
        print(VERSION)
        sys.exit(0)

    def parseTime(self, toParse):
        try:
            if isinstance(toParse, str):
                t = time.strptime(toParse, "%Y-%m-%d %H:%M:%S")
                return int(time.mktime(t)) * int(1e9)
        except ValueError as e:
            pass
        try:
            ns = int(toParse)
        except Exception as e:
            sys.stderr.write("Invalid time `%s'" % toParse)
            sys.exit(1)
        if ns < 0x7fffffff:
            return ns * int(1e9)
        return ns

    def decodeMessage(self, msg):
        print(len(msg))

    def processBlock(self, block):
        self.msgBlock += block
        while True:
            if self.msgSize == 0:
                # waiting for size
                if len(self.msgBlock) > 2:
                    self.msgSize = ord(self.msgBlock[0])*256 + ord(self.msgBlock[1])
                    self.msgBlock = self.msgBlock[2:]
            if self.msgSize > 0:
                if len(self.msgBlock) >= self.msgSize:
                    msgToDecode = self.msgBlock[0:self.msgSize-1]
                    self.decodeMessage(msgToDecode)
                    self.msgBlock = self.msgBlock[self.msgSize:]
                    self.msgSize = 0
                else:
                    break

    def parseHost(self, host):
        parts = host.split(':', 2)
        if len(parts) == 2:
            return (parts[0], parts[1])
        else:
            return (host, 5101)

    def get_mp_list(self, period):
        sc = self.client.getSudsClient()

        # getSummary is the only method in this script that's actually on the
        # StatsPort and not the StatsMtomPort, hence we have to set the port,
        # and also we can just call the service method directly and get the response.
        sc.set_options(port = "StatsPort", nosend = False)
        self.client.paramPlugin.setAttrs({'version' : '2'})

        summary = sc.service.getSummary("", self.client.createObject("ns0:ReportingPeriod")[period])
        
        if hasattr(summary, "channel"):
            for chan in summary.channel:
                print("Channel %s:" % chan._displayName)
                print("  %s" % chan._name)
                for cls in chan.cls:
                    print("    %s" % cls._name)
        if hasattr(summary, "interface"):
            for iface in summary.interface:
                print("Interface %s:" % iface._displayName)
                print("  %s" % iface._name)
                for cls in iface.cls:
                    print("    %s" % cls._name)
        sys.exit(0)

    def get_lens_csv(self, period, view, output=None):
        params={}
        if output:
            params["outputFormat"] = output
        namedRp = self.client.createNamedReportingPeriod(period)
        lensView = self.client.createLensView(view)
        dataGen = self.client.getLensCsvInBlocks(namedRp, lensView, params)

        return dataGen

    def get_flow_index(self, startTime, endTime, aggregation = [], watchlistMetadata = None,
                       showMeasurementPoints = None, query = None, summariesOnly = None, params=None,
                       output=None):

        aggr = []
        for p in aggregation:
            pTrimmed = p.strip()
            if pTrimmed not in ["conversations", "conversations-bidirectional", "talkers",
                                "listeners", "ports", "vports", "vlans", "applications",
                                "time-seconds", "time-minutes", "time-hours", "clients", "servers",
                                "client-server-direction", "eth-talkers", "eth-listeners"]:
                self.help("Invalid aggregation option:'"+pTrimmed+"'")
            aggr.append(pTrimmed)

        timeRange = self.client.createTimeRangeNs(self.parseTime(startTime), self.parseTime(endTime))
        if params is None:
            params = {}
        if watchlistMetadata:
            params["watchlistMetadata"] = "true"

        if showMeasurementPoints:
            params["showMeasurementPoints"] = "true"

        if output:
            params["outputFormat"] = output

        dataGen = self.client.getFlowTableCsvInBlocks(timeRange, query,
                                                          aggr, summariesOnly, params=params)
        return dataGen

    def get_multihop_csv(self, timestamp,message_id,message_index, mpReq=None, baseParams=None, output=None):
        params={}
        if output:
            params["outputFormat"] = output
        params.update(baseParams)
        messageId = self.client.createMessageId(message_id,timestamp,message_index)
        mpReq = self.client.createMeasurementPointRequest(mpReq)
        dataGen = self.client.getMultihopCsvInBlocks(mpReq, messageId, params=params)

        return dataGen
    
    
    def add_filters(self, cliFilterObject):

        if cliFilterObject == None:
            return None

        filterType = cliFilterObject["filterType"]
        filterText = cliFilterObject["filterText"]
        delimiter = cliFilterObject["delimiter"]
        regex = cliFilterObject["regex"]

        if not filterType and not filterText:
            return None

        if (not filterType and filterText) or (filterType and not filterText):
            sys.stderr.write("Both filter type and filter text must be specified if filtering is required.")
            sys.exit(1)

        #this is the 'filters' top level filter container for all the types.
        filter = self.client.createObject("ns0:FilterDefinition")
        #'Message' filters are distinct from the other three types, which are all 'expression filters'
        if filterType.lower() == "message":
            filter.messageFilterSequence = self.parseMessageFilterString(filterText, delimiter, regex)
        elif filterType.lower() in ["cql","bpf","wireshark"]:
            if filterText is not None:
                filterObject = self.client.createObject("ns0:ExpressionFilter")
                filterObject._expression = filterText
                if filterType.lower() == "cql":
                    filter.corvilPacketFilter = filterObject
                elif filterType.lower() == "bpf":
                    filter.berkeleyPacketFilter = filterObject
                elif filterType.lower() == "wireshark":
                    filter.tsharkDisplayFilter = filterObject
        else:
            sys.stderr.write("Unknown filter type:"+str(filterType)+"\n")
            sys.stderr.write("Supported filter types: CQL, BPF, Wireshark, Message\n")
            sys.exit(1)

        return filter


    #this parses the message filter format string passed in on the command line,
    #and produces something that will be understood by the 'createMessageFilterSequence' below
    def parseMessageFilterString(self, filterText, delimiter = ":", regex = False):
        """Create a createMessageFilterSequence object"""
        msgFilterSequence = self.client.createObject("ns0:MessageFilterSequence")
        msgFilterSequence._name = ""
        msgFilterSequence._allOtherTraffic = "hide"

        mfr = self.client.createObject("ns0:MessageFilterRule")
        msgFilterSequence.messageFilterRule.append(mfr)

        mfr._match = "show-if-is"

        #first do a switcheroo on any escaped delimiters, then split, and replace the delimiters again.
        switcheroo = filterText.replace("\\"+delimiter,"!!DELIM!!")
        splot = [elem.replace("!!DELIM!!",delimiter) for elem in switcheroo.split(delimiter)]

        if len(splot) != 4:
            sys.stderr.write("Cannot parse filter text \"%s\". \n" \
                        "all 4 elements are required (but may be blank) i.e. FIX::: \n"%filterText)
            sys.exit(1)

        mfr._messageProtocol = splot[0]
        mfr._messageType = splot[1]
        mfr._messageField = splot[2]
        mfr._messageFieldValue = splot[3]
        if regex:
            mfr._regex = "true"

        return msgFilterSequence

    def get_pcap(self, bidir, baseParams, mpReq, startTime, endTime, cliFilterObject, extraMps = None, snaplength = None, output = None):

        params = {'bothDirections' : str(bidir).lower()}
        if not snaplength == None:
            params['snaplength'] = snaplength

        if output:
            params["outputFormat"] = output

        params.update(baseParams)
        filter = self.add_filters(cliFilterObject)
        mpReq = self.client.createMeasurementPointRequest(mpReq)
        timeRange = self.client.createTimeRangeNs(self.parseTime(startTime), self.parseTime(endTime))
        additionalMps = []
        if extraMps is not None:
            for mpName in extraMps.split(','):
                extraMpReq = self.client.createMeasurementPointRequest(mpName)
                additionalMps.append(extraMpReq)
        dataGen = self.client.getPcapInBlocks(mpReq, timeRange, filter, additionalMps,
                params = params)
        # switch to binary mode on windows to prevent corruption of new line characters
        if sys.platform == "win32":
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY) # pylint: disable=no-member
        return dataGen

    def get_gap_csv(self, mpReq, startTime, endTime, baseParams, cliFilterObject, output=None):
        params={}
        if output:
            params["outputFormat"] = output
        params.update(baseParams)
        mpReq = self.client.createMeasurementPointRequest(mpReq)
        timeRange = self.client.createTimeRangeNs(self.parseTime(startTime), self.parseTime(endTime))
        filter = self.add_filters(cliFilterObject)
        dataGen = self.client.getMessageGapCsvInBlocks(mpReq, timeRange, filter, params=params)

        return dataGen

    def get_message_csv(self, bidir, includeCA, includeCI, columns, baseParams, mpReq, startTime, endTime,
                        cliFilterObject, output=None):
        params = {'bothDirections' : str(bidir).lower(),
                      'withCorrelation' : str(includeCA).lower()}
        if includeCI:
            params['withCorrelationIds'] = 'true'
        if columns:
            params['columnList'] = columns

        if output:
            params["outputFormat"] = output
        params.update(baseParams)
        filter = self.add_filters(cliFilterObject)

        mpReq = self.client.createMeasurementPointRequest(mpReq)
        timeRange = self.client.createTimeRangeNs(self.parseTime(startTime), self.parseTime(endTime))
        dataGen = self.client.getMessageCsvInBlocks(mpReq, timeRange, filter, params=params)

        return dataGen

    def get_packet_csv(self, bidir, columns, baseParams, mpReq, startTime, endTime, cliFilterObject, output=None):
        params = {'bothDirections' : str(bidir).lower()}
        if columns:
            params['columnList'] = columns
        if output:
            params["outputFormat"] = output
        params.update(baseParams)
        filter = self.add_filters(cliFilterObject)
        mpReq = self.client.createMeasurementPointRequest(mpReq)
        timeRange = self.client.createTimeRangeNs(self.parseTime(startTime), self.parseTime(endTime))
        dataGen = self.client.getPacketCsvInBlocks(mpReq, timeRange, filter, params=params)

        return dataGen

    def run(self, args):
        opts, args = getopt.gnu_getopt(args, "n:p:x:q:awsbcCzrl:m:t:g:T:f:L:d:F:")
        password = 'admin'
        userName = 'admin'
        bidir = False
        includeCA = False
        includeCI = False
        columns = None
        summariesOnly = None
        watchlistMetadata = None
        showMeasurementPoints = None
        query = None
        cne = None
        useHttps = False
        extraMps = None
        localCne = "local-cne"
        timeout = 3600
        snaplength = None
        output = "uncompressed"

        filterObj = {
            "filterType":None,
            "filterText":None,
            "regex":False,
            "delimiter":":"
        }

        for opt, arg in opts:
            if opt == '-n':
                userName = arg
            elif opt == '-p':
                password = arg
            elif opt == '-x':
                cne = arg
            elif opt == '-q':
                query = arg
            elif opt == '-b':
                bidir = True
            elif opt == '-c':
                includeCA = True
            elif opt == '-C':
                includeCI = True
            elif opt == '-z':
                useHttps = True
            elif opt == '-l':
                columns = arg
            elif opt == '-a':
                summariesOnly = True
            elif opt == '-w':
                watchlistMetadata = True
            elif opt == '-s':
                showMeasurementPoints = True
            elif opt == '-t':
                filterObj["filterType"] = arg
            elif opt == '-T':
                timeout = arg
            elif opt == '-f':
                filterObj["filterText"] = arg
            elif opt == '-m':
                extraMps = arg
            elif opt == '-L':
                localCne = arg
            elif opt == '-g':
                snaplength = arg
            elif opt == '-r':
                filterObj["regex"] = True
            elif opt == '-d':
                filterObj["delimiter"] = arg
            elif opt == '-F':
                output = arg

        if len(args) == 1 and args[0] == 'version':
            self.version()
        elif len(args) < 2:
            self.help()
        cmd = args[0]
        if cmd not in ['pcap', 'gap-csv', 'message-csv', 'packet-csv', 'lens-csv', 'multihop-csv', 'mp-list',
                       'flow-index', 'clock-tracking']:
            self.help()

        try:
            timeout = int(timeout);
        except ValueError:
            self.help("Invalid timeout value.\n")

        if (timeout <= 0):
            self.help("Timeout has to be a positive number.\n")

        host, port = self.parseHost(args[1])
        self.client = CorvilApiMtomClient(host, port=port,
            password = password, username=userName,cne=cne, useHttps=useHttps, timeout=timeout)

        if self.client.hostIsLmc and cmd != "lens-csv" and cne is None:
            self.help()

        if self.client.hostIsLmc and cne is not None:
            baseParams = {'cne':cne}
        else:
            baseParams = {}

        output_opts = {"uncompressed":None,
                           "zip":"zip",
                           "gzip":"gzip"}
        compressed_options = ["zip", "gzip"]
        if output not in output_opts:
            sys.stderr.write("'%s' is not a valid option for the output format -F, should be one of [%s]\n" %
                             (output, "|".join(output_opts.keys())))
            sys.exit(1)

        if cmd == 'mp-list':
            period = "1-hour"
            if len(args) == 3:
                period = args[2]
            self.get_mp_list(period)

        elif cmd == 'lens-csv':
            if len(args) < 3:
                self.help()
            period = args[2]
            view = 'Default'
            if len(args) == 4:
                view = args[3]
            dataGen = self.get_lens_csv(period, view, output_opts[output])
            for block in dataGen:
                sys.stdout.buffer.write(block)
            sys.exit(0)

        elif cmd == 'flow-index':
            if len(args) < 4 or len(args) > 5:
                self.help()
            aggr = []
            startTime = args[2]
            endTime = args[3]
            if len(args) >=5:
                aggr = args[4].split(",")
                if len(aggr) == 0:
                    self.help()
            dataGen = self.get_flow_index(startTime, endTime, aggr, watchlistMetadata, showMeasurementPoints,
                                          query, summariesOnly, baseParams, output_opts[output])
            for block in dataGen:
                sys.stdout.buffer.write(block)
            sys.exit(0)

        elif cmd == 'multihop-csv':
            if len(args) < 6:
                self.help()
            timestamp = args[3]
            message_id = args[4]
            message_index = args[5]
            mpReq = args[2]
            dataGen = self.get_multihop_csv(timestamp, message_id, message_index, mpReq, baseParams, output_opts[output])
            for block in dataGen:
                if output in compressed_options:
                    sys.stdout.buffer.write(block)
                else:
                    sys.stdout.write(block.decode())
            sys.exit(0)

        elif cmd == 'pcap':
            if len(args) < 5:
                self.help()

            if snaplength or snaplength == 0:
                try:
                    snaplength = int(snaplength);
                    if snaplength < 0 or snaplength > 65535:
                        raise ValueError()
                except ValueError:
                        self.help("snaplength must be an integral value between 0 and 65535.\n")
            
            mpReq = args[2]
            startTime = args[3]
            endTime = args[4]
            #Relocate this check here to allow the get_pcap call to be made unimpeded by
            #other users of the sample client API
            if os.isatty(sys.stdout.fileno()):
                sys.stderr.write("Not sending binary pcap data to STDOUT\n")
                sys.exit(1)

            if output not in output_opts:
                sys.stderr.write("'%s' is not a valid option for the output format -F, should be one of [%s]\n" %
                                (output, "|".join(output_opts.keys())))
                sys.exit(1)

            dataGen = self.get_pcap(bidir, baseParams, mpReq, startTime, endTime, filterObj, extraMps, snaplength, output_opts[output])
            for block in dataGen:
                sys.stdout.buffer.write(block)
            sys.exit(0)

        elif cmd == 'gap-csv':
            if len(args) < 5:
                self.help()
            mpReq = args[2]
            startTime = args[3]
            endTime = args[4]
            dataGen = self.get_gap_csv(mpReq, startTime, endTime, baseParams, filterObj, output_opts[output])
            for block in dataGen:
                if output in compressed_options:
                    sys.stdout.buffer.write(block)
                else:
                    sys.stdout.write(block.decode())
            sys.exit(0)

        elif cmd == 'message-csv':
            if len(args) < 5:
                self.help()
            mpReq = args[2]
            startTime = args[3]
            endTime = args[4]
            dataGen = self.get_message_csv( bidir, includeCA, includeCI, columns, baseParams, mpReq, startTime, endTime,
                                            filterObj, output_opts[output])
            for block in dataGen:
                if output in compressed_options:
                    sys.stdout.buffer.write(block)
                else:
                    sys.stdout.write(block.decode())
            sys.exit(0)

        elif cmd == 'packet-csv':
            if len(args) < 5:
                self.help()
            mpReq = args[2]
            startTime = args[3]
            endTime = args[4]
            dataGen = self.get_packet_csv(bidir, columns, baseParams, mpReq, startTime, endTime, filterObj,
                                          output_opts[output])
            for block in dataGen:
                if output in compressed_options:
                    sys.stdout.buffer.write(block)
                else:
                    sys.stdout.write(block.decode())
            sys.exit(0)

        elif cmd == 'clock-tracking':
            if len(args) < 4:
                self.help()
            if not localCne:
                self.help("Local CNE name cannot be empty.\n")
            startTime = args[2]
            endTime = args[3]
            mp = "channel//%s///ClockTracking" % (localCne)
            dataGen = self.get_message_csv( False, False, False, None, baseParams, mp, startTime, endTime, None)
            print('#client version: %s' % (VERSION,), flush = True)
            for block in dataGen:
                sys.stdout.write(block.decode())
            sys.exit(0)


if __name__ == '__main__':
    c = MtomTool(commandLine=True)
    c.run(sys.argv[1:])
