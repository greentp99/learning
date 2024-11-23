Readme for scripts version $Revision: 258304 $

The CorvilApiStatsClient provides a demonstration of how to retrieve live and
historical stats from the stats interface on the NBI. The script was developed
against Python v3.6 and Suds Jurko v0.6, which is bundled with the package

For simplicities sakes this demo client just prints the results to stdout.
Actual usage of the responses is very application dependent and will vary from
client to client. Introspecting into the response objects to retrieve the
desired data is relatively easy.

Corvil XML API example tool for retrieval of stats in historical and live modes.

Usage: CorvilApiStatsClient.py <command> <host> <options>

  Arguments:

    command                 One of 'get-stats', 'get-live-stats',
                            'get-summary', 'get-cnes', 'get-message-protocols',
                            'get-applications', 'get-message-protocols-details'

    host                    Name or IP address of the host to which the requests will be sent

  Options:

    -m <measurement-point>  List of fully qualified measurement points names, e.g.,
                            "channel//local-cne///PortA,channel//local-cne///PortA". If connecting to an CMC,
                            the name of a CNE configured on the CMC must precede the measurement point name,
                            separated by a color (:), e.g., "cne-alpha:channel//local-cne///PortA"

    -r <reporting-period>   Reporting period, One of: "1-hour", "12-hours", "24-hours", "48-hours",
                            "7-days", "30-days", and "60-days". Default is "1-hour"

    -s <stat>               List of statistic to request, e.g.: "e2e-latency,e2e-jitter"

    -x <configurable stat>  List of configurable statistics to add to request, e.g.: "stat-a,stat-b"

    -q <quantile>           List of percentiles to request, e.g.: "25,50,75"

    -p <admin-password>     Password for user 'admin'. Default is 'admin'

    -c <cne-name>           If connecting to an CMC, specify a CNE to connect to via the central
                            stats API. Using this option makes it an error to prepend a CNE name to
                            the measurement point names

    -t <history-size>       In Live requests, number of values that will be kept for the active
                            session. Default is 60

    -u <update-period>      In Live requests, the time between updates, in seconds. Default is 1

    -n <name>               Comma separated list of protocol names, e.g.: "protocol-a,protocol-b"

    -f <filter>             Optional fully qualified channel name to filter
                            get-summary method results, e.g.: "channel//local-cne///PortA"

Multiple measurement points, stats, configurable stats, and quantiles can be
specified by repeating the appropriate option, i.e.

-s e2e-latency,message-count -x "Cancels,Fill Ratio" -q "99,50"

Configurable statistics with spaces in their name must be enclosed in quotes as
above.

python3 CorvilApiStatsClient.py get-stats probe123 -s e2e-latency -m channel//local-cne///PortA -q 99,98

When communicating with the stats API on an CMC, a CNE can be specified as part
of the options. This CNE name should be the configured name of a CNE on the
CMC.

python3 CorvilApiStatsClient.py get-stats lmc123 -c cne123 -s e2e-latency -m channel//local-cne///PortA -q 99,98

This will use the CMC in forwarding mode, and will call the "get stats"
operation on the specified CNE and forward the response from the CNE.

Alternatively a CNE can be specified as part of the measurement point name, in
the form <cne-name>:<measurement-point-name>. This will return the data that
has been gathered on the CMC for that CNE and measurement point.

python3 CorvilApiStatsClient.py get-stats lmc123 -s e2e-latency -m probe123:channel//local-cne///PortA -q 99,98

These options can only be used on an CMC and cannot be used together. 

**Live Mode**

In live mode a history size and update period must additionally be specified.
The update period is the time period over which the returned values are
calculated.  The history size is the amount of values that the probe maintains
internally.

For the sake of the demo code the update period is also the time between
successive requests to the live API. This is not necessarily the case, though.
You could, for example, set the update period to 5 (seconds), the history size
to 10, and query the live API every 30 seconds or so, getting 6 values in each
response.

python3 CorvilApiStatsClient.py get-live-stats probe572 -s e2e-latency,message-count -x Fills,Cancels -m channel//local-cne///PortA

is a live request using the default update period of 1 second, default history
size of 60, and queries latency and message count from the specified channel.

The -c option can be used if querying live data on the CMC, and the CMC will
forward the request to the specified CNE. The CNE:FQN form of the measurement
point is however not supported on the CMC.

**Get Summary**

The get-summary command can be run with just a reporting period. It will return
a selected summary of information across the configured channels on the CNE or
CMC. This summary information can be used to discover channel names, and which
configurable statistics are supported by which channel.

You can specify channel name to filter get-summary results.

python3 CorvilApiStatsClient.py get-summary probe542 -f channel/FIX-SERVERS//local-cne/FIX-CLIENTS/FIX-RTT
