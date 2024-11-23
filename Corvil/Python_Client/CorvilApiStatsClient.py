#!/usr/bin/env python3

# Copyright (c) 2013, Corvil Limited. All rights reserved.
# THIS SOURCE CODE IS A TRADE SECRET OF CORVIL AND SHOULD NOT BE TRANSFERRED
# OR DISCLOSED TO ANY THIRD PARTY WITHOUT CORVIL'S PERMISSION. THIS SOURCE
# CODE IS LICENSED "AS IS", SOLELY FOR ILLUSTRATION PURPOSES, ONLY WITHIN
# THE LIMITED, SPECIFIC CONTEXT AND PARAMETERS INDICATED IN THE APPLICABLE
# CORVIL INSTRUCTIONS AND DOCUMENTATION, AND SUBJECT TO THE TERMS AND
# CONDITIONS OF THE CORVIL STANDARD SOFTWARE LICENSE AGREEMENT, INCLUDING
# WITHOUT LIMITATION THE LIABILITY LIMITATIONS SET FORTH THEREIN.

# NB: this was developed against Python v3.6 and Suds (suds-jurko) v0.6

# $Revision: 273095 $

"""

Corvil XML API example tool for streamed processing of MTOM attachments

Version: 3.2.0.202206301037-GA+273102

Usage: CorvilApiStatsClient.py [<options>] <command> <args> ...

  Commands + Arguments:
    version
        Prints client version
    summary                     <host>
        Get summary of specified CNE or CMC
    applications                <host>
        List of custom applications
    message-protocols           <host>
        List of installed message decoders
    message-protocols-details   <host> <protocol-name> ...
        Details of specified message decoder
    cnes                        <host> Get CNEs (CMC only command)
        List of CNEs (CMC only command)
    stats                       <host> <mp> <statistic> ...
        Get statistics from CNE or CMC
    live-stats                  <host> <mp> <statistic> ...
        Get live statistics from CNE or CMC
    analytics                   <host> <mp> <start-time> <end-time> <statistic> ...
        Get analytics from CNE or CMC
    clock-tracking              <host> <start-time> <end-time>
        Get clock tracking statistics from CNE
    lens-data                   <host> "<statistic>" "<statistic>"
        Get lens Data in csv format
        recognized options:
            -n, -p, -r, -s , -e , -b , -g, -z, -f

  Arguments:
    host            CNE or CMC to use when requesting data, can specify port: host:port
    mp              Fully qualified measurement point name, e.g.
                    "channel//local-cne///PortA". Use mp-list command for
                    full list of available measurement points
    start_time      Period start time (see Time Formats below)
    end_time        Period end time (see Time Formats below)
    protocol_name   Protocol name, e.g.: FIX
    statistic       Statistic name, e.g.: e2e-latency, packet-count.
                    Configurable statistic is prefixed with
                    'conf:', e.g.: conf:Orders, conf:Cancels
                    Stat event data is prefixed with 'event:',
                    e.g.: event:e2e-latency
                    For LensData use format : "stat,direction,aspect,percentile"
                    if stat is Configurable use stat-name as conf:, e.g: conf:orders
                    Specifying stat,direction would fetch all aspects for that stat
                    example :"packet-count,request" "latency,request,percentile,99.9" "conf:MOS LQK,request,min"
                    if sorting required append sort direction to the stat eg:"latency,request,percentile,99.9:ascending"
                    if stat name already contains , use \ to escape it.


  Options:
    -n <username>                   Specify username, default: admin
    -p <password>                   Specify password, default: admin
    -x <cne>                        Specify CNE for requests sent to CMC
    -r <reporting-period>           Reporting period, One of: "1-hour", "12-hours",
                                    "24-hours", "48-hours", "7-days", "30-days" and
                                    "60-days". Default is "1-hour" (summary, stats)
                                    "Last 1 hour","Last 24 hours", "Last 48 hours","Last 7 days"
                                    "Last 30 days","Last 60 days" (lens-data)
    -s <start-time>                 Start time of a time range (stats)
    -e <end-time>                   End time of a time range (stats)
                                    (Note: Specify either reporting
                                    period or start time and end time)
    -f <filter data>,
        --filter <filter data>      fully qualified channel name to filter summary method
                                    results, e.g.: "channel//local-cne///PortA" (summary)
                                    for lens data:
                                    Filters for lens-data separated by colon
                                    format: Session/subject:operator:value:CneName
                                    Session/Tag Type: Use Session for Session filtering,
                                        Use Tag Type if filtering by tag
                                    Operator : operator for filter
                                    standard list of operators: [is, isNot, isOneOf,isNotOneOf, isPresent, isNotPresent,
                                     contains, doesNotContain]
                                    value : Value to be filter by, can be tag value or a session value or cne name
                                    CneName: To Filter session only from a certain CNE, this is is optional
                                    example:
                                    Corvil:is:CNE1 Session:is:session1 Client:isOneOf:client1,client2 Client:isPresent:
                                    for multiple filters use space as separator , for eg:
                                    "Session/subject:operator:value:CneName Session/subject:operator:value:CneName"


    -m <mps>                        Comma-separated list of additional measurements
                                    points (stats, live-stats), e.g.:
                                    "channel//local-cne///PortA,channel//local-cne///PortB"
    -q <quantiles>                  Comma-separated list of quantile to request,
                                    e.g.: 25,50 (stats, live-stats, analytics)
    -u <update-period>              The time between updates, in seconds,
                                    default: 1 (live-stats)
    -i <iterations>                 Number of iterations, default: -1 which means
                                    infinite number of iterations (live-stats)
    -o <points>                     Number of points to request, default: 100 (analytics)
    -z                              use https to access the CNE
    -l <local-cne-name>             Local CNE name as configured by the "local-cne" command
                                    Default value: local-cne (clock-tracking)
    -t <thresholds>                 Comma-separated list of clock deviation thresholds (in ns).
                                    Default value: 1000,5000,25000 (clock-tracking)
    -T <timeout-seconds>            Request timeout in seconds
                                    Default value: 3600
    -R <resolutionMinutes>          Resolution (in minutes) of the time series data points in the response
       (in Minutes)                (e.g. resolutionMinutes=5 results in each data point covering a 5 minute period).
                                    The value must be a multiple of 5. If omitted, the resolution is calculated
                                    automatically based on the time period size.
    -b <businessHours>,
    --businessHours <businessHours> Business period named period name
    -g <grouping>, --grouping       Grouping Tag Types comma separated, e.g Client,Gateway,Sessions
                                    For Session grouping use keyword "Sessions" and it should be last grouping specified

  Time Formats:
    YYYY-MM-DD HH:MM:SS
    <epoch_sec>
    <epoch_nsec>
    <epoch_msec> for lens-data

"""
import re
from optparse import OptionParser
import logging
import suds
from suds import plugin
from suds import client
import sys
import time
import csv
import datetime
import itertools
import math

from LensDataModel import LensDataResponse

try:
    import ssl
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

VERSION='3.2.0.202206301037-GA+273102'

logging.basicConfig(level=logging.INFO)


logging.getLogger('suds').setLevel(logging.CRITICAL)
# Uncomment the line below to see the SOAP content being sent and received by SUDS
#logging.getLogger('suds.transport').setLevel(logging.DEBUG)

# matches all commas which dont have a backslash in front of it, uses negative lookbehind
split_pattern = re.compile(r'(?<!\\),')
colon_split_pattern = re.compile(r'(?<!\\):')
semi_colon_split_pattern= re.compile(r'(?<!\\);')
space_split_pattern = re.compile(r'(?<!\\)\s')

def list_to_str(l):
    if l is None:
        return None
    return "[%s]" % (', '.join(str(e) for e in l))


def dict_to_str(d):
    if d is None:
        return dict
    return "{%s}" % (', '.join('%s: %s' % (k, d[k]) for k in d.keys()))


def is_not_text(input):
    return type(input) is not suds.sax.text.Text and type(input) is not str

def str_to_list_of_ints(s):
    def convert(arg):
        if arg != "-":
            return int(arg)
        return arg
    if s:
        return list(map(convert, s.split(' ')))
    return []

def bool_to_str(b):
    return 'true' if b else 'false'

def parse_time(t, format = "ns"):
    try:
        t = time.mktime(time.strptime(t, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        pass
    try:
        t = int(t)
        if t < 0x7fffffff:
            if format == "ms":
                return t * int(1e3)
            else:
                return t * int(1e9)
        else:
            return t
    except ValueError:
        sys.stderr.write("Invalid time: %s\n" % (t,))
        sys.exit(1)


def value_to_str(value, factor=1):
    try:
        return str(float(value)/float(factor))
    except ValueError:
        return ''
    except TypeError:
        return ''


def value_to_str_integer(value, factor=1):
    try:
        return str(int(float(value)/float(factor)))
    except ValueError:
        return ''


def time_to_str(timestamp):
    return datetime.datetime.fromtimestamp(int(timestamp)/1000).strftime('%Y-%m-%d %H:%M:%S')


def column_header(type, unit=None):
    if unit:
        return '%s (%s)' % (type, unit)
    else:
        return '%s' % (type,)

class MethodNotAvailableException(Exception):
    pass
class SudsParameterPlugin(suds.plugin.MessagePlugin):
    """
    Suds plugin to specify extra method parameters This is necessary to allow
    for extra attributes on the root element of the suds request
    """
    def __init__(self):
        self.attrs = {}

    def setAttrs(self, attrs):
        """
        Set all attributes in one call, overwriting any pre-existing
        attributes
        """
        self.attrs = attrs

    def addAttr(self, attr, value):
        """
        Add a single attribute to the requests
        """
        self.attrs[attr] = value

    def removeAttr(self, attr):
        del self.attrs[attr]

    def marshalled(self, context):
        """
        Massage the SOAP request to add the provided attributes
        """
        body = context.envelope.getChild('Body')
        fnTag = body[0]
        for attrName, attrValue in list(self.attrs.items()):
            fnTag.set(attrName, attrValue)


class SudsRootAttributePlugin(suds.plugin.MessagePlugin):
    def __init__(self):
        self.attributes = {}

    def parsed(self, context):
        reply = context.reply
        for child in reply.getChild('Envelope').getChild('Body').getChildren():
            for attribute in child.attributes:
                self.attributes[attribute.name] = attribute.value

    def unmarshalled(self, context):
        for name, value in self.attributes.items():
            setattr(context.reply, '_%s' % (name,), value)


class NonEmptyRowCsvWriter(object):
    def __init__(self, writer):
        self.writer = writer

    def writerow(self, row):
        if row:
            self.writer.writerow(row)
        else:
            self.writer.writerow(['','',''])


class SummaryResponse(object):
    def __init__(self):
        self.filter = None
        self.channels = None

    def fromResponse(self, response):
        self.filter = getattr(response, 'filter', None)
        self.channels = []
        if hasattr(response, 'channel'):
            for channel in response.channel:
                self.channels.append(Channel().fromResponse(channel))
        return self

    def __str__(self):
        return "SummaryResponse(filter=%s, channels=%s)" % (
            self.filter, list_to_str(self.channels))

    def getSummaryCsvHeader(self):
        def getItemUnit(name):
            unit = None
            for ch in self.channels:
                unit = ch.summary.getUnit(name)
                if unit == None:
                    for cls in ch.classes:
                        unit = cls.summary.getUnit(name)
                        if unit != None:
                            return ' (%s)' % unit
            if unit == None:
                return ''
            return ' (%s)' % unit

        return ['configured capacity' + getItemUnit('configuredCapacity'),
              'effective capacity'  + getItemUnit('effectiveCapacity'),
              'total bytes' + getItemUnit('totalBytes'),
              'average utilisation',
              'network service indicator',
              'measure messages',
              'monitoring mechanism',
              'one second peak' + getItemUnit('oneSecondPeak'),
              'max microburst' + getItemUnit('maxMicroburst'),
              'packet microburst available',
              'link size packet delay' + getItemUnit('linkSizePacketDelay'),
              'link size queue length' + getItemUnit('linkSizeQueueLength'),
              'recommendation']

    def toCsv(self, output):
        if len(self.channels)>0:
            header = self.channels[0].getCsvHeader()
            summaryHeader = self.getSummaryCsvHeader()
            header.extend(summaryHeader)
            allConfStatNames = []
            for channel in self.channels:
                cnames = channel.summary.getConfStatNames()
                for name in cnames:
                    if name not in allConfStatNames:
                        allConfStatNames.append(name)
                for cls in channel.classes:
                    cnames = cls.summary.getConfStatNames()
                    for name in cnames:
                        if name not in allConfStatNames:
                            allConfStatNames.append(name)
            header.extend(allConfStatNames)
            output.writerow(header)
        for channel in self.channels:
            channel.toCsvSummary(output, allConfStatNames)


class Channel(object):
    def __init__(self):
        self.displayName = None
        self.name = None
        self.summary = None
        self.classes = None

    def fromResponse(self, response):
        self.displayName = response._displayName
        self.name = response._name
        self.summary = Summary().fromResponse(response.summary)
        self.classes = []
        for class_ in response.cls:
            self.classes.append(Class().fromResponse(class_))
        return self

    def __str__(self):
        return 'Channel(name=%s, displayName=%s, summary=%s, classes=%s)' % (
            self.displayName, self.name, self.summary,
            list_to_str(self.classes))

    def getCsvHeader(self):
        return ['#name', 'display name']

    def toCsv(self, output):
        output.writerow([self.displayName, self.name])
        self.summary.toCsv(output)
        for class_ in self.classes:
            class_.toCsv(output)

    def toCsvSummary(self, output, allConfStatNames):
        row = [self.displayName, self.name]
        rowSummary = self.summary.toCsvSummary(allConfStatNames)
        row.extend(rowSummary)
        output.writerow(row)
        for cls in self.classes:
            cls.toCsvSummary(output, allConfStatNames)

class Summary(object):
    def __init__(self):
        self.configuredCapacity = None
        self.effectiveCapacity = None
        self.totalBytes = None
        self.averageUtilisation = None
        self.networkServiceIndicator = None
        self.monitoringMechanism = None
        self.maxMicroburst = None
        self.linkSizePacketDelay = None
        self.linkSizeQueueLength = None
        self.oneSecondPeak = None
        self.recommendation = None
        self.measuresMessages = None
        self.packetMicroburstAvailable = None
        self.configurableStats = None
        self.configurableColumns = None
        self.configurableValues = None

    def fromResponse(self, response):
        def safe_set(name, wrapper=None):
            if hasattr(response, name):
                value = getattr(response, name)
                if wrapper:
                    setattr(self, name,
                            wrapper.fromResponse(value))
                else:
                    setattr(self, name, value)

        def safe_set_sci():
            name = 'networkServiceIndicator'
            if hasattr(response, name):
                nsiBlock = getattr(response, name)
                sci = nsiBlock["value"]
                if int(sci) > -1:
                    setattr(self, name, UnitFactorInt().fromResponse(nsiBlock))

        safe_set('configuredCapacity', UnitInt())
        safe_set('effectiveCapacity', UnitInt())
        safe_set('totalBytes', UnitInt())
        safe_set('averageUtilisation', UnitInt())
        safe_set_sci()
        safe_set('monitoringMechanism')
        safe_set('maxMicroburst', UnitInt())
        safe_set('linkSizePacketDelay', UnitFactorInt())
        safe_set('linkSizeQueueLength', UnitInt())
        safe_set('oneSecondPeak', UnitInt())
        safe_set('recommendation')
        safe_set('measuresMessages')
        safe_set('packetMicroburstAvailable')
        self.configurableStats = []
        self.configurableColumns = []
        self.configurableValues = dict()
        if hasattr(response, 'configurableStats'):
            for stat in response.configurableStats.configurableStat:
                cs = ConfigurableStatistic().fromResponse(stat)
                self.configurableStats.append(cs)
                self.configurableColumns.append(cs.name)
                self.configurableValues[cs.name] = '%s/%s' % (
                    cs.type, cs.customUnit if cs.customUnit else cs.unit
                )

        return self

    def __str__(self):
        return 'Summary(totalBytes=%s, networkServiceIndicator=%s, '\
               'monitoringMechanism=%s, maxMicroburst=%s, oneSecondPeak=%s, '\
               'recommendation=%s, measuresMessages=%s, '\
               'packetMicroburstAvailable=%s, configurableStats=%s)' % (
                   self.totalBytes, self.networkServiceIndicator,
                   self.monitoringMechanism, self.maxMicroburst,
                   self.oneSecondPeak, self.recommendation,
                   self.measuresMessages, self.packetMicroburstAvailable,
                   list_to_str(self.configurableStats))

    def getConfStatNames(self):
        names = []
        for cs in self.configurableStats:
            names.append(cs.name)
        return names

    def getConfStatByName(self, name):
        for c in self.configurableStats:
            if c.name == name:
                return c
        return None

    def getUnit(self, name):
        item = getattr(self, name)
        if item:
            if isinstance(item, UnitFactorInt):
                return item.unit
            elif isinstance(item, UnitInt):
                return item.unit
        return None

    def toCsv(self, output):
        #TODO: implement this if necessary
        pass

    def toCsvSummary(self, allConfigurableStats):
        row = []

        def safe_extend(item):
            if item:
                if isinstance(item, UnitFactorInt):
                    if item.factor != 1:
                        row.append(item.value / float(item.factor))
                    else:
                        row.append(item.value / item.factor)
                elif isinstance(item, UnitInt):
                    row.append(item.value)
                else:
                    row.append(item)
            else:
                row.append('')
        safe_extend(self.configuredCapacity)
        safe_extend(self.effectiveCapacity)
        safe_extend(self.totalBytes)
        safe_extend(self.averageUtilisation)
        safe_extend(self.networkServiceIndicator)
        safe_extend(bool_to_str(self.measuresMessages))
        safe_extend(self.monitoringMechanism)
        safe_extend(self.oneSecondPeak)
        safe_extend(self.maxMicroburst)
        safe_extend(bool_to_str(self.packetMicroburstAvailable))
        safe_extend(self.linkSizePacketDelay)
        safe_extend(self.linkSizeQueueLength)
        safe_extend(self.recommendation)
        for cname in allConfigurableStats:
            cstat = self.getConfStatByName(cname)
            if cstat != None:
                row.append(cstat.getValue())
            else:
                row.append('')

        return row


class UnitInt(object):
    def __init__(self):
        self.unit = None
        self.value = None

    def fromResponse(self, response):
        self.unit = response._unit
        self.value = int(response.value)
        return self

    def __str__(self):
        return 'UnitInt(unit=%s, value=%s)' % (self.unit, self.value)


class UnitFactorInt(UnitInt):
    def __init__(self):
        UnitInt.__init__(self)
        self.factor = None

    def fromResponse(self, response):
        UnitInt.fromResponse(self, response)
        if hasattr(response, '_factor'):
            self.factor = int(response._factor)
        else:
            self.factor = 1
        return self

    def __str__(self):
        return 'UnitFactorInt(unit=%s, factor=%s, value=%s)' % (self.unit,
                                                                self.factor,
                                                                self.value)


class Class(object):
    def __init__(self):
        self.displayName = None
        self.name = None
        self.summary = None

    def fromResponse(self, response):
        self.displayName = response._displayName
        self.name = response._name
        self.summary = Summary().fromResponse(response.summary)
        return self

    def __str__(self):
        return 'Class(name=%s, displayName=%s, summary=%s)' % (
            self.name, self.displayName, self.summary)

    def toCsv(self, output):
        row = [self.displayName, self.name]
        self.summary.toCsv(output)
        output.writerow(row)

    def toCsvSummary(self, output, allConfStatNames):
        row = [self.displayName, self.name]
        rowSummary = self.summary.toCsvSummary(allConfStatNames)
        row.extend(rowSummary)
        output.writerow(row)


class ConfigurableStatistic(object):
    def __init__(self):
        self.name = None
        self.type = None
        self.unit = None
        self.customUnit = None

    def fromResponse(self, response):
        self.name = response._name
        self.type = response._type
        self.unit = getattr(response, '_unit', None)
        self.customUnit = getattr(response, '_customUnit', None)
        return self

    def __str__(self):
        return 'ConfigurableStat(name=%s, type=%s, unit=%s, customUnit=%s)' % (
            self.name, self.type, self.unit, self.customUnit)

    def toCsv(self, output):
        output.writerow([self.name, self.type,
                         self.unit if self.unit else self.customUnit])

    def getValue(self):
        return "%s/%s" % (self.type, self.unit if self.unit else self.customUnit)


class MessageProtocolsResponse(object):
    def __init__(self):
        self.messageProtocols = None

    def fromResponse(self, response):
        self.messageProtocols = []
        for mp in response.messageProtocol:
            self.messageProtocols.append(
                MessageProtocol().fromResponse(mp))
        return self

    def __str__(self):
        return 'MessageProtocolsResponse(messageProtocols=%s)' % (
            list_to_str(self.messageProtocols),)

    def toCsv(self, output):
        output.writerow(['#protocol','description'])
        for messageProtocol in self.messageProtocols:
            messageProtocol.toCsv(output, header = False)


class MessageProtocol(object):
    def __init__(self):
        self.name = None
        self.description = None
        self.messageTypes = None
        self.fields = None

    def fromResponse(self, response):
        self.name = response._name
        self.description = response._description
        if hasattr(response, 'messageTypes'):
            self.messageTypes = []
            if hasattr(response.messageTypes, 'message'):
                for message in response.messageTypes.message:
                    self.messageTypes.append(message._name)
        if hasattr(response, 'fields'):
            self.fields = []
            if hasattr(response.fields, 'field'):
                for field in response.fields.field:
                    self.fields.append(field._name)
        return self

    def __str__(self):
        return 'MessageProtocol(name=%s, description=%s, messageTypes=%s, ' \
               'fields=%s)' % (self.name, self.description, self.messageTypes,
                               self.fields)

    def toCsv(self, output, header = True):
        if header:
            output.writerow(['#protocol','description'])
        output.writerow([self.name, self.description])
        if self.messageTypes:
            output.writerow(['#message types'])
            for messageType in self.messageTypes:
                output.writerow([messageType])
        if self.fields:
            output.writerow(['#message fields'])
            for field in self.fields:
                output.writerow([field])


class MessageProtocolsDetailsResponse(object):
    def __init__(self):
        self.messageProtocols = None

    def fromResponse(self, response):
        self.messageProtocols = []
        for messageProtocol in response:
            self.messageProtocols.append(
                MessageProtocol().fromResponse(messageProtocol))
        return self

    def __str__(self):
        return 'MessageProtocolsDetailsResponse(messageProtocol=%s)' % (
            list_to_str(self.messageProtocols))

    def toCsv(self, output):
        first = True
        for messageProtocol in self.messageProtocols:
            if first:
                first = False
            else:
                output.writerow([])
            messageProtocol.toCsv(output)



class ApplicationsResponse(object):
    def __init__(self):
        self.applications = None

    def fromResponse(self, response):
        self.applications = []
        for a in response:
            self.applications.append(
                Application().fromResponse(a))
        return self

    def __str__(self):
        return 'ApplicationsResponse(applications=%s)' % (
            list_to_str(self.applications),)

    def toCsv(self, output):
        output.writerow(['#application','type'])
        for application in self.applications:
            application.toCsv(output)


class Application(object):
    def __init__(self):
        self.name = None
        self.type = None

    def fromResponse(self, response):
        self.name = response._name
        self.type = response._type
        return self

    def __str__(self):
        return "Application(name=%s, type=%s)" % (self.name, self.type)

    def toCsv(self, output):
        output.writerow([self.name, self.type])


class StatsResponse(object):
    def __init__(self):
        self.startTime = None
        self.endTime = None
        self.measurementPoints = None

    def fromResponse(self, response, percentiles):
#        print response
        self.startTime = int(response._startTime)
        self.endTime = int(response._endTime)
        self.measurementPoints = []
        for measurementPoint in response.measurementPoint:
            self.measurementPoints.append(
                MeasurementPoint().fromResponse(measurementPoint, percentiles))
        return self

    def __str__(self):
        return "StatsResponse(startTime=%s, endTime=%s, " \
               "measurementPoints=%s)" % (
                   self.startTime, self.endTime, list_to_str(self.measurementPoints))

    def toCsv(self, output):
        if self._toCsvSummary(output):
            output.writerow([])
        if self._toCsvDistribution(output):
            output.writerow([])
        if self._toCsvScalarValue(output):
            output.writerow([])
        if self._toCsvTimeSeries(output):
            output.writerow([])
        if self._toCsvTimeSeriesEventData(output):
            output.writerow([])
        if self._toCsvTopN(output):
            output.writerow([])
        if self._toCsvTimeSeriesTopN(output):
            output.writerow([])

    def _toCsvScalarValue(self, output):
        type_filter = lambda x : isinstance(x, ScalarValue)
        columns = []
        for measurementPoint in self.measurementPoints:
            for stat in filter(type_filter, measurementPoint.stats):
                column = column_header(stat.type, stat.unit)
                if column not in columns:
                    columns.append(column)

        if columns:
            output.writerow(['#scalar value data'])
            output.writerow(['#measurement point', 'start time','start timestamp','end time','end timestamp'] + columns)
            for measurementPoint in self.measurementPoints:
                row = [measurementPoint.name]
                first = True
                for column in columns:
                    stat = measurementPoint.statsDict[column]
                    if first:
                        first = False
                        row.extend([time_to_str(stat.startTime), stat.startTime, time_to_str(stat.endTime), stat.endTime])
                    row.append(value_to_str(stat.value, stat.factor))
                output.writerow(row)
            return True
        return False

    def _toCsvTopN(self, output):
        type_filter = lambda x : isinstance(x, TopN)
        types = []
        for measurementPoint in self.measurementPoints:
            for stat in filter(type_filter, measurementPoint.stats):
                if not stat.type in types:
                    types.append(stat.type)

        if types:
            output.writerow(['#summary results for topn data'])
            output.writerow(['#measurement point', 'type',
                             'totalBytes (bytes)', 'totalPackets (packets)',
                             'totalFlows (flows)', 'maxError',
                             'availability (%)', 'periodEndsAt (ms)'])
            for measurementPoint in self.measurementPoints:
                for type in types:
                    stat = measurementPoint.statsDict[type]
                    output.writerow([
                        measurementPoint.name, type, stat.totalBytes,
                        stat.totalPackets, stat.totalFlows, stat.maxError,
                        stat.availability, stat.periodEndsAt])

            output.writerow([])
            output.writerow(['#topn data'])
            output.writerow(['#measurement point', 'type', 'key',
                             'byteCount (bytes)', 'byteCountPercentage (%)',
                             'packetCount (packets)', 'flowCount (flows)',
                             'bitRate (kbps)', 'application'])
            for measurementPoint in self.measurementPoints:
                for type in types:
                    stat = measurementPoint.statsDict[type]
                    for entry in stat.entries:
                        output.writerow([
                            measurementPoint.name, type, entry.key,
                            entry.byteCount, entry.byteCountPercentage,
                            entry.packetCount, entry.flowCount, entry.bitRate,
                            entry.application])
            return True
        return False

    def _toCsvTimeSeriesTopN(self, output):
        type_filter = lambda x : isinstance(x, TimeSeriesTopN)
        types = []
        for measurementPoint in self.measurementPoints:
            for stat in filter(type_filter, measurementPoint.stats):
                if not stat.type in types:
                    types.append(stat.type)

        if types:
            output.writerow(['#summary results for time series topn data'])
            row = ['#measurement point']
            for type in types:
                row.extend(['%s availability (%%)' % (type,), '%s config changes (ms)' % (type,)])
            output.writerow(row)
            for measurementPoint in self.measurementPoints:
                row = [measurementPoint.name]
                for type in types:
                    stat = measurementPoint.statsDict[type]
                    row.extend([stat.availability, stat.configChanges])
                output.writerow(row)

            output.writerow([])
            output.writerow(['#time series topn data'])
            output.writerow(['#measurement point', 'type', 'key',
                             'start time', 'start timestamp', 'end time',
                             'end timestamp', 'bit rate (bps)',
                             'packet rate (pps)'])
            for measurementPoint in self.measurementPoints:
                for type in types:
                    stat = measurementPoint.statsDict[type]
                    for keyData in stat.keyData:
                        for start, end, bitRate, packetRate in zip(
                                stat.startTimes, stat.endTimes,
                                keyData.bitRate, keyData.packetRate):
                            output.writerow([measurementPoint.name, stat.type,
                                             keyData.key, time_to_str(start),
                                             start, time_to_str(end), end,
                                             bitRate, packetRate])
            return True
        return False

    def _toCsvDistribution(self, output):
        type_filter = lambda x : isinstance(x, Distribution)
        columns = []
        for measurementPoint in self.measurementPoints:
            for stat in filter(type_filter, measurementPoint.stats):
                for column in stat.columns:
                    if column not in columns:
                        columns.append(column)

        if columns:
            output.writerow(['#distribution data'])
            output.writerow(['#measurement point'] + columns)
            for measurementPoint in self.measurementPoints:
                row = [measurementPoint.name]
                for column in columns:
                    for stat in filter(type_filter, measurementPoint.stats):
                        if column in stat.columns:
                            value = stat.values[column]
                            if isinstance(value, DistributionStatistic):
                                row.append(value_to_str(value.value, stat.factor))
                            else:
                                row.append(value)
                output.writerow(row)
            return True
        return False

    def _toCsvTimeSeries(self, output):
        type_filter = lambda x : isinstance(x, (
            TimeSeriesStatistic, TimeSeriesDistributionStatistic,
            TimeSeriesConfigurableStatistic,
            TimeSeriesDistributionConfigurableStatistic))
        all_stats = lambda mp : itertools.chain(mp.stats, mp.configurableStats)
        columns = []
        timeSeriesColumns = []
        for measurementPoint in self.measurementPoints:
            for stat in filter(type_filter, all_stats(measurementPoint)):
                for column in stat.summaryColumns:
                    if column not in columns:
                        columns.append(column)
                for column in stat.timeSeriesColumns:
                    if column not in timeSeriesColumns:
                        timeSeriesColumns.append(column)

        if columns:
            output.writerow(['#summary results for time series data'])
            output.writerow(['#measurement point'] + columns)
            for measurementPoint in self.measurementPoints:
                row = [measurementPoint.name]
                for column in columns:
                    stats = list(filter(type_filter, all_stats(measurementPoint)))
                    if stats:
                        for stat in stats:
                            if column in stat.summaryColumns:
                                row.append(stat.summaryValues[column])
                                break
                        else:
                            row.append('')
                    else:
                        row.append('')
                
                output.writerow(row)

            output.writerow([])
            output.writerow(['#time series data'])
            output.writerow(['#measurement point', 'start time',
                             'start timestamp (ms)', 'end time',
                             'end timestamp (ms)'] + timeSeriesColumns)
            
            responseStartTimes = None
            responseEndTimes = None

            for measurementPoint in self.measurementPoints:
                timeSeriesValues = []
                for column in timeSeriesColumns:
                    stats = list(filter(type_filter, all_stats(measurementPoint)))
                    if stats:
                        for stat in stats:
                            """ we can use even one starttime/endtime pair to get the 
                                bucket size, the extrapolate out the number of buckets from
                                the start and end time of the request
                                
                                WE ONLY NEED TO DO THIS ONCE PER RESPONSE hence the 'responseStartTimes' check
                                """
                            if stat.startTimes and len(stat.startTimes) > 0 and responseStartTimes == None:
                                responseStartTimes = []
                                responseEndTimes = []
                                bucketSize = stat.endTimes[0] - stat.startTimes[0]
                                """ self.endTime/startTime are the response end and start times """
                                buckets = int((self.endTime - self.startTime) / bucketSize)
                                
                                """ now given we have the number of buckets & the bucketsize, populate our
                                    response start and end times, starting with the RESPONSE start time.
                                    this will ensure we don't miss out on gaps at the start of the data """
                                bucketTime = self.startTime
                                for bucket in range(0,buckets):
                                    responseStartTimes.append(bucketTime)
                                    bucketTime = bucketTime + bucketSize
                                    responseEndTimes.append(bucketTime)

                        """ Now, having created the complete start and end times above, actually
                            handle the stats here """
                        for stat in stats:
                            if column in stat.timeSeriesValues:
                                values = stat.timeSeriesValues[column]
                                if values:
                                    """ We're assuming if there are values that there are corresponding start and end
                                        times, and therefore that the responseStartTimes and responseEndTimes have been
                                        populated above."""
                                    allValues = [''] * len(responseStartTimes)
                                    allIndex = 0
                                    for statIndex, startTime in enumerate(stat.startTimes):
                                        """ we want to iterate over the ACTUAL start times listed for the 
                                            stat, and check if and where they exist in the responseStartTimes array,
                                            and set the appropriate value on the tempValues array from this position
                                            on the 'values' array (which may have gaps)"""
                                        try:
                                            allIndex = responseStartTimes.index(startTime, allIndex)
                                            allValues[allIndex] = values[statIndex]
                                        except ValueError:
                                            pass

                                    timeSeriesValues.append(allValues)
                                    break
                        else:
                            timeSeriesValues.append(itertools.repeat(''))
                    else:
                        timeSeriesValues.append(itertools.repeat(''))

                if responseStartTimes and responseEndTimes:

                    for items in zip(responseStartTimes, responseEndTimes, *timeSeriesValues):
                        start, end = items[:2]
                        items = list(items[2:])
                        output.writerow([measurementPoint.name,
                                         time_to_str(start), start,
                                         time_to_str(end), end] + items)

            return True
        return False

    def _toCsvTimeSeriesEventData(self, output):
        type_filter = lambda x : isinstance(x, TimeSeriesEventData)
        columns = []
        timeSeriesColumns = []

        for measurementPoint in self.measurementPoints:
            for stat in filter(type_filter, measurementPoint.stats):
                for column in stat.summaryColumns:
                    if not column in columns:
                        columns.append(column)
                for column in stat.timeSeriesColumns:
                    if not column in timeSeriesColumns:
                        timeSeriesColumns.append(column)

        if columns:
            output.writerow(['#summary results for event data'])
            output.writerow(['#measurement point'] + columns)
            for measurementPoint in self.measurementPoints:
                row = [measurementPoint.name]
                for column in columns:
                    for stat in filter(type_filter, measurementPoint.stats):
                        if column in stat.summaryValues:
                            if stat.summaryValues[column] is not None:
                                if column.endswith('time-in-events (%)'):
                                    row.append(stat.summaryValues[column] / float(self.endTime - self.startTime) * 100)
                                else:
                                    row.append(stat.summaryValues[column])
                            else:
                                row.append("")
                output.writerow(row)

            output.writerow([])
            output.writerow(['#time series event data'])
            output.writerow(['#measurement point', 'start time',
                             'start timestamp (ms)', 'end time',
                             'end timestamp (ms)'] + timeSeriesColumns)

            for measurementPoint in self.measurementPoints:
                timeSeriesValues = []
                startTimes = None
                endTimes = None
                for column in timeSeriesColumns:
                    for stat in filter(type_filter, measurementPoint.stats):
                        if not startTimes or not endTimes:
                            startTimes = stat.startTimes
                            endTimes = stat.endTimes
                        if column in stat.timeSeriesValues:
                            timeSeriesValues.append(stat.timeSeriesValues[column])

                for items in zip(startTimes, endTimes, *timeSeriesValues):
                    startTime, endTime = items[:2]
                    items = list(items[2:])
                    output.writerow([measurementPoint.name,
                                     time_to_str(startTime), startTime,
                                     time_to_str(endTime), endTime] + items)
            return True
        return False

    def _toCsvSummary(self, output):
        type_filter = lambda x : isinstance(x, StatisticSummary)
        exists = False
        configurableColumns = []
        for measurementPoint in self.measurementPoints:
            for stat in filter(type_filter, measurementPoint.stats):
                exists = True
                for cs in stat.configurableColumns:
                    if not cs in configurableColumns:
                        configurableColumns.append(cs)

        if exists:
            output.writerow(['#measurement point summary'] + self._getSummaryColumns() + configurableColumns)
            def valueToStr(value):
                if isinstance(value, UnitFactorInt):
                    return value_to_str(value.value, value.factor)
                elif isinstance(value, UnitInt):
                    return str(value.value)
                elif value is None:
                    return ''
                elif value in (True, False):
                    return bool_to_str(value)
                else:
                    return str(value)

            for measurementPoint in self.measurementPoints:
                for stat in filter(type_filter, measurementPoint.stats):
                    row = [measurementPoint.name,
                           valueToStr(stat.configuredCapacity),
                           valueToStr(stat.effectiveCapacity),
                           valueToStr(stat.totalBytes),
                           valueToStr(stat.averageUtilisation),
                           valueToStr(stat.networkServiceIndicator),
                           valueToStr(stat.measuresMessages),
                           valueToStr(stat.monitoringMechanism),
                           valueToStr(stat.oneSecondPeak),
                           valueToStr(stat.maxMicroburst),
                           valueToStr(stat.packetMicroburstAvailable),
                           valueToStr(stat.linkSizePacketDelay),
                           valueToStr(stat.linkSizeQueueLength),
                           valueToStr(stat.recommendation)]
                    for cc in configurableColumns:
                        if cc in stat.configurableColumns:
                            row.append(stat.configurableValues[cc])
                        else:
                            row.append('')
                    output.writerow(row)

            return True
        return False


    def _getSummaryColumns(self):
        type_filter = lambda x : isinstance(x, StatisticSummary)
        def getItemUnit(name):
            unit = None
            for measurementPoint in self.measurementPoints:
                for stat in filter(type_filter, measurementPoint.stats):
                    unit = stat.getUnit(name)
            if unit:
                return ' (%s)' % (unit,)
            else:
                return ''

        return ['configured capacity' + getItemUnit('configuredCapacity'),
                'effective capacity'  + getItemUnit('effectiveCapacity'),
                'total bytes' + getItemUnit('totalBytes'),
                'average utilisation',
                'network service indicator',
                'measure messages',
                'monitoring mechanism',
                'one second peak' + getItemUnit('oneSecondPeak'),
                'max microburst' + getItemUnit('maxMicroburst'),
                'packet microburst available',
                'link size packet delay' + getItemUnit('linkSizePacketDelay'),
                'link size queue length' + getItemUnit('linkSizeQueueLength'),
                'recommendation']


class LiveStatsResponse(object):
    def __init__(self):
        self.statsGroupResponses = None
        self.updatePeriod = None

    def fromResponse(self, response):
        self.updatePeriod = int(response._updatePeriod)
        self.statsGroupResponses = []
        for statsGroupResponse in response.statsGroup:
            self.statsGroupResponses.append(
                StatsGroupResponse().fromResponse(statsGroupResponse))
        return self

    def __str__(self):
        return "LiveStatsResponse(statsGroupResponses=%s)" % \
               (list_to_str(self.statsGroupResponses))

    def printHeader(self, output):
        return self.statsGroupResponses[0].printHeader(output)

    """ We have a new 'historyLimit' argument in here as the live stats 
        response can have a 'history' and we don't want all the points
        printed out every time."""
    def toCsv(self, output, confstats, historyLimit = None, rowLimit = None):
        for statsGroupResponse in self.statsGroupResponses:
            statsGroupResponse.toCsvLive(output, self.updatePeriod, confstats, historyLimit, rowLimit)


class StatsGroupResponse(object):
    def __init__(self):
        self.measurementPoints = None
        self.timeStamp = None
        self.lagOffsetMs = None
        self.points = None
        self.name = None

    def fromResponse(self, response):
        self.measurementPoints = []
        self.name = response._name
        self.timeStamp = response._timestamp
        self.points = response._points
        self.lagOffsetMs = response._lagOffsetMs
        for measurementPoint in response.measurementPoints:
            for measurementPointResponse in measurementPoint[1]:
                self.measurementPoints.append(
                    MeasurementPointLive().fromResponse(measurementPointResponse))
        return self

    def __str__(self):
        return "StatsGroupResponse(measurementPoints=%s)" % (list_to_str(self.measurementPoints))

    def printHeader(self, output):
        row = ['#mp name', 'start time', 'start timestamp (s)', 'end time', 'end timestamp (s)']
        columns = self.measurementPoints[0].getHeader()
        confstats = dict()
        for mp in self.measurementPoints:
            cnf = mp.getConfigurableStats()
            for s in iter(cnf):
                if s not in confstats:
                    confstats[s] = cnf[s]
        row.extend(columns)
        for c in iter(confstats):
            row.extend(confstats[c])
        output.writerow(row)
        return confstats
    
    """New 'historyLimit' argument for live responses with history"""
    """We can also limit the number of rows returned i.e. given specific situation in live-stats
       we could end up needing, from [45,23,78,41,65,23], just 78,41,65 for example.
       in this case the historyLimit of 4 will ensure that we don't get 45 and 23 (because we've seen them before)
       and a 'rowLimit' of 3 will ensure that, of 78,41,65,23 that we only get 78,41,65. """
    def toCsvLive(self, output, updatePeriod, confstats, historyLimit = None, rowLimit = None):
        deferRows = []
        for measurementPoint in self.measurementPoints:
            mpRows = measurementPoint.toCsvLive(output, int(self.timeStamp), int(self.points), int(updatePeriod), confstats, historyLimit, True)
            if rowLimit:
                mpRows = mpRows[:rowLimit]
            deferRows.extend(mpRows)
        #we've gotten back potentially many rows here from multiple measurement points, and if there ARE
        #multiple rows per measurement point they will be sorted by measurement point then time. How we 
        #WANT to sort them is by time then measurement point, so we'll sort the list by the second element
        #which, rather conveniently, is a timestamp.
        if len(deferRows) > 0:
            deferRows.sort(key=lambda x:x[1])
            for deferRow in deferRows:
                output.writerow(deferRow)

class MeasurementPointLive(object):
    def __init__(self):
        self.dataSets = None
        self.topNs = None
        self.name = None

    def fromResponse(self, response):
        self.dataSets = []
        self.topNs = []
        self.name = response._name
        if hasattr(response, 'dataset'):
            for dataSet in response.dataset:
                self.dataSets.append(DataSet().fromResponse(dataSet))
        if hasattr(response, 'topn'):
            for topN in response.topn:
                self.topNs.append(TopN().fromResponse(topN))
        return self

    def __str__(self):
        return "MeasurementPointLive(dataSets=%s)" % (list_to_str(self.dataSets))

    def getHeader(self):
        row = []
        for dataSet in self.dataSets:
            if dataSet.type != None:
                dsrow = dataSet.getHeader()
                row.extend(dsrow)
        return row

    def getAnalyticsSummaryHeader(self):
        row = []
        for dataSet in self.dataSets:
            if dataSet.type != None:
                row.extend(dataSet.getAnalyticsSummaryHeader())
        return row

    def getHeaderText(self, name, sub, unit):
        result = name + ' ' + sub
        if unit != None:
            result += ' (' + unit + ')'
        return result

    def getConfigurableStatsSummaryHeader(self):
        result = dict()
        for dataSet in self.dataSets:
            if dataSet.configurableStat != None:
                unit = dataSet.unit
                if unit == None:
                    unit = dataSet.customUnit
                result[dataSet.configurableStat] = [self.getHeaderText(dataSet.configurableStat, 'min', unit),
                    self.getHeaderText(dataSet.configurableStat, 'max', unit)]
        return result

    def getConfigrableStatsDataSets(self):
        result = dict()
        for dataSet in self.dataSets:
            if dataSet.configurableStat != None:
                result[dataSet.configurableStat] = dataSet
        return result

    def getConfigurableStats(self):
        result = dict()
        for dataSet in self.dataSets:
            if dataSet.configurableStat != None:
                result[dataSet.configurableStat] = dataSet.getConfigurableStats()
        return result

    def findDataSet(self, dataSets, confStat):
        for ds in dataSets:
            if ds.configurableStat == confStat:
                return ds
        return None

    def toCsvSummary(self, output, confstats):
        row = [self.name]
        for dataSet in self.dataSets:
            if dataSet.type != None:
                summary = dataSet.getSummaryValues()
                row.extend(summary)
        for c in iter(confstats):
            dataSet = self.findDataSet(self.dataSets, c)
            if dataSet != None:
                row.extend(dataSet.getSummaryValues())
            else:
                row.extend(['',''])
        output.writerow(row)

    def toCsvDataSets(self, output, point, confstats):
        row = [self.name]
        for dataSet in self.dataSets:
            if dataSet.type != None:
                values = dataSet.getRow(point)
                row.extend(values)
        for c in confstats:
            dataSet = self.findDataSet(self.dataSets, c)
            if dataSet != None:
                values = dataSet.getRow(point)
            else:
                values = []
                for i in range(0, len(confstats[c].sets)):
                    values.append('')
            row.extend(values)
        output.writerow(row)

    def toCsvTopN(self, output):
        for topN in self.topNs:
            topN.topCsvTopN(output, self.name)

    def toCsvLive(self, output, groupTimestamp, groupPoints, updatePeriod, confstats, historyLimit = None, deferWrite = False):

        if groupPoints == 0:
            sti = groupTimestamp
            eti = groupTimestamp
            row = [self.name, datetime.datetime.utcfromtimestamp(sti), sti, datetime.datetime.utcfromtimestamp(eti), eti]
            for dataSet in self.dataSets:
                if dataSet.type != None:
                    dsrow = dataSet.getRow(-1)
                    row.extend(dsrow)
            for cstat in iter(confstats):
                dataSet = self.findDataSet(self.dataSets, cstat)
                if dataSet != None:
                    dsrow = dataSet.getRow(-1)
                    row.extend(dsrow)
                else:
                    dsrow = []
                    for i in range(0, len(confstats[cstat])):
                        dsrow.append('')
                    row.extend(dsrow)

            if deferWrite:
                return [].append(row)
            else:
                output.writerow(row)
        else:
            """"we want the facility here to NOT print the entire history every time, 
                for the most part the point limit will probably be 1 i.e. we're just 
                printing the most recent point in the history list. """
                
            startIndex = max(groupPoints-historyLimit if historyLimit else 0, 0)
            rows = []
            for idx in range(startIndex, groupPoints):
                sti = groupTimestamp - (groupPoints-idx)*updatePeriod
                eti = groupTimestamp - (groupPoints-idx-1)*updatePeriod
                row = [self.name, datetime.datetime.utcfromtimestamp(sti), sti, datetime.datetime.utcfromtimestamp(eti), eti]
                for dataSet in self.dataSets:
                    if dataSet.type != None:
                        dsrow = dataSet.getRow(idx)
                        row.extend(dsrow)
                for cstat in iter(confstats):
                    dataSet = self.findDataSet(self.dataSets, cstat)
                    if dataSet != None:
                        dsrow = dataSet.getRow(idx)
                        row.extend(dsrow)
                    else:
                        dsrow = []
                        for i in range(0, len(confstats[cstat])):
                            dsrow.append('')
                        row.extend(dsrow)
                rows.append(row)

            if deferWrite:
                return rows
            else:
                for row in rows:
                    output.writerow(row)


class DataSet(object):
    def __init__(self):
        self.sets = None
        self.factor = None
        self.customUnit = None
        self.unit = None
        self.type = None
        self.configurableStat = None
        self.numerator = None
        self.denominator = None
        self.summary_min = None
        self.summary_max = None
        self.error = None

    def fromResponse(self, response):
        if hasattr(response, '_error') and response._error:
            self.sets = []
            self.error = response._error
            self.type = getattr(response, '_type', None)
            self.unit = getattr(response, '_unit', None)
            self.customUnit = getattr(response, '_customUnit', None)
            self.configurableStat = getattr(response, '_configurableStat', None)
            if hasattr(response, 'set'):
                for dset in response.set:
                    self.sets.append(Set().fromResponse(dset))
        else:
            self.sets = []
            self.type = getattr(response, '_type', None)
            self.unit = getattr(response, '_unit', None)
            self.customUnit = getattr(response, '_customUnit', None)
            self.configurableStat = getattr(response, '_configurableStat', None)
            self.numerator = getattr(response, '_numerator', None)
            self.denominator = getattr(response, '_denominator', None)
            self.factor = response._factor
            if hasattr(response, 'set'):
                for dset in response.set:
                    self.sets.append(Set().fromResponse(dset))
            if hasattr(response, "summary"):
                self.summary_min = getattr(response.summary, '_min', None)
                self.summary_max = getattr(response.summary, '_max', None)
        return self

    def __str__(self):
        if self.error:
            return 'DataSet(error=%s)' %(self.error,)
        else:
            return "DataSet(sets=%s)" % (list_to_str(self.sets),)

    def toCsv(self, output):
        if  self.error:
            output.writerow([self.error])
        else:
            row = [
                self.factor, self.unit if self.unit else self.customUnit, self.type]
            if self.configurableStat is not None:
                row.extend([self.configurableStat])
            if self.numerator is not None:
                row.extend([self.numerator])
            if self.denominator is not None:
                row.extend([self.denominator])
            if self.summary_max is not None:
                row.extend([self.summary_max])
            if self.summary_min is not None:
                row.extend([self.summary_min])
            output.writerow(row)
            for dset in self.sets:
                dset.toCsv(output)

    def getRow(self, index):
        row = []
        if self.error != None:
            row.append(self.error)
            if len(self.sets) > 1:
                for i in range(0, len(self.sets)-1):
                    row.append('')
        else:
            for dset in self.sets:
                row.append(dset.getValue(index, int(self.factor)))
        return row

    def getHeader(self):
        row = []
        unit = self.unit
        if unit == None:
            unit = self.customUnit
        if len(self.sets) == 0:
            if unit != None:
                return ["%s (%s)" % (self.type, unit)]
            else:
                return [self.type]
        for dset in self.sets:
            if self.type != None:
                row.append(dset.getHeader(self.type, unit))
        return row

    def getHeaderText(self, name, sub, unit):
        result = name + ' ' + sub
        if unit != None:
            result += ' (' + unit + ')'
        return result

    def getAnalyticsSummaryHeader(self):
        row = []
        if self.type != None:
            unit = self.unit
            if unit == None:
                unit = self.customUnit
            row.append(self.getHeaderText(self.type, 'min', unit))
            row.append(self.getHeaderText(self.type, 'max', unit))
        return row

    def getConfigurableStats(self):
        row = []
        for dset in self.sets:
            if self.configurableStat != None:
                unit = self.unit
                if unit == None:
                    unit = self.customUnit
                row.append(dset.getHeader(self.configurableStat, unit))
        return row

    def getSummaryValues(self):
        if self.error == None:
            return [self.getWithFactor(self.summary_min),
                    self.getWithFactor(self.summary_max)]
        else:
            return [self.error, self.error]

    def getWithFactor(self, _number):
        try:
            return float(_number) / float(self.factor)
        except ValueError:
            return _number


class Set(object):
    def __init__(self):
        self.value = None
        self.type = None
        self.percentile = None

    def fromResponse(self, response):
        self.value = getattr(response, 'value', None)
        self.percentile = getattr(response, '_percentile', None)
        self.type = response._type
        return self

    def __str__(self):
        return "Set[type:%s][percentile:%s](value=%s)" % (self.type, self.percentile, self.value)

    def toCsv(self, output):
        output.writerow([self.type])
        output.writerow(str_to_list_of_ints(self.value))

    def getValue(self, index, factor):
        if index == -1:
            return '-'
        lst = str_to_list_of_ints(self.value)
        if index >= len(lst):
            return '-'
        val = lst[index]
        if val != '-':
            if factor != 1:
                if self.type != 'count':
                    val = str(int(val)/float(factor))
            else:
                val = str(int(val)/int(factor))
        return val

    def getHeader(self, dstype, dsunit):
        result = dstype
        if self.type != 'value':
            result += ' ' + self.type
        if self.percentile:
            result += ' %s' % self.percentile
        if dsunit:
            result += ' (%s)' % dsunit
        return result


class MeasurementPoint(object):
    def __init__(self):
        self.name = None
        self.stats = None
        self.statsDict = None
        self.configurableStats = None
        self.configurableStatsDict = None

    def fromResponse(self, response, percentiles):
        self.name = response._name
        self.stats = []
        self.statsDict = dict()
        self.configurableStats = []
        self.configurableStatsDict = dict()
        for attribute in dir(response):
            stat = getattr(response, attribute)
            statObject = None
            confStatObject = None
            if not callable(stat) and not attribute.startswith('_'):
                class_ = stat.__class__.__name__
                if class_ == 'TimeSeries':
                    statObject = TimeSeriesStatistic().fromResponse(stat)
                elif class_ == 'TimeSeriesTopN':
                    statObject = TimeSeriesTopN().fromResponse(stat)
                elif class_ == 'TimeSeriesDistribution':
                    statObject = TimeSeriesDistributionStatistic().fromResponse(stat, percentiles)
                elif class_ == 'ScalarValue':
                    statObject = ScalarValue().fromResponse(stat)
                elif class_ == 'Distribution':
                    statObject = Distribution().fromResponse(stat)
                elif class_ == 'TopN':
                    statObject = TopN().fromResponse(stat)
                elif class_ == 'Summary':
                    statObject = StatisticSummary().fromResponse(stat)
                elif attribute == 'statEventData':
                    for subStat in stat:
                        class_ = subStat.__class__.__name__
                        if class_ == 'TimeSeriesEventData':
                            self.stats.append(TimeSeriesEventData().fromResponse(subStat))
                elif attribute in ['configurableStatCount',
                                   'configurableStatMinMeanMax',
                                   'configurableStatTotal',
                                   'configurableStatRatio']:
                    for configurableStat in stat:
                        class_ = configurableStat.__class__.__name__
                        if class_ == 'TimeSeries':
                            confStatObject = TimeSeriesConfigurableStatistic().fromResponse(configurableStat)
                        elif class_ == 'TimeSeriesDistribution':
                            confStatObject = TimeSeriesDistributionConfigurableStatistic().fromResponse(configurableStat)
                        else:
                            print("Not a configurable stat: %s" % (
                                configurableStat,))
                        if confStatObject:
                            self.configurableStats.append(confStatObject)
                            header=column_header(confStatObject.name, getattr(confStatObject, 'unit', None))
                            self.configurableStatsDict[header] = confStatObject
                else:
                    print("Not a stat: %s" % (stat,))
                if statObject:
                    self.stats.append(statObject)
                    self.statsDict[column_header(statObject.type, getattr(statObject, 'unit', None))] = statObject

        return self

    def __str__(self):
        return "MeasurementPoint(name=%s, stats=%s, statsDict=%s, configurableStats=%s, configurableStatsDict=%s)" % (
            self.name, list_to_str(self.stats), dict_to_str(self.statsDict),
            list_to_str(self.configurableStats), dict_to_str(self.configurableStatsDict))

    def toCsv(self, output):
        output.writerow([self.name])
        for stat in sorted(self.stats, key=lambda stat: stat.type):
            stat.toCsv(output)
        for configurableStat in sorted(
                self.configurableStats, key=lambda stat: stat.name):
            configurableStat.toCsv(output)


class Statistic(object):
    def __init__(self):
        self.type = None

    def fromResponse(self, response):
        self.type = response._type
        return self


class TimeSeriesBase(object):
    def __init__(self):
        self.startTimes = None
        self.endTimes = None
        self.factor = None
        self.availability = None
        self.configChanges = None

    def fromResponse(self, response):
        self.startTimes = str_to_list_of_ints(response.startTimes)
        self.endTimes = str_to_list_of_ints(response.endTimes)
        self.factor = int(response.factor)
        self.availability = int(response.availability)
        self.configChanges = response.configChanges
        return self

    def setTimeseriesValuesFromResponse(self, response):
        if hasattr(response, 'values'):
            self.values = str_to_list_of_ints(response.values)
        else:
            self.mins = str_to_list_of_ints(response.mins)
            self.means = str_to_list_of_ints(response.means)
            self.maxs = str_to_list_of_ints(response.maxs)
            self.counts = str_to_list_of_ints(response.counts)

    def createTimeseriesColumns(self, column_name):
        self.timeSeriesValues = {}
        if self.values is not None:
            self.timeSeriesValues[column_name] = [value_to_str(i, self.factor) for i in self.values]
        else:
            #reporting period is > 24 hours; expect different response format
            if self.means is not None and self.counts is not None:
                vs = []
                for (c,m) in zip(self.counts, self.means):
                    vs.append(value_to_str(c*m, self.factor))
                self.timeSeriesValues[column_name] = vs

    def getRoundingErrorPostfix(self):
        if self.values is None and  self.counts is not None and len(self.counts) > 0:
            e = max(self.counts)
            if e != 0:
                return " +/- " + str(math.ceil(float(e)/2))
        return ""


class UnitMixin(object):
    def __init__(self):
        self.unit = None

    def fromResponse(self, response):
        self.unit = response.unit
        return self


class TimeSeries(TimeSeriesBase):
    def __init__(self):
        TimeSeriesBase.__init__(self)
        self.values = None
        self.min = None
        self.mean = None
        self.max = None
        self.total = None
        self.counts = None
        self.mins = None
        self.means = None
        self.maxs = None

    def fromResponse(self, response):
        TimeSeriesBase.fromResponse(self, response)
        self.setTimeseriesValuesFromResponse(response)
        self.min = str(response.min)
        self.mean = str(response.mean)
        self.max = str(response.max)
        self.total = str(response.total)
        return self


class TimeSeriesStatistic(TimeSeries, Statistic, UnitMixin):
    def __init__(self):
        TimeSeries.__init__(self)
        Statistic.__init__(self)
        UnitMixin.__init__(self)
        self.summaryColumns = None
        self.summaryValues = None
        self.timeSeriesColumns = None
        self.timeSeriesValues = None

    def fromResponse(self, response):
        TimeSeries.fromResponse(self, response)
        Statistic.fromResponse(self, response)
        UnitMixin.fromResponse(self, response)

        self.summaryColumns = []
        self.summaryValues = dict()
        column_name = self.columnName('min')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.min, self.factor)
        column_name = self.columnName('mean')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.mean, self.factor)
        column_name = self.columnName('max')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.max, self.factor)
        column_name = self.columnName('total')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.total, self.factor)
        column_name = '%s availability (%%)' % (self.type,)
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = self.availability
        column_name = '%s config changes (ms)' % (self.type,)
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = self.configChanges

        self.timeSeriesColumns = []
        self.timeSeriesValues = dict()
        column_name = self.columnName('value')
        column_name = column_name + self.getRoundingErrorPostfix()
        self.timeSeriesColumns.append(column_name)
        self.createTimeseriesColumns(column_name)


        return self

    def __str__(self):
        return "TimeSeriesStatistic(type=%s, startTimes=%s, endTimes=%s, " \
               "value=%s, min=%s, mean=%s, max=%s, total=%s, unit=%s, " \
               "factor=%s, availability=%s, configChanges=%s, " \
               "summaryColumns=%s, summaryValues=%s, timeSeriesColumns=%s," \
               "timeSeriesValues=%s)" % (
                   self.type, self.startTimes, self.endTimes, self.values,
                   self.min, self.mean, self.max, self.total, self.unit,
                   self.factor, self.availability, self.configChanges,
                   list_to_str(self.summaryColumns),
                   dict_to_str(self.summaryValues),
                   list_to_str(self.timeSeriesColumns),
                   dict_to_str(self.timeSeriesValues))

    def toCsv(self, output):
        output.writerow([self.type])
        output.writerow(self.startTimes)
        output.writerow(self.endTimes)
        output.writerow(self.values)
        output.writerow(self.mins)
        output.writerow(self.means)
        output.writerow(self.maxs)
        output.writerow(self.counts)
        output.writerow([self.min, self.mean, self.max, self.total, self.unit,
                         self.factor, self.availability, self.configChanges])

    def columnName(self, name):
        return '%s %s (%s)' % (self.type, name, self.unit)


class UnitOrCustomUnitMixin(object):
    def __init__(self):
        self.unit = None
        self.customUnit = None

    def fromResponse(self, response):
        self.unit = getattr(response, 'unit', None)
        self.customUnit = getattr(response, 'customUnit', None)
        return self


class NameMixin(object):
    def __init__(self):
        self.name = None

    def fromResponse(self, response):
        self.name = response._name


class TimeSeriesConfigurableStatistic(TimeSeries,
                                      UnitOrCustomUnitMixin,
                                      NameMixin):
    def __init__(self):
        TimeSeries.__init__(self)
        UnitOrCustomUnitMixin.__init__(self)
        NameMixin.__init__(self)
        self.summaryColumns = None
        self.summaryValues = None
        self.timeSeriesColumns = None
        self.timeSeriesValues = None

    def fromResponse(self, response):
        TimeSeries.fromResponse(self, response)
        UnitOrCustomUnitMixin.fromResponse(self, response)
        NameMixin.fromResponse(self, response)

        self.summaryColumns = []
        self.summaryValues = dict()
        column_name = self.columnName('min')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.min, self.factor)
        column_name = self.columnName('mean')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.mean, self.factor)
        column_name = self.columnName('max')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.max, self.factor)
        column_name = self.columnName('total')
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = value_to_str(self.total, self.factor)
        column_name = '%s availability (%%)' % (self.name,)
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = self.availability
        column_name = '%s config changes (ms)' % (self.name,)
        self.summaryColumns.append(column_name)
        self.summaryValues[column_name] = self.configChanges

        self.timeSeriesColumns = []
        self.timeSeriesValues = dict()
        column_name = self.columnName('value')
        column_name = column_name + self.getRoundingErrorPostfix()
        self.timeSeriesColumns.append(column_name)
        self.createTimeseriesColumns(column_name)

        return self

    def __str__(self):
        return "TimeSeriesConfigurableStatistic(name=%s, startTimes=%s, " \
               "endTimes=%s, value=%s, min=%s, mean=%s, max=%s, total=%s, " \
               "unit=%s, customUnit=%s, factor=%s, availability=%s, " \
               "configChanges=%s, summaryColumns=%s, summaryValues=%s, " \
               "timeSeriesColumns=%s, timeSeriesValues=%s)" % (
                   self.name, self.startTimes, self.endTimes, self.values, self.min,
                   self.mean, self.max, self.total, self.unit, self.customUnit,
                   self.factor, self.availability, self.configChanges,
                   self.summaryColumns, self.summaryValues,
                   self.timeSeriesColumns, self.timeSeriesValues)

    def toCsv(self, output):
        output.writerow([self.name])
        output.writerow(self.startTimes)
        output.writerow(self.endTimes)
        output.writerow(self.values)
        output.writerow([self.min, self.mean, self.max, self.total,
                         self.unit if self.unit else self.customUnit,
                         self.factor, self.availability, self.configChanges])

    def columnName(self, name):
        unit = self.customUnit if self.customUnit else self.unit
        if unit:
            return '%s %s (%s)' % (self.name, name, unit)
        else:
            return '%s %s' % (self.name, name)


class TimeSeriesTopN(TimeSeriesBase, Statistic):
    def __init__(self):
        Statistic.__init__(self)
        TimeSeriesBase.__init__(self)
        self.keyData = None

    def fromResponse(self, response):
        TimeSeriesBase.fromResponse(self, response)
        Statistic.fromResponse(self, response)
        self.keyData = []
        if hasattr(response, 'keyData'):
            for keyData in response.keyData:
                self.keyData.append(KeyData().fromResponse(keyData))
        return self

    def __str__(self):
        return "TimeSeriesTopN(type=%s, keyData=%s, startTimes=%s, " \
               "endTimes=%s, factor=%s, availability=%s, configChanges=%s)" % (
                   self.type, list_to_str(self.keyData), self.startTimes,
                   self.endTimes, self.factor, self.availability, self.configChanges)

    def toCsv(self, output):
        output.writerow([self.type])
        output.writerow(self.startTimes)
        output.writerow(self.endTimes)
        for keyData in self.keyData:
            keyData.toCsv(output)
        output.writerow([self.factor, self.availability, self.configChanges])


class KeyData(object):
    def __init__(self):
        self.key = None
        self.bitRate = None
        self.packetRate = None

    def fromResponse(self, response):
        self.key = response._key
        self.bitRate = str_to_list_of_ints(response.bitRate)
        self.packetRate = str_to_list_of_ints(response.packetRate)
        return self

    def __str__(self):
        return "KeyData(key=%s, bitRate=%s, packetRate=%s)" % (
            self.key, self.bitRate, self.packetRate)

    def toCsv(self, output):
        output.writerow([self.key])
        output.writerow(self.bitRate)
        output.writerow(self.packetRate)


class DistributionData(object):
    def __init__(self):
        self.quantile = None
        self.values = None
        self.min = None
        self.mean = None
        self.max = None
        self.summaryValue = None
        self.count = None

    def fromResponse(self, response):
        self.quantile = response._quantile
        self.values = str_to_list_of_ints(response.values)
        self.min = str(response.min)
        self.mean = str(response.mean)
        self.max = str(response.max)
        if hasattr(response, "summaryValue"):
            self.summaryValue = str(response.summaryValue)
        if hasattr(response, 'count'):
            self.count = str(response.count)
        return self

    def __str__(self):
        return "DistributionData(quantile=%s, values=%s, min=%s, mean=%s, " \
               "max=%s, summaryValue=%s, count=%s)" % (
                   self.quantile, self.values, self.min, self.mean, self.max,
                   self.summaryValue, self.count)

    def toCsv(self, output):
        output.writerow([self.quantile])
        output.writerow(self.values if self.values is not None else [])
        temp_row = [self.min, self.mean, self.max]
        if self.summaryValue is not None:
            temp_row.append(self.summaryValue)
        output.writerow(temp_row)


class TimeSeriesDistribution(TimeSeriesBase, UnitMixin):
    def __init__(self):
        TimeSeriesBase.__init__(self)
        UnitMixin.__init__(self)
        self.quantiles = None

    def fromResponse(self, response):
        TimeSeriesBase.fromResponse(self, response)
        UnitMixin.fromResponse(self, response)
        self.quantiles = []
        for data in response.data:
            self.quantiles.append(DistributionData().fromResponse(data))
        self.startTimes = str_to_list_of_ints(response.startTimes)
        self.endTimes = str_to_list_of_ints(response.endTimes)
        return self

    def __str__(self):
        return "TimeSeriesDistribution(quantiles=%s, startTimes=%s, " \
               "endTimes=%s, unit=%s, factor=%s, availability=%s, " \
               "configChanges=%s)" % (
                   list_to_str(self.quantiles), self.startTimes, self.endTimes,
                   self.unit, self.factor, self.availability, self.configChanges)


class TimeSeriesDistributionStatistic(TimeSeriesDistribution, Statistic):
    def __init__(self):
        TimeSeriesDistribution.__init__(self)
        Statistic.__init__(self)
        self.summaryColumns = None
        self.summaryValues = None
        self.timeSeriesColumns = None
        self.timeSeriesValues = None

    def fromResponse(self, response, percentiles):
        TimeSeriesDistribution.fromResponse(self, response)
        Statistic.fromResponse(self, response)

        def addSummary(name):
            column_name = self.columnName(name)
            count_name = '%s count' % (self.type)
            if count_name not in self.summaryColumns:
                self.summaryColumns.append(count_name)
            for quantile in self.quantiles:
                if quantile.quantile == name:
                    self.summaryColumns.append(column_name)
                    self.summaryValues[column_name] = value_to_str(quantile.summaryValue, self.factor)
                    if count_name not in self.summaryValues:
                        self.summaryValues[count_name] = value_to_str_integer(quantile.count)

        self.summaryColumns = []
        self.summaryValues = dict()

        addSummary('min')
        addSummary('mean')
        addSummary('max')
        if percentiles:
            for percentile in percentiles.split(','):
                addSummary(percentile)

        def addTimeSeries(name):
            column_name = self.columnName(name)
            for quantile in self.quantiles:
                if quantile.quantile == name:
                    self.timeSeriesColumns.append(column_name)
                    self.timeSeriesValues[column_name] = [value_to_str(i, self.factor) for i in quantile.values]


        self.timeSeriesColumns = []
        self.timeSeriesValues = dict()

        addTimeSeries('min')
        addTimeSeries('mean')
        addTimeSeries('max')
        if percentiles:
            for percentile in percentiles.split(','):
                addTimeSeries(percentile)


        return self

    def __str__(self):
        return "TimeSeriesDistributionStatistic(type=%s, quantiles=%s, " \
               "startTimes=%s, endTimes=%s, unit=%s, factor=%s, " \
               "availability=%s, configChanges=%s, summaryColumns=%s," \
               "summaryValue=%s, timeSeriesColumns=%s," \
               "timeSeriesValues=%s)" % (
                   self.type, list_to_str(self.quantiles), self.startTimes,
                   self.endTimes, self.unit, self.factor, self.availability,
                   self.configChanges, self.summaryColumns,
                   self.summaryValues, self.timeSeriesColumns,
                   self.timeSeriesValues)

    def toCsv(self, output):
        output.writerow([self.type])
        output.writerow(self.startTimes)
        output.writerow(self.endTimes)
        for quantile in self.quantiles:
            quantile.toCsv(output)
        output.writerow([self.unit, self.factor, self.availability,
                         self.configChanges])

    def columnName(self, name):
        return '%s %s (%s)' % (self.type, name, self.unit)


class TimeSeriesDistributionConfigurableStatistic(TimeSeriesBase,
                                                  UnitOrCustomUnitMixin,
                                                  NameMixin):
    def __init__(self):
        TimeSeriesBase.__init__(self)
        UnitOrCustomUnitMixin.__init__(self)
        NameMixin.__init__(self)
        self.quantiles = None
        self.summaryColumns = None
        self.summaryValues = None
        self.timeSeriesColumns = None
        self.timeSeriesValues = None

    def fromResponse(self, response):
        TimeSeriesBase.fromResponse(self, response)
        UnitOrCustomUnitMixin.fromResponse(self, response)
        NameMixin.fromResponse(self, response)
        self.quantiles = []
        for data in response.data:
            self.quantiles.append(DistributionData().fromResponse(data))
        self.startTimes = str_to_list_of_ints(response.startTimes)
        self.endTimes = str_to_list_of_ints(response.endTimes)

        def addSummary(name):
            column_name = self.columnName(name)
            count_name = '%s count' % (self.name)
            self.summaryColumns.append(column_name)
            if count_name not in self.summaryColumns:
                self.summaryColumns.append(count_name)
            for quantile in self.quantiles:
                if quantile.quantile == name:
                    self.summaryValues[column_name] = value_to_str(getattr(quantile, name), self.factor)
                    if count_name not in self.summaryValues:
                        self.summaryValues[count_name] = value_to_str_integer(quantile.count)

        self.summaryColumns = []
        self.summaryValues = dict()

        addSummary('min')
        addSummary('mean')
        addSummary('max')

        def addTimeSeries(name):
            column_name = self.columnName(name)
            self.timeSeriesColumns.append(column_name)
            for quantile in self.quantiles:
                if quantile.quantile == name:
                    self.timeSeriesValues[column_name] = [value_to_str(i, self.factor) for i in quantile.values]


        self.timeSeriesColumns = []
        self.timeSeriesValues = dict()

        addTimeSeries('min')
        addTimeSeries('mean')
        addTimeSeries('max')

        return self

    def __str__(self):
        return "TimeSeriesDistributionConfigurableStatistic(name=%s, " \
               "quantiles=%s, startTimes=%s, endTimes=%s, unit=%s, " \
               "factor=%s, availability=%s, configChanges=%s, " \
               "summaryColumns=%s, summaryValues=%s, timeSeriesColumns=%s, " \
               "timeSeriesValues=%s)" % (
                   self.name, list_to_str(self.quantiles), self.startTimes,
                   self.endTimes, self.unit, self.factor, self.availability,
                   self.configChanges, list_to_str(self.summaryColumns),
                   dict_to_str(self.summaryValues),
                   list_to_str(self.timeSeriesColumns),
                   dict_to_str(self.timeSeriesValues))

    def toCsv(self, output):
        output.writerow([self.name])
        for quantile in self.quantiles:
            quantile.toCsv(output)
        output.writerow(self.startTimes)
        output.writerow(self.endTimes)
        output.writerow([self.unit, self.factor, self.availability,
                         self.configChanges])

    def columnName(self, name):
        unit = self.customUnit if self.customUnit else self.unit
        if unit:
            return '%s %s (%s)' % (self.name, name, unit)
        else:
            return '%s %s' % (self.name, name)


class ScalarValue(Statistic):
    def __init__(self):
        Statistic.__init__(self)
        self.startTime = None
        self.endTime = None
        self.unit = None
        self.value = None
        self.factor = None

    def fromResponse(self, response):
        Statistic.fromResponse(self, response)
        self.endTime = int(response.endTimes)
        self.startTime = int(response.startTimes)
        self.unit = response.unit
        self.value = int(response.value)
        self.factor = int(response.factor)
        return self

    def __str__(self):
        return "ScalarValue(type=%s, startTime=%s, endTime=%s, unit=%s, " \
               "value=%s, factor=%s)" % (
                   self.type, self.startTime, self.endTime, self.unit, self.value,
                   self.factor)

    def toCsv(self, output):
        output.writerow([self.type])
        output.writerow([self.startTime, self.endTime, self.unit, self.value,
                         self.factor])


class Distribution(Statistic):
    def __init__(self):
        Statistic.__init__(self)
        self.quantiles = None
        self.min = None
        self.mean = None
        self.max = None
        self.unit = None
        self.factor = None
        self.availability = None
        self.values = None
        self.columns = None

    def fromResponse(self, response):
        Statistic.fromResponse(self, response)
        self.unit = response.unit
        self.values = dict()
        self.columns = []

        min = DistributionStatistic().fromResponse(response.min)
        self.min = min
        column_name = self.columnName('min', min)
        self.values[column_name] = min
        self.columns.append(column_name)

        mean = DistributionStatistic().fromResponse(response.mean)
        self.mean = mean
        column_name = self.columnName('mean', mean)
        self.values[column_name] = mean
        self.columns.append(column_name)

        max = DistributionStatistic().fromResponse(response.max)
        self.max = max
        column_name = self.columnName('max', max)
        self.values[column_name] = max
        self.columns.append(column_name)

        self.quantiles=[]
        if hasattr(response, "quantile"):
            if isinstance(response.quantile, list):
                for quantile in response.quantile:
                    q = Quantile().fromResponse(quantile)
                    self.quantiles.append(q)
                    column_name = self.columnName('percentile', q)
                    self.values[column_name] = q
                    self.columns.append(column_name)
            else:
                q = Quantile().fromResponse(response.quantile)
                self.quantiles.append(q)
                column_name = self.columnName('percentile', q)
                self.values[column_name] = q
                self.columns.append(column_name)

        self.factor = int(response.factor)
        self.availability = response.availability
        column_name = self.type + ' availability (%)'
        self.values[column_name] = self.availability
        self.columns.append(column_name)
        return self

    def __str__(self):
        return "Distribution(type=%s, quantiles=%s, min=%s, mean=%s, " \
               "max=%s, unit=%s, factor=%s, availability=%s, values=%s)" % (
                   self.type, list_to_str(self.quantiles), self.min, self.mean,
                   self.max, self.unit, self.factor, self.availability, dict_to_str(self.values))

    def columnName(self, name, dist):
        c = self.type
        if hasattr(dist, 'name'):
            c += ' %s' % (dist.name,)
        c += ' %s' % (name,)
        if dist.valueFilter:
            c += ' %s' % (dist.valueFilter,)
        if self.unit:
            c += ' (%s)' % (self.unit,)
        return c


class DistributionStatistic(object):
    def __init__(self):
        self.value = None
        self.valueFilter = None

    def fromResponse(self, response):
        if is_not_text(response):
            self.value = float(response.value) if response.value != '-' else None
            self.valueFilter = getattr(response, '_valueFilter', None)
        else:
            self.value = float(response) if response != '-' else None
        return self

    def __str__(self):
        return "DistributionStatistic(value=%s, valueFilter=%s)" % (self.value, self.valueFilter)

    def toCsv(self, output):
        if self.valueFilter is None:
            output.writerow([self.value])
        else:
            output.writerow([self.valueFilter, self.value])


class Quantile(DistributionStatistic):
    def __init__(self):
        DistributionStatistic.__init__(self)
        self.name = None

    def fromResponse(self, response):
        DistributionStatistic.fromResponse(self, response)
        self.name = response._quantile
        return self

    def __str__(self):
        return "Quantile(name=%s, value=%s, valueFilter=%s)" % (self.name, self.value, self.valueFilter)

    def toCsv(self, output):
        output.writerow([self.name, self.value])


class TopN(Statistic):
    def __init__(self):
        Statistic.__init__(self)
        self.entries = None
        self.totalBytes = None
        self.totalPackets = None
        self.totalFlows = None
        self.maxError = None
        self.availability = None
        self.periodEndsAt = None

    def fromResponse(self, response):
        Statistic.fromResponse(self, response)
        self.entries = []
        if hasattr(response, 'entry'):
            for entry in response.entry:
                self.entries.append(TopNEntry().fromResponse(entry))
        if hasattr(response, 'totalBytes'):
            self.totalBytes = int(response.totalBytes)
        if hasattr(response, 'totalPackets'):
            self.totalPackets = int(response.totalPackets)
        if hasattr(response, 'totalFlows'):
            self.totalFlows = int(response.totalFlows)
        if hasattr(response, 'maxError'):
            self.maxError = int(response.maxError)
        if hasattr(response, 'availability'):
            self.availability = int(response.availability)
        if hasattr(response, 'periodEndsAt'):
            self.periodEndsAt = int(response.periodEndsAt)
        return self

    def __str__(self):
        return "TopN(type=%s, entries=%s, totalBytes=%s, totalPackets=%s, " \
               "totalFlows=%s, maxError=%s, availability=%s, " \
               "periodEndsAt=%s)" % (
                   self.type, list_to_str(self.entries), self.totalBytes,
                   self.totalPackets, self.totalFlows, self.maxError,
                   self.availability, self.periodEndsAt)

    def toCsv(self, output):
        output.writerow([self.type])
        for entry in self.entries:
            entry.toCsv(output)
        if any([self.totalBytes, self.totalPackets, self.totalFlows,
                self.maxError, self.availability, self.periodEndsAt]):
            output.writerow([self.totalBytes, self.totalPackets,
                             self.totalFlows, self.maxError, self.availability,
                             self.periodEndsAt])

    def topCsvTopN(self, output, mp):
        for entry in self.entries:
            entry.toCsvTopN(output, mp, self.type)

class TopNEntry(object):
    def __init__(self):
        self.key = None
        self.byteCount = None
        self.byteCountPercentage = None
        self.packetCount = None
        self.flowCount = None
        self.bitRate = None
        self.application = None
        self.messageCount = None

    def fromResponse(self, response):
        self.key = response.key
        if hasattr(self, 'byteCount'):
            self.byteCount = int(response.byteCount)
        if hasattr(response, 'byteCountPercentage'):
            self.byteCountPercentage = float(response.byteCountPercentage)
        if hasattr(response, 'packetCount'):
            self.packetCount = int(response.packetCount)
        if hasattr(response, 'flowCount'):
            self.flowCount = int(response.flowCount)
        if hasattr(response, 'bitRate'):
            self.bitRate = int(response.bitRate)
        if hasattr(response, 'application'):
            self.application = response.application
        if hasattr(response, 'messageCount'):
            self.messageCount = int(response.messageCount)
        return self

    def __str__(self):
        return "TopNEntry(key=%s, byteCount=%s, byteCountPercentage=%s, " \
               "packetCount=%s, flowCount=%s, bitRate=%s, application=%s)" % (
                   self.key, self.byteCount, self.byteCountPercentage,
                   self.packetCount, self.flowCount, self.bitRate, self.application)

    def toCsv(self, output):
        row = [self.key, self.byteCount, self.byteCountPercentage,
               self.packetCount, self.flowCount, self.bitRate]
        if self.application:
            row.append(self.application)
        output.writerow(row)

    def toCsvTopN(self, output, mp, topNType):
        row = [mp, topNType, self.key]
        row.append(self.byteCount if self.byteCount != None else '')
        row.append(self.packetCount if self.packetCount != None else '')
        row.append(self.messageCount if self.messageCount != None else '')
        row.append(self.application if self.application != None else '')
        output.writerow(row)

class StatisticSummary(Summary, Statistic):
    def __init__(self):
        Summary.__init__(self)
        Statistic.__init__(self)
        self.configuredCapacity = None

    def fromResponse(self, response):
        Summary.fromResponse(self, response)
        Statistic.fromResponse(self, response)
        return self

    def __str__(self):
        return 'StatisticSummary(type=%s, configuredCapacity=%s, ' \
               'effectiveCapacity=%s, totalBytes=%s, ' \
               'averageUtilisation=%s, networkServiceIndicator=%s, ' \
               'monitoringMechanism=%s, maxMicroburst=%s, ' \
               'linkSizePacketDelay=%s, linkSizeQueueLength=%s, ' \
               'oneSecondPeak=%s, recommendation=%s, measuresMessages=%s, ' \
               'packetMicroburstAvailable=%s, configurableStats=%s' % (
            self.type, self.configuredCapacity, self.effectiveCapacity,
            self.totalBytes, self.averageUtilisation,
            self.networkServiceIndicator, self.monitoringMechanism,
            self.maxMicroburst, self.linkSizePacketDelay,
            self.linkSizeQueueLength, self.oneSecondPeak,
            self.recommendation, self.measuresMessages,
            self.packetMicroburstAvailable,
            list_to_str(self.configurableStats)
        )

    def toCsv(self, output):
        output.writerow([self.type])
        row = []
        if self.configuredCapacity:
            row = [self.configuredCapacity.value, self.configuredCapacity.unit]
        row.extend([self.totalBytes.value, self.totalBytes.unit,
                    self.networkServiceIndicator.value,
                    self.networkServiceIndicator.unit,
                    self.networkServiceIndicator.factor,
                    self.monitoringMechanism])
        if self.maxMicroburst is not None:
            row.extend([self.maxMicroburst.value, self.maxMicroburst.unit])
        if self.oneSecondPeak is not None:
            row.extend([self.oneSecondPeak.value, self.oneSecondPeak.unit])
        row.extend([self.recommendation,
                    bool_to_str(self.measuresMessages),
                    bool_to_str(self.packetMicroburstAvailable)])
        output.writerow(row)
        for configurableStat in self.configurableStats:
            configurableStat.toCsv(output)


class CnesResponse(object):
    def __init__(self):
        self.cnes = None

    def fromResponse(self, response):
        self.cnes = []
        for cne in response:
            self.cnes.append(Cne().fromResponse(cne))
        return self

    def __str__(self):
        return "CnesResponse(cnes=%s)" % (list_to_str(self.cnes))

    def toCsv(self, output):
        output.writerow(['#cne','ip address'])
        for cne in self.cnes:
            cne.toCsv(output)


class Cne(object):
    def __init__(self):
        self.name = None
        self.ip = None

    def fromResponse(self, response):
        self.name = response._name
        self.ip = response._ip
        return self

    def __str__(self):
        return "Cne(name=%s, ip=%s)" % (self.name, self.ip)

    def toCsv(self, output):
        output.writerow([self.name, self.ip])


class AnalyticsResponse(object):
    def __init__(self, numPoints):
        self.fastPass = False
        self.timeRange = None
        self.measurementPoints = None
        self.points = int(numPoints)

    def fromResponse(self, response):
        self.fastPass = response._fastPass
        self.timeRange = TimeRange().fromResponse(response.timeRange)
        self.measurementPoints = []
        for mp in response.measurementPoints:
            self.measurementPoints.append(
                MeasurementPointLive().fromResponse(mp[1]))
        return self

    def __str__(self):
        return "AnalyticsResponse(fastPass=%s, timeRange=%s, " \
               "measurementPoints=%s)" % (
                   self.fastPass, self.timeRange, list_to_str(self.measurementPoints))

    def toCsvSummary(self, output):
        output.writerow(['#summary results for analytics data'])
        header = ['#measurement point']
        columns = self.measurementPoints[0].getAnalyticsSummaryHeader()
        header.extend(columns)
        confStats = dict()
        for measurementPoint in self.measurementPoints:
            cnf = measurementPoint.getConfigurableStatsSummaryHeader()
            for c in iter(cnf):
                if c not in confStats:
                    confStats[c] = cnf[c]

        for c in iter(confStats):
            header.extend(confStats[c])
        if len(header) > 1:
            output.writerow(header)
            for measurementPoint in self.measurementPoints:
                measurementPoint.toCsvSummary(output, confStats)

    def toCsvDataSets(self, output, points):
        output.writerow([])
        output.writerow(['#analytics data'])
        header = ['#measurement point']
        columns = self.measurementPoints[0].getHeader()
        confStats = dict()
        for mp in self.measurementPoints:
            cds = mp.getConfigrableStatsDataSets()
            for c in iter(cds):
                if c not in confStats:
                    confStats[c] = cds[c]

        header.extend(columns)
        for c in iter(confStats):
            ds = confStats[c]
            unit = ds.unit
            if unit == None:
                unit = ds.customUnit
            if len(ds.sets) == 1:
                col = c
                if unit != None:
                    col += " (%s)" % unit
                header.append(col)
            else:
                for s in ds.sets:
                    h = s.getHeader(c, unit)
                    header.append(h)

        if len(header) > 1:
            output.writerow(header)
            for point in range(0, points):
                for mp in self.measurementPoints:
                    mp.toCsvDataSets(output, point, confStats)

    def toCsvTopN(self, output):
        hasTopN = False
        for mp in self.measurementPoints:
            if len(mp.topNs) > 0:
                hasTopN = True
                break
        if not hasTopN:
            return
        output.writerow([])
        output.writerow(['#topn data'])
        output.writerow(['#measurement point','type','key','byte count','packet count','message count','application'])
        for mp in self.measurementPoints:
            mp.toCsvTopN(output)

    def toCsv(self, output):
        self.toCsvSummary(output)
        self.toCsvDataSets(output, self.points)
        self.toCsvTopN(output)

class ClockEventsResponse(object):

    def __init__(self, numPoints, thresholds):
        self.timeRange = None
        self.points = int(numPoints)
        self.response = None
        self.thresholds = thresholds

    def fromResponse(self, response):
        self.response = response.measurementPoints.measurementPoint
        self.timeRange = TimeRange().fromResponse(response.timeRange)
        return self

    def getClockAvailability(self, clock):
        availability = list(map(int, clock['availability'].split(' ')))
        result = sum(availability)
        if (result > 0):
            result /= float(self.points)
        return result

    def getClockSamples(self, clock, field_name):
        return [int(x) for x in clock[field_name].split(' ') if x and (x != '-')]

    def getClockMaxAdjustment(self, clock):
        max_samples = self.getClockSamples(clock, 'max-sampleNs')
        min_samples = self.getClockSamples(clock, 'min-sampleNs')
        return max(abs(max(max_samples) or 0), abs(min(min_samples) or 0))

    def getSampleCounters(self, clock):
        field_name = "sample-count" if (clock['_sample-type'] == "adjustment") else "sample-time"
        result = { 'total': 0 }
        for threshold in self.thresholds:
            result[threshold] = 0;

        for sample_count in clock[field_name]:
            if ('_thresholdNs' in sample_count):
                threshold = sample_count._thresholdNs
                if (threshold in self.thresholds):
                    result[threshold] = int(sample_count.value)
            else:
                result['total'] = int(sample_count)

        return result

    def toCsv(self, output):
        header = ['# clock name', 'clock type', 'availability', 'max deviation','sample count/time']
        for threshold in self.thresholds:
            header.append("samples >" + str(threshold) + "ns")
        output.writerow(header)

        if ('clock-summary' in self.response):
            for clock in self.response["clock-summary"]:
                availability = self.getClockAvailability(clock)
                max_adjustment = self.getClockMaxAdjustment(clock)
                row_data = [clock._source, clock._type, availability, max_adjustment]

                sample_counters = self.getSampleCounters(clock)
                row_data.append(sample_counters['total'])
                for threshold in self.thresholds:
                    row_data.append(sample_counters[threshold])

                output.writerow(row_data)

class TimeRange(object):
    def __init__(self):
        self.fromNs = None
        self.toNs = None

    def fromResponse(self, response):
        self.fromNs = response._fromNs
        self.toNs = response._toNs
        return self

    def __str__(self):
        return 'TimeRange(fromNs=%s, toNs=%s)' % (self.fromNs, self.toNs)

    def toCsv(self, output):
        output.writerow([self.fromNs, self.toNs])


class TimeSeriesEventData(TimeSeriesBase, UnitMixin):
    def __init__(self):
        TimeSeriesBase.__init__(self)
        UnitMixin.__init__(self)
        self.name = None
        self.values = None
        self.min = None
        self.mean = None
        self.max = None
        self.total = None
        self.lastViolationTime = None
        self.lastViolationValue = None
        self.summaryColumns = None
        self.summaryValues = None
        self.timeSeriesColumns = None
        self.timeSeriesValues = None


    def fromResponse(self, response):
        TimeSeriesBase.fromResponse(self, response)
        UnitMixin.fromResponse(self, response)
        self.name = response._name
        self.min = int(response.min) if response.min != "-" else None
        self.mean = int(response.mean) if response.mean != "-" else None
        self.max = int(response.max) if response.max != "-" else None
        self.total = int(response.total) if response.total != "-" else None
        self.lastViolationTime = int(response.lastViolationTime) if response.lastViolationTime != '-' else None
        self.lastViolationValue = int(response.lastViolationValue) if response.lastViolationValue != '-' else None
        self.setTimeseriesValuesFromResponse(response)

        self.summaryColumns = []
        self.summaryValues = dict()

        def addSummary(column_name, value):
            self.summaryColumns.append(column_name)
            self.summaryValues[column_name] = value

        addSummary('%s time-in-events (%s)' % (self.name, self.unit), self.total)
        addSummary('%s time-in-events (%%)' % (self.name,), self.total)
        addSummary('%s availability (%%)' % (self.name,), self.availability)
        addSummary('%s config changes' % (self.name,), self.configChanges)
        addSummary('%s last violation time (ms)' % (self.name,), self.lastViolationTime)
        addSummary('%s last violation value' % (self.name,), self.lastViolationValue)

        column_name = '%s value (%s)' % (self.name, self.unit)
        column_name = column_name + self.getRoundingErrorPostfix()
        self.timeSeriesColumns = [column_name]
        self.createTimeseriesColumns(column_name)

        return self

    def __str__(self):
        return 'TimeSeriesEventData(name=%s, unit=%s, factor=%s, ' \
               'availability=%s, configChanges=%s, min=%s, mean=%s, max=%s, ' \
               'total=%s, lastViolationTime=%s, lastViolationValue=%s, '  \
               'values=%s, startTimes=%s, endTimes=%s)' % (
            self.name, self.unit, self.factor, self.availability,
            self.configChanges, self.min, self.mean, self.max, self.total,
            self.lastViolationTime, self.lastViolationValue, self.values,
            self.startTimes, self.endTimes)


class CorvilApiStatsClient(object):
    SOCKET_TIMEOUT_SECONDS = 3600

    """
    Simple class to wrap the SUDS service
    """
    def __init__(self, host, port=5101, username='admin', password='', cne=None, useHttps=False, timeout=SOCKET_TIMEOUT_SECONDS):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.url = "http://%s:%s/ws/stats-v2?WSDL" % (host, port)
        if useHttps:
            self.url = "https://%s/api/ws/stats-v2?WSDL" % (host)
        # At least a 'version="1"' attribute is needed on the root element of
        # all requests.
        self.requestAttributes = SudsParameterPlugin()
        self.requestAttributes.setAttrs({'version': '2'})

        self.rootAttributePlugin = SudsRootAttributePlugin()

        if cne is not None:
            self.requestAttributes.addAttr("cne", cne)

#        print "CLIENT URL:%s %s/%s" % (self.url, username, password)

        self.sudsClient = suds.client.Client(
            self.url, username=self.username, cache=None,
            password=self.password,
            plugins=[self.requestAttributes, self.rootAttributePlugin],
            timeout = timeout)

        # Check if this is an CMC or a CNE. The CMC has a 'getCnes' method.
        self.hostIsLmc = True
        try:
            self.hostIsLmc = (hasattr(self.sudsClient.service, "getCnes") and
                              callable(self.sudsClient.service.getCnes))
        except suds.MethodNotFound:
            self.hostIsLmc = False

    def createElement(self, name, nameAttr=None):
        """
        Create a named element to assemble a request
        """
        elem = self.sudsClient.factory.create(name)
        if nameAttr is not None:
            elem._name = nameAttr
        return elem

    def createReportingPeriodElement(self, reportingPeriodName):
        """
        Create a request element for a given reporting period
        """
        period = self.createElement("ns0:ReportingPeriod")[reportingPeriodName]
        return period

    def create_lens_data_time_element(self, reporting_period, start_time, end_time, business_hours):
        """
           Transforms a time object to time element for lens API.

           Args:
           time(object): time object

           Returns:
               object: Time element to be used in API

           Raises:
                ValueError: Value Error if time element doesn't contain the necessary fields
        """
        # pylint: disable=protected-access
        time_element = self.createElement('ns0:ContextTime')
        if reporting_period:
            named_period_obj = self.createElement('ns0:NamedPeriod')
            named_period_obj._name = reporting_period
            time_element["namedPeriod"] = named_period_obj
        else:
            custom_period_obj = self.createElement('ns0:CustomPeriod')
            if start_time and end_time:
                custom_period_obj._from = start_time
                custom_period_obj._to = end_time
                time_element['customPeriod'] = custom_period_obj
            else:
                raise ValueError("start_time and end_time is mandatory for custom period ")

        if business_hours:
            business_period_obj = self.createElement('ns0:BusinessHours')
            business_period_obj._namedPeriod = business_hours
            time_element['businessHours'] = business_period_obj
        return time_element

    def create_grouping_element(self, grouping):
        """
       Transforms a grouping object to grouping element for lens API.

       Args:
       grouping(object): grouping object

       Returns:
           object: Grouping element to be used in API
       """
        # pylint: disable=protected-access
        grouping_obj = None
        if grouping:
            grouping_obj = self.createElement('ns0:ContextGrouping')
            for name in grouping.split(","):
                if "sessions" != name.lower():
                    group_by_tag_obj = self.createElement('ns0:ContextGrouping.groupBy')
                    group_by_tag_obj._tagType = name
                    grouping_obj.groupBy.append(group_by_tag_obj)
                else:
                    group_by_session_obj = self.createElement('ns0:ContextGrouping.groupBy')
                    group_by_session_obj._sessions = True
                    grouping_obj.groupBy.append(group_by_session_obj)
        return grouping_obj

    def __check_if_stat_present(self, stats, stat_obj):
        for stat in stats:
            if stat_obj._name == stat._name and stat_obj._type == stat._type and stat_obj._direction == stat._direction:
                return stat

        return None

    def create_stats_element(self, stats):
        """
       Transforms a stat object to stat element for lens API.

       Args:
       stat(object): stat object
       Stat:direction:aspect:percentile

       Returns:
           object: stat element to be used in API

       """
        # pylint: disable=protected-access
        stats_obj = None

        if stats:
            stats_obj = self.createElement('ns0:StatisticsWithAspect')
            for stat_element in stats:
                existing_stat = None
                stat_obj = self.createElement('ns0:StatisticWithAspect')
                stat = re.split(split_pattern, stat_element)
                count_of_stat_element = len(stat)
                direction_and_sort = re.split(colon_split_pattern, stat[1])
                if len(direction_and_sort) > 1:
                    stat_obj._direction = direction_and_sort[0].replace("\\", "")
                    stat_obj._sort = direction_and_sort[1].replace("\\", "")
                else:
                    stat_obj._direction = stat[1].replace("\\", "")

                stat_name = ""
                stat_type = stat[0].replace("\\", "")

                if stat_type.startswith("conf"):
                    stat_name = stat[0].split(":", 1)[1].replace("\\", "")
                    stat_type = ""

                stat_obj._name = stat_name
                stat_obj._type = stat_type

                if count_of_stat_element >= 3:
                    stat_obj_aspect = self.createElement('ns0:StatisticAspect')
                    aspect_sort = []
                    if ":" in stat[-1]:
                        aspect_sort = re.split(colon_split_pattern, stat[-1])
                        stat_obj_aspect._sort = aspect_sort[-1]

                    if count_of_stat_element == 3:
                        if aspect_sort:
                            stat_obj_aspect._type = aspect_sort[0]
                        else:
                            stat_obj_aspect._type = stat[-1]

                    if count_of_stat_element == 4:
                        stat_obj_aspect._type = stat[2]
                        if aspect_sort:
                             stat_obj_aspect._value = aspect_sort[0]
                        else:
                            stat_obj_aspect._value = stat[3]
                    if stats_obj.stat:
                        existing_stat = self.__check_if_stat_present(stats_obj.stat, stat_obj)
                    if existing_stat:
                        existing_stat.aspect.append(stat_obj_aspect)
                    else:
                        stat_obj.aspect.append(stat_obj_aspect)
                if not existing_stat:
                    stats_obj.stat.append(stat_obj)
        return stats_obj

    def create_filter_element(self, filters):
        """
        Transforms a filter object to filter element for lens API.

        Args:
        filter(object): Filter object

        Returns:
            object: Filter element to be used in A0PI
        FilterType:value:operator:subject
        """
        # pylint: disable=protected-access
        filters_obj = None
        if filters:
            filters_obj = self.createElement('ns0:ContextFilters')
            multi_filter = re.split(space_split_pattern, filters)
            for filter in multi_filter:
                flt = re.split(colon_split_pattern, filter)
                for index in range(0, len(flt)):
                    flt[index] = flt[index].replace("\\", "")
                filter_obj = self.createElement('ns0:ContextFilter')
                filter_type = flt[0]
                if "session" == filter_type.lower():
                    filter_obj._session = True
                    if len(flt) == 4:
                        filter_obj._cneName = flt[3]
                else:
                    filter_obj._session = False
                    filter_obj._subject = filter_type
                if "," in flt[2]:
                    flt_values = re.split(split_pattern, flt[2])
                    for value in flt_values:
                        filter_value_bj = self.createElement('ns0:FilterValue')
                        filter_value_bj.value = value
                        filter_obj.filterValue.append(filter_value_bj)
                else:
                    filter_obj._value = flt[2]
                filter_obj._operator = flt[1]
                filters_obj.filter.append(filter_obj)
        return filters_obj

    def createMeasurementPointElement(self, measurementPoints):
        """
        Create a request element for a given list of measurement points
        """
        requestedMps = self.createElement("ns0:MeasurementPointsRequestCNE")
        for mpSpec in measurementPoints:
            cne, mpName = mpSpec.split(':', 1)
            mpReq = self.createElement(
                'ns0:MeasurementPointRequestCNE', mpName)
            mpReq._cne = cne
            requestedMps.measurementPoint.append(mpReq) # pylint: disable=maybe-no-member
        return requestedMps

    def createStatWithPercentilesList(self, statNames, percentiles=None):
        """
        Assemble the list of stats elements required for a historical request, with the requested
        percentiles added if necessary
        """
        stats = []
        for statName in statNames:
            stat = self.createElement("ns0:StatsWithPercentiles")
            stat.value = statName
            if percentiles:
                stat._requestedPercentiles = percentiles
            stats.append(stat)
        return stats

    def createLiveStatsGroup(self, statNames, confStatNames, percentiles, measurementPoints):
        """
        Assembles the 'statsGroup' element for the live request, which contains a list of stats with
        requested percentiles, and a list of measurementPoints
        """
        statsGroup = self.createElement(
            "ns0:StatsGroupRequest", "statsgroupname")

        if statNames is not None:
            for statName in statNames:
                stat = self.createElement("ns0:Stat", statName)
                if percentiles:
                    stat._requestedPercentiles = percentiles
                statsGroup.definition.stat.append(stat) # pylint: disable=maybe-no-member

        if confStatNames is not None:
            for confStatName in confStatNames:
                stat = self.createElement("ns0:ConfigurableStat", confStatName)
                statsGroup.definition.configurableStat.append(stat) # pylint: disable=maybe-no-member

        for mpName in measurementPoints:
            measPoint = self.createElement(
                "ns0:MeasurementPointRequest", mpName)
            statsGroup.measurementPoints.measurementPoint.append(measPoint) # pylint: disable=maybe-no-member

        return statsGroup

    def getStats(self, mps, cne, stats, configurableStats, percentiles,
                 reporting_period, startTime, endTime, events):
        """
        Convenience wrapper for the Corvil XML API getStats method
        """
        if startTime:
            startTime /= 1e6
            startTime = int(startTime)
        if endTime:
            endTime /= 1e6
            endTime = int(endTime)
        kwargs = {}

        if self.hostIsLmc and cne is None:
            # If the host IS an CMC and we haven't specified the CNE in the request, we have to use
            # the measurement points element.
            kwargs['measurementPoints'] = \
                self.createMeasurementPointElement(mps)
        else:
            # If we have a CNE or an CMC with the CNE in the request, we want to use the names list,
            # but ensure they're not of the form CNE:FQN
            kwargs['name'] = mps

        if startTime and endTime:
            kwargs['timeRange'] = {'from': startTime, 'to': endTime}
        else:
            kwargs['reportingPeriod'] = \
                self.createReportingPeriodElement(reporting_period)

        kwargs['stats'] = \
            self.createStatWithPercentilesList(stats, percentiles)

        kwargs['configurableStat'] = configurableStats
        kwargs['statEventData'] = events
        response = self.sudsClient.service.getStats(**kwargs)
        return StatsResponse().fromResponse(response, percentiles)

    def getSummary(self, reporting_period, filter):
        """
        Convenience wrapper for the Corvil XML API getSummary method
        """
        if filter:
            response = self.sudsClient.service.getSummary(filter=filter,
                                                          reportingPeriod=reporting_period)
        else:
            response = self.sudsClient.service.getSummary(
                reportingPeriod=reporting_period)
        return SummaryResponse().fromResponse(response)

    def createLiveStatsSession(self, *args, **kwargs):
        """
        Convenience wrapper for the Corvil XML API createLiveStatsSession method
        """
        return self.sudsClient.service.createLiveStatsSession(*args, **kwargs)

    def closeLiveStatsSession(self, *args, **kwargs):
        """
        Convenience wrapper for the Corvil XML API createLiveStatsSession method
        """
        return self.sudsClient.service.closeLiveStatsSession(*args, **kwargs)


    def getLiveStats(self, *args, **kwargs):
        """
        Convenience wrapper for the Corvil XML API getLiveStats method
        """
        return self.sudsClient.service.getLiveStats(*args, **kwargs)

    def getCnes(self, *args, **kwargs):
        """
        Convenience wrapper for the Corvil XML API getCnes method
        """
        response = self.sudsClient.service.getCnes(*args, **kwargs)
        return CnesResponse().fromResponse(response)

    def getMessageProtocols(self, *args, **kwargs):
        """
        Convenience wrapper for the Corvil XML API getMessageProtocols method
        """
        response = self.sudsClient.service.getMessageProtocols(*args, **kwargs)
        messageProtocolResponse = MessageProtocolsResponse()
        messageProtocolResponse.fromResponse(response)
        return messageProtocolResponse

    def getMessageProtocolsDetails(self, messageProtocols):
        """
        Convenience wrapper for the Corvil XML API getMessageProtocolsDetails
        method.
        """
        response = self.sudsClient.service.getMessageProtocolsDetails(
            messageProtocols)
        messageProtocolsDetailsResponse = MessageProtocolsDetailsResponse()
        messageProtocolsDetailsResponse.fromResponse(response)
        return messageProtocolsDetailsResponse

    def getApplications(self, *args, **kwargs):
        """
        Convenience wrapper for the Corvil XML API getApplications method
        """
        response = self.sudsClient.service.getApplications(*args, **kwargs)
        applicationsResponse = ApplicationsResponse()
        applicationsResponse.fromResponse(response)
        return applicationsResponse

    def getAnalytics(self, filter, start_time, end_time, statistics,
                     configurable_statistics, percentiles, points):
        measurementPoints = {'measurementPoint': [{'_name': filter}]}
        timeRange = {'_fromNs': start_time,
                     '_toNs': end_time}

        definition = {
            '_points': int(points),
            'stat': [
                {'_name': statistic,
                 '_requestedPercentiles': percentiles}
                    for statistic in statistics],
            'configurableStat': [
                {'_name':conf_stat,
                 '_requestedPercentiles' : percentiles}
                    for conf_stat in configurable_statistics]
        }
        response = self.sudsClient.service.getAnalytics(
            measurementPoints=measurementPoints, timeRange=timeRange,
            definition=definition)
        analyticsResponse = AnalyticsResponse(points)
        analyticsResponse.fromResponse(response)
        return analyticsResponse

    def getClockEvents(self, local_cne, start_time, end_time, points, thresholds):
        measurement_point  = { 'measurementPoint': [{'_name': "channel//%s///ClockTracking" % (local_cne)}] }
        time_range = {
            '_fromNs': start_time,
            '_toNs': end_time
        }

        thresholds_str = ",".join([str(threshold) for threshold in thresholds])
        definition = {
            '_points': int(points),
            'stat': [
                {
                    '_name': "clock-events",
                    '_thresholdsNs': thresholds_str
                }
            ],
        }
        response = self.sudsClient.service.getAnalytics(
            measurementPoints=measurement_point, timeRange=time_range,
            definition=definition)
        clockEventsResponse = ClockEventsResponse(points, thresholds)
        clockEventsResponse.fromResponse(response)
        return clockEventsResponse

    def getLensData(self, reporting_period, start_time, end_time, business_hours, grouping, stats, filter):

        # Suds lens data format : getLensData(ns0:ContextTime time, ns0:ContextFilters filters,
        # ns0:ContextGrouping grouping, ns0:StatisticsWithAspect stats)

        if "getLensData" in self.sudsClient.wsdl.services[0].port("StatsPort").methods:
            time_element = self.create_lens_data_time_element(reporting_period, start_time, end_time,
                                                              business_hours)
            grouping_element = self.create_grouping_element(grouping)
            stats_element = self.create_stats_element(stats)
            filter_element = self.create_filter_element(filter)
            response = self.sudsClient.service.getLensData(
                time=time_element, filters=filter_element, grouping=grouping_element, stats=stats_element)
            lens_data_response = LensDataResponse(time_range=reporting_period)
            lens_data_response.init_from_response(response)

            return lens_data_response
        else:
            raise MethodNotAvailableException("getLensData not available on Stats XML API")


def usage(error=""):
    """
    Print out error message, followed by program usage, and exit
    """
    sys.stdout.write("\n" + error)
    sys.stdout.write(__doc__)  # doc string from top of file.
    sys.exit(2)

def version():
    print(VERSION)
    sys.exit(0)


def liveUpdate(client, timestamp, session, statsGroup):
    """
    Repeatedly request live stats
    """
    try:
        # Set the timestamp on the statsGroup. In every iteration we'll use the timestamp returned
        # from the previous call, this ensures we'll retrieve all the data
        #statsGroup._timestamp = timestamp
        #statsGroup._name = "statsgroupname"
        liveResponse = client.getLiveStats(session, statsGroup)
        # print
        # print "Received live response:"
        # print str(liveResponse)
    except suds.WebFault as webFault:
        print("Error retrieving live stats: %s" % webFault.fault.faultstring)
        sys.exit(1)

    # Get the timestamp from the response and return it so that liveUpdate can
    # be called again.
    newTimestamp = liveResponse.statsGroup[0]._timestamp
    return (liveResponse, newTimestamp)


def validate_time(start_time, end_time):
    if start_time <= 0 or end_time <= 0:
        usage("Invalid custom time format, should be epoch in milliseconds")
    if int(math.log10(start_time)) != 12 or int(math.log10(end_time)) != 12:
        usage("Invalid custom time format, should be epoch in milliseconds")
    if start_time == end_time:
        usage("Invalid custom time format, start time should be greater than end time")
    start_time_struct = time.gmtime(int(start_time/1000))
    end_time_struct = time.gmtime(int(end_time/1000))
    if start_time_struct.tm_sec % 5 != 0 or start_time_struct.tm_min % 5 != 0:
        usage("Invalid custom start time format, should be on 5 minute boundary")
    if end_time_struct.tm_sec % 5 != 0 or end_time_struct.tm_min % 5 != 0:
        usage("Invalid custom end time format, should be on 5 minute boundary")

def parseArgs(args):
    """
    Parse the command line, perform some initial sanity checking
    """
    parser = OptionParser()
    parser.add_option("-n", "--user", default="admin")
    parser.add_option("-p", "--password", default="admin")
    parser.add_option("-x", "--cne")
    parser.add_option("-r", "--reporting-period", default="1-hour")
    parser.add_option("-s", "--start-time")
    parser.add_option("-e", "--end-time")
    parser.add_option("-f", "--filter")
    parser.add_option("-m", "--measurement-point")
    parser.add_option("-q", "--quantile")
    parser.add_option("-u", "--update-period", default="1")
    parser.add_option("-i", "--iterations")
    parser.add_option("-o", "--points", default="100")
    parser.add_option("-z", "--https", action="store_true", default=False)
    parser.add_option("-l", "--local-cne", type="string", default="local-cne")
    parser.add_option("-t", "--thresholds", type="string", default="1000,5000,25000")
    parser.add_option("-T", "--timeout", type="int", default=CorvilApiStatsClient.SOCKET_TIMEOUT_SECONDS)
    parser.add_option("-R", "--resolutionMinutes", type="int")
    parser.add_option("-b", "--business-hours", type="string", default=None)
    parser.add_option("-g", "--grouping", type="string", default=None)

    (options, args) = parser.parse_args()

    if len(args) == 1 and args[0] == 'version':
        version()
    elif len(args) < 2:
        usage("Invalid arguments: %s" % (args,))
    command, host = args[0], args[1]

    if options.timeout <= 0:
        usage('Timeout must be a positive number')

    if command == 'message-protocols-details':
        if len(args) < 3:
            usage('Missing <protocol-name>')
        options.protocol_name = args[2:]

    if command in ['stats', 'live-stats']:
        if len(args) < 4:
            usage()
        if options.measurement_point:
            options.measurement_point = [args[2]] + options.measurement_point.split(',')
        else:
            options.measurement_point = [args[2]]

        if options.resolutionMinutes and options.resolutionMinutes % 5 != 0:
            usage("The value of 'resolutionMinutes' attribute must be a multiple of 5")

        options.stat = []
        options.conf_stat = []
        options.stat_event = []
        for arg in args[3:]:
            if arg.startswith('conf:'):
                options.conf_stat.append(arg[5:])
            elif arg.startswith('event:'):
                options.stat_event.append(arg[6:])
            else:
                options.stat.append(arg)


    if command == 'analytics':
        if len(args) < 6:
            usage()
        options.filter = args[2]
        options.start_time = parse_time(args[3])
        options.end_time = parse_time(args[4])
        options.stat = []
        options.conf_stat = []
        options.reporting_period = None
        for arg in args[5:]:
            if arg.startswith('conf:'):
                options.conf_stat.append(arg[5:])
            else:
                options.stat.append(arg)

    if command == 'clock-tracking':
        if len(args) < 4:
            usage()
        options.start_time = parse_time(args[2])
        options.end_time = parse_time(args[3])
        options.stat = ['clock-events']
        options.conf_stat = []
        options.reporting_period = None
        options.points = 20

    if command == 'lens-data':
        options.cne = None
        if options.start_time and options.end_time:
            try:
                start_time = int(options.start_time)
                end_time = int(options.end_time)
                validate_time(start_time, end_time)
            except ValueError: # time in string format
                options.start_time = parse_time(options.start_time, format="ms")
                options.end_time = parse_time(options.end_time, format="ms")

            options.reporting_period = None
        elif options.reporting_period in (None, "1-hour"):
            options.reporting_period = "Last 1 hour"
        options.stat = []
        for arg in args[2:]:
            if "," not in arg:
                usage('**** stat format for lensData is "stat,direction,aspect,percentile:sortOrder"')
            options.stat.append(arg)

    if options.quantile:
        options.quantile = options.quantile.split(',')

    if options.start_time and command not in ('analytics', 'summary', 'clock-tracking', 'lens-data'):
        options.start_time = parse_time(options.start_time)
        options.end_time = parse_time(options.end_time)
        options.reporting_period = None

    port = 5101
    parts = host.split(':', 2)
    if len(parts) == 2:
        host = parts[0]
        port = parts[1]

    return options, command, host, port


def validateMeasurementPoints(measurementPoints, needCne):
    """
    Ensure the measurement points are specified correctly for the selected operation mode and host
    """
    if not measurementPoints:
        usage("At least one measurement point name must be specified")
    for measurementPoint in measurementPoints:
        splot = measurementPoint.split(':', 1)
        if not needCne and len(splot) == 2:
            # if the host is a CNE or if the host is an CMC and a CNE option has been specified,
            # disallow CNEs to be specified per-measurement point
            usage("Measurement point %s is in the form CNE:FQN. This is not permitted on a CNE or "
                  "an CMC in which the CNE has been specified separately in the options"
                  % measurementPoint)
        if needCne and len(splot) != 2:
            # If the host is an CMC and there is no CNE attribute on the request, ensure each
            # measurement point is of the form CNE:MP_FQN so that a measurementPoint element can be
            # assembled for SUDS
            usage("Measurement point %s must be of the form CNE:FQN. This is required when the "
                  "host is an CMC and no CNE has been specified separately in the options."
                  % measurementPoint)


def validateOptions(options, command, hostIsLmc):
    """
    Validate command line options with knowledge of the type of host requests will be sent to (CMC
    or CNE)
    """
    if command == 'stats':
        if not options.stat and not options.conf_stat \
                and not options.stat_event:
            usage("At least one statistic must be specified")

    if command == 'live-stats':
        if not options.stat and not options.conf_stat:
            usage("At least one statistic must be specified")

    if command in ('stats', 'live-stats', 'analytics', 'clock-tracking'):
        if command in ('stats', 'live-stats'):
            validateMeasurementPoints(
                options.measurement_point, hostIsLmc and options.cne is None)

        options.requestedPercentiles = ",".join(
            options.quantile) if options.quantile else None

    if not hostIsLmc and options.cne is not None:
        usage("Cannot specify a cne option unless host is an CMC")

    if command in ('stats'):
        if options.reporting_period is None and not (options.start_time and options.end_time):
            usage("A reporting period or time range must be specified for the %s command" %
                  command)

    if command in ('summary'):
        if options.reporting_period is None:
            usage("A reporting period must be specified for the %s command" %
                  command)

    if command == "cnes" and not hostIsLmc:
        usage("cnes command can only be run on an CMC")

    if command in ('analytics'):
        if not options.filter:
            usage("%s requires filter (-f <measurement-point>)" % (command,))
        if not (options.start_time and options.end_time):
            usage("%s requires time range (-s <start-time> -e <end-time>)" % (
                command,))
        if not options.stat and not options.conf_stat:
            usage("At least one statistic must be specified")

    if command == 'clock-tracking':
        if not options.local_cne:
            usage("Local CNE name cannot be empty")
        try:
            options.thresholds = [ int(i) for i in options.thresholds.split(",")]
        except ValueError:
            usage("Thresholds have to be provided as a comma-separated value list")

    if command == 'lens-data':
        if options.grouping:
            groupings = options.grouping.split(",")
            if "session" in [x.lower() for x in groupings]:
                usage("***** GroupBy name should be Sessions ****")
        order_by = False
        for stat in options.stat:
            stats_elements = stat.split(",")
            stat_order = re.split(colon_split_pattern, stats_elements[-1])
            if len(stat_order) == 2:
                if order_by:
                    usage("***** Sorting by more than one statistic is not allowed ****")
                order_by = True

        if options.filter:
            multi_filter = re.split(space_split_pattern, options.filter.strip())
            for flt in multi_filter:
                filter = re.split(colon_split_pattern, flt.strip())
                if len(filter) == 1 or len(filter) < 3:
                    usage("***** --filter option format should be  Session/Tag Type:operator:value:CneName****")
                if filter[1] is None:
                    usage("***** for --filter option operator cannot be empty, refer usage below")
                if filter[2] is None:
                    usage("***** for --filter option value cannot be empty, refer usage below")
                if filter[0].lower() != "session" and (len(filter) == 4 ):
                    usage("***** for --filter option CNE Name is accepted only with session filtering")

def showResponse(name, response):
    """
    Show API response consistently across commands
    """
    print()
    print("Received %s response" % name)
    print(response)


def outputHeader(command, options, host, port):
    print('#client version: %s' % (VERSION,))
    print('#%s request generated at %s' % (command, time_to_str(time.time()*1000)))
    if options.cne:
        print('#CMC: %s:%s' % (host, port))
        print('#CNE: %s' % (options.cne,))
    elif command == 'cnes':
        print('#CMC: %s:%s' % (host, port))
    else:
        print('#CNE: %s:%s' % (host, port))
    if options.reporting_period and command in ["stats", "summary", "lens-data"]:
        print('#Reporting period: %s' % (options.reporting_period,))
    elif (options.start_time or options.end_time) and command in ["lens-data"]:
        print('#Time period: %s to %s' % (time_to_str(options.start_time ), time_to_str(options.end_time)))
    elif options.start_time or options.end_time:
        print('#Time period: %s to %s' % (time_to_str(options.start_time // 1000000), time_to_str(options.end_time // 1000000)))
    print('')


def outputCsv(response):
#    output = NonEmptyRowCsvWriter(csv.writer(sys.stdout))
    output = csv.writer(sys.stdout)
    response.toCsv(output)

def writeCsv(response):
    writer = csv.writer(sys.stdout)
    for row in response.to_csv():
        writer.writerow(row)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    options, command, host, port = parseArgs(argv[1:])
    client = CorvilApiStatsClient(host,
        username=options.user, password=options.password,
        cne=options.cne, port=int(port), useHttps=options.https, timeout=options.timeout)

    validateOptions(options, command, client.hostIsLmc)
    if command == 'stats':
        if options.resolutionMinutes:
            client.requestAttributes.addAttr('resolutionMinutes', str(options.resolutionMinutes))
        try:
            statsResponse = client.getStats(
                options.measurement_point, options.cne, options.stat,
                options.conf_stat, options.requestedPercentiles,
                options.reporting_period, options.start_time, options.end_time, options.stat_event)
            outputHeader(command, options, host, port)
            outputCsv(statsResponse)

        except suds.WebFault as webFault:
            print("Error attempting to fetch stats: %s" % webFault.fault.faultstring)
            sys.exit(1)

    elif command == "live-stats":
        
        liveHistorySize = 8
        client.requestAttributes.addAttr("historySize", liveHistorySize)
        client.requestAttributes.addAttr("updatePeriod", options.update_period)

        statsGroup = client.createLiveStatsGroup(
            options.stat, options.conf_stat,
            options.requestedPercentiles,
            options.measurement_point)
        createSessionResponse = None
        try:
            # For live stats requests we have to create live session first, then retrieve the
            # returned session number, and use that session number in our subsequent live stats
            # requests.
            createSessionResponse = client.createLiveStatsSession(statsGroup)

            # The response that SUDS returns is just the contents of the first child element in
            # the response. In this case it's simply the session number.
            # print "Created live stats session #%s" % createSessionResponse

            # Now call the initial getLiveStats, with a null timestamp'''
            newTimestamp = None
            previousTimestamp = None
            iterationCounter = 0
            maxIterations = -1
            if options.iterations:
                maxIterations = int(options.iterations)
            output = NonEmptyRowCsvWriter(csv.writer(sys.stdout))
            headerWritten = False
            confstats = dict() 
            
            outputHeader(command, options, host, port)
            
            updatePeriod = int(options.update_period)
            while maxIterations >= 0 and iterationCounter < maxIterations or maxIterations < 0:
                previousTimestamp = newTimestamp
                liveResponse, newTimestamp = liveUpdate(client, newTimestamp, createSessionResponse, statsGroup)
                
                if previousTimestamp == None or previousTimestamp == newTimestamp:
                    """ Do nothing. This is either the first iteration of the loop OR
                        the timestamps are the same, so nothing to do. """
                    pass
                else:
                    """ work out how many rows we need, somewhere between 1 and liveHistorySize"""
                    elapsed = int(newTimestamp) - int(previousTimestamp)
                    historyLimit = min(int(elapsed / updatePeriod), liveHistorySize)
                    
                    """now if we've returned a pile more rows than we need because we have a maxIterations, then 
                       we have to pass a 'rowLimit' to the csv Output as well"""
                    rowLimit = min(historyLimit, maxIterations - iterationCounter) if maxIterations != -1 else None
                    
                    response = LiveStatsResponse().fromResponse(liveResponse)
                
                    if not headerWritten:
                        headerWritten = True
                        confstats = response.printHeader(output)
                    response.toCsv(output, confstats, historyLimit = historyLimit, rowLimit = rowLimit)
                    iterationCounter += historyLimit
                
                #finally, lets just do this sleep IFF we're actually doing another iteration.
                #previously it would do it every time, which was a bit annoying if your update
                #period was 30 seconds and you had to wait for 30 seconds
                if (maxIterations >= 0 and iterationCounter < maxIterations) or maxIterations < 0:
                    time.sleep(updatePeriod)

        except suds.WebFault as webFault:
            print("Error attempting to create live stats session: %s" % webFault.fault.faultstring)
            sys.exit(1)
        except KeyboardInterrupt:
            print("Exiting...")
            if createSessionResponse != None:
                client.requestAttributes.removeAttr("historySize")
                client.requestAttributes.removeAttr("updatePeriod")
                client.closeLiveStatsSession(createSessionResponse)
            sys.exit(0)

    elif command == "summary":
        outputHeader(command, options, host, port)
        outputCsv(client.getSummary(options.reporting_period, options.filter))

    elif command == "cnes":
        outputHeader(command, options, host, port)
        outputCsv(client.getCnes())

    elif command == "message-protocols":
        outputHeader(command, options, host, port)
        outputCsv(client.getMessageProtocols())

    elif command == "applications":
        outputHeader(command, options, host, port)
        outputCsv(client.getApplications())

    elif command == "message-protocols-details":
        if options.protocol_name:
            outputHeader(command, options, host, port)
            outputCsv(client.getMessageProtocolsDetails(
                [{'_name': protocol_name} for protocol_name in
                 options.protocol_name]))
        else:
            usage('Missing protocol name.')
    elif command == "analytics":
        outputHeader(command, options, host, port)
        outputCsv(client.getAnalytics(options.filter,
                                      options.start_time, options.end_time,
                                      options.stat, options.conf_stat,
                                      options.requestedPercentiles, options.points))
    elif command == "clock-tracking":
        outputHeader(command, options, host, port)
        outputCsv(client.getClockEvents(options.local_cne, options.start_time, options.end_time,
                                      options.points, options.thresholds))
    elif command == "lens-data":
        try:

            lensDataResponse = client.getLensData(options.reporting_period, options.start_time, options.end_time,
                                                  options.business_hours, options.grouping, options.stat, options.filter)
            outputHeader(command, options, host, port)
            writeCsv(lensDataResponse)
        except suds.WebFault as webFault:
            if "detail" in webFault.fault:
                print("Error attempting to fetch lens data \n %s" % webFault.fault.faultstring)
                print("Detail: \n %s" % webFault.fault.detail[0].value)

            sys.exit(1)
        except MethodNotAvailableException as exception:
            print("*** LensData not available on %s: %s ***" % (host, exception))
            sys.exit(1)
    # Unknown command
    else:
        commands = ['stats', 'live-stats', 'summary', 'cnes',
                    'message-protocols', 'applications',
                    'message-protocols-details', 'analytics', 'clock-tracking', 'lens-data']
        usage("'%s' is not a recognised command. Command must be one of %s." % (
            command, ', '.join(commands)))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
